# Non-ASCII arguments to native executables from Git Bash

**Send non-ASCII text to an HTTP API from Python, or give it to `curl` on stdin or in a file, never as a `curl`
argument from Git Bash on Windows.** Git Bash's `curl` receives its arguments in the Windows ANSI code page, so the
text is already wrong when `curl` encodes it, and the server answers success for whatever arrives.

## Which programs receive the wrong text

Bash hands the text over intact, and what a program receives depends on how it reads its command line. One that
reads it as wide characters gets every character. One that reads it through the ANSI entry point gets each
character converted to the machine's ANSI code page first. Git Bash's `curl` reads it through the ANSI entry
point: it is `/mingw64/bin/curl`, a MinGW build, and its `curl --version` output lists no `Unicode` among the
features, which curl's manual describes as "Unicode support on Windows".

Measured 2026-11-13 with the curl 7.87.0 that Git for Windows 2.39.1 ships, on a machine whose ANSI code page is
cp1251, by capturing each request on a local listener:

| Argument | What was sent |
|---|---|
| `--data-urlencode "x=a · b"` | `x=a+%B7+b` (UTF-8 would be `%C2%B7`) |
| `--data-urlencode "x=— € я"` | `x=%97+%88+%FF` |
| `--data-urlencode "x=é → ✓"` | `x=e+%3E+%3F`, the text `e > ?` |
| `-d "x=a · b"` | the single byte `0xB7` for the dot |
| `-H "X-Test: a · b"` | the same byte, in the header |

A character the code page holds becomes its one byte there. A character it lacks is replaced by a lookalike or a
question mark before `curl` runs, so no decoding on the server brings it back.

The same text, passed as an argument from the same shell, arrived intact at Windows' own `curl`
(`/c/Windows/System32/curl.exe`, 8.22.0, which lists `Unicode`), and at Python, Node and git.

## What the server stores

The server answers success whatever it was given, and what it keeps differs by server:

- UptimeRobot kept the escape as text. A monitor named with a `·` through `--data-urlencode` was stored with a
  literal `%B7` in the dot's place (2026-11-13).
- qBittorrent's `torrents/rename` stored `U+FFFD`: `Silo — Season 3` read back as `Silo � Season 3`, with HTTP 200
  (2026-10-04).

Read the value back after any write that carries non-ASCII text. Print it with `ascii()` or a hex dump, since the
console shows a mangled character and a correct one in ways that are easy to confuse.

## Ways around it

- Build the request in Python, with the script in a heredoc. A literal in the heredoc reaches Python as UTF-8,
  and `urllib.parse.urlencode` encodes it as UTF-8. The qBittorrent rename sent from Python stored the em dash
  correctly.
- Keep `curl` and give it the value on stdin or in a file, which it reads as bytes. With the text piped in from
  a `printf '%s' 'a · b'`, the argument `--data-urlencode 'x@-'` sent `x=a+%C2%B7+b`. Pipe it with `printf '%s'`,
  since `echo` adds a newline that `curl` encodes as `%0A`.
- Percent-encode the UTF-8 by hand and pass it with plain `-d`, which sends it unchanged: `-d 'x=a%20%C2%B7%20b'`.
  UptimeRobot stored the `·` correctly from a name sent this way.
