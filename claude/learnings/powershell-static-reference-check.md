# Checking a PowerShell script's references without running it

A script that dot-sources a library from another repo breaks when the library renames a function, a parameter or a type, and nothing reports it until the script runs. For a script that takes over the machine, such as a screenshot capture, that is after the pointer has moved. A commit gate can catch the rename statically: parse the script, load its library the way the script would, and resolve every name. Each of those steps has a trap, and every trap below was measured on PowerShell 7 on 2026-09-25. The worked example is the docs-relevance skill's `scripts/check-capture-scripts.ps1`.

## Load the library in a PowerShell instance of its own

Dot-sourcing the library into the checker's own session lets the checker's functions and variables mask or be overwritten by the library's. Load it into `[powershell]::Create()` instead:

- `AddScript($text)` runs in the instance's global scope unless `useLocalScope` is passed as `$true`, so the functions a dot-sourced file defines survive into later calls.
- The objects it returns are live, not serialized, so `ResolveParameter` and `GetMember` work on them from the checker.
- `$PSScriptRoot` resets on every `AddScript` call. To evaluate a dot-source target such as `(Join-Path $PSScriptRoot 'lib\x.ps1')`, set it in the same script text: `` "`$PSScriptRoot = '<dir>'`nWrite-Output <target text>" ``.
- Set `$ErrorActionPreference = 'Stop'` in the instance when the scripts being checked set it. Under the default `Continue`, a library whose top level catches its own error still leaves an error record, and `HadErrors` reports a load failure the real run never has.
- A hostless instance records a native command's stderr as an error record.

## A runspace does not isolate types

Types from `Add-Type`, and the assemblies behind them, belong to the process, not the runspace. Checking several scripts in one process lets them interfere: two scripts that each `Add-Type` a helper with the same name and different members collide (the second fails with "type name already exists" and its members look missing), and a type one script adds resolves while the next is checked. Check each script in a process of its own:

- `Start-Job -FilePath` runs the file as a script block, so `$PSScriptRoot` and `$PSCommandPath` are empty inside it. Have the job invoke the file instead: `Start-Job { param($File, $Target) & $File -Target $Target } -ArgumentList $PSCommandPath, $path`. Return a `[pscustomobject]` from the child; `Receive-Job` hands it back deserialized.
- Under `$ErrorActionPreference = 'Stop'`, `Receive-Job` turns an error the child raised into a terminating error in the parent, so one crashing child ends the run without naming the script. Pass `-ErrorAction SilentlyContinue -ErrorVariable jobErrors` and report the error as that script's result.

## Resolving each kind of name

- **Commands.** `CommandAst.GetCommandName()` gives the name, or `$null` for a dynamic one. Resolve it with `Get-Command -Name ([WildcardPattern]::Escape($name))`, since `?` and `*` are wildcards otherwise.
- **Aliases.** A library that renames a function often keeps the old name as an alias. Follow `ResolvedCommand` and check the parameters of the function it points at; `ResolvedCommand` is `$null` when the target no longer exists, and `.Definition` still names it.
- **Parameters.** `CommandInfo.ResolveParameter($name)` applies PowerShell's own prefix and alias matching and throws when nothing matches or a prefix is ambiguous. Leave cmdlets out: a dynamic parameter such as `Get-ChildItem -File` is missing from their parameter list and would be reported.
- **Types.** Evaluate the type literal inside the instance, with the script's `using` statements prepended to the same text: `using namespace` applies only to literals parsed alongside it, and `'Name' -as [type]` ignores it. `try { [Name] } catch { }` returns nothing for an unknown type; an unresolved literal sets `HadErrors` without throwing. An open generic resolves as ``[List`1]``.
- **Types the script defines.** A `class` or `enum` in the script never exists in the instance. Skip it wherever it appears inside a literal (`[Shot[]]`, `[List[Shot]]`), and resolve the literal's other parts one by one so a renamed library type beside it is still caught.
- **Types a library function loads.** An assembly loaded by `Add-Type -AssemblyName` inside a function body is not loaded until the function runs, and a static check never runs it. Require the script to load the assemblies whose types it names.
- **Empty files.** `Get-Content -Raw` returns `$null` for an empty or BOM-only file, and `[regex]::Matches($null, ...)` throws; `[IO.File]::ReadAllText` returns an empty string.

## What a static check cannot see

The properties and methods of the objects a library function returns, parameters passed by splatting, a mandatory parameter a call leaves out, and how positional arguments bind all resolve only at run time. List them in the checker's header, so its green result is not read as covering them.
