@rem `dev-port <command> [args...]`: run a dev server on the port the ports registry holds for this project.
@rem The dotfiles install puts this directory on PATH; the logic is in ..\scripts\dev-port.mjs.
@node "%~dp0..\scripts\dev-port.mjs" %*
