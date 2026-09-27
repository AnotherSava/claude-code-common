# Writing a literal `\uXXXX` escape into a file

Some source files spell an invisible character as an escape on purpose, so a reader can see it:

```ts
const SHOW_GAP = "\u2003\u2003"; // two em spaces — invisible if written literally
```

Editing such a line the normal way does not work, because **a `\uXXXX` sequence typed into a tool argument reaches the tool as the character itself**, not as the six-character text. Both halves of the job fail:

## 1. Edit can't match the line

`old_string: 'const SHOW_GAP = "\u2003\u2003";'` arrives as `const SHOW_GAP = "<em><em>";` and finds nothing — the file holds `\`, `u`, `2`, `0`, `0`, `3`. Doubling the backslash (`\\u2003`) did not match either; the tool reports that it retries with the escapes and the characters swapped, and neither form hit. Practical rule: **don't try to edit these lines with Edit — do it from a script.**

## 2. A script writes the character, not the escape

Same conversion, one layer earlier. In a Bash heredoc, `\\u2003` inside a Python string arrives as `\u2003` and Python's own string parsing then decodes it, so the file gets a real em space. A raw string (`r'...'`) doesn't rescue anything the harness already converted.

**Fix — never type the sequence. Build the backslash from its code point:**

```python
esc = lambda cp: chr(92) + "u%04X" % cp          # 92 = backslash

template = 'const PART_GAP = "@EM@";'            # placeholder, not the escape
src = template.replace("@EM@", esc(0x2003))
```

Write the whole block with `@NAME@` placeholders and substitute afterwards; nothing in the tool argument then looks like an escape.

## Verifying is its own trap

`repr()` distinguishes the two, but by exactly one backslash — `'"\\u2003"'` is the escape text, `'"\u2003"'` is the character — and that is easy to misread when it comes back in a tool result. Print code points instead:

```python
print([hex(ord(c)) for c in line if ord(c) > 126 or c == chr(92)])
# ['0x5c']    → a backslash is present: the file holds the escape text
# ['0x2003']  → no backslash: the file holds the real character
```

This is ASCII-safe as well, which matters on Windows: printing the character itself raises `UnicodeEncodeError` from a cp1251 stdout (see `claude-code-integration.md`).

## The one you will actually hit: `settings.json`

Claude Code serialises its own settings file with `"` written as `\u0022` inside hook command
strings:

```json
"command": "python -S \u0022$HOME/.claude/hooks/doppler-guard.py\u0022"
```

Every hook command is therefore an un-editable line by the rule above — `old_string` containing
`\u0022` arrives as a plain `"` and matches nothing. Two further traps compound it:

- **Edit strips trailing whitespace from `new_string`.** A replacement meant to end in a space
  silently loses it. Replacing `"command": "python` with `"command": "python -S ` yields
  `python -S\u0022$HOME/…` — no separator — and the shell hands Python the single argument
  `-S/Users/…`, which dies with `Unknown option: -/`.
- **A broken command string can lock you out of your own tools.** `doppler-guard.py` runs as a
  blocking `PreToolUse` hook matched on `^(Bash|Write|Edit)$`. Break its command and all three
  mutation tools start failing on the hook error — there is no way to repair the file from inside
  the session, and the user has to run a shell command to undo it.

**Procedure — never edit the live file in place:**

```bash
cp claude/settings.json /tmp/candidate.json
sed -i '' 's|"python |"python -S |g' /tmp/candidate.json   # sed sees real bytes; no escape games
python3 -c 'import json; json.load(open("/tmp/candidate.json"))'   # 1. still valid JSON?
# 2. execute every command string and check none report "Unknown option" / "can't open file"
cp /tmp/candidate.json claude/settings.json                # only now touch the live file
```

Use a stream editor, not Edit, for these files: `sed`/`python` operate on the bytes on disk, so
`\u0022` is just six ordinary characters to them. And validate *before* the copy — settings
hot-reloads on write, so the first bad save is already in force.

## `\n` has the same problem, and a whitespace-normalizing destination hides it

The trap above is usually caught by a failed match, which is loud. It goes silent when the escape is
part of **prose being written into a store that collapses whitespace**. Real case, 2026-09-03: a memo
whose text quoted the shell fix `base64 -i "$CASK" | tr -d '\n'` went through `memos.py`, which then
did `text = " ".join(" ".join(args).split())` to force one line per entry. The `\n` had already become
a real newline on the way in, `str.split()` treats it as whitespace like any other, and what got stored
was `tr -d ' '` — a command that deletes **spaces**. No error, no failed match, and the memo's own
remedy quietly wrong until someone runs it.

That particular store has since stopped collapsing: a memo is its own file, so only the title is
normalised to one line and the body is written verbatim. The lesson generalises past the fix — ask of
any destination whether it normalises what it stores, because the ones that do cannot warn you.

Two defences, both cheap:

- Pass the text as an **argv element** rather than through a shell string. Verified:
  `subprocess.run([sys.executable, script, "add", text])` preserves a literal backslash-n exactly. It
  is the layered shell-plus-language quoting that turns it into a real newline, not the destination.
- **Read the entry back** after writing anything holding an escape or a shell fragment. A store that
  flattens whitespace by design (correct, for one-line-per-entry) cannot warn you, so the write is
  the last moment the mistake is visible.

## A `$'\r'` typed into a Bash command stops being a CR

