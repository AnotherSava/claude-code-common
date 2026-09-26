<#
  Checks that a project's Windows screenshot capture scripts can still reach what they use from this skill.

  The capture scripts borrow their machinery from this skill, so a fix here reaches every project that shoots
  screenshots. The cost is a dependency on paths and names this repo can rename, and nothing in the project
  reads them: its tests, build and CI never run a capture, so a stale name goes unreported until someone next
  re-shoots a figure. A missing dot-sourced file fails before the capture touches anything, but a renamed
  function fails at its call, which for Invoke-WindowShot comes after the capture has moved the pointer and
  opened the window it came to photograph.

  A project runs this from its local commit gate, from the repo root, and not from CI, because the paths resolve
  under the developer's ~/.claude, which no runner has:
    pwsh -NoProfile -NonInteractive -File ~/.claude/skills/docs-relevance/scripts/check-capture-scripts.ps1
  It checks docs/screenshots/capture unless another folder is passed as the first argument. It runs on Windows
  only, since the capture library it loads is Windows-only; elsewhere it exits 1 without checking anything, so
  a gate shared with macOS decides for itself what to do there.

  Everything is read out of the capture scripts rather than listed here, so a new reference is checked from the
  commit that adds it. Each .ps1 under the capture folder is checked on its own, and each problem line starts
  with its kind:
  - PARSE: the script does not parse. Its .claude/skills paths are still checked, nothing else in it is.
  - MISSING: a .claude/skills path written out whole anywhere in the script, comments included, or a file it
    dot-sources, does not exist.
  - UNREADABLE: a dot-source this check cannot turn into a file path, such as a relative path, one starting
    with ~, or one built from a variable the script assigns more than once or from other variables. The target
    expression is evaluated with $PSScriptRoot set to the script's folder. A dot-source of a variable the script
    assigns exactly once, as a guard that tests the path before loading it does, is evaluated through that
    assignment.
  - LOAD: a script it dot-sources, or one of its own Add-Type calls, fails when run.
  - UNKNOWN: a command it calls is not a function it defines, a function from a script it dot-sources, or a
    command PowerShell finds.
  - PARAM: a named parameter it passes to a PowerShell function binds to none of that function's parameters.
  - TYPE, MEMBER: a [Type] does not resolve, or a [Type]::Member is not a public static member.
  - CRASH: checking the script failed outright, with the error that stopped it.
  A script that does not parse, or has a dot-source that is MISSING, UNREADABLE or fails to LOAD, has none of its
  names checked, since the functions and types that dot-source would add cannot be told from real unknowns.

  Each capture script is checked in a pwsh process of its own, because a type Add-Type defines stays loaded for
  the life of the process and would otherwise carry over from one script to the next. Inside that process its
  dot-sourced scripts run in a PowerShell instance of their own, with $ErrorActionPreference set to Stop as the
  capture scripts set it, so their top-level code executes but cannot reach this script's variables or
  functions. Types resolve in that instance, with the capture script's using statements and its own Add-Type
  calls applied. So a capture script loads every assembly whose types it names with an Add-Type of its own, even
  one a skill function it calls loads today: function bodies are never run here, and a capture that relies on
  one breaks when the skill stops loading it. A class or enum the script defines is taken as it is, and the
  other types in a literal that names one, such as List in [List[Shot]], are resolved one by one. A script with
  an Add-Type whose arguments are not constant gets no type checks, and the last line says so.

  Not checked: a script a skill function runs when called, such as window-shot.ps1, and the keys of the
  hashtable Invoke-WindowShot passes to it; the properties and methods of what a skill function returns, such
  as .Right on Get-PrimaryWorkArea's rectangle; variables a skill script sets; type names written as strings, as
  New-Object takes them; parameters passed to cmdlets or by splatting, a mandatory parameter a call leaves out,
  and how positional arguments bind; argument values, such as one a ValidateSet no longer lists; arguments
  passed on a dot-source line; and capture scripts in other languages.
#>
using namespace System.Management.Automation.Language

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Folder = 'docs/screenshots/capture',
    # Set only when this script runs itself for one capture script; see the comment block. $Root carries the
    # caller's repo root, which problem lines are written relative to.
    [string]$Capture,
    [string]$Root
)

