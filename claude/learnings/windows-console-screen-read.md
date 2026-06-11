# Reading a Windows console's on-screen text

How an external process reads the **visible text** of another terminal's console — e.g. to detect what a TUI app is showing (a spinner, a prompt, a footer hint). This is the *read* counterpart to `windows-terminal-title.md`, which covers *writing* a tab title; both share the same attach machinery.

## Getting attached to the target console

Identical to the title-writing path in `windows-terminal-title.md`: the hook/dashboard isn't in the target's console, so it `AttachConsole(pid)`s to a process running in that tab. Reuse everything from that learning — the `FreeConsole → AttachConsole → … → FreeConsole` dance, the one-console-per-process mutex, the ancestor-pid-chain candidate list, and the **far-to-near** walk (first successful attach is the real terminal; near-end transients hold invisible `CREATE_NO_WINDOW` consoles). Serialize reads and title-writes behind the **same** mutex — a process has one console attachment, so they must not interleave.

## Reading the screen buffer

Once attached, open the active screen buffer and read its visible rows:

```
CreateFileW("CONOUT$", GENERIC_READ|GENERIC_WRITE, FILE_SHARE_READ|FILE_SHARE_WRITE,
            NULL, OPEN_EXISTING, 0, NULL)         // handle to the attached console's buffer
GetConsoleScreenBufferInfo(h, &csbi)              // gives srWindow = visible viewport
for y in csbi.srWindow.Top ..= csbi.srWindow.Bottom:
    ReadConsoleOutputCharacterW(h, buf, width, coord(0, y), &read)   // one row of chars
CloseHandle(h)
```

- **Read `srWindow`, not the whole buffer.** `dwSize` is the full scrollback (can be thousands of rows); `srWindow` is the visible viewport — what the user actually sees. Iterate `srWindow.Top..=srWindow.Bottom`.
- **`COORD` is passed by value as a packed `u32`** across the FFI: `((y as u32) << 16) | (x as u32 & 0xFFFF)`. Declaring it as a 2-`i16` struct by value is ABI-fragile; the packed-u32 form is what works (Rust `extern "system"`).
- `ReadConsoleOutputCharacterW` returns **characters only** — no attributes/color. Fine for text matching. Use the `…W` (wide) variant; box-drawing and spinner glyphs are non-ASCII.
- `CONSOLE_SCREEN_BUFFER_INFO` layout (for a hand-rolled `#[repr(C)]`): `COORD dwSize; COORD dwCursorPosition; WORD wAttributes; SMALL_RECT srWindow; COORD dwMaximumWindowSize;` — i.e. `i16 ×2, i16 ×2, u16, i16 ×4, i16 ×2`.

## Matching what you read — TUI strings are runtime-built

The footer hints you'll want to match (e.g. Claude Code's `esc to interrupt`) are **assembled at runtime from template literals**, so they are **not** greppable as contiguous strings in the app binary — don't try to confirm them by `grep`-ing the exe; read them off the live screen instead. Word fragments (`interrupt`, `shortcuts`) may appear in the binary, the full phrase won't.

- Restrict matching to the **bottom N rows** (the input box + footer region). The same phrase can appear in scrollback above (your own earlier output, a prior footer) and produce false matches.
- Prefer a **mode-independent structural anchor** over a text hint when you need to positively confirm "the app is at its prompt". For Claude Code the input box is framed by a long `─` (U+2500) rule present in every mode; the `? for shortcuts` hint is **absent in auto-accept mode**. (Claude-Code specifics live in `claude-code-integration.md`.)

## Verification trap

Claude Code's **Bash tool** runs in its own hidden conPTY, so reads taken from a Bash-tool command see *that* console, not the user's terminal. The **PowerShell tool**'s persistent host shares the real terminal console — verify console-read behavior from PowerShell. (Same trap as title-writing; see `windows-terminal-title.md`.)
