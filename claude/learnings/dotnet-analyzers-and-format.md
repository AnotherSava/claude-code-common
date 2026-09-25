# .NET analyzers and dotnet format: adopting a linter

Roslyn analyzers are the linter for a C# project: CA rules (code analysis) and IDE rules (code style) both run inside the compiler, so the build is the lint gate and no separate tool needs remembering. What follows was measured adopting them on a .NET 10 WPF/WinForms app (SDK 10.0.112), 2026-09-25.

## Turning it on

In a root `Directory.Build.props`, so every project gets it:

```xml
<AnalysisLevel>latest</AnalysisLevel>
<AnalysisMode>All</AnalysisMode>
<EnforceCodeStyleInBuild>true</EnforceCodeStyleInBuild>
<GenerateDocumentationFile>true</GenerateDocumentationFile>
<NoWarn>$(NoWarn);CS1591</NoWarn>
<PublishDocumentationFile>false</PublishDocumentationFile>
```

- `EnforceCodeStyleInBuild` makes IDE rules report in a build, but only at the severity `.editorconfig` gives them; `dotnet_analyzer_diagnostic.category-Style.severity = warning` raises them all.
- IDE0005 (unnecessary `using`) reports in a build **only** when `GenerateDocumentationFile` is on. That also enables doc-comment checks (CS1573, CS0419), so suppress CS1591 (missing comment) and stop the `.xml` shipping with `PublishDocumentationFile=false`.
- The gate is `-warnaserror`, on a `--no-incremental` build: MSBuild skips analysis for unchanged projects (measured in `dotnet-tray-app.md`, Testing).
- **Pin the SDK in `global.json`, and have CI install from it** (`actions/setup-dotnet` with `global-json-file: global.json`, not `dotnet-version: 10.x`). The analyzers ship with the compiler, so SDK feature bands disagree: 10.0.112 passed cleanly while CI's unpinned 10.0.401 flagged two `!` suppressions as unnecessary (IDE0370) and two `using`s (IDE0005), and the build went red on the first push after adoption with the local gate green. The newer band was only stricter — the fixed tree built cleanly on both — so the pin is about CI moving to a stricter band on its own, not about the two being irreconcilable.

## Measuring the baseline

Measure every rule, then set each preference option to the side the code already takes **before** counting. With default options the count is mostly the code disagreeing with defaults it never chose: 2,498 style warnings dropped to 607 once `var`, `csharp_prefer_braces`, file-scoped namespaces and expression-bodied methods matched the code. Then read the flagged sites per rule; a rule's reputation says nothing about its hits here. Library-oriented CA rules (CA1002, CA1062, CA2007 in a UI app) are the usual switch-offs for an application. CA1515 is the reverse, an application-only rule asking for public types to be made internal; it clashes with test projects whose public `[Theory]` methods take the app's types, and with tool assemblies calling into the app, which then need `InternalsVisibleTo`.

## dotnet format traps

- `--severity` takes `info`, `warn`, `error` or `hidden`. `--severity warning` prints usage and exits 1.
- `#pragma warning disable/restore` lines must be at **column 0**. The formatter places every directive except `#region` there, so an indented pragma raises IDE0055.
- `dotnet format style` runs editor-only analyzers the build never does. JSON002 ("probable JSON string") fired 122 times there and zero times in the build; switch it off, or `dotnet format style --severity warn` puts `/*lang=json,strict*/` in front of every JSON-looking string literal in the tests.
- Fixers produce shapes worth rewriting by hand: IDE0022 (expression body) moves a comment between `=>` and the expression; IDE0045 writes `x == 0 ? false : Call()` (use `x != 0 && Call()`); IDE0066 (switch expression) leaves a trailing comma on the last arm.

## Rules with non-obvious fixes

- **CA1031** (catch general exception): `catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)` satisfies it; a filter that does not test the type, such as `when (!ct.IsCancellationRequested)`, does not. At a deliberate boundary that logs, suppress with a reason on the pragma.
- **CA2020** (`(int)IntPtr` no longer throws on overflow): wrapping in `unchecked(...)` does not clear it; type the parameter `nint`.
- **CA2000** flags `TextWriter.Synchronized(new StreamWriter(...))`, because it cannot see the wrapper take ownership. A `lock` around the writer's uses is thread-safe without the wrapper.
- **CA2213** (undisposed field) fires on every WinForms control field, which the form disposes through `Controls`. One pragma pair around the control field block, with that reason, and fix the genuinely undisposed ones.
- **CA2216** on a type owning a native hook handle: move the handle into a `SafeHandle`. If Windows calls a delegate through that hook, have the handle reference the delegate too; an object awaiting finalization keeps what it references alive, so the callback cannot be collected before the finalizer unhooks.
- **CA1307**: xUnit's `Assert.Contains/StartsWith/EndsWith(string, string)` compare with the **current culture** (xunit.assert 2.9.3 docs), and CA1310 does not cover them. Pass `StringComparison.Ordinal` to them, which is what CA1307 asks for; switching CA1307 off on the grounds that CA1310 covers culture leaves these unchecked.

## Line endings

Set `end_of_line = lf` in `.editorconfig` and `* text=auto eol=lf` in the repo's `.gitattributes`. With `end_of_line` unset the formatter writes the platform newline into the trivia it rebuilds, so a Windows run inserts CRLF into LF files and a macOS run does not. With it set, the build still passes a CRLF file: IDE0055 does not check line endings. Only `dotnet format whitespace --verify-no-changes` reports it, as ENDOFLINE on every CRLF line, so the `-warnaserror` gate misses a file a Windows tool rewrote, and the `.gitattributes` rule normalising it on commit is what keeps the repo LF. See `git-line-endings.md` for normalising a working tree.