$ErrorActionPreference = 'Stop'
$root = if ($Capture) { $Root } else { (Get-Location).Path }
# A path under .claude/skills in either slash style. It ends on a word character, so a full stop after one in a
# comment is not part of it.
$skillPath = '\.claude[\\/]skills[\\/][\w.\-\\/]*\w'

# Runs $Script in $Shell's global scope, so the functions a dot-sourced script defines outlive the call, and
# returns its output with the first error, if any.
function Invoke-Isolated([powershell]$Shell, [string]$Script) {
    $Shell.Commands.Clear()
    $Shell.Streams.ClearStreams()
    try {
        $output = @($Shell.AddScript($Script).Invoke())
        $failure = if ($Shell.HadErrors) { $Shell.Streams.Error[0].ToString() }
    }
    catch {
        $output = @()
        $failure = ($_.Exception.InnerException ?? $_.Exception).Message
    }
    return [pscustomobject]@{ Output = $output; Failure = $failure }
}

function Quote([string]$Text) { "'$($Text.Replace("'", "''"))'" }

function Get-RelativePath([string]$Path) { [IO.Path]::GetRelativePath($root, $Path).Replace('\', '/') }

# The type names a type literal is built from, each one resolvable on its own: [List[Shot]] is List`1 and Shot,
# and [Shot[]] is Shot.
function Get-TypeNames([ITypeName]$TypeName) {
    if ($TypeName -is [ArrayTypeName]) { return Get-TypeNames $TypeName.ElementType }
    if ($TypeName -is [GenericTypeName]) { return @("$($TypeName.TypeName.FullName)``$($TypeName.GenericArguments.Count)") + @($TypeName.GenericArguments | ForEach-Object { Get-TypeNames $_ }) }
    return $TypeName.FullName
}

if ($Capture) {
    $problems = [Collections.Generic.List[string]]::new()
    $notCovered = [Collections.Generic.List[string]]::new()
    $missing = [Collections.Generic.List[object]]::new()
    $checked = @{ Commands = 0; Types = 0; Members = 0 }
    $rel = Get-RelativePath $Capture
    $tokens = $null
    $errors = $null
    $ast = [Parser]::ParseFile($Capture, [ref]$tokens, [ref]$errors)
    if ($errors) {
        $problems.Add("PARSE      ${rel}:$($errors[0].Extent.StartLineNumber): $($errors[0].Message)")
        return [pscustomobject]@{ Problems = $problems; NotCovered = $notCovered; Missing = $missing; Checked = $checked }
    }
    $nodes = $ast.FindAll({ $true }, $true)
    $localFunctions = @($nodes | Where-Object { $_ -is [FunctionDefinitionAst] } | ForEach-Object Name)
    $localTypes = @($nodes | Where-Object { $_ -is [TypeDefinitionAst] } | ForEach-Object Name)
    $usings = ($ast.UsingStatements | ForEach-Object { $_.Extent.Text }) -join "`n"

    $shell = [powershell]::Create()
    $null = Invoke-Isolated $shell "`$ErrorActionPreference = 'Stop'"
    $loaded = $true
    foreach ($dot in $nodes | Where-Object { $_ -is [CommandAst] -and $_.InvocationOperator -eq 'Dot' }) {
        $where = "${rel}:$($dot.Extent.StartLineNumber)"
        $element = $dot.CommandElements[0]
        $target = $element.Extent.Text
        $expression = $target
        if ($element -is [VariableExpressionAst]) {
            $assignments = @($nodes | Where-Object { $_ -is [AssignmentStatementAst] -and $_.Left -is [VariableExpressionAst] -and $_.Left.VariablePath.UserPath -eq $element.VariablePath.UserPath })
            # The right-hand side is a statement, so it is wrapped to be evaluated as one argument.
            if ($assignments.Count -eq 1 -and $assignments[0].Operator -eq 'Equals') { $expression = "($($assignments[0].Right.Extent.Text))" }
        }
        $evaluated = Invoke-Isolated $shell "`$PSScriptRoot = $(Quote (Split-Path -Parent $Capture))`nWrite-Output $expression"
        $path = if (-not $evaluated.Failure -and $evaluated.Output.Count -eq 1) { [string]$evaluated.Output[0] }
        if (-not $path -or -not [IO.Path]::IsPathRooted($path)) {
            $problems.Add("UNREADABLE $where dot-sources $target, which this check cannot turn into a file path")
            $loaded = $false
            continue
        }
        $path = [IO.Path]::GetFullPath($path)
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            $missing.Add([pscustomobject]@{ Path = $path; Line = "MISSING    $path`n           dot-sourced at $where" })
            $loaded = $false
            continue
        }
        $load = Invoke-Isolated $shell ". $(Quote $path)"
        if ($load.Failure) {
            $problems.Add("LOAD       $path, dot-sourced at ${where}: $($load.Failure)")
            $loaded = $false
        }
    }
    # Names wait until every dot-source loads; the comment block says why.
    if ($loaded) {
        $typesChecked = $true
        foreach ($addType in $nodes | Where-Object { $_ -is [CommandAst] -and $_.GetCommandName() -eq 'Add-Type' }) {
            if ($addType.Find({ param($node) $node -is [VariableExpressionAst] -or $node -is [ExpandableStringExpressionAst] -or $node -is [SubExpressionAst] }, $true)) {
                $notCovered.Add("types in $rel (the Add-Type at line $($addType.Extent.StartLineNumber) has arguments that are not constant)")
                $typesChecked = $false
                continue
            }
            $added = Invoke-Isolated $shell $addType.Extent.Text
            if ($added.Failure) { $problems.Add("LOAD       the Add-Type at ${rel}:$($addType.Extent.StartLineNumber) fails: $($added.Failure)") }
        }

        foreach ($call in $nodes | Where-Object { $_ -is [CommandAst] -and $_.InvocationOperator -ne 'Dot' }) {
            $name = $call.GetCommandName()
            if (-not $name -or $localFunctions -contains $name) { continue }
            $checked.Commands++
            $where = "${rel}:$($call.Extent.StartLineNumber)"
            $command = (Invoke-Isolated $shell "Get-Command -Name $(Quote ([WildcardPattern]::Escape($name))) -ErrorAction SilentlyContinue").Output | Select-Object -First 1
            if (-not $command) {
                $problems.Add("UNKNOWN    $where calls $name, which is not a function it defines, a function from a script it dot-sources, or a command PowerShell finds")
                continue
            }
            if ($command.CommandType -eq 'Alias') {
                if (-not $command.ResolvedCommand) {
                    $problems.Add("UNKNOWN    $where calls $name, an alias of $($command.Definition), which does not exist")
                    continue
                }
                $command = $command.ResolvedCommand
            }
            # A cmdlet can take dynamic parameters its parameter list does not show, such as Get-ChildItem -File.
            if ($command.CommandType -notin 'Function', 'Filter') { continue }
            foreach ($parameter in $call.CommandElements | Where-Object { $_ -is [CommandParameterAst] }) {
                try { $null = $command.ResolveParameter($parameter.ParameterName) }
                catch { $problems.Add("PARAM      $where passes -$($parameter.ParameterName) to $name, which binds it to none of its parameters") }
            }
        }

        if ($typesChecked) {
            $resolved = @{}
            foreach ($type in $nodes | Where-Object { $_ -is [TypeExpressionAst] -or $_ -is [TypeConstraintAst] }) {
                $parts = @(Get-TypeNames $type.TypeName)
                $names = if ($parts | Where-Object { $localTypes -contains $_ }) { @($parts | Where-Object { $localTypes -notcontains $_ }) } else { @($type.TypeName.FullName) }
                if (-not $names) { continue }
                $checked.Types++
                foreach ($name in $names) {
                    if (-not $resolved.ContainsKey($name)) { $resolved[$name] = (Invoke-Isolated $shell "$usings`ntry { [$name] } catch { }").Output | Select-Object -First 1 }
                    if (-not $resolved[$name]) { $problems.Add("TYPE       ${rel}:$($type.Extent.StartLineNumber) uses [$name], which does not resolve") }
                }
            }
            foreach ($member in $nodes | Where-Object { $_ -is [MemberExpressionAst] -and $_.Static -and $_.Expression -is [TypeExpressionAst] -and $_.Member -is [StringConstantExpressionAst] }) {
                $type = $resolved[$member.Expression.TypeName.FullName]
                # PowerShell adds ::new to every type; a local or unresolved type has no members to look up here.
                if (-not $type -or $member.Member.Value -eq 'new') { continue }
                $checked.Members++
                if (-not $type.GetMember($member.Member.Value, [Reflection.BindingFlags]'Public, Static, IgnoreCase, FlattenHierarchy')) {
                    $problems.Add("MEMBER     ${rel}:$($member.Extent.StartLineNumber) uses [$($type.FullName)]::$($member.Member.Value), which is not a public static member")
                }
            }
        }
    }
    return [pscustomobject]@{ Problems = $problems; NotCovered = $notCovered; Missing = $missing; Checked = $checked }
}

if (-not $IsWindows) {
    Write-Host "check-capture-scripts: checked nothing. The capture library it loads is Windows-only, so run it on Windows."
    exit 1
}
if (-not (Test-Path -LiteralPath $Folder -PathType Container)) {
    Write-Host "check-capture-scripts: $Folder is not a folder under $root. Run this from the repo root, or pass the capture folder as the first argument."
    exit 1
}
$captureFolder = (Resolve-Path -LiteralPath $Folder).Path
$folderName = Get-RelativePath $captureFolder
$problems = [Collections.Generic.List[string]]::new()
$notCovered = [Collections.Generic.List[string]]::new()
$missing = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
$checked = @{ Paths = 0; Commands = 0; Types = 0; Members = 0 }
$scripts = @(Get-ChildItem $captureFolder -Recurse -File -Filter *.ps1 | Sort-Object FullName)

foreach ($src in $scripts) {
    foreach ($match in [regex]::Matches([IO.File]::ReadAllText($src.FullName), $skillPath)) {
        $checked.Paths++
        $full = [IO.Path]::GetFullPath((Join-Path $HOME $match.Value))
        if (-not (Test-Path -LiteralPath $full) -and $missing.Add($full)) { $problems.Add("MISSING    $full`n           named in $(Get-RelativePath $src.FullName): $($match.Value)") }
    }
}

foreach ($src in $scripts) {
    # A job runs in a pwsh process of its own. It invokes the file, since -FilePath would run it as a script
    # block, where $PSScriptRoot is empty.
    $result = Start-Job { param($Check, $Capture, $Root) & $Check -Capture $Capture -Root $Root } -ArgumentList $PSCommandPath, $src.FullName, $root | Receive-Job -Wait -AutoRemoveJob -ErrorAction SilentlyContinue -ErrorVariable jobErrors
    if ($jobErrors -or -not $result) {
        $problems.Add("CRASH      checking $(Get-RelativePath $src.FullName) failed: $(if ($jobErrors) { $jobErrors[0] } else { 'it returned nothing' })")
        continue
    }
    $result.Problems | ForEach-Object { $problems.Add($_) }
    $result.NotCovered | ForEach-Object { $notCovered.Add($_) }
    $result.Missing | Where-Object { $missing.Add($_.Path) } | ForEach-Object { $problems.Add($_.Line) }
    foreach ($key in $result.Checked.Keys) { $checked[$key] += $result.Checked[$key] }
}

$note = if ($notCovered.Count -gt 0) { " NOT COVERED: $($notCovered -join '; ')." }
# Matching nothing fails: the capture scripts could stop naming the skill in a shape this check reads, and
# checking nothing would print the same success as checking everything.
if ($checked.Paths -eq 0 -and $problems.Count -eq 0) {
    Write-Host "check-capture-scripts: no capture script under $folderName names a .claude/skills path. Update this check if they reach the skill some other way, or remove it from the project's commit gate if they no longer use one.$note"
    exit 1
}
if ($problems.Count -gt 0) {
    $problems | ForEach-Object { Write-Host $_ }
    Write-Host "check-capture-scripts: $($problems.Count) problem(s). Where the dotfiles repo moved or renamed a skill script or a name in one, update the capture scripts to match; an UNREADABLE line means this check needs extending instead.$note"
    exit 1
}
Write-Host "check-capture-scripts: $($checked.Paths) skill path reference(s), $($checked.Commands) command call(s), $($checked.Types) type reference(s) and $($checked.Members) static member reference(s) resolve.$note"
