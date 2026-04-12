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
