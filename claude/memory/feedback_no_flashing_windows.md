---
name: feedback_no_flashing_windows
description: A scheduled job or spawned process on Windows must never put a console window on the user's desktop, however briefly
metadata:
  type: feedback
---

**Windows should never flash.** A scheduled task, a background job, or anything else launched on the
user's behalf must not put a console window on their desktop — not for a second, not at 03:00 when
nobody is looking.

`pythonw.exe` covers a Python entry point. Anything else needs a GUI-subsystem launcher that starts the
child with `CREATE_NO_WINDOW` (`0x08000000`). **Both halves are required**: the launcher alone still
flashes because the child allocates its own console, and the flag alone still flashes because the
launcher had one. Since `pythonw` discards stdout and stderr, that launcher must also capture the
child's output, or a scheduled failure leaves no trace anywhere.

**Why:** the rule was stated without qualification, and the violation had been running nightly and
unnoticed. It arrives by a specific trap: the documented fix for "Task Scheduler cannot invoke MSYS
`bash.exe` directly" is to wrap it in `cmd.exe`, which silently undoes the no-window work done for the
Python job beside it. Two correct-looking fixes, written up separately, quietly contradicting each other.

**How to apply:** when registering or reviewing any Windows scheduled task, ask what subsystem the
`-Execute` target is before asking whether the command is right — `cmd.exe`, `powershell.exe` and a bare
`bash.exe` all show a window under an Interactive logon. Applies equally to processes spawned during a
session, which is the same promise in a shorter timeframe. Mechanics and the launcher source are in
`learnings/windows-scheduled-tasks-nonadmin.md`.
