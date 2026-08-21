# Hook performance — measured costs

All figures measured on this Windows 11 / Git Bash machine (Python 3.13.5, Node 24.13.0) on
2026-08-19. Each is the wall-clock of an N-run loop divided by N, N ≥ 20; two independent passes
agreed within ~1.5 ms on every repeated row. Re-measure before trusting these on another machine —
process spawn on Windows is roughly 100× more expensive than on Linux/macOS, so a hook that is free
elsewhere is not free here.

## Process floor

| Invocation | ms/run |
|---|---|
| bare exe (`/usr/bin/true`) — the Windows spawn floor | 28.8 |
| `bash -c :` | 31.2 |
| `cmd.exe /c` | 35–36 |
| `node -e ""` | 47.4 |
| `python -c pass` | 58.4 |
| `python -S -c pass` (skips `site`) | 39.9 |
| **`python3 -c pass`** (bash shim → `exec python`) | **81.6** |

`python3` is not a real binary here: `~/bin/python3` is a 29-byte bash script. Invoking it costs
**+23 ms every time** versus `python`, for identical behaviour.

## Python import cost (delta vs `python -c pass`)

| Imports | delta |
|---|---|
| `json` / `re` / `sys,os` / `pathlib` / `datetime`, each alone | ~0–1 ms |
| all five together — the typical hook set | **+2.8 ms** |
| `subprocess` | +3.6 ms |

Imports are nearly free because `site.py` already paid for them. `site` itself costs 18.4 ms —
more than 6× every import combined. **Trimming imports is a non-fix.** If Python startup must
shrink, `-S` is the only meaningful lever, and it disables `site`/`sitecustomize` and
`site-packages`, so it suits stdlib-only hooks.

## Reading a JSON payload from stdin (256 B)

| Pattern | ms/run |
|---|---|
| bash builtins only (`read -r -d ''`, `[[ == * ]]`) — zero forks | **32.5** |
| `node -e "JSON.parse(readFileSync(0,'utf8'))"` | 47.5 |
| `python -c "json.load(sys.stdin)"` | 59.9 |
| `bash -c 'grep …'` — one fork | 62.7 |
| `bash -c 'cat …'` — one fork | 64.0 |
| `jq` | **not installed on this machine** — a hook depending on it fails outright |

Bash is only the cheap option when it forks nothing. One `grep` or `cat` makes it slower than
Python doing a real parse.

## Real hooks, discard path

Each fed a payload that hits its first early return; all verified rc=0, zero stdout.

| Hook | `python` | `python3` shim |
|---|---|---|
| minimal hook (parse stdin, discard) — the floor | 60.6 | 84.0 |
| `doppler-guard.py` | 63.8 | 84.0 |
| `skill-tracked.py` | 65.3 | 88.0 |
| `plan-archive.py done` | 66.5 | 93.4 |
| `plan-archive.py start` | 67.8 | 90.0 |
| `memos-surface.py on-prompt` | 72.5 | 95.7 |

Script size barely matters: 0.2 KB → 11.4 KB spans only 60.6 → 66.5 ms. **Optimize invocation form
and spawn count, not lines of code.**

## Shebang

| Form | ms/run |
|---|---|
| `python3 script.py`, correct shebang | 84.0 |
| `python3 script.py`, deliberately broken shebang | 83.5 — runs fine, rc=0 |
| `./script.py` (shebang honoured via `env`) | 99.4 |

The shebang is inert when the hook is invoked as `<interpreter> script.py`. Executing by path is
the slowest form.

## Frequency tiers

Cost per invocation matters only in proportion to how often the event fires. In descending order
of how much a millisecond is worth:

| Tier | Events | Budget |
|---|---|---|
| Per streaming chunk | `MessageDisplay` | Forks per delta with a ~10 s timeout that blocks TUI rendering. Avoid unless essential. |
| Every ~2 s | `statusLine` (`refreshInterval`) | One small file read. No git, no transcript, no network. |
| Every tool call | `PreToolUse` / `PostToolUse` with no matcher | Native exe or an `if` gate. Never an unnarrowed interpreter. |
| Common tool subset | `PreToolUse` matched to `Bash\|Write\|Edit` | Synchronous cost lands on most tool calls — accept only when the condition can't be an `if` rule. |
| Per turn | `UserPromptSubmit`, `Stop` | Async; note `UserPromptSubmit` has a 30 s timeout, not 600 s. |
| Rare | `SessionStart`, `Notification`, `PreCompact`, `SessionEnd` | Interpreter startup is noise here. `SessionEnd` shares a 1.5 s budget across all hooks. |
| Conditional | anything behind an `if` rule | Zero when it doesn't match. |

## The rules that follow from the numbers

1. **Say `python`, not `python3`** — the largest free win available, ~23 ms × every invocation.
2. **Narrow with `if` before anything else** — it is the only gate that costs zero startup.
3. **Nothing is free.** A hook that does nothing costs ~61 ms. Budget per invocation.
4. **Don't rewrite Python in bash "for speed"** unless it can be pure builtins with zero forks.
   Node saves ~11 ms over Python for the same parse — real, but far smaller than the shim tax and
   rarely worth a rewrite.
5. **`async: true` is the only thing that reaches effectively 0 ms** on the user's turn. A faster
   script is a smaller constant; async removes the term.
