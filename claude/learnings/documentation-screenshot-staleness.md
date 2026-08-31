# Detecting stale documentation screenshots

A screenshot in `docs/` is documentation that decays invisibly: the prose beside it stays
true while the pixels stop being, and nothing renders differently when it happens. This is
the measured basis for the screenshot step in the `documentation` skill — that skill owns
the procedure; this file records which signals were tested, which were rejected, and why
capture is not automated.

Measured across five repos that carry `docs/screenshots/`: agterm, bga-assistant,
chrome-assistant, jsonl-logs-intellij-plugin, tauri-dashboard.

## The only signal that proves staleness is text, not time

These apps are mostly chrome and labels, and those labels are string literals in the source.
Read the shot, lift the distinctive strings, grep them source-scoped, and `git log -S` the
misses. Two genuinely stale shots were found this way, both invisible to every date heuristic:

- **agterm `keymap-editor.png`** shows the generated `keymap.conf` header, whose text is a
  Swift literal in `ConfigPaths.swift`. The shot's last content line reads
  `# map cmd+shift+d toggle_split`; the source now reads `cmd+shift+l`, changed by
  `9846869` (2026-08-09), and a whole `global-hotkey` block added by `f8679fd` is absent
  from the shot entirely.
- **jsonl-logs `gear-menu.png`** ends at `Scroll to latest on open`. The source builds that
  menu with four `settingToggle(...)` calls; three of them are missing from the shot.

The second case is the additive variant and it is the higher-yield one: a UI that *gains* a
menu item never contradicts a visible string, it just fails to show the new one. So check
both directions — every literal in the shot still exists in source, and every set the source
enumerates appears in the shot in full.

Two traps in the grep itself:

- **Scope it to source.** An unscoped `git grep` for a removed literal hits `CHANGELOG.md`
  and the plan doc describing the removal, so the string looks present and the shot looks
  current. Exclude `':!*.md' ':!docs' ':!CHANGELOG.md'`.
- **Order by ancestry, not date.** The jsonl shot and the commit that invalidated it are
  both dated 2026-04-25. Use `git merge-base --is-ancestor <shot-commit> <change-commit>`.

## Only strings the repo renders are evidence

The check breaks on any frame containing UI the project does not own. chrome-assistant's
hero is a live mail client: `Compose`, `Snoozed` and `Drafts` are visible, stable, entirely
non-runtime, and appear nowhere in that repo's source. A naive check reports CERTAIN STALE
on all three — on the one project whose screenshots must never be re-shot, because they
contain real correspondence and double as store-listing assets.

The same applies to a game table's board chrome, an IDE's own menus, and whatever is running
inside a terminal pane in a terminal app's screenshots. The needed boundary is not "ignore
runtime data"; it is that only strings this repo renders are admissible, and which source
trees those are is per-project. It cannot be derived — it takes one hand-written line in the
project's `CLAUDE.md`. Without it, report `NOT CHECKED (third-party UI in frame)`.

## Signals measured and rejected

- **File mtime — worthless, and anti-correlated with truth.** Git stores no mtimes, so
  checkout/rebase/stash stamp everything with "now". Every file in each repo carried one
  identical mtime; the stale `keymap-editor.png` and the current `ConfigPaths.swift` matched
  to the second. Never use it in any form.
- **Blob commit date vs source commit date — correct input, unusable alone.** In agterm,
  345 of 351 tracked `.swift` files changed after the shot's commit. Only after narrowing to
  the shot's *backing* files does it become a candidate generator (22x noise reduction), and
  it still yields candidates, never verdicts.
- **Commit count / age in releases** — a fact, not a verdict. Useful only to order a queue,
  and a queue ordered by age is one nobody works.
- **Diff-text against filename stems — over-fires badly.** On one agterm commit, stem
  matching against the whole diff flagged 7 of 12 shots; restricted to changed lines it
  flagged exactly one, the wrong one, and missed the shot that was actually stale.
- **Dimension drift — only where a convention exists.** chrome-assistant is modally
  1280x800 (the store's required size), so an outlier there is a real finding. jsonl-logs
  has nine distinct sizes because the shots are deliberate crops, so the same check is void.
  Gate on the convention before applying it.
- **Derived-asset dimension ratios — rejected.** agterm's `docs/screenshots/*.png` to
  `site/assets/screenshot-*.webp` ratios are 1.000, 1.078 and 1.663, because four of eleven
  were deliberately re-cropped to the site's hero ratio and no conversion script exists.
  Comparing a master against its derivative is a permanent false positive.

## Mapping a shot to the code behind it

Ranked by what actually worked:

1. **Prose terms from the page that embeds the shot.** Extract the bolded and
   code-formatted terms and grep them over the source tree; the most-hit file is the backing
   one. This found the right file in every jsonl case.
2. **Co-change history** — strong where the project has the habit of re-shooting inside the
   feature commit, silent otherwise. Across all five repos that happened four times total.
3. **Filename tokens — ranking only, never evidence.** Right area, wrong file, and one
   confident false match: `main.png` mapped to `main.swift`. The file that renders
   `keymap-editor.png` is `ConfigPaths.swift`, which contains no "keymap" in its name.
4. **Alt text — useless.** One to three generic words.

## Reconciling files against references

- **A prose mention is not a reference.** Confirming an orphan with a bare basename grep
  clears it on any plan doc or changelog that *records the file being dropped*. In agterm
  that silently cleared all seven orphans; excluding `docs/plans` and `CHANGELOG.md` restores
  them, leaving `quick-terminal.png` as the one genuinely dead file.
- **Join derived copies by stem before calling anything dead.** Six of agterm's seven
  "orphans" are still live on its website through a `site/assets/screenshot-<stem>.webp`
  twin, so the docs master is not deletable.
- **Match citation forms, not paths.** Scanning for any image-looking token flags runtime
  URLs quoted in prose (an extension's `getURL("assets/.../hex_5.png")`) as broken links.
  Match `](path)` and `src="path"`; then a *separate* basename pass catches `href=` and
  `content=` (favicons, `og:image` cards) that the embed pattern misses.
- **Root-absolute URLs resolve against the site root, not the repo root.** Getting this
  wrong reported 18 false broken links in one site directory.

## Why capture is not automated

No project in the survey has a capture recipe, script, npm target or CI step — every shot
was taken and cropped by hand. The framing that would have to be reproduced is recorded
nowhere: window size, device scale (the same five repos mix 72, 96 and 144 dpi), theme,
in-app state, and the crop itself, which odd pixel dimensions on 2x captures prove was
manual. Only agterm pins anything, and only for its website heroes.

Recapture is also blocked per project for unrelated reasons — OAuth-gated real mail,
a logged-in third-party game session, a sample log file that exists in no revision, live
usage values that never recur — and, worse, it fails *silently*: a locked display makes
`screencapture` write an all-black PNG and exit 0; a capture inside the first ~2 s of a
webview's mount records a half-scale window; a fresh browser profile renders logged-out.
Nothing in any repo would catch any of these — no dimension assertion, no visual diff — so a
wrong recapture reads as a normal-looking image beside prose it no longer matches.

Flag and let a human shoot the replacement. The verification method, if a comparison is ever
needed, is the overlay in `icon-tracing-pixel-overlay.md`: old and new at the same size, old
faded to grey, new composited semi-transparent, laid out `old | new | overlay`.
