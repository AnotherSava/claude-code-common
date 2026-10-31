# Deciding a file's git execute bit when the disk cannot say

Git records each file as `100644` or `100755`, and a hook or script committed `644` is never run on the machine that checks it out. A tool that decides the mode for the index has to read the bit from somewhere. On Windows the disk does not have it, and every probe that seems to read it gives an answer anyway.

## Every disk probe on Windows says "executable"

Measured on Windows with Git Bash, on a file holding only `#!/usr/bin/env python3` after `chmod 644`:

| Probe | Answer |
|---|---|
| `os.access(path, os.X_OK)` | `True`, for any file that exists |
| `os.stat(path).st_mode` | `0o100666` |
| Git Bash `stat -c %a` | `755`, because MSYS marks a file starting with `#!` as executable |

So a rule like "a shebang and an executable disk copy", which is correct on macOS and Linux, gives `+x` to every file with a shebang on Windows, deliberately non-executable libraries included. Gate the disk half on `os.name != "nt"`. Don't look for a better probe, because the bit is not stored.

A shebang alone does not work as a fallback signal. One repo held 63 shebang'd files at `755` and 44 at `644`, because hooks invoked as `python3 file.py` and sourced shell libraries keep a shebang without being executable.

## What git itself does under `core.filemode=false`

Windows clones run with `core.filemode=false`, and there git ignores the disk bit both ways:

- `git add` of a path already in the index **keeps the index mode**. A tracked file's mode therefore survives every edit, and a tool should leave it alone instead of re-deriving it.
- `git add` of a new path records `100644`.
- `git add --chmod=+x <path>` (or `git update-index --chmod=+x`) is the one way to set the bit.

## A tool that clears the index throws `--chmod=+x` away

A commit helper that runs `git reset` before staging, so that nothing staged earlier rides along, also wipes a `+x` the user staged on purpose. After the reset, `git add` records the new file as `644` again. Read the modes of the paths being committed before the reset, and re-apply `+x` after staging to any path that was `100755` and came back `100644`. Do this only under `core.filemode=false`, because elsewhere the disk is the authority and git already recorded it.

The same reset on a refusal throws the bit away for good, since the helper's own memory of it ends with the run: the retry reads `100644` before its reset and has nothing to re-apply. Measured with `core.filemode=false` and a rejected commit message: `git add --chmod=+x tool.sh` gave `100755`, the refusal left `tool.sh` unstaged, and the retry committed it `100644`. A refusal that clears the index has to name the `+x` paths it dropped, so the caller stages them again before retrying.

A snapshot built in a scratch index seeded from the real one keeps a pre-staged mode with no extra work, because `git add` preserves the seeded entry's mode.

## Testing it from a non-Windows machine

Setting `core.filemode=false` on macOS reproduces git's half of the behaviour, but not the `os.access` half. That one only shows up on Windows, so a test that expects `755` from an executable disk copy has to be skipped there. The Windows gate is still the only proof that the Windows branch works.
