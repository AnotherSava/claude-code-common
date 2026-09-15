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

## The signature when it is a script path rather than `-c`

Passing a *script* instead of `-c` gives the failure a shape that points at the wrong cause. WSL cannot
see any Windows path, so every spelling fails identically:

```
bash "C:\repo\…\link.sh"   -> /bin/bash: C:repo…link.sh: No such file or directory
bash "C:/repo/…/link.sh"   -> /bin/bash: C:/repo/…/link.sh: No such file or directory
bash "/c/repo/…/link.sh"   -> /bin/bash: /c/repo/…/link.sh: No such file or directory
```

The first line is the trap: MSYS argv conversion has mangled the backslashes out, so the message reads
as a shell-escaping bug and sends you to fix quoting. It is not — the forward-slash and `/c/` forms fail
just as hard, and `os.path.isfile()` on the same string returns `True` in the calling process. **Two
spellings failing the same way is the tell**, because a quoting fault would not touch the `/c/` form.
`/mnt/c/…` is the only path such a shell could have opened.

Measured 2026-09-15: diagnosed as an argv[0] fault in MSYS bash and committed with that explanation in a
code comment, because the fix — spawning by absolute path — is the same either way and therefore
appeared to confirm it. `uname -a` was what settled it, after the fact.

## `which` as a resolver is right; `which` as a check is the trap

These read alike and are opposites, which is worth stating because the section above only warns against
the second:

```python
subprocess.run([shutil.which("bash"), script])   # correct — the resolved path is what gets spawned
assert shutil.which("bash"); subprocess.run(["bash", script])   # the trap — asserts Git, runs WSL
```

`which` searches `PATH`, where Git's bash is; `CreateProcess` searches System32 first, where WSL's is.
Spawning `which`'s *result* never reaches System32, so the discrepancy cannot arise. Prefer
`bin\bash.exe` when hardcoding, but on a script that also runs on macOS, `shutil.which("bash")` is the
portable form and returns a genuine MINGW64 bash here (verified with `uname -a`).

## Where this does *not* bite

A Windows scheduled task that names an absolute interpreter path is unaffected, and so is anything
launched from an interactive Git Bash, because there `PATH` resolution happens inside MSYS rather than
through `CreateProcess`. The failure appears specifically when a *program* spawns `bash` by bare name —
a wrapper script, a test harness, a job runner — which is also where it is least expected.
