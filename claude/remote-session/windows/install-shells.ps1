# Puts the `claude` function into every shell on this machine that has a profile, so starting a
# session anywhere goes through start-here.sh and ends up inside the holder's tmux server.
#
#     powershell -NoProfile -ExecutionPolicy Bypass -File install-shells.ps1
#
# install.ps1 runs this first. Run on its own it touches neither the holder nor the scheduled task,
# so no session dies.
#
# Windows has three shells here and each reads its own profile: Git Bash, Windows PowerShell 5.1 and
# PowerShell 7 never share a file. Wiring them by hand is what put a stale function in one of the
# three for months — it launched claude.exe directly, so every session opened from that shell was
# unattachable, and nothing said so. The function is written from the repo instead.
#
# A `claude` function that is already the thin caller is left alone. One that is anything else is
# reported rather than overwritten: the profile is the user's file and this script did not write
# what is in it.

$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath = Join-Path (Split-Path -Parent $here) 'config.secret.env'

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

# The call every shell makes, built from the config rather than repeated per profile: after a repo
# move or a distro rename, one run prints the new call for every profile still holding the old one.
$call = 'wsl -d {0} -- {1}/claude/remote-session/wsl/start-here.sh' -f $config['WSL_DISTRO'], $config['REPO_WSL_PATH']

$rationale = @(
    'Starts Claude inside the holder''s tmux server, so the session can be attached later - from a',
    'second terminal on this machine, or from the Mac. Written by',
    'claude/remote-session/windows/install-shells.ps1. Everything this function used to do (the',
    '--continue fallback, suppressing Claude''s own terminal-title writes) lives in that script,',
    'which is versioned in the repo. See claude/remote-session/README.md.'
)

# Both PowerShells spell the function identically, so they share one block rather than carrying a
# copy each — two copies are what a later edit to the wording changes only one of.
$psBlock = { param($call, $rationale)
    @($rationale | ForEach-Object { "# $_" }) + @('function claude {', "    $call @args", '}')
}

$pwsh = Get-Command pwsh.exe -ErrorAction SilentlyContinue

# Each shell: where its profile is, how it spells a function, and how it forwards its arguments.
$shells = @(
    @{
        Name       = 'Git Bash'
        Path       = Join-Path $env:USERPROFILE '.bashrc'
        Installed  = [bool](Get-Command git.exe -ErrorAction SilentlyContinue)
        Definition = '^\s*(function\s+claude\b|claude\s*\(\s*\))'
        Block      = { param($call, $rationale)
            @($rationale | ForEach-Object { "# $_" }) + @('claude() {', "  $call `"`$@`"", '}')
        }
    },
    @{
        Name       = 'Windows PowerShell 5.1'
        Path       = & powershell.exe -NoProfile -Command '$PROFILE.CurrentUserCurrentHost'
        Installed  = $true
        Definition = '^\s*function\s+claude\b'
        Block      = $psBlock
    },
    @{
        Name       = 'PowerShell 7'
        Path       = if ($pwsh) { & pwsh.exe -NoProfile -Command '$PROFILE.CurrentUserCurrentHost' } else { $null }
        Installed  = [bool]$pwsh
        Definition = '^\s*function\s+claude\b'
        Block      = $psBlock
    }
)

$stale = @()

foreach ($shell in $shells) {
    if (-not $shell.Installed) {
        Write-Host ("{0}: not installed, skipped" -f $shell.Name)
        continue
    }
    if (-not $shell.Path) { throw ("could not resolve the profile path for {0}" -f $shell.Name) }

    $lines = if (Test-Path $shell.Path) { @(Get-Content $shell.Path) } else { @() }

    # Whitespace is normalised on both sides: a hand-indented copy of the right call is still the
    # right call, while a different distro or repo path is not and has to be seen as different.
    $wanted = $call -replace '\s+', ' '
    $hasCall = $lines | Where-Object { ($_ -replace '\s+', ' ') -match [regex]::Escape($wanted) }
    $hasDefinition = $lines | Where-Object { $_ -match $shell.Definition }

    if ($hasCall -and $hasDefinition) {
        Write-Host ("{0}: already calls start-here.sh, left alone ({1})" -f $shell.Name, $shell.Path)
        continue
    }
    if ($hasDefinition) {
        $stale += $shell
        Write-Host ("{0}: has a claude function without the current start-here.sh call - {1}" -f $shell.Name, $shell.Path)
        continue
    }

    $parent = Split-Path -Parent $shell.Path
    if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }

    # Built by appending to an array rather than by adding two together. A single-element array
    # unwraps to its element on the way out of an `if`, so a blank separator line becomes the string
    # '' and `+` then concatenates instead of joining - which writes the whole function as one line.
    $out = @()
    if ($lines.Count -gt 0 -and $lines[-1].Trim() -ne '') { $out += '' }
    $out += & $shell.Block $call $rationale
    Add-Content -Path $shell.Path -Value $out
    Write-Host ("{0}: wrote the claude function into {1}" -f $shell.Name, $shell.Path)
}

if ($stale.Count -gt 0) {
    Write-Host ''
    Write-Host 'Replace the claude function in each file above with this, keeping that shell''s syntax:'
    Write-Host ''
    foreach ($shell in $stale) { (& $shell.Block $call $rationale) | ForEach-Object { Write-Host "  $_" } }
    Write-Host ''
    throw 'a claude function without the current call is in the way; nothing was overwritten'
}

# A shell reads its profile once, at startup, so every terminal open right now still holds whatever
# was there before. Say so: the function looks broken in exactly those windows and nowhere else.
Write-Host ''
Write-Host 'Terminals already open keep the function they started with - restart them.'
