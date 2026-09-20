---
name: memo
description: Capture an off-task idea to the project's memo backlog, or list and act on existing memos
model: haiku
allowed-tools: Read, Edit, Bash(git rev-parse:*), Bash(python ~/.claude/skills/memo/memos.py:*), PowerShell
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
<Repo root>/.claude/memos/<slug>.md                 an open memo
<Repo root>/.claude/memos/done/<date>-<slug>.md     one that has been addressed
```

Open versus done is **which directory the file sits in** — there is no status marker to read or flip. Each file is a frontmatter block carrying `created:` and optionally `platform:`, an `# H1` title, and an optional body:

```markdown
---
created: 2026-09-12 05:17:22
platform: windows
---

# Improve memos by storing in separate files

Body prose, as long as it needs to be.
```

The `memos.py` helper owns the timestamp, the slug, the title derivation and the rendered listing — you hand-format none of them. An open memo's frontmatter carries its sort key rather than its filename, so adding a future ordering (priority, area) is a new field instead of renaming every file.

**Closing prefixes the close date onto the name**, and that is the one place the rule above is deliberately inverted. Done memos are never deleted and no command lists them — `list` and `show` both resolve against the open backlog — so their only reader is a file browser, `ls` or `git status`, and a name is the only thing those sort by. The date is stored there and nowhere else, so no field can disagree with it. `reopen` needs no rule to strip the prefix: the slug is re-derived from the title, which is where every name comes from.

**`platform:` is optional and names the box that can act on the memo** — `macos` or `windows`. Its absence means either machine, which is what nearly every memo is, and an unbound memo writes the same bytes it did before the field existed. It **marks and never filters**: a bound memo keeps its place in the listing, keeps its number, and is closed the same way, so nothing can desync. A platform is not a host — the day a second mac exists, `macos` means either of them, and the fix is a separate `host:` field rather than a second meaning for this one.

**Every command here refuses in a repo that has not adopted this layout**, naming the version and pointing at `/adopt`. That layout is a convention the dotfiles repo defines and versions, so a repo below the newest version affecting `memo` is one where every command would be wrong in both directions: a listing reports an empty backlog while the old file holds items, and an `add` writes a memo beside it and leaves the migration half done. Run `/adopt` in that repo and re-run the command — in a repo already in the right shape it records the version in seconds and changes nothing. A refusal is never something to work around by writing the file by hand.

## Process

### If `$ARGUMENTS` is non-empty — record a memo

1. **Write the title yourself.** Run `python ~/.claude/skills/memo/memos.py add --title "<short title>" "<the rest of the idea>"`. The title is the one line that shows up in every listing and in the status bar, so make it a sentence that names the thing and the change — "Quote values when host-publish renders the per-host .env", not "quoting bug". Put everything else in the body argument; it is preserved verbatim, newlines and all.
   - Without `--title` the helper derives one from the first sentence. That is the fallback for the model-free `memo <text>` shell function, not for you — you have read the idea and can title it better.
   - Preserve the user's intent and scope. Don't expand a one-liner into a spec.
2. **Anchor on symbol names, never `file:NN`.** Name the method, the heading, the config key, the test — `the (leading, filling) = matchedExactly ? ... ternary in ResolvePreferringSchema`, not `AchievementMetadata.cs:494`. A memo is read weeks or months after it is written, by which time a line number points at unrelated code and reads as authoritative while being wrong. Measured: one memo carried five line numbers into the same file and all five were stale within a day, off by ~50 lines, invalidated by edits made in the session that wrote them. The global prose rule already bans line anchors; memos get them anyway because the number is on screen at the moment of writing.
3. **Add `--platform macos|windows` only when the memo's own body already says the work needs that box.** A codepage the other machine does not have, a PowerShell API, a toolchain installed on one side — the constraint has to be in the idea, not in where it happened to be captured. Most memos surface on whichever machine the user is at and are actionable on either, so the default is no flag: two of the first ten memos written under this field qualified, and two more *looked* machine-specific from the box they were captured on while being portable. When the whole memo is work only the other machine can do, the flag is the wrong tool — route it to the live session there instead (`~/.claude/skills/wrap-up/SKILL.md` step 5 has the rule). The flag is for a memo that was going into the backlog anyway.
4. Confirm in a single line with the new open count (e.g. "Memo'd — 3 open."). **Do not** start working on the idea, switch tasks, or elaborate. The whole point is to offload it and keep going.

