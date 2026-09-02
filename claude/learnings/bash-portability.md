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
never meant to be a command, which reads like a missing dependency rather than a parse problem.

**It then fails two different ways depending on `set -e`, and each one hides something different.** Corrected
2026-09-01: an earlier version of this section said errexit "does not fire", reasoning that the failed command is
the last statement of its line so the shell carries on. That reasoning is backwards — the line's exit status *is*
the failed command's, which is precisely what errexit acts on. It fires.

```bash
$ bash -c 'source probe.env; echo "returned: $?"'
probe.env: line 1: migrate: command not found
returned: 0                      # ← reports SUCCESS; the failure is swallowed, not merely unreported

$ bash -c 'set -e; source probe.env; echo "still running"'
probe.env: line 1: migrate: command not found
                                 # ← never prints; the shell is gone, exit 127
```

Without `set -e` the source returns **0**, because a sourced file returns the status of its LAST line — so a bad
line anywhere but the end is swallowed whole, and `if source config; then` is satisfied by a file that loaded
nothing. With `set -e` the sourcing shell aborts on the spot at exit 127, and every key *below* the offending line
is never assigned while the ones above it are — a dead script plus a half-populated environment. Assume the
second when auditing: `set -e` is standard in anything that is not a throwaway, and it is the mode where the
damage reaches keys that have nothing to do with the bad line.

Both hold for the prefix assignment inline in a script, not just sourced from one. Neither is version-specific:
measured on bash 3.2.57 (macOS system bash) and on `/bin/sh`.

The same line is *fine* when read rather than executed. If a file is a data table for a program that parses it
(`grep '^KEY=' file | cut -d= -f2-`), its values can legitimately be unquoted commands, spaces and all — the
mistake is assuming that anything shaped like `KEY=value` is safe to `source`. Say so in the file itself, and
make any worked example in its header print a key that actually exists; an example quoting a key that was later
removed demonstrates nothing and hides the contradiction.

**Where the value's tail is a real executable, sourcing does not fail — it RUNS it.** The case above is benign
only because `migrate` is on nobody's PATH. `DEV_CMD=bash ../scripts/dev.sh` parses the same way, so sourcing
assigns `bash` to `DEV_CMD` for the duration of `../scripts/dev.sh` and then executes that script — starting a
dev server as a side effect of a file you meant only to read, while `DEV_CMD` still ends up unchanged. Measured
with a stand-in that only echoes:

```bash
$ printf 'DEV_CMD=bash ../fake.sh\n' > sub/probe.env      # fake.sh echoes a marker
$ bash -c 'cd sub; DEV_CMD=PRESET; source probe.env; echo "[$DEV_CMD]"'
EXECUTED-BY-SOURCE
[PRESET]
```

So the hazard is not uniform across a family of look-alike config files: whether sourcing one is a confusing
no-op or an accidental launch depends on which values happen to name binaries. Audit the whole set, not just the
file that raised the question. Note too that the path is resolved against the *caller's* cwd, so the same file is
inert from one directory and live from another — which is exactly the kind of difference that makes it
reproduce for one person and not the next.

Measured 2026-08-30, bash 3.2 (macOS).

## Two Git-Bash-on-Windows traps when embedding another language

**A quoted heredoc still loses backslashes on the way into Python.** Writing a script inline with
`python <<'PYEOF' … PYEOF` looks like it should pass the body through verbatim, but doubled backslashes
arrive collapsed. A regex character class is where this bites, because the damage is syntactically
valid right up until it isn't:

```python
re.compile(r'[^:@/\s"\]+')   # authored
re.compile(r'[^:@/\s"\]+')    # received -> the \] escapes the bracket
# re.PatternError: unterminated character set at position 55
```

The position in the error points into the mangled class, not at anything you wrote, so it reads as a
typo you cannot find. Same failure invoking PowerShell: `"$env:USERDOMAIN\$env:USERNAME"` arrives
without its separator and account lookups fail with `No mapping between account names and security IDs
was done`.

Fix: write the script to a real file and run it (`python script.py`, `powershell -File script.ps1`).
Reserve heredocs for bodies with no backslashes.

