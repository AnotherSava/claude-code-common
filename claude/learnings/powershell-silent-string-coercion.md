# Two ways PowerShell folds an array into one string without saying so

Both turned up in the same script, one after the other, writing a multi-line block into a file. The
symptom is identical and silent each time: the file gets one long line where it should get several,
no error, exit 0. Measured 2026-09-22.

## A single-element array unwraps on its way out of `if`

```powershell
$prefix = if ($lines.Count -gt 0) { , '' } else { @() }
Add-Content -Path $file -Value ($prefix + $block)
```

The `, ''` is the unary comma that builds a one-element array, and it is correct where it stands.
PowerShell unwraps a single-element array as it leaves the `if`, so `$prefix` arrives as the *string*
`''` — and `'' + $block` is then string concatenation, not array concatenation. `Add-Content` is
handed one string with every line joined by `$OFS` (a space) and writes exactly that.

The tell is a file whose content is right but whose newlines are all spaces. Nothing warns, because
both operands are legal on both sides of `+`.

Build the list by appending to an array that is already one:

```powershell
$out = @()
if ($lines.Count -gt 0 -and $lines[-1].Trim() -ne '') { $out += '' }
$out += $block
Add-Content -Path $file -Value $out
```

`$out += …` keeps the array an array whatever the right-hand side is, and `Add-Content` writes one
line per element. The same trap reaches any cmdlet with an array-valued parameter, not just this one.

## `-f` binds tighter than `+`, so only the last piece is formatted

```powershell
throw ("could not replace $name: {0} - re-run this from an " +
       "Administrator PowerShell." -f $_.Exception.Message)
```

This reads as "format the whole message", and is parsed as `"could not…{0}…" + ("Administrator…" -f
$msg)`. The format operator applies to the second literal, which has no placeholder, so it returns
that string untouched — and the `{0}` in the first half is printed verbatim to the user. The error
message then carries a literal `{0}` where the reason should be.

Interpolate instead of formatting a concatenation:

```powershell
$denied = $_.Exception.Message
throw "could not replace $name: $denied - re-run this from an Administrator PowerShell."
```

Or wrap the whole concatenation in its own parentheses before `-f`. Interpolation is the one that
cannot be got wrong by adding another line to the message later.
