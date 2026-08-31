# Skill Context Evaluator Limitations

The `!` backtick syntax in SKILL.md Context sections runs shell commands during preprocessing. The evaluator has several constraints discovered through trial and error.

## Non-zero exit = fatal error

Any command that exits non-zero crashes skill loading with `Error: Shell command failed for pattern`. There is no way to suppress this — `2>/dev/null` does not help because the evaluator checks the exit code, not stderr.

**Workaround**: Use `|| echo <fallback>` for commands that might fail benignly:
```
- Count: !`grep -c "pattern" file 2>/dev/null || echo 0`
- Exists: !`test -f some/file && echo yes || echo no`
```

Commands that can legitimately fail with no sensible fallback (e.g. `gh pr view` when no PR exists) must go in the skill body, not in context.

## Shell environment differences

Context commands run in a subprocess that may differ from the normal Bash tool environment. Observed issues:

- `@{upstream}` (git upstream ref) — failed to resolve in context, worked fine in Bash tool. Likely caused by curly braces being interpreted differently in the evaluator's shell.
- `--format="%h %ai %s"` — nested double quotes inside the context pattern caused parsing issues.
- `2>/dev/null` — stderr redirection may not work as expected (the evaluator may parse the command string before passing to shell).

**Workaround**: Keep context commands simple. Avoid nested quotes, special shell syntax, and redirections. Use `--oneline` instead of `--format="..."`. For complex commands, use a helper script.

## Fallback chains work

The `||` operator works in context commands:
```
!`git log @{upstream}..HEAD --format="%h %ai %s" 2>/dev/null || git log origin/master..HEAD --format="%h %ai %s" 2>/dev/null`
```
This works because if the first command fails, the second runs and (if it succeeds) the overall exit code is 0.

## In a pipeline, `|| fallback` sees only the LAST command's exit code

A fallback appended to a pipeline binds to the pipeline's status, which is the **last** element's — not the failure of the command that actually produced no data. So this silently renders an empty label instead of the fallback when `doppler` fails:

```
!`doppler projects --json 2>&1 | tr ',' '\n' | grep -o '"name":"[^"]*"' | head -30 || echo UNAVAILABLE`
```

`head` exits 0 on empty input, so `|| echo` never fires. Put a command that *discriminates* last — `grep` exits 1 when it matches nothing:

```
!`doppler projects --json 2>&1 | tr ',' '\n' | grep -o '"name":"[^"]*"' || echo UNAVAILABLE`
```

Verified both directions: the working form renders the project list normally, and forcing the failure (`--token bogus`) renders `UNAVAILABLE`. The cost is losing `head`'s output cap, so only drop it where the result set is inherently small. Always test the failure path — the success path looks identical either way, and a silently-empty context label is far harder to diagnose later than a loud one.

## A new or edited Context line cannot be tested in the session that wrote it

Skills are discovered at session start. A skill directory created mid-session is not
invocable — `Skill` answers `Unknown skill: <name>`, so the throwaway-probe trick (a minimal
skill holding just the candidate `!` lines, invoked once and deleted) does not work in the
session that needs the answer. An edited line in an *existing* skill has the same problem
from the other side: invoking that skill to see whether the line renders also runs the whole
skill body, which is rarely acceptable just to test a Context line.

This matters because the failure is not local: a non-zero exit kills skill loading before
the body is read, so one bad Context line makes the whole skill unusable until someone
edits the file. Combined with the quoting hazards above, that argues for keeping Context
lines to shapes already proven in the file, and **moving anything novel into a process
step**, where the Bash tool runs it in an environment you can exercise immediately.

The convention that data a step needs on *every* invocation belongs in Context still holds —
but a command that only runs when an earlier check is non-empty is conditional by
definition, so the body is its correct home anyway. Gate on a simple Context line, put the
complex command behind the gate.

## Commands that work reliably in context

- `git status --short`
- `git diff --stat`, `git diff`
- `git log --oneline -N` (no remote ranges)
- `git log main..HEAD --oneline` (local branch range)
- `git rev-parse --abbrev-ref HEAD`
- `git branch --sort=-committerdate`
- `ls -t <dir> | head -N`
- `grep -c "pattern" file || echo 0`
- `test -f <file> && echo yes || echo no`
- `cat <file> || echo MISSING`

## Commands that fail or are unreliable in context

- `gh pr view` — fails when no PR exists (non-zero exit)
- `git log @{upstream}..HEAD` — curly braces may cause issues
- Commands with `--format="%h %ai %s"` — nested quotes parsed incorrectly
- Any command that can legitimately return non-zero


## `$1`, `$2`, … are eaten before the shell sees them — and the corruption is silent

A context probe using awk positional fields does not reach awk intact. Observed 2026-08-29 in the `publish`
skill, whose file on disk reads:

```
!`grep -c "publish()" ~/.bashrc ~/.zshrc 2>/dev/null | awk -F: '{s+=$2} END {print s+0}'`
```

and whose evaluator handed awk this:

```
awk: syntax error at source line 1
 context is
	 >>> {s+=for <<< } END {print s+0}
```

`$2` was replaced by the string `for`. Not blanked, not escaped — substituted with something that happens to
be an awk reserved word, so the failure surfaces as a syntax error rather than as a wrong number. Deterministic
across repeated invocations, and fatal: a non-zero exit kills skill loading before the body is read (see the
first section), so **the whole skill becomes unusable** and no amount of re-invoking helps.

Diagnose it by reading the file rather than trusting the error. The message quotes the *mangled* command, so it
looks like a defect in the skill; `grep -n` on the source shows the original is correct and the loader is at
fault. Do not "fix" the skill — the edit would be wrong, and in a vendored skill it would be reverted anyway.

**Avoid positional fields in context probes entirely.** Equivalents that survive:

```
# instead of: ... | awk -F: '{s+=$2} END {print s+0}'
... | cut -d: -f2 | paste -sd+ - | bc
... | grep -c .                      # when a count of matching LINES is enough
```

The general rule for these probes: anything the evaluator might read as a variable — `$1`, `$2`, `$@`, and by
extension `$(...)` — is a hazard, and the safest probes are plain pipelines of `grep`, `cut`, `test`, `ls` and
`wc`.

