---
name: memo
description: Capture an off-task idea to the project's memo backlog, or list and act on existing memos
model: haiku
allowed-tools: Read, Edit, Bash(git rev-parse:*), Bash(date:*), Bash(tput cols:*), Bash(python ~/.claude/skills/memo/memos.py:*), PowerShell
---

# Memo

Park a stray idea now so it isn't lost — without derailing the current task — or review the backlog and pick something up.

A memo is lighter than a GitHub issue: a half-formed thought worth keeping, not a tracked unit of work. The backlog lives in one file, `.claude/memos.md`, committed with the project. Open items resurface on their own at session start, at task completion, and during `/commit`.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Now: !`date '+%Y-%m-%d %H:%M %Z'`
- Open memos: !`python ~/.claude/skills/memo/memos.py count`

## Arguments

`$ARGUMENTS` holds the memo text. It may be empty.

## Process

The memo file is `<Repo root>/.claude/memos.md` — a Markdown checklist, one line per entry, newest at the bottom: `- [ ] <YYYY-MM-DD HH:MM> — <idea>` open (local time, 24-hour), `- [x] …` addressed. The `memos.py` helper owns the timestamp and the rendered, aligned listing (numbered, newest-first, wrapped so each memo's text lines up under its first line) — you hand-format neither.

### If `$ARGUMENTS` is non-empty — record a memo

1. Run `python ~/.claude/skills/memo/memos.py add "<the idea, lightly cleaned up>"`. The helper creates the file (and `.claude/`) if needed, stamps the local time, appends the entry, and prints the new counts. Preserve the user's intent and scope — don't expand a one-liner into a spec.
2. Confirm in a single line with the new open count (e.g. "Memo'd — 3 open."). **Do not** start working on the idea, switch tasks, or elaborate. The whole point is to offload it and keep going.

### If `$ARGUMENTS` is empty — review the backlog

1. **Detect the terminal width** so the listing fills the screen — the helper's stdout is piped, which hides the real width, so determine it yourself:
   - **Windows:** use the **PowerShell tool** to evaluate `$Host.UI.RawUI.WindowSize.Width` (the PowerShell tool specifically — `powershell.exe` from Bash reports the wrong console).
   - **macOS/Linux:** run `tput cols` (or read `$COLUMNS`).

   Subtract a 2-column gutter, then run `python ~/.claude/skills/memo/memos.py list --width <N>` to render the backlog (drop `--width` if you couldn't determine it — the helper falls back to ~100).
2. Present that output **verbatim, inside a fenced code block** — it's numbered newest-first and wrapped so each memo's text lines up under its first line, and the code block preserves that alignment. If it shows "(no open memos)", say so and stop.
3. Offer two paths: address one now (the user gives a number), or leave them. If the user picks one, that begins a new task — find that memo's line in `.claude/memos.md` and flip its `- [ ]` to `- [x]` (Edit in place) once it's genuinely done, and proceed with the work normally.
4. If addressed (`- [x]`) items have accumulated, offer to prune them in the same breath.

## Out of scope
- Don't promote a memo to a GitHub issue unless asked — memos are deliberately lighter. (When one matures, offering to file it is fine.)
- Don't reword or reprioritize existing memos unprompted.
