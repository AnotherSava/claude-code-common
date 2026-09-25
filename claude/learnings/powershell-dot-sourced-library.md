# Writing a dot-sourced PowerShell library

A helper file that other scripts dot-source runs its functions inside the caller's session, so two things resolve differently from how they read: which directory a path is relative to, and whose error preference a native command runs under. Both were verified on 2026-09-25 on Windows PowerShell 5.1 and PowerShell 7.

## Which directory a path resolves against

Inside a function defined in a dot-sourced file:

- **`$PSScriptRoot`** is the directory of the file that defines the function — the library. Use it for files shipped beside the library.
- **`$MyInvocation.PSScriptRoot`** is the directory of the script whose line called the function. Use it for anything that belongs to the caller's project, such as its repo root or its `tmp/`. When the call goes through a wrapper function in the caller's own lib, it is the wrapper's directory, which is still inside the caller's repo.

Never find the caller's repo from a path argument such as an output file: a caller may stage that file in `%TEMP%`, outside every repo, and a lookup that throws there can lose the only copy if the caller deletes the file in `finally`. Find the root by walking up from the caller's directory to the first one holding `.git`, not by running `git rev-parse`: git may be missing from PowerShell's PATH when it was installed for Git Bash only, or may refuse the repo as dubious ownership.

## Native stderr becomes a terminating error under `Stop` on 5.1

On Windows PowerShell 5.1, `2>$null` on a native command still turns its stderr into an error record, and with the caller's `$ErrorActionPreference = 'Stop'` that record throws a `RemoteException`. So `git -C $dir rev-parse --show-toplevel 2>$null` outside a repo throws git's `fatal: not a git repository` before the next line can read `$LASTEXITCODE`. PowerShell 7 returns exit code 128 without throwing.

A library cannot know the caller's preference, so run the probe in a child scope that sets its own:

```powershell
$root = & { $ErrorActionPreference = 'Continue'; git -C $dir rev-parse --show-toplevel 2>$null }
if (-not $root) { throw "…" }
```

The assignment is local to the scriptblock, so the caller's `Stop` is still in force afterwards, and `$LASTEXITCODE` still carries git's exit code.
