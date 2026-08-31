---
name: documentation
description: Update stale documentation and comments to match current code
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(git diff:*), Bash(git status:*), Bash(git rev-parse:*), Bash(git ls-files:*), Bash(git grep:*), Bash(git log:*), Bash(file:*), Bash(cp:*)
---

# Update Documentation

Scan project documentation and comments for references that no longer match the code, and fix them.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Uncommitted changes: !`git status --short`
- Diff summary: !`git diff --stat $(git rev-parse -q --verify HEAD || echo 4b825dc642cb6eb9a060e54bf8d69288fbee4904)`
- Full diff: !`git diff $(git rev-parse -q --verify HEAD || echo 4b825dc642cb6eb9a060e54bf8d69288fbee4904)`
- GH Pages index present: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && test -f "$R/docs/index.md" && echo yes || echo no`
- Doc image files: !`git ls-files --full-name -co --exclude-standard -- ':/docs/*.png' ':/docs/*.jpg' ':/docs/*.jpeg' ':/docs/*.gif' ':/docs/*.webp' | grep . || echo NONE`

## Working directory

All file paths below (`README.md`, `docs/`, `docs/pages/`, `docs/index.md`, `docs/screenshots/`, `CLAUDE.md`) are relative to **Repo root** from Context. The current working directory may be a subdirectory (e.g. `src-tauri/`, `frontend/`), so always prefix the Repo root value when calling Read/Edit/Write/Grep/Glob. Bare paths are cwd-relative and will silently miss files that live at the actual root.

## Process

1. **Read `README.md`** (at the repo root) and fix any references to changed paths, APIs, or behavior

2. **Read all files in `docs/pages/`** (if the folder exists) and check for both staleness and gaps:
   - Rewrite any sections that no longer match the code — removed features, changed message protocols, new data flows, renamed concepts
   - Check whether features added or significantly changed in the current diff are missing from the relevant docs page. A new user-visible capability, config option, or behavioral change should appear in the page that covers its area. Propose additions and wait for approval
   - **Update the features section.** When the diff adds a new user-facing feature or changes an existing one, the curated feature listings must reflect it — the dedicated features page (e.g. `docs/pages/features.md`), any enumerated feature list in `docs/index.md`, and the README's feature list. Add a new entry for a new feature; revise the existing entry for a changed one. A feature that exists in code but is absent from (or stale in) these listings is a documentation gap even when every other page is accurate. Propose the additions/edits and wait for approval
   - **Check embedded diagrams** (` ```mermaid ` blocks, ASCII flowcharts/trees, and structural tables) that depict architecture, data flow, state machines, or file layout. When code changes — or another doc you just edited — alters the structure a diagram illustrates (a renamed/removed module, a new component, a changed path or edge), update the diagram itself, not just the surrounding prose. A stale node, missing arrow, or wrong label in a diagram is as misleading as stale text.
   - **Check pages that moved in the nav hierarchy** (e.g. a former top-level page now nested as a subpage). A relocated page often (a) duplicates content that now belongs to a sibling page — trim it to a pointer so each page owns one concern; and (b) keeps heading levels from its old position (a former subsection's `###` where siblings use `##`). Also re-verify its relative links resolve from the new location.

3. **Align README with the GH Pages index** — only if **GH Pages index present** is `yes`. Read `README.md` and `docs/index.md` together and reconcile them so they describe the same product at the same point in time:
   - Tagline / one-line description must match (ignoring italics and minor punctuation).
   - The set of user-facing features / supported sites / supported games listed in each must match exactly — no feature appears in one but not the other.
   - Per-feature blurbs in the README must match the intro paragraph of the corresponding `docs/index.md` section (same facts, same scope claims). Wording may differ slightly; facts must not.
   - Install link, beta / access notices, and status blurbs must match.
   - If the README contains per-feature blurbs, each feature link must point to `https://<org>.github.io/<repo>/pages/<feature>` (or `/pages/<product>` in the monorepo variant) and the corresponding `docs/pages/<feature>.md` file must exist.
   - The footer "See full project documentation at …" block in the README must list every page that exists under `docs/pages/` (user-facing pages + Developer guide); no page may be listed that doesn't exist, and no existing user-facing page may be missing.
   - When in doubt about which side is correct, treat `docs/index.md` + `docs/pages/<feature>.md` as the source of truth and update the README to match.

4. **Check documentation screenshots.** A screenshot is documentation that goes stale invisibly — the prose beside it stays true while the pixels stop being. Run this whenever **Doc image files** is not `NONE`; when it is `NONE`, say so rather than staying silent. Report the counts on every run, including a clean one.

   - **Reconcile the files against the references.** List the referencing markup with `git grep --full-name -InoE '\]\([^)]+\.(png|jpg|jpeg|gif|webp)\)|src=.[^ >]+\.(png|jpg|jpeg|gif|webp)' -- ':/docs' ':/README.md' ':!/docs/plans'` and resolve each path relative to the file citing it, skipping `http` and `data:` URLs. A reference with no file is **DANGLING** — a broken image on the published site. A file no reference resolves to is an orphan *candidate*: confirm with `git grep -F <basename> -- '*.md' '*.html' '*.json' '*.xml' ':!/docs/plans' ':!/CHANGELOG.md'`, which catches the `href=` and `content=` forms the embed pattern misses (favicons, `og:image` cards, store manifests). **A prose mention is not a reference** — read the matching line before it clears anything. Those two exclusions matter: a plan doc or changelog recording that an image was *dropped* names the file, and grepping it unexcluded clears every orphan it names, turning the whole check into a silent pass. Before reporting that nothing is wrong, confirm the scan finds a reference you already know exists — a missed embed form returns a comfortable empty result forever.
   - **Classify a confirmed orphan before proposing anything about it.** No output from `git log --oneline -S '<basename>' --all -- '*.md'` means it was never referenced in any revision — wired up wrong when it was added. Output means it lost a reference it once had, which is usually a deliberate removal recorded in a commit or a plan doc. Also look for a derived twin by stem before calling anything dead: the master under `docs/` is often the source of a converted copy that a published site tree still serves, so an image orphaned in the docs can be live on the website. Report either kind; delete neither without asking.
   - **Prove staleness only for shots the diff implicates.** Map each page embedding a screenshot to its backing source by grepping the page's bolded and code-formatted terms over the source tree — filename tokens and co-change history rank candidates, they are not evidence. When a page's backing files appear in **Diff summary**, Read the screenshots that page embeds and check the code two ways: every literal visible in the shot still exists in source, and every set the source enumerates — menu items, tabs, status labels — appears in the shot in full. Scope the grep with `':!*.md' ':!docs' ':!CHANGELOG.md'`; unscoped, it hits the changelog entry describing the removal and reports a false negative. A missing literal, or a set the shot shows only part of, is **STALE** — name the commit with `git log -S`, ordering same-day commits by `git merge-base --is-ancestor`, never by date.
   - **Only strings this repo renders are evidence.** A frame containing third-party UI — a mail client, a game table, the IDE's own menus, whatever runs inside a terminal pane — holds stable text that will never appear in this source, and reading its absence as proof produces a confident false positive on exactly the projects whose screenshots must not be re-shot. Where the frame is not wholly this project's UI, report `NOT CHECKED (third-party UI in frame)` and prove nothing. Making the check work there takes one hand-written line in that project's `CLAUDE.md` naming the source trees that own the strings — propose it, never guess it.
   - **No verdict from a date.** File mtime is the checkout time and is identical across the whole tree; commit age says only that the codebase moved on. Neither is evidence of anything about an image.
   - **When a shot is stale, sweep its neighbourhood** before reporting: its alt text and caption, the prose describing it, every other page embedding the same file, sibling shots of the same screen, and any second copy under a published site tree — a `site/` or equivalent directory with its own derived images and its own `<figcaption>` text, which goes stale independently of the image it captions. Say whether that tree was scanned. Do not compare a master's dimensions against a derived copy's; deliberate re-crops make that a permanent false positive.
   - **Report three verdicts and the size of the haystack** — `STALE` with its proof, `NOT CHECKED` with its reason, and a count of the images only inventoried. Give the reach in one sentence: which directories were scanned, which images were opened rather than listed, and that this check reads text, so it can prove a shot stale and can never prove one current.
   - **Replacing a stale shot: the user takes the picture, this step does the rest.** Never capture, and never launch an app, a server or a browser to try. On approval, take the replacement the user shot — with nothing attached, the newest PNG on their Desktop — compare its dimensions against the file it replaces with `file <path>` and raise a mismatch before going further, copy it into place, then run the neighbourhood sweep above so the caption, alt text and prose move with it. Do not overwrite the committed image until the replacement is in hand and accepted.
   - Do not restate layout or markup rules here — `~/.claude/skills/github-pages/SKILL.md` owns the `docs/screenshots/` location, the per-page relative-path table, and the hero-versus-inline image markup. Consult it when a screenshot has to be added, moved, or re-pathed.

5. **Read `CLAUDE.md`** (project-local `.claude/CLAUDE.md` if it exists, otherwise repo root) and fix any stale file descriptions

6. **Check comments and docstrings** in modified source files (use **Uncommitted changes** and **Full diff** to identify them) that reference changed behavior

7. **Update dimensioned drafts** — only if the repo keeps drafts (Glob `**/dimensioned_drafts/*.py` outside ignored dirs; skip this step when nothing matches). Drafts are documentation of model geometry: when a model source file changed in the diff, find the draft scripts that document it (match by model name/directory and by constants mirrored from the model's dimensions class) and check every drawn value — dimensions, profile vertices, removed/added features, not just labels. Update the draft script to the current model, re-run it to regenerate the SVG, and include both files in the change set. A draft documenting a feature the model no longer has is stale documentation just like prose.

8. **Suggest improvements** — if documentation would benefit from a new file or reorganization, suggest it to the user and wait for approval before proceeding

9. **Report** what was updated. If nothing was stale, say so. Call out README ↔ `docs/index.md` mismatches explicitly, even when fixed.

## Out of scope

- Do NOT touch code logic — only comments, docstrings, and doc files
- Do NOT create new documentation files or restructure existing ones without explicit approval
- Do NOT capture, crop, resize, recompress, retouch, or delete an image file, and do NOT start a server, launch an app, or drive a browser to produce one — report the stale, orphaned, or dangling ones and let the user decide
- Do NOT add a screenshot flag, demo mode, or seed-data hook to the product to make a capture easier
