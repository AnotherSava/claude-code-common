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

| Type | Command | Admin needed? | Cross-drive? |
|---|---|---|---|
| Directory junction | `mklink /J` | no | yes |
| Symbolic link (dir) | `mklink /D` / `New-Item -ItemType SymbolicLink` | yes, unless **Developer Mode** is on | yes |

Prefer a **junction** when a script redirects a directory (e.g. a cache folder
into a repo) — it needs no elevation. `New-Item -ItemType SymbolicLink` succeeds
without admin only when Windows Developer Mode is enabled (the README's "run as
Administrator" requirement is the safe default for users who don't have it on).

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
target_win="$(cygpath -w "$repo_dir")"    # D:\projects\...\memory
powershell -NoProfile -Command "New-Item -ItemType Junction -Path '$link_win' -Target '$target_win'"
```

- Build Windows-form paths with `cygpath -w`.
- Use **single quotes** around the paths inside the PS command — backslashes are
  literal in PowerShell single-quoted strings, and bash has already expanded the
  variables. (Swap `Junction` → `SymbolicLink` if you specifically need a symlink
  and have admin / Developer Mode.)

This is the same `New-Item` the README tells users to run by hand; the only
difference is the script invokes it via `powershell -Command` instead of the
user typing it into a PowerShell prompt.

## Reading a junction back (idempotency check)

A junction created this way appears to Git Bash as a **symlink**: `[ -L "$p" ]`
is true. But `readlink` returns a POSIX path with a **lowercased drive and
trailing slash**:

```
readlink C:/Users/.../memory  ->  /d/projects/.../.claude/memory/
```

So a naive string compare against the stored Windows/forward-slash target fails.
Normalize both sides with `cygpath -w` before comparing:

```bash
if [ -L "$cache" ] && [ "$(cygpath -w "$(readlink "$cache")")" = "$target_win" ]; then
  echo "already linked"; exit 0
fi
```
