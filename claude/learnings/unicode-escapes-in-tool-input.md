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

## Why it's worth the trouble

Nothing breaks if the literal character goes in — the code runs identically. What breaks is the convention: the file's own comment claims an escape "rather than the literal character, which is invisible in source", and the next reader sees an empty-looking string with no way to tell U+2003 from U+2009 or a plain space. Whole-file greps for the constant also stop working.
