# Elevating from Claude Code's shell on Windows

**Get the user watching the PC's screen immediately before a `Start-Process -Verb RunAs`.** Its UAC prompt takes that screen at once and is cancelled after two minutes, so a user who is away, or working from another machine, never answers it. An installer's own elevation waits for them.

## What was measured

On 2026-11-13, on Windows 11, in a session whose Claude Code process runs under a background holder and not as a child of the terminal window that displays it:

- **`Start-Process -Verb RunAs`:** the prompt was on the secure desktop within a second of the request. A probe saw the input desktop become inaccessible and `consent.exe` start, and no UAC window appeared on the ordinary desktop. Unanswered, the request ended after 122 s with `This command cannot be run due to the error: The operation was canceled by the user.` Two earlier attempts ended the same way after 124 s and 127 s: one while the user was at another machine, and one after they had said they were ready to approve.
- **`msiexec` for a per-machine MSI:** `Start-Process msiexec -ArgumentList '/i', ... -Wait` waited twelve minutes, until the user connected to the PC, and then installed. An uninstall and an install run one after the other from the same shell both exited 0. Each time the secure desktop was up for a second or two, so the prompt was answered as soon as it was shown. What held the request until then was not observed. Microsoft's UAC guidance says a request from a program that is not in the foreground waits as a flashing taskbar button.
- **Over Parsec:** the user answered the installer's prompts from another machine through Parsec. Whether Parsec shows a `RunAs` prompt was not observed: twice one went unanswered while a Parsec session was connected.

## What this means in practice

- **A cancel is not a refusal.** The error after two minutes is the prompt going unanswered. Ask before reporting that the user declined.
- **Installers:** call `msiexec`, or a setup exe whose manifest asks for elevation, directly. Its prompt waits for the user, and each call asks on its own, so two operations mean two prompts.
- **Waiting:** an installer's elevation blocks until the user answers, which can take longer than the Bash tool's timeout. Run it with `run_in_background`.
- **Anything that is not an installer** has only the `RunAs` route, which the learning `windows-file-acl-delete-denied.md` shows for an ACL repair. Say when the prompt is about to appear, and expect an answer or a cancel within two minutes.
- **MSI install location:** pass the installer's directory property on the command line, for example `APPDIR=C:\Programs\<App>\` for a WiX `InstallDir` UI. The property's name is in the verbose log (`/l*v`) as `WIXUI_INSTALLDIR = <name>`. Moving an installed app means uninstalling and installing again, so the uninstall entry and any shortcuts the MSI created follow the new path.
