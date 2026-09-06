# Spawning bash from a program on Windows

A bare `bash` in a child-process call does not get Git Bash. It usually gets WSL, and the script then
runs on a different operating system — which presents as a tool that "cannot be found" rather than as
a shell that was never the one you meant.

## The mechanism

`CreateProcess` (which Python's `subprocess`, .NET's `Process.Start`, Node's `child_process` and most
others sit on) searches, in order: the directory of the calling executable, the current directory, the
**System directory**, the Windows directory, then `PATH`. `C:\Windows\System32\bash.exe` is the **WSL
launcher**, shipped with Windows. So System32 wins long before Git's `usr/bin/bash.exe` on `PATH`.

Measured on Windows 11, from a Python child process:

```
subprocess.run(["bash", "-c", "uname -a"])
  -> Linux CHROME 6.6.87.2-microsoft-standard-WSL2 ... GNU/Linux
```

**The obvious check disagrees with reality, in the same process.** `shutil.which("bash")` searches only
`PATH`, so it returns `C:\Program Files\Git\usr\bin\bash.EXE` — confirming the shell you expected while
the actual spawn goes to WSL. A `which`-based assertion here is worse than none: it manufactures
confidence. The same trap applies to any language's `which`-alike.

## Why it is hard to recognise

Inside WSL you are in a different OS with a different filesystem view and a different environment:

```
LOCALAPPDATA  <UNSET>       USERPROFILE  <UNSET>       APPDATA  <UNSET>
HOMEDRIVE     <UNSET>       HOMEPATH     <UNSET>       HOME     /home/<user>
```

So every Windows-hosted tool is absent and every `%LOCALAPPDATA%`-rooted lookup expands to a path under
`/`. A well-written script notices, fails closed, and reports the tool as missing — which reads as a
PATH or installation problem on the Windows side, and sends you to fix a resolver that is working
correctly. Two wrong root causes came out of exactly this before anyone ran `uname`.

If the script logs to a file rather than to stderr — the correct design for anything run by a scheduler
— the child's stdout and stderr come back **empty** alongside a non-zero exit, removing the last obvious
clue. Check the script's own log before theorising.

## The fix, and the diagnostic

Spawn by absolute path:

```python
GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"      # or usr\bin\bash.exe
subprocess.run([GIT_BASH, "script.sh"])
```

Resolve it rather than hardcoding where a project already has a resolver, and prefer `bin\bash.exe`
(the wrapper intended for external callers) over `usr\bin\bash.exe`.

**The diagnostic is one command, and it beats any amount of inference:** run `uname -a` inside the
process that failed. It distinguishes MSYS (`MINGW64_NT-…`) from WSL (`Linux … microsoft-standard-WSL2`)
immediately, and it is available before you know what you are looking for.

## Where this does *not* bite

A Windows scheduled task that names an absolute interpreter path is unaffected, and so is anything
launched from an interactive Git Bash, because there `PATH` resolution happens inside MSYS rather than
through `CreateProcess`. The failure appears specifically when a *program* spawns `bash` by bare name —
a wrapper script, a test harness, a job runner — which is also where it is least expected.