Probing CR counts on 2026-09-27, `grep -c $'\r'` and `grep -Uc $'\r'` typed into a Bash tool command
both reported every line of a file that held no CR at all. The pattern that reached grep matched
everything, so it was no longer a CR; the escape did not survive the trip from tool input to Git
Bash. The same greps with the CR built from hex behaved correctly: 0 on the LF file, and on a CRLF
file 0 for plain grep and 3 for `grep -U`.

Build control bytes from hex whenever a probe depends on them, so no escape passes through the tool
input at all:

```bash
cr=$(printf '0d' | xxd -r -p)                     # a CR in a variable
printf '610d0a620d0a' | xxd -r -p > crlf.bin     # exact file bytes, newlines included
xxd -p crlf.bin                                   # read back before trusting any count
```

Write newlines into the file the same way rather than into a variable: command substitution strips
trailing newlines, so `nl=$(printf '0a' | xxd -r -p)` is empty and every "line" collapses into one.
The read-back is what shows it.

## A NUL byte passes every compiler gate; only git notices

The failures above are at least *visible* once you look at the bytes. U+0000 is the case where nothing looks at
them. Real case, 2026-09-11: an `Edit` meant to write separators inside a TypeScript template literal —

```ts
this.userKey = `${baseUrl} ${opts.token} ${this.userName}`;
```

— put two literal NUL bytes where the spaces belonged. The separator still *worked* (NUL is a fine delimiter), so
there was no behavioural symptom, and **`tsc --noEmit`, `vitest` (451 tests) and a full `next build` all passed**.
The only thing that objected was git:

```
web/src/lib/jellyfin/client.ts | Bin 14949 -> 16999 bytes
Binary files a/…/client.ts and b/…/client.ts differ
```

**`Bin` or `Binary files … differ` on a text source file means NUL bytes, essentially always** — git's heuristic is
a NUL in the first 8000 bytes. Left alone it costs every future diff, blame and review of that file.

Find them by byte offset rather than by eye, since `head`/`cat` render them as nothing:

```python
b = open(path, "rb").read()
print(b.count(b"\x00"), b.find(b"\x00"))
print(repr(b[i - 60:i + 60]))        # surrounding source, with \x00 shown
```

Fix with a byte-level replace (`open(path, "wb").write(b.replace(old, new))`), not Edit — same reason as above: you
cannot type the character into a tool argument to match on it.

Two things generalise:

- **Read the diff, not just the gates.** Three green checks said this file was fine; `git diff --stat` was the only
  instrument that saw it. That is an argument for running the commit flow rather than committing off a passing build.
- **Prefer a separator you can see.** `JSON.stringify([a, b, c])` as a cache key is unambiguous, plain ASCII, and
  cannot go invisible — reach for it over a hand-joined delimiter when the value only has to be unique.

## Why it's worth the trouble

Nothing breaks if the literal character goes in — the code runs identically. What breaks is the convention: the file's own comment claims an escape "rather than the literal character, which is invisible in source", and the next reader sees an empty-looking string with no way to tell U+2003 from U+2009 or a plain space. Whole-file greps for the constant also stop working.

## A third layer: `re.sub`'s replacement string

Even with the backslash built from its code point, `re.sub(pattern, replacement, text)` **parses
escapes in the replacement** — so a replacement containing `\uXXXX` raises
`re.PatternError: bad escape \u` before any matching happens, and one containing `\1` silently
becomes a group reference. Pass a function instead, whose return value is used verbatim:

```python
s = re.sub(pattern, lambda m: replacement, s)   # replacement used as-is
```

`str.replace` does **not** parse escapes, so a multi-line search string that fails there is a
whitespace or line-ending mismatch rather than an escaping one. On a CRLF file read with
`newline=''`, a search string joined with `\n` never matches. **Edit by line index instead** — it
sidesteps quoting entirely, and it is the only approach that stayed reliable on a file mixing CRLF
with literal escape text. Repeated failed `replace` calls also leave a file half-edited: check the
region afterwards rather than assuming a no-op, since one such sequence left three stray lines that
only surfaced as a syntax error two runs later.

## Backslash-heavy code through a Python heredoc

Python's own string-literal parsing bites any code that is mostly backslashes — C# verbatim strings,
regex patterns, Windows paths — when a Python heredoc carries it as a literal, and it does so before
`str.replace` ever sees the string. In a non-raw literal, `\1` becomes `\x01`, `\a` a bell, `\\` a
single backslash, and `\s` or `\g` survive only as a `SyntaxWarning: invalid escape sequence`.
Measured across one C# session: an `old` string holding `'\\'` matched nothing; a `new` string
turned `@"\\nas\games"` into `@"\nas\games"` and was written; and a test line quoting
`'...\1687950\achievements.json'`, meant to be deleted, matched nothing because its `\16` and `\a`
decoded to control characters. Only the second raised a `SyntaxWarning` (for `\g`), and that warning
was the only sign of the corrupted write; `\16` and `\a` are valid escapes and warn about nothing.
An `assert s.count(old) == 1` before writing caught the other two, and it guards only the `old`
side, never what `new` writes.

- **Use the Edit tool** for a C# or regex edit that contains a backslash but no `\uXXXX` sequence.
  Its strings reach the file without passing through Python's escape parsing, which a script's
  literals cannot avoid. A line that holds a `\u` escape is still the case from the first section:
  build it from the code point, as the second section shows.
- When a script is the right tool (many files, a block deletion), **anchor on text with no
  backslash in it** — cut by `s.index(marker)` or drop whole lines containing a marker — and never
  retype the backslash-bearing lines at all.
- Treat any `SyntaxWarning: invalid escape sequence` from a heredoc as a corrupted write until the
  file shows otherwise.
