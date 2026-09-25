# Installs the holder: the piece that keeps the WSL distro and the tmux server alive between
# connections. Run it once on the Windows machine, and again after changing anything it writes.
#
#     powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1
#
# What it does, and why each part is not optional:
#
#   - Writes `.wslconfig` so a distro is never shut down for being idle. Left alone, WSL takes the
#     distro down about 45 s after the last connection closes and the tmux server dies with it.
#   - Registers a scheduled task that starts the holder at logon. A scheduled task is the only way
#     the holder outlives the connection that started it: anything launched from an SSH session
#     belongs to Win32-OpenSSH's job object and is killed on disconnect, and `start /b` does not
#     escape it.
#   - Runs the task through a windowless launcher, so nothing ever flashes on the desktop.
#
# The task is registered Interactive, which means it runs in the logged-on desktop session. That is
# deliberate: session 0, where sshd lives, cannot reach the desktop, so an agent hosted there could
# build and unit-test a Windows GUI app but never show it or drive it. The cost is that logging off
# ends the holder; the at-logon trigger is what brings it back.

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$TaskName = 'ClaudeRemoteSessionHolder'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath = Join-Path (Split-Path -Parent $here) 'config.secret.env'

# --- configuration -------------------------------------------------------------------------------

if (-not (Test-Path $configPath)) { throw "no config at $configPath" }

$config = @{}
foreach ($line in Get-Content $configPath) {
    if ($line -match '^\s*([A-Z_]+)=(.*)$') { $config[$Matches[1]] = $Matches[2].Trim() }
}
foreach ($key in 'WSL_DISTRO', 'REPO_WSL_PATH') {
    if (-not $config[$key]) {
        throw "$key is missing from $configPath - is this checkout still transcrypt-locked? Run transcrypt in it."
    }
}
$distro = $config['WSL_DISTRO']

# --- the shell functions ---------------------------------------------------------------------------

# Before anything else, because it needs none of what follows and because it refuses rather than
# overwriting: a stale `claude` function is then reported while every session is still running,
# instead of after re-registering the task has killed them all.
& (Join-Path $here 'install-shells.ps1')

# --- .wslconfig ----------------------------------------------------------------------------------

# `instanceIdleTimeout = -1` is the documented way to stop a distro being shut down for idleness.
# The VM's own `vmIdleTimeout` has no documented disable value, so it is left alone: the holder's
# blocking `sleep infinity` is what keeps the VM from ever being idle, and that is the real
# mechanism. This file only removes the distro-level half.
$wslConfig = Join-Path $env:USERPROFILE '.wslconfig'
if (Test-Path $wslConfig) {
    if ((Get-Content $wslConfig -Raw) -match 'instanceIdleTimeout') {
        Write-Host "wslconfig: already sets instanceIdleTimeout, leaving $wslConfig alone"
    } else {
        throw "$wslConfig exists and does not set instanceIdleTimeout. Add instanceIdleTimeout=-1 under a [general] section by hand rather than having this script overwrite settings it did not write."
    }
} else {
    Set-Content -Path $wslConfig -Encoding ascii -Value @(
        '# Written by claude/remote-session/windows/install.ps1.',
        '[general]',
        '# Never shut a distro down for being idle; the tmux server holding the Claude sessions',
        '# lives inside it and would go with it.',
        'instanceIdleTimeout=-1'
    )
    Write-Host "wslconfig: wrote $wslConfig"
}

# --- the windowless launcher ---------------------------------------------------------------------

# Resolve pythonw from the active interpreter rather than hardcoding an install path. Nothing an
# interactive shell happens to have is necessarily on a task's PATH, so the registered action must
# name every executable absolutely.
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw 'python is not on PATH, so pythonw.exe cannot be resolved' }
$pythonw = Join-Path (Split-Path -Parent $python) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { throw "no pythonw.exe beside $python" }

$wsl = Join-Path $env:SystemRoot 'System32\wsl.exe'
if (-not (Test-Path $wsl)) { throw "no wsl.exe at $wsl" }

# --- the holder script, copied into the distro -----------------------------------------------------

# The holder runs from the distro's own filesystem rather than from the checkout on D:. A script a
# Linux process is executing over the drvfs mount is an open Windows file handle for as long as it
# runs, so leaving it in the repo makes `git pull` on this machine fail on a locked file whenever the
# holder is up - a failure that names the file and not the reason. Re-run this script after changing
# holder.sh, or what it uses from lib.sh (the keepalive session's name and remote_session_holder_up);
# nothing else refreshes these copies. Every other script sources the checkout's lib.sh and sees a
# change on its next run.
#
# lib.sh goes with it because holder.sh sources it for the keepalive session's name, and sits beside
# it there rather than one directory up as it does in the checkout.
$wslHome = (& $wsl -d $distro -- sh -c 'printf %s "$HOME"') -replace "`0", ''
if (-not $wslHome) { throw "could not read HOME inside $distro" }
$holderDir = "$wslHome/.local/share/claude-remote-session"
$holder = "$holderDir/holder.sh"
# Built from the config rather than through `wslpath`, which is handed the Windows path by way of
# PowerShell and wsl.exe argument parsing and gets its backslashes eaten on the way.
$sourceDir = "$($config['REPO_WSL_PATH'])/claude/remote-session"

