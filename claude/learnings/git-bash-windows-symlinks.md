# Creating symlinks & junctions on Windows from Git Bash

Committed shell scripts in this repo are often authored on macOS (`ln -s`) but
must also run under Git Bash on Windows, where linking behaves completely
differently. This covers creating a link **programmatically from inside a bash
script**. (For interactive human setup, the README install block has the user
run `New-Item -ItemType SymbolicLink` directly in a PowerShell prompt — native
PowerShell, so none of the MSYS mangling below applies.)

## `ln -s` silently copies

From Git Bash / MSYS, `ln -s target link` does **not** create a link by default —
it makes a *copy*. Never rely on it for the Windows path of a committed script.
(`export MSYS=winsymlinks:nativestrict` changes this, but you can't assume the
user's environment sets it.)

## Two Windows link types

| Type | Command | Admin needed to create? | Cross-drive? |
|---|---|---|---|
| Directory junction | `mklink /J` / `New-Item -ItemType Junction` | no | yes |
| Symbolic link (dir) | `mklink /D` / `New-Item -ItemType SymbolicLink` | yes, unless **Developer Mode** is on | yes |

That third column says who may *create* a link, not who may *follow* one, and only the
first of those is a property of the type.

## Create every link from an elevated prompt

Elevate before creating a link of either type. Windows refuses to follow a reparse point
created by a non-administrator — `ERROR_UNTRUSTED_MOUNT_POINT`, WinError 448 — and it
refuses a symlink as readily as a junction, so the junction's "no admin needed" buys a
link that gets created and then cannot be walked.

The refusal belongs to the process doing the walking rather than to the link, which is
what makes it quiet: one shell resolves the path and another raises on it. Measured on
the Windows machine:

- 2026-09-16, from the Git Bash session that had just created a `~/.claude/conventions`
  junction without elevation — `python ~/.claude/conventions/check.py` ran through it and
  reported all 9 rules held.
- 2026-09-18, from a Python launched over SSH — that same junction raised 448, and so did
  `~/.claude/memory` and `~/.claude/scripts`, both of them **symlinks**, while the nine
  other install links beside them resolved. Every project memory cache junction on the
  machine raised it too, 19 of 19.

**Recreate a suspect link rather than inspecting it.** `(Get-Item -LiteralPath $p -Force).LinkType`
gives the type and says nothing about trust, and nothing exposes trust directly — the only
test is whether the process that has to follow the link can. From an elevated PowerShell:

```powershell
[System.IO.Directory]::Delete($p, $false)    # removes the reparse point, never the target
New-Item -ItemType SymbolicLink -Path $p -Target $t
```

## `cmd //c mklink` fails from Git Bash

Calling mklink via cmd from a bash script does **not** work — MSYS mangles the
`/J` switch before cmd sees it:

```
$ cmd //c mklink /J "$link_win" "$target_win"
Invalid switch - "C:\Users\...\link".
```

None of the usual MSYS escapes rescue it:
- `MSYS_NO_PATHCONV=1 cmd //c …` → now `//c` is mangled and cmd opens interactively.
- `MSYS2_ARG_CONV_EXCL='*' cmd //c …` → still fails.
- `cmd //c "mklink /J \"$l\" \"$t\""` (single command string) → still fails.

## Reliable method from bash: shell out to PowerShell

```bash
link_win="$(cygpath -w "$cache_dir")"     # C:\Users\...\memory
target_win="$(cygpath -w "$repo_dir")"    # D:\...\memory
powershell -NoProfile -Command "New-Item -ItemType SymbolicLink -Path '$link_win' -Target '$target_win'"
```

- Build Windows-form paths with `cygpath -w`.
- Use **single quotes** around the paths inside the PS command — backslashes are
  literal in PowerShell single-quoted strings, and bash has already expanded the
  variables.
- Check elevation first, and when the shell does not have it, print that command for the
  user to run and exit non-zero. Falling back to `-ItemType Junction` is the trap the
  section above describes: it succeeds, and leaves behind a link some process will refuse.

```bash
powershell -NoProfile -Command "([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)" | tr -d '\r'
```

Keep the outer parentheses. Without them PowerShell binds `.IsInRole` to
`[WindowsIdentity]::GetCurrent()` rather than to the cast result, and the error names the wrong
type — *`[System.Security.Principal.WindowsIdentity]` does not contain a method named 'IsInRole'* —
which reads as the method not existing rather than as a precedence mistake. Measured 2026-09-18,
where it surfaced as a guard reporting that elevation could not be determined and blocking
everything.

This is the same `New-Item` the README tells users to run by hand; the only
difference is the script invokes it via `powershell -Command` instead of the
user typing it into a PowerShell prompt. The worked example is
`claude/scripts/link-project-memory.sh`.

## Reading a link back (idempotency check)

Both types appear to Git Bash as a **symlink**: `[ -L "$p" ]` is true for a
junction too. But `readlink` returns a POSIX path with a **lowercased drive and
trailing slash**:

```
readlink C:/Users/.../memory  ->  /d/.../.claude/memory/
```

So a naive string compare against the stored Windows/forward-slash target fails.
Normalize both sides with `cygpath -w` before comparing:

```bash
if [ -L "$cache" ] && [ "$(cygpath -w "$(readlink "$cache")")" = "$target_win" ]; then
  echo "already linked"; exit 0
fi
```

That test cannot tell a junction from a symlink, so a script carrying it reports every
junction an earlier version of itself created as already linked and never replaces one.
Ask PowerShell for the type where replacing them is the point:

```bash
powershell -NoProfile -Command "(Get-Item -LiteralPath '$link_win' -Force).LinkType" | tr -d '\r'   # SymbolicLink | Junction
```

### From Python the same junction is not a link at all

Do not port that `[ -L ]` test into Python by analogy — the two disagree on the
same path, on the same machine, in the same second. Measured 2026-09-15 on a
wired memory cache:

```
exists: True | islink: False | samefile as the target: True
```

`os.path.islink()` returns **False** for a directory junction, because a junction
is a reparse point and not a symlink, while Git Bash's `[ -L ]` returns true for
it. A Python idempotency check written from the bash form above therefore reports
a correctly wired cache as unwired, and whatever it guards runs again or records
a gap that is not there.

Use `os.path.samefile(link, target)` instead: it compares `st_dev`/`st_ino`, so it
answers the question actually being asked — do these two paths reach the same
directory — for a junction, a symlink and a bind mount alike. It is also the only
form that catches a *copy* standing in for a link, which every textual comparison
passes. See `comparing-paths-symlinks-and-case.md` for the case-folding half of
the same problem.

## Checking one over SSH, where the shell is cmd.exe

Windows OpenSSH hands you **cmd.exe**, not Git Bash, so `[ -L ]`, `readlink` and
`cygpath` are all unavailable. Use `dir /al`, which lists only reparse points and
prints the target in brackets:

```
> dir /al %USERPROFILE%\.gitignore
03/29/2026  12:39 AM    <SYMLINK>      .gitignore [{{projects-root}}\claude\git\gitignore]
```

A plain file produces `File Not Found` from `/al` while `dir` without the flag
still lists it — that pair is the test, and it distinguishes a real link from one
of the silent copies above. This is the check worth running after any "pull the
dotfiles repo on the other machine" step: the pull updates the repo file, and a
copy masquerading as a link never moves, so the repo reads current while the
thing that is actually consulted is stale.
