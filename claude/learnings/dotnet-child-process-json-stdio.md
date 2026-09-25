# Running child processes with JSON over stdio from .NET on Windows

A host that starts a helper process per request, writes one JSON request to its stdin and reads one JSON answer from its stdout looks like ten lines of `Process` code. Every item below broke a real implementation of that (the url-cleaner plugin runner, 2026-09-24), and most of them fail silently or only under a misbehaving child.

## Start settings

- `UseShellExecute = false`, `CreateNoWindow = true`, all three streams redirected, arguments through `ArgumentList` (never a joined string). A GUI host with `CreateNoWindow` gives the child a hidden console, and the child's own children inherit it, so nothing flashes on screen.
- **Stdin must not start with a byte-order mark.** `Encoding.UTF8` writes one, and Node's `JSON.parse` rejects the request. Use `new UTF8Encoding(encoderShouldEmitUTF8Identifier: false)` for `StandardInputEncoding` (and the same for stdout and stderr).
- **Refuse `.cmd` and `.bat`.** `CreateProcess` hands a batch file to `cmd.exe`, whose argument parsing no quoting from `ArgumentList` makes safe (the "BatBadBut" class). Check the extension with trailing spaces and dots trimmed, and check the *resolved* path too: Windows drops trailing spaces and dots when it resolves a name, so `tool.cmd ` reaches cmd.exe past a literal extension check.
- **Resolve the executable yourself** and pass an absolute path. Split PATH on `;`, trim each entry, and strip surrounding quotes: installers sometimes write a quoted entry, which `cmd.exe`'s lookup accepts, but `CreateProcess`'s own search (the one `Process.Start` relies on for a bare name) does not, and neither does a naive `Path.Combine`.

## Reading, writing and deadlines

- **Start reading stdout and stderr before writing stdin, never after the wait.** A child that writes a lot of stderr before reading its input (2 MB was enough) blocks on the full pipe and never exits, so a host that reads only after `WaitForExitAsync` waits out its deadline; a request larger than the stdin pipe buffer blocks the host's write as well. Verified by moving the stderr reader after the wait: the call deadlocked until its timeout.
- **Cap what you buffer from stdout.** Unbounded `ReadToEndAsync` on a child that writes forever pushed a host to about 4.8 GB before a 5-second deadline. Read in chunks into a bounded buffer, and end the child when it passes the cap; keep only a rolling tail of stderr.
- **Cancelling `WaitForExitAsync` doesn't stop the process.** At the deadline, kill it explicitly, and bound the wait after the kill too: a process stuck in kernel I/O may not exit promptly. `Kill(entireProcessTree: true)` can throw `AggregateException` when a descendant can't be terminated (an elevated helper), so catch it.
- **The streams can outlive the process.** A process the child started inherits the pipes and can hold them after the child exits: stdout and stderr, and stdin, where a request larger than the pipe buffer (between 4,000 and 5,000 characters here) then blocks the host's write indefinitely. After the child exits, give stdout, stderr **and the stdin write** one short grace (2 s) together, then end whatever still holds them. Otherwise the call returns late, and each blocked reader keeps a thread-pool thread for as long as the leftover lives.
- **Only stdout decides the answer.** Record which pipes had closed *before* ending the leftovers: ending them closes the rest, and checking afterwards reports the wrong reason. If stdout reached end-of-file, the answer is complete even when a leftover still held stdin or stderr.

## Job objects

- One host-wide job with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, whose handle the host holds for its whole life, ends every child and grandchild when the host ends, including on a forced stop that never runs exit code. Verified: a deploy's `Stop-Process -Force` of the host ended a hung child and its child.
- A second, per-call job nested in it lets `TerminateJobObject` end one call's processes. Assign the process to the host-wide job first, then to a freshly created, empty per-call job, which Windows 8+ nests under it; the reverse order fails once the host job holds another call's process. It reaches an orphaned grandchild whose parent has already exited, which a walk of the live process tree misses.
- Struct layout for `JOBOBJECT_EXTENDED_LIMIT_INFORMATION` on x64: the basic limit struct (two `long`, `uint` flags, two `UIntPtr`, `uint`, `UIntPtr`, two `uint`), then six `ulong` I/O counters, then four `UIntPtr`. Info class 9, flag `0x2000`.

## Testing it with Node fixtures

- **A Node child can't test a tree kill.** libuv puts the processes Node spawns in a kill-on-close job of its own, so they end when Node ends however the host killed it. Verified: `Kill(entireProcessTree: false)` still left none of Node's children behind. The job reaches only Node's direct children: libuv sets `JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK`, so their own children break away and outlive it.
- **A leftover that holds the pipes needs a non-Node plugin.** `cmd.exe /c "start /b ping -n 30 127.0.0.1 & exit /b 0"` exits at once while `ping` keeps the inherited pipes; both run under the hidden console, so nothing appears on screen. Redirecting ping's output with `>nul` doesn't release stdout here, because `start` hands ping cmd's own handles.
- **A mutation proves a test covers what it claims.** Several of these tests passed with the protection removed until they were rewritten: remove the guard, watch the test fail, restore.

## Text that isn't valid UTF-16

A child that cuts a string between the halves of an emoji produces a lone surrogate, as a `\ud83c` escape in its JSON or as raw text on stderr.

- `JsonElement.GetString()` throws `InvalidOperationException` on a lone-surrogate escape, not `JsonException`. Catch it where answers are parsed, or it escapes the call.
- `File.AppendAllText(path, text)` uses an encoder that throws `EncoderFallbackException` on a lone surrogate. Pass `new UTF8Encoding(false)`, which replaces it instead; a logger must never be what breaks its caller.
- When keeping the last N characters of a string, move the cut forward by one if it lands on a low surrogate.
