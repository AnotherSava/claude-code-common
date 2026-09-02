# Registering a Windows scheduled task without admin rights

Everything below was measured on Windows 11 with a non-elevated PowerShell
(`WindowsPrincipal.IsInRole(Administrator)` → `False`), registering into the user's own task space.

## What a non-admin can and cannot register

| Attempt | Result |
| --- | --- |
| `-LogonType Interactive` + daily trigger | **OK** |
| `-LogonType Interactive` + full settings set | **OK** |
| `-LogonType S4U` ("run whether logged on or not") | **FAILED — Access is denied** |
| `-AtLogOn` trigger with no `-User` | **FAILED — Access is denied** |
| `-AtLogOn -User <current identity>` | **OK** |

Two of those failures are worth knowing because the error names no cause — both surface as a bare
`Access is denied` from `Register-ScheduledTask`, with nothing pointing at which parameter caused it.

**S4U is the one people reach for**, because it is how you get "run whether the user is logged on or
not" without storing a password. It requires elevation. If you cannot elevate, the honest options are
Interactive (runs only while logged on) or a stored password — there is no third way. Note S4U also
gets a restricted token with no access to network resources, so for any task that must reach a remote
host it is the wrong choice even when you *can* register it.

**An unscoped `-AtLogOn` means "any user who logs on"**, which is a privileged, machine-wide
registration. Scoping it to the current account makes it a per-user trigger and registers fine:

```powershell
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name   # e.g. MACHINE\User
New-ScheduledTaskTrigger -AtLogOn -User $identity
```

## Two defaults that silently defeat the point

`New-ScheduledTaskSettingsSet` defaults, read off a fresh object:

- `StartWhenAvailable` = **False** — a run missed because the machine was off is simply skipped, never
  caught up. For anything that must not miss a day, this must be set explicitly.
- `DisallowStartIfOnBatteries` = **True** — on a laptop the task silently does not start on battery.
- `ExecutionTimeLimit` = `PT72H`.

```powershell
New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)
```

Read the registered settings back with `(Get-ScheduledTask -TaskName X).Settings` — note the property
is `MultipleInstances`, **not** `MultipleInstancesPolicy`; the latter formats as blank and reads like
the setting failed to apply when it did.

## Avoiding a console window, and the cost of doing so

Point the action at `pythonw.exe` rather than `python.exe`. Resolve it from the active interpreter
instead of hardcoding an install path:

```powershell
$pythonw = & python -c "import os,sys;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"
```

`pythonw` discards stdout **and** stderr. A crash under it leaves no trace anywhere, so the script must
write its own log file and a heartbeat — otherwise the first symptom of a broken daily job is noticing,
weeks later, that nothing has been produced.

## Verify by firing it, not by registering it

Registration succeeding says nothing about whether the task runs. The task's own session differs from
an interactive shell in working directory, PATH, and access to ssh keys and agents — the classic
"works when I run it by hand, fails at 03:00".

```powershell
Start-ScheduledTask -TaskName X
Get-ScheduledTaskInfo -TaskName X | Select LastRunTime, LastTaskResult, NumberOfMissedRuns
```

`LastTaskResult` of `0` plus an observable side effect (a log line, a changed heartbeat file) is the
proof. Assert the side effect, not just the exit code.

## Bash-to-PowerShell quoting

Invoking a non-trivial PowerShell snippet from Git Bash via `powershell -Command "..."` mangles
backslashes, so `$env:USERDOMAIN\$env:USERNAME` arrives broken and account lookups fail with
`No mapping between account names and security IDs was done`. Write the script to a `.ps1` and run it
with `-File`; the same rule that applies to Python heredocs applies here.

## A winget-installed tool on PATH may be a 0-byte alias that resolves in some contexts and not others

`winget` does not put the real executable on PATH. It puts a shim in `%LOCALAPPDATA%\Microsoft\WinGet\Links\`
which is a **0-byte reparse point** (an App Execution Alias) pointing into
`%LOCALAPPDATA%\Microsoft\WinGet\Packages\<Publisher>.<Package>_<hash>\<tool>.exe`.

```powershell
(Get-Item "$env:LOCALAPPDATA\Microsoft\WinGet\Links\<tool>.exe" -Force).Attributes
# Archive, ReparsePoint      <- length is 0
```

**Whether it resolves depends on the calling context, and the failure is silent.** Invoked through
PowerShell over an SSH session it produced no stdout, no stderr and no testable exit code — three separate
probes came back completely empty, which reads exactly like "the tool is not installed" and sent a
diagnosis down the wrong path entirely. Invoked non-interactively through Git Bash on the same machine the
same alias worked fine, because MSYS follows the reparse point. So neither "it works" nor "it emits
nothing" is a property of the alias — it is a property of the alias *and* the shell resolving it.

For a scheduled task this matters twice over: the task runs in a context you did not test interactively,
and a tool that silently produces nothing is far worse than one that errors. A credential helper that
renders an empty environment lets the real command run *unauthenticated* rather than failing fast.

**Call the absolute `WinGet\Packages\...` path in anything scheduled**, and resolve it once at install time
rather than hardcoding the hash-suffixed directory, which changes on package upgrade:

```powershell
$exe = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter <tool>.exe |
        Select-Object -First 1).FullName
```

The general rule this is an instance of: **on Windows, "the command is on PATH" is not the same claim as
"this context can execute it"** — and a reparse point is exactly the kind of thing an existence check sees
through without noticing. The same blindness is why file-walking code needs an explicit reparse-attribute
test rather than a symlink test.
