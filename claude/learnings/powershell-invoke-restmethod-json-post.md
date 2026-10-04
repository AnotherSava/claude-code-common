# Posting JSON from Windows PowerShell 5.1 with Invoke-RestMethod

Three things go wrong with a one-line `Invoke-RestMethod` POST handed to a user to paste, and all three fail quietly. Measured 2026-10-04 on Windows PowerShell 5.1.26100 against a loopback server.

## A string body without a charset is sent as Latin-1

```powershell
Invoke-RestMethod -Method Post -Uri $url -ContentType 'application/json' -Body '{"path":"D:/p/проект"}'
```

When the `Content-Type` names no charset, 5.1 encodes a string `-Body` with its default encoding, ISO-8859-1, and replaces any character outside it. A Cyrillic path reaches the server as `??`. An accented Latin one arrives as bytes that are not valid UTF-8, which a strict JSON parser rejects with a 400. The `??` case is worse because the server sees a well-formed request naming the wrong thing and may answer 200.

Name the charset, which makes the cmdlet encode as UTF-8:

```powershell
-ContentType 'application/json; charset=utf-8'
```

PowerShell 7.4 and later default to UTF-8. A command handed to a Windows user cannot assume that is the shell they open.

## An error reply's body is hidden unless you catch it

On a 4xx or 5xx, 5.1 throws `The remote server returned an error: (409) Conflict.` and prints none of the body. A server that explains its refusal in the body is then reduced to a status code. The body is on the error record:

```powershell
try { Invoke-RestMethod ... } catch { if ($_.ErrorDetails.Message) { $_.ErrorDetails.Message } else { $_.Exception.Message } }
```

`ErrorDetails` is filled only when an HTTP response came back. A refused connection, a DNS failure or a timeout leaves it empty, so `catch { $_.ErrorDetails.Message }` on its own prints nothing at all when the server is not running. The `else` branch is what reports that.

## `-ErrorAction Stop` ends a pasted line, which makes it PowerShell 5.1's `&&`

Windows PowerShell 5.1 has no `&&`, so one step depending on the step before has to be built differently. A cmdlet run with `-ErrorAction Stop` raises a terminating error, and that error abandons the rest of a `;`-joined line typed at the prompt:

```powershell
Move-Item "C:/missing" "C:/x" -ErrorAction Stop; Write-Output "SECOND RAN"
```

That prints the `Move-Item` error and never `SECOND RAN`. Without `-ErrorAction Stop` the error is non-terminating and the next statement runs anyway. That matters wherever a later command assumes the earlier one did its job, such as a call reporting a folder move that failed.