**`/tmp` is not the same directory for bash and for a Windows-native interpreter.** MSYS maps `/tmp`
into the user's temp dir; Python on Windows resolves `/tmp` against the *current drive*, so a file bash
wrote to `/tmp/x` is looked for at `D:\tmp\x` and reported missing:

```
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/captest/vault/index.json'
```

Both halves succeed individually, which makes it read as the writer having failed rather than the
reader looking elsewhere. Translate with `pwd -W` (or `cygpath -w`) before handing a path across, or
keep scratch files inside the project on an explicit path.

## A heredoc and a pipe both claim stdin — and the loser gets echoed in the error

Feeding a value to an interpreter on stdin while the *script* also arrives on stdin. Measured 2026-08-31,
and it leaked a live credential into a session transcript:

```bash
printf '%s' "$SECRET" | python3 <<'EOF'
import sys
value = sys.stdin.read()      # never sees $SECRET
...
EOF
```

Both redirections target file descriptor 0. What python actually received began with the piped value and
continued into the heredoc's text, so the first line it parsed was the secret with `import` welded onto the
end — and the `SyntaxError` printed that line verbatim. The value went to the terminal, the log and the
transcript, in a command written specifically to keep it out of all three.

**Pass the value in the environment and keep stdin for the script.** The command line stays clean (only the
`$( )` that produced it is recorded), and there is nothing for a parse error to echo:

```bash
SECRET=$(pbpaste) python3 <<'EOF'
import os
value = os.environ['SECRET']
EOF
```

The same collision applies to `ruby`/`node`/`sh` with a heredoc, and to `ssh host <<'EOF'` when you also
wanted to pipe data to the remote command. Three rules that generalise:

- **One consumer per stdin.** If the script is on stdin, data is not; if data is on stdin, put the script in
  a file or `-c`.
- **Never let a secret reach a place a parser can quote.** A syntax error prints the offending line, so any
  value that can end up *inside* the program text can end up in the error text.
- **`--silent` flags hide command OUTPUT, not command INPUT.** A tool's quiet mode does nothing about a
  value the shell already echoed while failing to run it.

The safe route when the value must be validated before use is to prove it works rather than to pattern-match
it — a guessed prefix check rejected a perfectly good key here, and the fix was to attempt the API call and
store only on success. That keeps the value in a variable and a pipe, never in a command line or a script
body.

## Reading uptime: two mechanisms, and a parse that fails by returning a plausible number

There is no portable way to ask how long a machine has been up, and the macOS form has a trap that
produces a wrong answer rather than an error.

**Linux, and Git Bash on Windows** — `/proc/uptime`, whose first field is seconds since boot. MSYS
synthesises it, so this works in Git Bash even though Windows has no procfs. Measured, not assumed:

```bash
cut -d' ' -f1 /proc/uptime | cut -d. -f1     # -> 206438
```

**macOS** — no `/proc` at all; it comes from the kernel's boot timestamp:

```
$ sysctl -n kern.boottime
{ sec = 1780435744, usec = 167386 } Tue Jun  2 14:29:04 2026
```

**The trap:** the obvious `sed -E 's/.*sec = ([0-9]+).*/\1/'` matches **`usec`**, because `.*` is
greedy and `usec = ` ends with the literal `sec = `. It returns `167386` — a boot epoch in 1970,
and an uptime of about 56 years. Nothing errors; a threshold computed from it is simply wrong, and
wrong in a direction that looks like a very stale machine.

Match the field rather than the text around it:

```bash
sysctl -n kern.boottime |
  awk -F'[= ,]+' '{for(i=1;i<NF;i++) if($i=="sec"){print $(i+1); exit}}'
```

Cross-check any uptime arithmetic against `uptime(1)` once — 92 days from the epoch subtraction
against "92 days, 30 mins" from `uptime` is the whole verification, and it takes one line.

The general shape, which recurs well beyond this: a regex that can match a *longer token ending in
the token you wanted* fails silently. `sec`/`usec`, `id`/`uuid`, `name`/`hostname`. Anchor on a
field boundary, and prefer a field-splitting tool to a regex over the whole line.
