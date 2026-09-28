# .NET filesystem APIs on Windows — silent-skip gotchas

Four APIs that answer wrongly rather than throwing. Each was found the hard way; each produced a bug
with no exception, no log line, and nothing in the output to say anything had gone wrong.

## `EnumerationOptions.AttributesToSkip` defaults to `Hidden | System`

The usual recursive-scan incantation is silently blind to hidden directories:

```csharp
// Skips every hidden or system directory — including the one you were looking for.
Directory.EnumerateFiles(root, "marker.txt",
    new EnumerationOptions { RecurseSubdirectories = true, IgnoreInaccessible = true });
```

`AttributesToSkip` is not something you opt into; it defaults to `FileAttributes.Hidden | FileAttributes.System`.
A hidden folder is not *visited and rejected* — it is never enumerated, so nothing downstream can even
report it as skipped. The tell when debugging: your "found" log line is missing for a path you can see
in Explorer with hidden files shown, **and** your "rejected because…" line is missing too. One absent,
the other present, means a filter of yours; both absent means the enumerator never got there.

This bites in the real world because installers, game repacks and sync tools mark data folders hidden
routinely — no user ever set the bit.

```csharp
// Hidden folders visible; system ones still skipped.
new EnumerationOptions
{
    RecurseSubdirectories = true,
    IgnoreInaccessible = true,
    AttributesToSkip = FileAttributes.System
}
```

Keep `System` in the skip set. `$RECYCLE.BIN` and `System Volume Information` are hidden **and**
system, so skipping system alone still keeps a scan out of them — whereas `AttributesToSkip = 0`
walks straight in.

`EnumerationOptions` is a mutable class, so a shared `static readonly` instance is a caller-mutable
global. Expose it as a property that returns a fresh one, and route every scan in the codebase through
it — this setting is exactly the kind that gets fixed in one call site and left wrong in six others.

## `File.SetLastWriteTimeUtc` throws on a directory; the getter doesn't

The read side is polymorphic and the write side is not:

| Call | On a file | On a directory | On a missing path |
|---|---|---|---|
| `File.GetLastWriteTimeUtc` | works | **works** | `1601-01-01`, no throw |
| `Directory.GetLastWriteTimeUtc` | works | works | `1601-01-01`, no throw |
| `File.SetLastWriteTimeUtc` | works | **`UnauthorizedAccessException`** | throws |
| `Directory.SetLastWriteTimeUtc` | — | works | throws |

The getters returning `1601-01-01` instead of throwing is useful: "absent" becomes a comparable value,
so a change-detection stamp array needs no existence checks and no null handling.

**A directory's own last-write-time moves when an entry is added to or removed from it.** That makes
it a cheap probe for "did a file appear in here" without enumerating: stamp the folder alongside the
files you care about, and a new file inside it invalidates your cache for free.

Windows timestamp granularity is coarse enough that two writes inside one tick are indistinguishable.
In tests, don't rely on the clock advancing — set the timestamp explicitly with
`File.SetLastWriteTimeUtc(path, DateTime.UtcNow.AddSeconds(5))`.

## `File.ReadAllText[Async]` opens with `FileShare.Read` — readers block writers

`FileShare.Read` means *other readers may join*, not *this is a harmless read*. A concurrent **writer**
gets `IOException: The process cannot access the file … because it is being used by another process`.

The asymmetry matters whenever one component watches a file another component writes:

- The **reader** usually has a retry loop, because everyone expects the writer to hold the file.
- The **writer** usually has none, because nobody thinks of a reader as an obstacle.

This is a classic intermittent test failure: a test writes a fixture file that the code under test is
concurrently reading, and the *test's* write throws. The failure surfaces under CPU load (a full suite,
CI) and vanishes when the test is run alone, which makes it read like a product race when it is really
the harness lacking the defence the product already has. Fix it on the writing side:

```csharp
private static void WriteFile(string path, string contents)
{
    for (var attempt = 0; ; attempt++)
    {
        try { File.WriteAllText(path, contents); return; }
        catch (IOException ex) when (attempt < 20
                                     && ex is not (FileNotFoundException or DirectoryNotFoundException))
        {
            Thread.Sleep(10);
        }
    }
}
```