& $wsl -d $distro -- sh -c "mkdir -p '$holderDir' && cp '$sourceDir/lib.sh' '$sourceDir/wsl/holder.sh' '$holderDir/' && chmod +x '$holder'"
if ($LASTEXITCODE -ne 0) { throw "could not install the holder script into $holderDir" }
Write-Host "holder: installed $holder"

# The keepalive session's name is defined once, in lib.sh. PowerShell cannot source that file, so it
# reads the value rather than repeating the literal - a rename there would otherwise leave this
# assertion looking for a session nobody creates, and report a running holder as down.
$libText = & $wsl -d $distro -- cat "$sourceDir/lib.sh"
if ($libText -join "`n" -notmatch 'REMOTE_SESSION_KEEPALIVE=(\S+)') {
    throw "no REMOTE_SESSION_KEEPALIVE in $sourceDir/lib.sh"
}
$keepalive = $Matches[1]

$logDir = Join-Path $env:LOCALAPPDATA 'claude-remote-session'
$log = Join-Path $logDir 'holder.log'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

# The launcher is copied out of the checkout for the same reason holder.sh is: the task runs it for
# as long as the user is logged on, and a running script is an open file handle, so `rm` and
# `git pull` both fail on the repo copy with "Permission denied" while the holder is up. Measured -
# holder.sh was moved for this and run-hidden.py was left behind, which is the whole failure.
$launcher = Join-Path $logDir 'run-hidden.py'
Copy-Item -Path (Join-Path $here 'run-hidden.py') -Destination $launcher -Force

# --- the task ------------------------------------------------------------------------------------

$argument = '"{0}" --log "{1}" -- "{2}" -d {3} -- {4}' -f $launcher, $log, $wsl, $distro, $holder
$action = New-ScheduledTaskAction -Execute $pythonw -Argument $argument -WorkingDirectory $here

# An unscoped -AtLogOn means "any user who logs on", which is a machine-wide registration a non-admin
# cannot make; scoping it to this account makes it a per-user trigger.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited

# ExecutionTimeLimit defaults to PT72H, which would kill a holder meant to run for as long as the
# user is logged on; PT0S means no limit. The battery flags matter on a laptop, where the defaults
# silently decline to start.
$settings = New-ScheduledTaskSettingsSet -Hidden -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

# An existing registration is replaced in place with -Force, never removed and re-created. Measured
# 2026-09-22 on the machine that registered it: `Unregister-ScheduledTask` on this task fails with
# "Access is denied" for the same non-elevated account, while overwriting it succeeds — so a re-run
# that deletes first needs elevation the first install did not. That failure used to be swallowed by
# `-ErrorAction SilentlyContinue` and surface one line later as Register-ScheduledTask reporting
# "Cannot create a file when that file already exists", an error about the wrong step.
#
# A running task is stopped first, because -Force will not replace one that is running.
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
$wasRunning = [bool]($existing -and $existing.State -eq 'Running')
if ($wasRunning) { Stop-ScheduledTask -TaskName $TaskName }

try {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal `
        -Settings $settings -Force `
        -Description 'Holds the WSL distro and tmux server that carry the Claude sessions.' | Out-Null
} catch {
    # The stop above happened for a replacement that then did not happen, so put the holder back
    # before reporting. A failed run that leaves the task stopped is worse than one that changes
    # nothing: the holder is gone until the next logon, and nothing says so.
    if ($wasRunning) { Start-ScheduledTask -TaskName $TaskName }
    if (-not $existing) { throw }
    # Measured 2026-09-22 on the machine that registered it: the task file grants the registering
    # account read-only access, so replacing the task is denied to the same user who created it and
    # the first install is the only one that runs unelevated. Read the ACL for yourself with
    # icacls "$env:SystemRoot\System32\Tasks\<task>". The raw error names neither the task nor
    # elevation, which is why it is translated rather than passed through.
    # Interpolated rather than built with -f, which binds tighter than + and would have formatted
    # only the last piece of a concatenated message - leaving a literal {0} in what the user reads.
    $denied = $_.Exception.Message
    throw "could not replace the existing $TaskName task: $denied - re-run this script from an Administrator PowerShell, or delete the task there first."
}
Write-Host "task: registered $TaskName"

# --- proof ---------------------------------------------------------------------------------------

# Registering says nothing about whether it runs: a task's session differs from an interactive shell
# in working directory, PATH and credentials. Assert the side effect, not the exit code — and assert
# both halves the holder owns: its own process, and the tmux server it keeps alive.
Start-ScheduledTask -TaskName $TaskName

$deadline = (Get-Date).AddSeconds(60)
$running = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 3
    & $wsl -d $distro -- sh -c "pgrep -f claude-remote-session/holder.sh >/dev/null && tmux has-session -t '=$keepalive'" *> $null
    if ($LASTEXITCODE -eq 0) { $running = $true; break }
}

if (-not $running) {
    Write-Host "holder: NOT RUNNING after 60 s."
    Write-Host "holder: read $log, which is the only place a failure under pythonw can surface."
    (Get-ScheduledTaskInfo -TaskName $TaskName) | Select-Object LastRunTime, LastTaskResult | Format-List
    exit 1
}

Write-Host "holder: running, $distro is held open"
Write-Host "holder: log is $log"
