# A detached process that holds its launcher's output pipe

A script that starts a long-running process in the background and then exits can still hang whoever
is reading its output. A reader of a pipe waits for end-of-file, and EOF arrives only when *every*
process holding the pipe's write end has closed it. If the background process inherited the
launcher's stdout or stderr, it holds that pipe open for as long as it runs. The script exits 0, the
reader blocks, and nothing reports an error.

## Symptom

- `some-launcher.sh | tail`, `$(some-launcher.sh)`, or any tool that captures output until EOF
  hangs until its own timeout, then shows nothing — `tail` prints only at EOF.
- The same script run directly, or through something that waits for the *process* to exit rather
  than for the stream to end, returns promptly. That is why the defect survives: the usual
  invocation path does not show it.
- `ps` shows the launcher gone and only the background process (and its children) still alive.

Measured 2026-10-06 with a dev-server deploy script on Windows: a plain run returned in 13 s, and the
same run piped through `tail -30` sat for 120 s until killed. With the fix it returned in 8 s.

## Windows: `Start-Process` with redirection passes on every inheritable handle

`Start-Process -RedirectStandardOutput … -RedirectStandardError …` cannot use ShellExecute, so it
calls CreateProcess with handle inheritance on. The child then inherits every inheritable handle
PowerShell holds — including PowerShell's own stderr and stdin, which, when PowerShell was launched
from Git Bash inside a pipeline, are the caller's pipe. The server's redirected log files do not
help: those are the child's *standard* handles, and the inherited copies ride along beside them.

The fix is to give PowerShell none of the caller's streams, so there is nothing of the caller's to
inherit:

```bash
powershell.exe -NoProfile -Command "try { Start-Process -WindowStyle Hidden -FilePath 'cmd.exe' \
  -ArgumentList '/c','<cmd>' -WorkingDirectory '<dir>' \
  -RedirectStandardOutput '<out.log>' -RedirectStandardError '<err.log>' -ErrorAction Stop } \
  catch { Set-Content -LiteralPath '<err.log>' -Value ('launch failed: ' + \$_); exit 1 }" \
  </dev/null >/dev/null 2>&1
```

Silencing PowerShell's stderr would also silence a launch failure, so the `try`/`catch` writes the
reason into the server's own error log, where a "server did not come up" message already points.
Use string concatenation inside the `-Value`, not an inner double-quoted string: bash's `\"` inside a
`-Command` argument goes through the Windows command-line quoting on its way to PowerShell.

`Start-Process` *without* redirection goes through ShellExecute, which passes no handles — launching
a GUI app that way does not have this problem. That is the documented behaviour, not one measured
here.

Python's `subprocess.Popen` does not have it either when the child's three streams are set
explicitly (`stdin=DEVNULL, stdout=fh, stderr=fh`): on Windows it restricts inheritance to exactly
those handles.

## Unix: `nohup` leaves stdin alone when it is not a terminal

`nohup cmd >log 2>err &` redirects the two output streams, so it does not cause the EOF hang, but
`nohup` replaces stdin only when stdin is a terminal. Under a pipe or a tool, the background process
keeps the caller's stdin. Add `</dev/null` to cut the last stream.

## Testing for it

A test that only checks the exit status cannot see this. Read the launcher's stdout through a pipe
on a separate thread, wait for the process, then require the reader to reach EOF within a few
seconds of the exit. In Python, do not use `subprocess.run(..., timeout=…)` for this: on Windows its
timeout path kills the child and then calls `communicate()` again, which blocks on the very pipe the
grandchild still holds. Clean up by killing the background process by the port or PID it took —
that also closes the held pipe and lets the reader thread finish.

The dotfiles repo's `claude/tests/deploy-dev-server.py` is a worked example, run from its commit gate.

What to do as the caller, when a launcher may still have this defect, is in `bash-portability.md`
under "Piping a script that leaves a server running": redirect to a file, and why `tee` and `set -m`
do not help.
