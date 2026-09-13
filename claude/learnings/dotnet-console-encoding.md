# A .NET console app silently drops non-ASCII on a Windows console

A .NET CLI that prints arbitrary text — achievement names, filenames, API data — loses every
character the console's codepage cannot map, and says nothing. There is no exception and no non-zero
exit; the characters are replaced with `?` and the run reports success. That is the opposite failure
mode from Python, which raises `UnicodeEncodeError` on the same machine (see
`python-windows-console-encoding.md`) — and the quiet one is worse, because a redirected run produces
a file that looks complete.

Measured on a Russian-locale Windows 11 box, 2026-09-11:

```
$ powershell -NoProfile -Command "[Console]::OutputEncoding.WebName; [Console]::Out.Write('RU=Тест JP=こんにちは')"
cp866
RU=Тест JP=?????
```

Two things worth noting in that output. The Japanese is gone, permanently, with no diagnostic. And
the codepage is **cp866** — the *OEM* console codepage — not the cp1251 that the same machine's
*ANSI* codepage would give. Python's stdout follows the ANSI/locale codepage, `System.Console`
follows the console's OEM one, so the two languages fail on different character sets on one machine
and a fix verified in one says nothing about the other.

## Fix at the entry point

```csharp
static int Main(string[] args)
{
    Console.OutputEncoding = Encoding.UTF8;
    ...
}
```

One assignment, in `Main`, before anything prints. Verified with the same command:

```
$ powershell -NoProfile -Command "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; [Console]::Out.Write('RU=Тест JP=こんにちは')"
RU=Тест JP=こんにちは
```

`chcp 65001` in the shell fixes it too, but only for whoever remembers — it does not travel with the
tool.

## Redirecting from PowerShell 5.1 re-encodes the file

Even with the process emitting correct UTF-8, `>` in Windows PowerShell 5.1 writes **UTF-16LE with a
BOM**:

```
$ powershell -NoProfile -Command "'Тест' > enc-test.txt" && xxd enc-test.txt
00000000: fffe 2204 3504 4104 4204 0d00 0a00       ..".5.A.B.....
```

That breaks anything downstream that assumes UTF-8 — `diff`, `grep`, a CI artifact comparison, a
paste into a web form. Bash redirection (`>` from Git Bash) passes the bytes through untouched, and
PowerShell 7 defaults to UTF-8, so the trap is specific to the 5.1 that ships with Windows.

For a tool whose output is *meant* to be saved and diffed, the durable answer is an explicit output
option rather than a note in the docs:

```csharp
File.WriteAllText(outPath, text, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
```

No BOM, because a BOM shows up as a spurious first-line difference in a diff.

## Worth catching before shipping

ASCII fixtures never reach it, and unit tests assert on returned strings rather than on what
`Console.Write` put on the screen. Run the real command once against real non-ASCII data on Windows
and look at the output — that is the whole test, and it takes one run.
