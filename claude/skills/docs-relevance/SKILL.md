---
name: docs-relevance
description: >-
  Check that a project's documentation still matches the code and that what should be documented is.
  TRIGGER when: /wrap-up runs it as a clean-up pass, or the user asks whether the docs are stale, out of date, or missing a feature.
  DO NOT TRIGGER when: the task is how a document is written rather than whether it is true — that is `docs-style` — or the question is whether the screenshots are current, which is `screenshot-relevance`.
user-invocable: false
context: fork
effort: medium
background: true
allowed-tools: Read, Edit, Write, Bash(python ~/.claude/scripts/worktree-sandbox.py:*), Bash(cd:*), Bash(git add:*), Bash(git diff:*), Bash(git status:*), Bash(git rev-parse:*), Bash(git ls-files:*), Bash(git grep:*), Bash(git log:*), Bash(cp:*), Bash(ls:*), Bash(mkdir:*)
---

<!--
This skill runs as a backgrounded forked subagent, which has three consequences its steps must respect.

A fork starts with a fresh context: it gets this file and CLAUDE.md, and sees nothing of the conversation
that invoked it. Every step below therefore derives what it needs from the repository, never from what was
discussed. A step that needs the conversation does not belong here.

A background fork runs with a narrower tool set than a normal turn, and `Grep` and `Glob` are not in it —
measured 2026-09-30. Use `git grep` (add `--untracked` to reach new files) and `git ls-files` instead; a
step written around the missing tools loses itself silently rather than failing. `allowed-tools` above no
longer lists them for that reason.

Edits made here land outside the session's checkpoints, so `/rewind` will not undo them. That is why
step 0 moves the work into a sandbox and this skill never writes to the user's tree at all.
-->


# Update Documentation

Scan project documentation and comments for references that no longer match the code, and fix them.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Uncommitted changes: !`git status --short`
- Diff summary: !`git diff --stat $(git rev-parse -q --verify HEAD || echo 4b825dc642cb6eb9a060e54bf8d69288fbee4904)`
- Full diff: !`git diff --no-textconv $(git rev-parse -q --verify HEAD || echo 4b825dc642cb6eb9a060e54bf8d69288fbee4904)`
- Code in unpushed commits (empty when there is none; read it with `git log -p --no-textconv HEAD --not --remotes`): !`git log --stat --oneline HEAD --not --remotes`
- GH Pages index present: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && test -f "$R/docs/index.md" && echo yes || echo no`
- Remotes, nothing above `(end of remotes)` meaning none: !`git remote -v; echo "(end of remotes)"`

## Working directory

Read `~/.claude/skills/shared/forked-sandbox.md` before anything else, with `docs-relevance` as `<name>`. Its Working directory section governs every path below.

## Process

**First, read the project's own guidelines, and let them override any step below.** A project `CLAUDE.md` — `.claude/CLAUDE.md` where it exists, otherwise the one at the repo root — is the only place a repo can say how it wants to be documented, and this skill has opinions that a repo is entitled to refuse, such as that a features list should exist. Those are defaults, not requirements. Where the project says otherwise, the project wins, and the step is skipped rather than argued with.

Say in the report which of its rules applied, so a skipped step reads as a decision already taken rather than as a check that quietly did not run. Step 4 reads the same file for staleness — that is a different job, and finding a rule here does not excuse checking whether the rest of it is still true.

**Documentation another account owns is reported and nothing else.** Read **Remotes** from Context: an `upstream` pointing at an account that is not the user's marks a fork, and an `origin` that does marks a clone of someone else's project, where every file is upstream's. The files that account wrote are not this skill's to edit, so a comment that omits a field there is reported in step 8 and left alone — no patch for it, and **no memo**, because the backlog is work this repo has undertaken and upstream's documentation is not it. Two exceptions, where the finding is really the user's: the gap touches a change they carry on their own branch, or it belongs to an issue they have already raised upstream. Anything else reaches upstream only as an issue they ask for, so never offer one unprompted and never open the offer by proposing a memo. The project's own code and the user's own docs are checked as written in every step below; it is only the verdict on an upstream-owned file that stops at reporting.

**An upstream-owned file is not examined for refinement at all, so nothing of that kind is reported either.** A finding nobody here can act on is not free: it reaches the caller, gets carried into the next `/wrap-up`, and is dispositioned `drop` there — every time, on the same files, because nothing about them changes. So in a fork, a finding in upstream's documentation that nobody here can act on is passed over rather than written up: prose that could be tighter, a flag upstream documents and has since removed. Note that the second is false rather than merely unpolished, and still goes — falsehood is not the axis, because a falsehood about upstream's own code returns identically on every future run and can only ever be dropped, exactly like the unpolished prose. Step 8 names the directories skipped on this ground and gives no findings from inside them. **What still gets reported is the class the user can act on here: documentation this repo's own diff has made false.**

0. **Work in a sandbox**, as step 0 of `~/.claude/skills/shared/forked-sandbox.md` says.

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

4. **Read `CLAUDE.md`** (project-local `.claude/CLAUDE.md` if it exists, otherwise repo root) and fix any stale file descriptions

5. **Check comments and docstrings** in modified source files (use **Uncommitted changes** and **Full diff** to identify them) that reference changed behavior. A `TODO` or `FIXME` in a modified file whose described work the code now does is stale too: remove it, or rewrite it to the part still undone.

6. **Update dimensioned drafts** — only if the repo keeps drafts (`git ls-files -- '*dimensioned_drafts/*.py'`, which lists tracked drafts and so skips ignored dirs by construction; skip this step when it prints nothing). Drafts are documentation of model geometry: when a model source file changed in the diff, find the draft scripts that document it (match by model name/directory and by constants mirrored from the model's dimensions class) and check every drawn value — dimensions, profile vertices, removed/added features, not just labels. Update the draft script to the current model, re-run it to regenerate the SVG, and include both files in the change set. A draft documenting a feature the model no longer has is stale documentation just like prose.

7. **Suggest improvements** — if documentation would benefit from a new file or reorganization, suggest it to the user and wait for approval before proceeding

8. **Report** what was updated, with the patch path. If nothing was stale, say so. Call out README ↔ `docs/index.md` mismatches explicitly, even when fixed.

   **Mark every claim this run could not check, not only the paths.** A cross-repo *pointer* is the easy one to notice, because a missing file is visibly a thing the sandbox cannot see. A sentence asserting how another repo's code *behaves* is the same unverifiable claim wearing prose, and it reads as settled fact in the patch — so it goes out under the same flag, naming what would settle it. The word a document already uses is not evidence either: carrying it forward is how an unchecked claim acquires a second source. Measured 2026-10-01: a patch rewrote a docstring to say the dashboard recognises a relayed turn by "a preamble it minted", flagged the `classification.md` path beside it as unverified, and said nothing about the mechanism — which was wrong, reached a pushed commit, and took one `grep` for the constant to settle once anybody looked.

## Out of scope

- Do NOT touch code logic — only comments, docstrings, and doc files
- Do NOT patch, or memo, a documentation gap in a file the project's upstream owns, except where it belongs to a change the user carries on their own branch or to an issue they have already raised. Report a gap that makes upstream's documentation false about this repo's own diff and stop there; raise one upstream only when the user asks
- Do NOT examine an upstream-owned file for refinement at all, and do not report what such an examination would have found
- Do NOT create new documentation files or restructure existing ones without explicit approval
- Do NOT check screenshots — that is `screenshot-relevance`, which `/wrap-up` runs on its own verdict
