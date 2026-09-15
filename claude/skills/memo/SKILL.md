---
name: memo
description: Capture an off-task idea to the project's memo backlog, or list and act on existing memos
model: haiku
allowed-tools: Read, Edit, Bash(git rev-parse:*), Bash(tput cols:*), Bash(python ~/.claude/skills/memo/memos.py:*), PowerShell
---

# Memo

Park a stray idea now so it isn't lost — without derailing the current task — or review the backlog and pick something up.

A memo is lighter than a GitHub issue: a half-formed thought worth keeping, not a tracked unit of work. The backlog lives in `.claude/memos/`, one file per memo, committed with the project. Open items resurface on their own at session start, at task completion, and during `/commit`.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Open memos: !`python ~/.claude/skills/memo/memos.py count`

## Arguments

`$ARGUMENTS` holds the memo text. It may be empty.

## Storage

One memo is one file, so a memo is as long as the idea needs:

```
<Repo root>/.claude/memos/<slug>.md        an open memo
<Repo root>/.claude/memos/done/<slug>.md   one that has been addressed
```

Open versus done is **which directory the file sits in** — there is no status marker to read or flip. Each file is a `created:` frontmatter block, an `# H1` title, and an optional body:

```markdown
---
created: 2026-09-12 05:17:22
---

# Improve memos by storing in separate files

Body prose, as long as it needs to be.
```

The `memos.py` helper owns the timestamp, the slug, the title derivation and the rendered listing — you hand-format none of them. Frontmatter carries the sort key rather than the filename, so adding a future ordering (priority, area) is a new field instead of renaming every file.

**Every command here refuses in a repo that has not adopted this layout**, naming the version and pointing at `/adopt`. That layout is a convention the dotfiles repo defines and versions, so a repo below the newest version affecting `memo` is one where every command would be wrong in both directions: a listing reports an empty backlog while the old file holds items, and an `add` writes a memo beside it and leaves the migration half done. Run `/adopt` in that repo and re-run the command — in a repo already in the right shape it records the version in seconds and changes nothing. A refusal is never something to work around by writing the file by hand.

## Process

### If `$ARGUMENTS` is non-empty — record a memo

1. **Write the title yourself.** Run `python ~/.claude/skills/memo/memos.py add --title "<short title>" "<the rest of the idea>"`. The title is the one line that shows up in every listing and in the status bar, so make it a sentence that names the thing and the change — "Quote values when host-publish renders the per-host .env", not "quoting bug". Put everything else in the body argument; it is preserved verbatim, newlines and all.
   - Without `--title` the helper derives one from the first sentence. That is the fallback for the model-free `memo <text>` shell function, not for you — you have read the idea and can title it better.
   - Preserve the user's intent and scope. Don't expand a one-liner into a spec.
2. **Anchor on symbol names, never `file:NN`.** Name the method, the heading, the config key, the test — `the (leading, filling) = matchedExactly ? ... ternary in ResolvePreferringSchema`, not `AchievementMetadata.cs:494`. A memo is read weeks or months after it is written, by which time a line number points at unrelated code and reads as authoritative while being wrong. Measured: one memo carried five line numbers into the same file and all five were stale within a day, off by ~50 lines, invalidated by edits made in the session that wrote them. The global prose rule already bans line anchors; memos get them anyway because the number is on screen at the moment of writing.
3. Confirm in a single line with the new open count (e.g. "Memo'd — 3 open."). **Do not** start working on the idea, switch tasks, or elaborate. The whole point is to offload it and keep going.

### If `$ARGUMENTS` is empty — review the backlog

1. **Detect the terminal width** so the listing fills the screen — the helper's stdout is piped, which hides the real width, so determine it yourself:
   - **Windows:** use the **PowerShell tool** to evaluate `$Host.UI.RawUI.WindowSize.Width` (the PowerShell tool specifically — `powershell.exe` from Bash reports the wrong console).
   - **macOS/Linux:** run `tput cols` (or read `$COLUMNS`).

   Subtract a 2-column gutter, then run `python ~/.claude/skills/memo/memos.py list --width <N>` to render the backlog (drop `--width` if you couldn't determine it — the helper falls back to ~100).
2. Present that output **verbatim, inside a fenced code block** — it's numbered newest-first and wrapped so each memo's title lines up under its first line, and the code block preserves that alignment. If it shows "(no open memos)", say so and stop.
3. A trailing ` …` on a line means that memo has a body beyond its title. Read one with `python ~/.claude/skills/memo/memos.py show <n>`; don't paste bodies into the listing.
4. Offer two paths: address one now (the user gives a number), or leave them. If the user picks one, that begins a new task — do the work, then run `python ~/.claude/skills/memo/memos.py done <n>` once it's genuinely done, which moves the file into `done/`. That prints an `undo:` line; `memos.py reopen <slug>` moves it back if it was closed too early. Closing several at once means naming them in **one** command (`done 2 4`) — a number indexes the listing you just read, and closing one renumbers the rest, so separate calls land on memos you never named.
5. If addressed memos have accumulated in `done/`, offer to clear them with `python ~/.claude/skills/memo/memos.py prune` in the same breath.
6. If two memos capture the same idea, do the work once and **drop** the redundant one — `python ~/.claude/skills/memo/memos.py drop <n>` — rather than marking both done. A duplicate in `done/` reads like two separate pieces of work in the backlog's history. Drop only on a duplicate the user has confirmed; it deletes the file, and git is the only way back. Name the duplicate by its slug here, not by its number: closing the memo you kept has already renumbered the listing, `done` and `drop` cannot share one command, and this is the step that deletes.

### Editing a memo

To revise one in place, get its path with `python ~/.claude/skills/memo/memos.py path <n|slug>` and edit that file. Keep the `# H1` as the first line after the frontmatter; everything below it is free markdown.

## Out of scope
- Don't promote a memo to a GitHub issue unless asked — memos are deliberately lighter. (When one matures, offering to file it is fine.)
- Don't reword or reprioritize existing memos unprompted.
- Don't add fields to the frontmatter. `created` is the only one anything reads; a field no step reads yet doesn't get one.
