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

## Process spawns are ~100× more expensive on Windows — never fork per line

Forking a process costs ~1ms on Linux/macOS and **~100–200ms in Git Bash on Windows**. A loop body
that shells out therefore scales catastrophically: a `$(printf … | tr …)` used to trim whitespace,
run over a 28-line file for each of 4 items, turned a script that should take milliseconds into a
**30-second stall** — long enough to blow a Claude Code skill's two-minute context-probe budget and
kill skill loading outright. The same script measured 263ms once the forks were removed.

Do the work with parameter expansion, which is builtin and free:

```bash
line=${line%%#*}                          # strip a trailing comment
line=${line#"${line%%[![:space:]]*}"}     # ltrim
line=${line%"${line##*[![:space:]]}"}     # rtrim
```

Read each file **once** into a variable rather than re-reading it per item, and test membership with
a `case` glob over a newline-delimited string instead of calling `grep` per candidate:

```bash
case $declared in *$'\n'"$name"$'\n'*) continue ;; esac
```

The rule of thumb: inside any loop, treat `$( )`, pipes, `grep`, `sed`, `tr`, `cut`, and `awk` as
expensive. One invocation over the whole input is fine; one per line is not. This bites hardest in
scripts a skill runs synchronously, where the cost lands in the user's latency rather than in a
background job.

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

**Unquoted `[...]` in a path is a glob, and in zsh it is fatal or silent depending on
where it lands.** This bites hardest on Next.js dynamic routes, whose directory names
are literally bracketed:

```sh
git diff --stat -- web/src/app/events/[slug]/page.tsx   # matches NOTHING
npx vitest run src/app/events/[id]/page.test.ts         # "no matches found"
```

`[slug]` is a character class matching one of `s`, `l`, `u`, `g` — so the path is not the
path you typed. Two different failures follow, and neither says "your glob was wrong":

- Passed to a tool that takes a **pathspec** (`git diff`, `git add`, `git log`), the
  non-matching pattern reaches git, matches no tracked file, and the command **succeeds
  with empty output**. A `--shortstat` reports nothing changed and a plan built on it
  silently omits the file.
- Used where zsh must expand it first, zsh's `nomatch` aborts the whole command with
  `no matches found:` — where bash would have passed the pattern through untouched.

Quote the path (`'…/[slug]/page.tsx'`) or escape the brackets. Worth a habit: any path
with `[`, `?` or `*` in it gets single-quoted, even when it looks literal.

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

## `exit` inside `$( )` ends the subshell, not the script

A validation helper written the obvious way silently does nothing:

```bash
need() { local v; v="$(getval "$1")"; [ -n "$v" ] || { echo "ERROR: $1 missing"; exit 1; }; printf '%s' "$v"; }
HOST="$(need SSH_HOST)"     # missing -> HOST holds the ERROR TEXT, script continues
```

Command substitution runs in a subshell, so `exit` terminates *that*, and the error message becomes the
variable's value. The script then proceeds with a host of `ERROR: SSH_HOST missing` — worse than crashing,
because the failure surfaces somewhere unrelated. `set -e` does not help: the substitution's non-zero status is
consumed by the assignment.

Read first, validate after, in the parent shell — and collect every problem rather than dying on the first:

```bash
HOST="$(getval SSH_HOST)"; REPO="$(getval REMOTE_REPO)"
MISSING=""
for k in HOST REPO; do [ -n "${!k}" ] || MISSING="$MISSING $k"; done
[ -n "$MISSING" ] && { echo "ERROR: missing:$MISSING"; exit 1; }
```

`${!k}` is the indirect expansion — bash-only, fine in a `#!/bin/bash` script, not in POSIX `sh`.

The same trap applies to `return` in a function called from a substitution, and to `exit` inside a pipeline
segment (`cmd | while read …; do exit 1; done` exits the subshell the loop runs in).

## A prefix assignment is not an assignment — `source`ing a "config" of commands silently loads nothing

`VAR=value command` is a **prefix assignment**: it runs `command` with `VAR` in *that command's* environment
only. The calling shell's `VAR` is untouched — not set to `value`, not cleared. So a config file whose lines
look like assignments but carry unquoted multi-word values does nothing useful when sourced:

```bash
$ printf 'BUILD_SERVICES=app migrate\n' > probe.env
$ bash -c 'BUILD_SERVICES=PRESET; source probe.env; echo "[$BUILD_SERVICES]"'
probe.env: line 1: migrate: command not found
[PRESET]
```

Two things make this nastier than a plain error. The variable keeps a *stale* value, so downstream code runs on
whatever was there before rather than failing; and the only hint is a `command not found` for a word that was
never meant to be a command, which reads like a missing dependency rather than a parse problem. `set -e` does
not fire — the prefix assignment's exit status is the failed command's, but it is the last statement of that
line and the shell carries on to the next.

The same line is *fine* when read rather than executed. If a file is a data table for a program that parses it
(`grep '^KEY=' file | cut -d= -f2-`), its values can legitimately be unquoted commands, spaces and all — the
mistake is assuming that anything shaped like `KEY=value` is safe to `source`. Say so in the file itself, and
make any worked example in its header print a key that actually exists; an example quoting a key that was later
removed demonstrates nothing and hides the contradiction.

Measured 2026-08-30, bash 3.2 (macOS).
