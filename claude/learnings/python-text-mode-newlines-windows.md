# Python's text-mode write turns an LF file into CRLF on Windows

An in-place edit through `Path.read_text()` and `Path.write_text()` rewrites every line ending of the file on
Windows. Reading in text mode folds `\r\n` and `\n` to `\n`, and writing in text mode translates each `\n` to
`os.linesep`, which is `\r\n` there. So a script that changes one line of an LF file hands back a file whose every
line changed, while the content diff it intended looks right.

Pass `newline="\n"` on the write, or work in bytes:

```python
p.write_text(text, encoding="utf-8", newline="\n")   # Python 3.10+
p.write_bytes(text.encode("utf-8"))
open(p, "w", encoding="utf-8", newline="\n")         # any version
```

Measured on Windows, Python 3.13.5: a file holding `b"a\nb\n"` read and written back unchanged with
`write_text(..., encoding="utf-8")` became `b"a\r\nb\r\n"`; the same round trip with `newline="\n"` stayed
`b"a\nb\n"`. macOS and Linux write `\n` either way, so the same script is correct there and wrong here. One
change set on 2026-09-25 converted 14 files this way.

## How it shows up

Git hides most of it. With `core.autocrlf=input`, `git diff` and `git diff --stat` show only the intended lines,
since git normalises on the way in, and the only sign is a warning per file on every git command:
`warning: in the working copy of '<file>', CRLF will be replaced by LF the next time Git touches it`. `file <path>`
reports `with CRLF line terminators`. A `grep -c $'\r$'` from Git Bash can report 0 on such a file, so check with
`file` rather than grep.

The working tree then differs from what will be committed, and a file this session never meant to touch can be swept
up: a cleanup loop over `git diff --name-only` that strips `\r` also rewrites any other dirty file in the tree.