### If `$ARGUMENTS` is empty — review the backlog

1. **Render the backlog** with `python ~/.claude/skills/memo/memos.py list`. On macOS and Linux the helper finds the real terminal width itself, via `skills/shared/terminal_width.py` — pass no `--width`.
   - **Windows only:** the helper cannot detect it there (a console is not a pty), so get the width from the **PowerShell tool** evaluating `$Host.UI.RawUI.WindowSize.Width` — that tool specifically, since `powershell.exe` from Bash reports the wrong console — subtract a 2-column gutter, and pass `--width <N>`. When `ToolSearch` surfaces no PowerShell tool the width is simply not available; run the plain command and accept the ~100 fallback rather than hunting for a substitute. Do not reach for `tput cols` from Git Bash: measured 2026-09-15, it answered 80 on a wider terminal and `$COLUMNS` was empty — the piped default wearing a plausible number, which is worse than no answer.
2. Present that output **verbatim, inside a fenced code block** — it's numbered newest-first and wrapped so each memo's title lines up under its first line, and the code block preserves that alignment. If it shows "(no open memos)", say so and stop.
3. Two markers appear on a line, and they mean different things. A trailing ` …` means that memo has a body beyond its title — read it with `python ~/.claude/skills/memo/memos.py show <n>`, and don't paste bodies into the listing. A leading `[macos]` or `[windows]` means the work needs that box; the listing still shows and numbers it normally, so the marker is information and never a reason to skip a line.
4. Offer two paths: address one now (the user gives a number), or leave them. If the user picks one, that begins a new task — do the work, then run `python ~/.claude/skills/memo/memos.py done <n>` once it's genuinely done, which moves the file into `done/`. That prints an `undo:` line; `memos.py reopen <slug>` moves it back if it was closed too early. Closing several at once means naming them in **one** command (`done 2 4`) — a number indexes the listing you just read, and closing one renumbers the rest, so separate calls land on memos you never named. **When the memo they pick is tagged for the other platform**, do whatever part of it is portable here and route the rest to the live session on that box per `~/.claude/memory/peer_messaging.md`, then leave it open unless the portable part was the whole memo.
5. Never offer to clear `done/`. Addressed memos stay there for good, dated and greppable, and there is no command to remove them — a backlog's record of what was decided is the cheapest thing in the repo to keep and the only thing in it that cannot be rebuilt.
6. If two memos capture the same idea, do the work once and **drop** the redundant one — `python ~/.claude/skills/memo/memos.py drop <n>` — rather than marking both done. A duplicate in `done/` reads like two separate pieces of work in the backlog's history. Drop only on a duplicate the user has confirmed; it deletes the file, and git is the only way back. Name the duplicate by its slug here, not by its number: closing the memo you kept has already renumbered the listing, `done` and `drop` cannot share one command, and this is the step that deletes.

### Editing a memo

To revise one in place, get its path with `python ~/.claude/skills/memo/memos.py path <n|slug>` and edit that file. Keep the `# H1` as the first line after the frontmatter; everything below it is free markdown. Binding or unbinding a memo happens here too — `--platform` writes only at capture, so adding or removing the `platform:` line in the frontmatter is how an existing memo gains or loses its tag.

## Out of scope
- Don't promote a memo to a GitHub issue unless asked — memos are deliberately lighter. (When one matures, offering to file it is fine.)
- Don't reword or reprioritize existing memos unprompted.
- Don't add a field to the frontmatter that nothing reads yet. `created` and `platform` are the two anything reads, and `platform` was only added once five readers for it shipped in the same change — `list`, `show`, `count`, the status bar, and the context injected when a memo is picked from it. A field written but rendered nowhere is invisible to every listing and would be dropped by the first code that rewrites a memo file.
