---
created: 2026-09-15 10:55:28
platform: windows
---

# Make the PowerShell memo wrapper refuse unquoted text whose commas and backticks it silently eats

Measured 2026-09-15 on the Windows box while verifying the memo backlog gate — the memo this came out of, now in `done/`. The bash and PowerShell `memo` wrappers in `claude/learnings/shell-environment.md` are documented as equivalent, and the bash half promises "no quotes needed". On Windows two unquoted characters are eaten with no signal.

## What was measured

pwsh 7.6.6, codepage 866, through a function forwarding `@args` to python — the exact shape of the `memo` wrapper:

- **Comma.** `t fix the a, b, c thing` arrives as `[fix, the, a, b, c, thing]`. PowerShell parses `a, b, c` in argument mode as an array literal, so the commas become the array operator and disappear; splatting then flattens it. Bash passes the commas through attached to their words.
- **Backtick.** A backtick followed by `n` in the text arrives as a literal newline where those two characters were — PowerShell applies its own escape sequences inside an unquoted argument. Bash keeps both characters.

Both exit 0 and write a plausible memo. Same class as the whitespace-collapse bug that `cmd_add` in `memos.py` carries a warning comment about — a memo whose quoted shell fragment was silently rewritten.

Not silent, so not a problem: `@` and a bare apostrophe are parse errors that stop the command outright; so are parentheses and braces. Passing through unchanged: em-dash, square brackets, colon, and leading-hyphen flags such as `-v` and `--verbose`.

Shared with bash, so not a parity gap: `$word` is expanded by both shells, and an undefined one collapses to nothing on both.

## Candidate fixes, not decided

1. A note in the **PowerShell `memo` wrapper** section of `learnings/shell-environment.md` telling the reader to quote text containing a comma or a backtick. Cheapest, and the only portable half — that edit can be made from either machine.
2. Make it loud instead, which the loud-errors rule prefers. The wrapper can detect the case without changing the parse: when PowerShell folds `a, b, c` into an array, it reaches `$args` as one nested non-string element. A wrapper that tests for that and refuses, naming the fix, turns silent corruption into a message at the moment of the mistake.

## Also on this wrapper

`memo` is defined only in the PowerShell 7 profile. The Windows PowerShell 5.1 profile defines `claude` but not `memo`, so `type memo` fails there — item 5 of the verification checklist in that same learnings file. Worth deciding whether 5.1 is still in use on that box before adding it.

## Why this needs that box

The parse is PowerShell-side, so reproducing it or proving either fix needs pwsh. The capture-guards memo in this same backlog records that the Mac which measured it had no pwsh. Only the doc half of fix 1 is portable.
