@echo off
REM Opens the same session the Mac attaches to, in this Windows terminal.
REM
REM   attach.cmd <project>
REM
REM Running this while agterm is already attached is the point: tmux serves both clients at once.
REM
REM The distro comes out of the shared config rather than relying on WSL's default, so a second
REM distro installed later cannot silently redirect this.

setlocal
if "%~1"=="" (
    echo usage: attach.cmd ^<project^>
    exit /b 2
)

set "CONFIG=%~dp0..\config.secret.env"
if not exist "%CONFIG%" (
    echo attach: no config at %CONFIG%
    exit /b 1
)

set "DISTRO="
for /f "usebackq tokens=2 delims==" %%v in (`findstr /b /c:"WSL_DISTRO=" "%CONFIG%"`) do set "DISTRO=%%v"
if "%DISTRO%"=="" (
    echo attach: WSL_DISTRO is missing from %CONFIG% ^(is this checkout still transcrypt-locked?^)
    exit /b 1
)

pushd "%~dp0..\wsl"
wsl.exe -d %DISTRO% -- ./cc-session.sh %1
popd
