# Bash Portability

The user runs committed shell scripts on both Windows (Git Bash, modern
bash 4/5) and macOS (system `/bin/bash`, version 3.2.57). Scripts in
shared repos should avoid bash 4+ features so they work on both.

## Why macOS bash is stuck at 3.2

Apple has not shipped a newer system bash since 2007 (license change to
GPLv3). `#!/usr/bin/env bash` resolves to `/bin/bash` unless Homebrew's
`bash` (in `/opt/homebrew/bin` or `/usr/local/bin`) is earlier on PATH.
Default Macs do not have Homebrew bash, so portable code is the safe bet.

## Bash 4+ features to avoid (with portable alternatives)

| Avoid | Portable replacement |
|---|---|
| `mapfile -t arr < <(cmd)` | `arr=(); while IFS= read -r line; do arr+=("$line"); done < <(cmd)` |
| `readarray` (alias for mapfile) | Same as above |
| `declare -A assoc` | Use parallel arrays, or `eval` tricks, or just don't |
| `${var,,}` / `${var^^}` (case) | `tr '[:upper:]' '[:lower:]'` / `'[:lower:]' '[:upper:]'` |
| `&>>` append both streams | `>>file 2>&1` |
| `[[ $a == $b ]]` (still works in 3.2) | Fine — bash 3.2 has `[[` |

## Detection

`bash --version` reports the version. On a stock Mac you'll see
`GNU bash, version 3.2.57(1)-release`. Git Bash on Windows reports 4.x
or 5.x.

## When this matters

Only for `.sh` files committed to a shared repo. Ad-hoc commands in the
Bash tool inherit whatever shell the harness picked — usually fine, but
if a command fails with `command not found: mapfile` (or similar
bash-4-only feature), suspect bash 3.2 and rewrite portably.

## bash vs zsh — the Bash tool is not the shell your script will run in

On macOS the Bash tool runs **zsh**, while committed scripts, CI `run:` blocks and
`#!/bin/bash` files run **bash**. Testing a snippet in the tool and shipping it is how
shell bugs get through in both directions.

**zsh does not word-split unquoted parameter expansions.** This is the big one, and it
silently changes meaning rather than erroring:

```sh
P="--project foo"
cmd $P          # bash: two args.  zsh: ONE arg "--project foo" -> "unknown flag"
for h in $list  # bash: iterates lines.  zsh: ONE iteration with the whole blob
```

Symptoms are misleading: the zsh version of the flag case fails with a flag-parsing
error from the tool being called, and the loop case silently "finds" everything missing.
Write `${=P}` in zsh, or better, don't rely on splitting at all — quote properly and
iterate with `while IFS= read -r`.

**`case … ) ;;` inside `$( … )` is a parse error in bash** (not in zsh):

```sh
# zsh: fine.  bash: "syntax error near unexpected token `;;'"
missing=$(for h in $list; do case "$s" in *"$h"*) ;; *) echo "$h";; esac; done)
```

Portable rewrite — no `case`, no word-splitting, works in bash, zsh and dash:

```sh
missing=$(printf '%s\n' "$list" | while IFS= read -r h; do
  [ -n "$h" ] || continue
  printf '%s' "$s" | grep -qF -- "$h" || echo "$h"
done)
```

**Verify with the target shell, not the tool.** `bash -n file` / `sh -n file` catch parse
errors, and running the script under each shell catches the splitting differences. Note
`bash -n` on an *empty* file also passes — if extraction produced nothing, the check is
vacuous, so assert the file is non-empty first.