Excluding the not-found subclasses keeps a genuine bad-path bug failing fast instead of spinning for
the full retry budget. Note that `FileNotFoundException` and `DirectoryNotFoundException` both derive
from `IOException`, so a bare `catch (IOException)` swallows them.

Related timing trap in such tests: `Task.Delay(5)` is a *floor*, not a deadline, and the default
Windows timer granularity is ~15.6 ms unless something in the process has raised it. A test that
sequences events by "wait 5 ms, which is less than the code's 10 ms debounce" is not sequencing
anything — it wins by luck and by the read window being sub-millisecond. Give such margins an order of
magnitude, not a factor of two.

## `new Uri(@"C:\a#b\")` escapes the `#` — this one is fine

Worth knowing so you don't code around it: the `Uri` constructor recognises the DOS-path form and
percent-escapes `#` to `%23` rather than treating it as a fragment delimiter. `AbsoluteUri` comes back
as `file:///C:/a%20%231/` with an empty `Fragment`, and `LocalPath` round-trips. Folder names
containing `#` need no special handling when building a base URI.

## A drive root keeps its separator, so `root + '\'` never matches under it

`Path.TrimEndingDirectorySeparator(@"D:\")` returns `D:\` unchanged, and it has to: `D:` alone means the
current directory on drive D, not its root. So the common "is `path` inside `root`" idiom —
`path.StartsWith(root + Path.DirectorySeparatorChar)` after trimming both — builds the prefix `D:\\` for a
drive root and matches nothing below it. Measured 2026-09-27: an existing games root of `D:\` failed to
cover `D:\Persona 5 Royal`, so a planner that adds a game's parent when nothing covers it appended `D:\`
to the config once per game. The same shape hides in a "StartsWith, then require a separator next" check
(`D:\X` has `X` there) and in path-traversal guards built as `GetFullPath(base) + separator`, which also
break the moment a base arrives already ending in one.

Compare paths as a root plus a list of folder names instead: `Path.GetPathRoot(full.AsSpan())` for the
root (`D:\`, `\\server\share`), the rest split on both separators with empty entries dropped. Containment
is then "same root, and the folder's names are a prefix of the path's", compared case-insensitively. A
drive root is simply an empty name list, and `C:\GamesOther` can't match `C:\Games` because names compare
whole. The string overload of `GetPathRoot` is annotated nullable in .NET 10; the span overload is not.

To check a BCL behaviour like this one without creating a project, `dotnet fsi probe.fsx` runs an F#
script against the installed runtime in a few seconds.

## Expanding variables truncates a path at a NUL, before `GetFullPath` can reject it

On .NET 10 for Windows, `Path.GetFullPath` throws `ArgumentException` for an empty string, for a string
of only spaces (`The path is empty.`), and for any path holding a NUL (`Null character in path.`). A
tab-only string is not among them: it resolves to a name made of the tab under the current directory.
Measured 2026-09-28 on runtime 10.0.12, calling `[IO.Path]::GetFullPath` from PowerShell 7.6.

`Environment.ExpandEnvironmentVariables` drops everything from the first NUL on, whether or not the
string holds a variable — it passes the string to Win32's `ExpandEnvironmentStrings`, which reads it as
NUL-terminated. `C:\a<NUL>b\c` comes back as `C:\a`. A config reader that expands before parsing
therefore never shows `GetFullPath` a NUL: an entry carrying one, which a JSON config can through a
`\u0000` escape, resolves silently to the shorter path instead of failing. A `%VAR%` whose value is only
spaces does reach `GetFullPath` and throws, and trimming the raw entry does not catch it, because the
expansion runs after the trim.

Neither exception names the input or where it came from — "The path is empty" for an entry that reads
`%SPACES%`. Check a config value that is parsed as a path where the config is validated, after
expansion, with an error naming the key and the entry; left to the first reader that parses it, the
failure is a framework message through a stack trace.
