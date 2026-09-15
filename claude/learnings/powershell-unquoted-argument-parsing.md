# PowerShell eats unquoted argument text — and a function eats more than a native command does

A shell wrapper that forwards user prose to a program (`memo <text>`, `note <text>`, `todo <text>`) is
documented everywhere as "no quotes needed". On PowerShell that is false for three characters, and two
of the three fail **silently**: the command exits 0 and the program receives text nobody typed.

Measured 2026-09-15 on Windows 11, pwsh 7.6.6, console codepage 866, against
`function t { python -c "import sys; print(sys.argv[1:])" @args }` — the exact shape of a forwarding
wrapper. Compared against the bash equivalent, `f() { python -c '...' "$@"; }`.

## The function/native split is the part nobody expects

The same comma behaves differently depending on what is being called:

```powershell
# native command, invoked directly — the comma is literal text
pwsh -NoProfile -Command "python -c '...' alpha two, delete me"
['alpha', 'two,', 'delete', 'me']

# through a FUNCTION forwarding @args — the comma is the array operator and is consumed
function t { python -c '...' @args }
t alpha two, delete me
['alpha', 'two', 'delete', 'me']
```

PowerShell parses `two, delete` in argument mode as an array literal, so `$args` arrives as
`alpha`, `@('two','delete')`, `me` — three elements, the middle one nested. Splatting flattens it and
the comma is gone. Proven directly:

```powershell
function u { $args | ForEach-Object { Write-Output "[$_]" } }
u alpha two, delete me
[alpha]
[two delete]        # <- one element holding two, joined by the stringifier
[me]
```

So testing a wrapper by calling the target program directly will not reproduce the bug. The function
is the thing that has to be called.

## What survives and what does not

| In the typed text | Through a pwsh function | Through bash | Loud? |
|---|---|---|---|
| `a, b, c` | `a b c` — commas gone | `a,` `b,` `c` | **silent** |
| backtick + `n` | a literal newline | two characters, kept | **silent** |
| `$HOME` | expanded to the path | expanded to the path | silent, **both shells** |
| `$undefined` | token disappears | token disappears | silent, **both shells** |
| `@` | ParserError: unrecognized token | kept | loud |
| `'` (apostrophe) | ParserError: missing terminator | opens a quote | loud |
| `(`, `)` | tries to run the inner word as a command | kept | loud |
| `{`, `}` | ScriptBlock error | kept | loud |
| `—` em-dash, `[x]`, `note:`, `-v`, `--verbose` | kept | kept | — |

The em-dash surviving is worth recording separately: it goes through pwsh argument passing and into
Python's `sys.argv` intact under codepage 866, so a mangled em-dash downstream is not this layer's
fault. See `python-windows-console-encoding.md` for the layer that does mangle it.

## A wrapper cannot prevent this, but it can refuse

The parse happens before the function body runs, so no amount of quoting *inside* the wrapper helps.
Detection is available though, and it is exact rather than heuristic: when PowerShell folds `a, b, c`
into an array, that array reaches `$args` as a single **non-string** element. Nothing else produces
one.

```powershell
if ($args | Where-Object { $_ -isnot [string] }) {
    Write-Error "Quote the text — an unquoted comma is PowerShell's array operator and is dropped."
    return
}
```

That turns silent corruption into a message at the moment of the mistake, which is the only moment the
typed text still exists. The backtick has no such tell — it is indistinguishable from the escape the
user meant — so it stays a documentation matter.

## Related

- `powershell-docker-inline-quoting.md` — the same family, one layer up: `$` interpolation and quote
  nesting inside *quoted* strings passed through `docker run … bash -c`.
- `unicode-escapes-in-tool-input.md` — the collapse-whitespace mistake on the receiving side, where
  joining argv with `" ".join()` and then `.split()`ing it rewrites a quoted shell fragment.
