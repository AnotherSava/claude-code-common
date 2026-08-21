# Reading and writing the clipboard from a shell

Every claim below was measured on Windows 11 / Git Bash (MSYS2), by writing a known byte sequence to
the clipboard and reading it back through `od -c`. The headline: Git Bash's `/dev/clipboard` is
byte-exact in both directions, and PowerShell's `Get-Clipboard` silently corrupts data on its way
through a pipe.

## The reader, per OS

| OS | Read | Write |
|---|---|---|
| Windows (Git Bash / MSYS2) | `cat /dev/clipboard` | `… > /dev/clipboard` |
| macOS | `pbpaste` | `… \| pbcopy` |
| Linux (Wayland) | `wl-paste -n` | `wl-copy` |
| Linux (X11) | `xclip -selection clipboard -o` | `xclip -selection clipboard` |

The `/dev/clipboard` device is an MSYS/Cygwin invention — it does not exist on macOS or Linux, and a
Windows one-liner copied to the Mac fails with `cat: /dev/clipboard: No such file or directory`.

## `/dev/clipboard` is byte-exact, in both directions

No line-ending translation happens on either read or write, and the encoding is UTF-8:

| Written to the clipboard | Read back via `cat /dev/clipboard` |
|---|---|
| `a` CR LF `b` (set by PowerShell) | `a \r \n b` — 4 bytes, CR preserved |
| `a` LF `b` (written by bash) | `a \n b` — 3 bytes, no CRLF conversion |
| `x` LF | `x \n` — 2 bytes, trailing newline preserved |
| `é` (U+00E9, set by PowerShell) | `303 251` — correct UTF-8 |

So it neither adds nor removes anything. Whatever the clipboard holds is what you get.

## Never pipe PowerShell's `Get-Clipboard`

Reading the clipboard through PowerShell from bash corrupts the value twice over:

```bash
powershell.exe -NoProfile -Command "Get-Clipboard -Raw" | …   # WRONG
```

- PowerShell's pipeline appends its own CRLF, so the value comes out two bytes longer than what was
  copied — even with `-Raw`.
- Its stdout goes through the **console output codepage**, which transliterates non-ASCII: a clipboard
  holding `éz` arrives as `ez`. The character is not escaped or mangled, it is silently replaced, so
  nothing downstream can detect the loss.

Using `[Console]::Out.Write((Get-Clipboard -Raw))` fixes the trailing CRLF but not the codepage
transliteration. There is no reason to reach for PowerShell here at all — `/dev/clipboard` is exact.

## `$( )` strips a trailing `\n` but not a trailing `\r`

Command substitution strips trailing *newlines* only. Anything copied out of a Windows application
arrives CRLF-terminated, so the naive idiom leaves an invisible carriage return on the end of the
value:

```bash
V=$(cat /dev/clipboard)            # "secret\r"  ← trailing CR survives
V=$(cat /dev/clipboard | tr -d '\r')  # "secret"  ← correct
```

This is the classic silent-corruption bug for anything downstream that compares strings or sends the
value over the wire. The `tr -d '\r'` also normalizes inner CRLF to LF, which is what a multi-line
value (a PEM key, a JSON blob) generally wants.

The mirror-image trap on the way out: most CLIs terminate their output with a newline, so a value
piped straight to the clipboard arrives with one attached — and pasting that into a single-line web
form submits the form. Wrap it, which strips the trailing newline while leaving inner ones intact:

```bash
printf '%s' "$(some-command --plain)" > /dev/clipboard
```

## Saving and restoring the clipboard around a test

Clobbering the user's clipboard is rude, and the obvious save idiom loses trailing newlines because
`$( )` strips them. Guard with a sentinel character, and restore from a shell variable rather than a
temp file — the clipboard may itself hold a secret, which has no business being written to disk:

```bash
SAVED=$(cat /dev/clipboard; printf X); SAVED=${SAVED%X}
trap 'printf "%s" "$SAVED" > /dev/clipboard' EXIT
# … clobber the clipboard freely …
```

Put the restore in an `EXIT` trap, not at the end of the script: any early `exit` on a failed
assertion would otherwise leave the user's clipboard destroyed.

## The clipboard is volatile shared state

It is a single global slot shared by every process on the machine. Between two consecutive tool calls
it can change under you — another Claude session, a clipboard manager, or the user copying something
while reading your last message. Observed live: a clipboard restored to its original 23 bytes at the
end of one command held a different 15-byte value by the start of the next.

Consequences for any script: read it in the same command that consumes it, never capture it in one
step and use it in a later one, and if you need to know whether the content is what you expect,
compare rather than print — `cmp -s <(cat /dev/clipboard) <(printf 'expected')` answers the question
without ever putting the value on screen.

## Related

- The `/doppler` skill's "Store a value from the clipboard" section — the secrets application of all
  of the above, where the point is that the value reaches the store without passing through a command
  line or the transcript.
- `git-line-endings.md` — CRLF handling on the git side of the same machine.
