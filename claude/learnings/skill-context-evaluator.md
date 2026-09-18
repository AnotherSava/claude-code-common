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

- `@{upstream}` (git upstream ref) — failed to resolve in context, worked fine in Bash tool. Originally read as curly braces being interpreted differently in the evaluator's shell; the ref alone is in fact fine, and the hazard is narrower — see *A revision range is deferred, the bare ref is not* below.
- `--format="%h %ai %s"` — nested double quotes inside the context pattern caused parsing issues.
- `2>/dev/null` — stderr redirection may not work as expected (the evaluator may parse the command string before passing to shell).
- A backslash in an interpolated argument is eaten, and the resulting path looks plausible. Measured 2026-09-17: `/plannotator-annotate docs\convention-versions.md` reached the CLI through the skill's `!` line as `docsconvention-versions.md` and failed with `File not found`. The evaluator runs the command through a POSIX shell, so a Windows-style path typed as a slash-command argument loses its separators — and the error names a file nobody asked for rather than a quoting problem. Re-run with forward slashes; a skill taking a path argument cannot assume the user typed one.

**Workaround**: Keep context commands simple. Avoid nested quotes, special shell syntax, and redirections. Use `--oneline` instead of `--format="..."`. For complex commands, use a helper script.

## A revision range is deferred, the bare ref is not — and deferral is not a failure

The blanket reading of `@{upstream}` as unusable is too wide. Measured 2026-09-17 on the `pull` skill,
whose Context section held seven `!` lines: five preprocessed normally and two were handed back. The
split does not follow the ref, it follows the **revision range**.

Preprocessed, `@{upstream}` present as a bare argument:

```
!`git rev-parse --abbrev-ref @{upstream} 2>/dev/null || echo NO-UPSTREAM`     → origin/main
!`git diff --name-status HEAD @{upstream} 2>/dev/null || echo NONE`           → the file list
```

Deferred, the same ref inside a two- or three-dot range:

```
!`git rev-list --left-right --count @{upstream}...HEAD 2>/dev/null || echo NO-UPSTREAM`
!`git log --oneline -n 40 HEAD..@{upstream} 2>/dev/null || echo NONE`
```

The consequence is milder than the fatal exit described at the top of this file, and different in kind:
nothing fails. The loader prefixes the skill with `[Run these 2 commands first, exactly as written, and
use their output where each is named below.]` and replaces each value with `[output of command N, …]`,
so the skill still runs correctly at the cost of one extra round trip. Distinguish the two when
diagnosing — a deferred line renders a bracketed instruction, a failing line stops the skill loading.

What was measured is `@{upstream}` **bare** against `@{upstream}` **inside a range**, two cases each.
Whether a range of plain refs also defers is untested: `release` carried
`git rev-list HEAD..origin/main --count` in its Context on 2026-09-17, which suggests it does not, but
nobody watched it render, and invoking that skill to find out would cut a release.

The remedy is the same either way: a command carrying a remote revision range belongs in a process step,
named there so later steps can cite it, as `pull` step 1 does.

## `!` lines are not evaluated in the order they are written

A Context section reads like a script, and it is not one. Measured 2026-09-17 in the `pull` skill,
whose first line was `git fetch -q` and whose third was `git diff --name-status HEAD @{upstream}`: the
third rendered **empty** against a remote four commits ahead, and the identical command run seconds
later in a process step returned 56 paths. The diff had read the tracking ref as it stood before the
fetch moved it.

This is nastier than the deferral above, because nothing looks wrong. A deferred line renders a visible
bracketed instruction; this one renders a plausible, confident, empty answer — and "no incoming files"
is exactly the value that makes the skill decide there is nothing to do.

So a Context section cannot contain a step and its dependant. Any line whose output depends on a
*mutation* performed by another line — a fetch, an unstage, a generated file — belongs in a process
step, where the ordering is guaranteed because every `!` line has finished before the body runs. Keep
in Context only what is true regardless of what else ran: the working tree, the index, config values
like `git rev-parse --abbrev-ref @{upstream}`, which reads `.git/config` rather than the remote.

The mutating line itself can stay — the fetch still has to happen, and its failure is still a
precondition worth rendering. What cannot stay beside it is anything that reads the result.

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

## Testing a Context line means running the skill

A skill created or edited mid-session is picked up without a restart, and its file is re-read
on every invocation. Measured 2026-09-17: `pull` was created at 11:10 and invoked at 11:19,
20:23 and 21:04 in one session, rendering its current Context each time — two lines fewer
after an edit between the second invocation and the third. The `Skill` tool refused it for
`disable-model-invocation`, which is a registry hit rather than a miss.

The cost of a test is what bites, not its availability. Invoking a skill to watch one Context
line render runs the whole body, which is rarely acceptable: `release` cuts a release,
`commit` commits. A throwaway probe — a minimal skill holding just the candidate `!` lines,
invoked once and deleted — follows from the mid-session pickup above, but nobody has run one.

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
- `git rev-parse --abbrev-ref @{upstream} || echo <fallback>` (the ref as a bare argument)
- `git diff --name-status HEAD @{upstream} || echo <fallback>` (two revisions as separate arguments)
- `git fetch -q || echo <fallback>`
- `git branch --sort=-committerdate`
- `ls -t <dir> | head -N`
- `grep -c "pattern" file || echo 0`
- `test -f <file> && echo yes || echo no`
- `cat <file> || echo MISSING`

## Commands that fail or are unreliable in context

- `gh pr view` — fails when no PR exists (non-zero exit)
- `git log HEAD..@{upstream}`, `git rev-list @{upstream}...HEAD` — `@{upstream}` inside a revision range; deferred to a manual run rather than preprocessed. A range of plain refs (`HEAD..origin/main`) is untested, not known-bad
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

