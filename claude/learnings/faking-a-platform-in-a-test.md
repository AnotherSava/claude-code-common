# Driving the other platform's branch in a test

A module that branches on `process.platform` has exactly one branch any given host can reach, so a suite
run on one machine ships the other platform's code unexercised — and the first person to reach that code is
whoever pulls on the other box. Forcing the flag is the instrument available, and it moves more than the
branch it was aimed at.

Measured 2026-10-07 on macOS with Node 24.15, against `~/.claude/skills/ports/scripts/dev-port.mjs`, whose
Windows branch quotes a command line for cmd.exe and whose POSIX branch passes an argv array.

## Fake it before the import, not after

```js
Object.defineProperty(process, 'platform', { value: 'win32' })
const { run } = await import(pathToFileURL(modulePath).href)
```

The module reads `process.platform` when its function runs, so the value only has to be in place before the
call — but a static `import` is hoisted above every statement in the file, so the module would observe the
real value while loading and may capture it in a module-level constant. A dynamic `await import()` after the
assignment is what orders the two. Each case gets its own child process, since neither the fake nor a
module's captured copy of it can be undone.

## The fake reaches every conditional, not only yours

That module carries two: the shell flag under test, and the interpreter name it spawns the registry
through — `python` on win32, `python3` everywhere else. Forcing win32 on macOS asked for `python`, which
need not exist there, and the failure arrives from the port resolver rather than from the branch under test.
The fix is a scratch `bin` holding a `python` shell script that execs `python3`, prepended to `PATH`.
Enumerate a module's platform conditionals before trusting a forced case: the one you did not mean to flip
is the one that fails somewhere unrelated.

Node's `child_process` reads the faked value too, building its shell invocation from it, so a faked win32
spawn looks for `process.env.comspec || 'cmd.exe'` and fails with ENOENT on a Mac. Pointing `comspec` at
`/bin/sh` makes the case runnable, and the substitution is honest about what it measures: Node's non-cmd
branch hands the command line to `sh -c` unchanged, and sh applies the same double-quote rule cmd.exe does,
so the quoting under test is genuinely exercised while cmd.exe's own parsing is not. Say which half the case
covers.

## What does not follow the fake

Native calls answer for the real platform whatever `process.platform` says. The clearest is `os.homedir()`,
which reads `USERPROFILE` on Windows and `HOME` on POSIX — see `absence-versus-unreadable.md`, where that
split silently measured an installed tree as absent. So a forced platform separates the module's behaviour
from the runtime's: redirecting a home for a test needs both variable names set, and the fake has no say in
which one is read.

## A branch the host cannot drive is NOT COVERED

Some branches are unreachable rather than merely unexercised, and the honest report differs from both a
pass and a failure. Node refuses to spawn a `.cmd` or `.bat` without `shell: true` — the CVE-2024-27980
hardening, in `claude-code-integration.md` — so Windows cannot drive a no-shell case against an npm shim,
and a POSIX shell script is not executable there either. Probe the precondition, and put NOT COVERED with
its reason in the line the gate prints, since a suite's summary line is the only part of it anyone reads on
a pass.
