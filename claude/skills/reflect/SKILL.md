---
name: reflect
description: >-
  Extract and persist conversation learnings before context loss.
  TRIGGER when: user runs /reflect, or before /clear or compaction.
allowed-tools: Bash(bash ~/.claude/skills/reflect/gather-context.sh), Read, Write, Edit, Glob, Grep, Bash(git rev-parse:*), Bash(readlink:*), Bash(rm:*)
---

# Reflect

Extract durable knowledge from the current conversation and persist it to long-term memory. Run this before compacting or clearing context so insights are not lost.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Current working directory: !`pwd`
- Project CLAUDE.md: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && cat "$R/CLAUDE.md" 2>/dev/null || echo "(none)"`
- Project skills: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && ls "$R/.claude/skills/" 2>/dev/null || echo "(none)"`
- Global inventory (global CLAUDE.md, global memory index, current project ID + its memory index, global learnings, global skills), bundled into one permission-checked call: !`bash ~/.claude/skills/reflect/gather-context.sh 2>/dev/null || echo "(gather-context blocked — Process step 1 will fall back to the Read tool)"`

## Working directory

`CLAUDE.md`, `.claude/skills/`, and the project memory dir derived from the project ID are all relative to **Repo root** from Context (NOT cwd — /reflect can be invoked from a subdirectory like `src-tauri/`). The bundled `gather-context.sh` already derives the project ID from the repo root; the manual fallback in Process step 1 below uses Repo root the same way.

## Process

1. **Review pre-loaded context.** The Context section has two inventory sources:
   - **Project-local** (always available): project CLAUDE.md and project skills listing.
   - **Global inventory** (from `gather-context.sh`): parse the `=== global-claude-md ===`, `=== global-memory-index ===`, `=== project-id ===`, `=== project-memory-index ===`, `=== global-learnings ===`, and `=== global-skills ===` blocks. The script has already deduced the current project's mangled ID from CWD (replace every non-alphanumeric character with `-`; see `~/.claude/skills/skill/references/claude-project-memory-paths.md`) and cat'd only *this* project's `MEMORY.md` — no directory scanning needed.

   If the global-inventory line starts with `(gather-context blocked …)`, fall back to loading each source manually:
   - Read `~/.claude/CLAUDE.md`
   - Read `~/.claude/memory/MEMORY.md`
   - Compute the current project ID by mangling **Repo root** from Context (replace every non-alphanumeric character with `-`) — NOT cwd, since cwd may be a subdirectory and would produce a nonexistent project ID. Then Read `~/.claude/projects/<project-id>/memory/MEMORY.md`
   - Glob `~/.claude/learnings/*` (filenames are self-documenting; read bodies only when topic overlaps the current session)
   - Glob `~/.claude/skills/*/SKILL.md`

   Only read the full body of a specific memory, learning, or `SKILL.md` when its name suggests overlap with something in the current conversation.

2. **Use the pre-loaded project memory.** The `=== project-memory-index ===` block from Context already contains the current project's `MEMORY.md` (or `(none)` if the project has no memory yet). Individual memory files live at `~/.claude/projects/<project-id>/memory/<memory-name>.md` — use the project ID from the `=== project-id ===` block when you need to read or write one.

   **Project memory may be version-controlled.** If `~/.claude/projects/<project-id>/memory` is a symlink (wired by `~/.claude/scripts/link-project-memory.sh`), it points into the repo's committed `<repo>/.claude/memory/`. The Write/Edit tools refuse to write through symlinks, so resolve it with `readlink` and write to the real repo path; the saved file is then committable with the rest of the work.

   **Check skills relevant to the session.** From the project-skills listing and the `=== global-skills ===` block, identify any skills the user invoked or whose scope overlaps with potential findings. Read those `SKILL.md` files so you can judge whether a finding should become a skill update.

3. **Scan the conversation** for knowledge worth persisting. Look for these categories — but only extract what is **durable** (useful in future conversations), **non-obvious** (not derivable from code or git), and **not already stored** (check against the memory indexes and learnings list from steps 1 and 2):

   **a. Feedback** — user corrections or confirmed approaches
   - "don't do X", "stop doing Y", "yes that's the right approach"
   - Include the *why* so edge cases can be judged later
   - Destination: project memory (if project-specific) or global memory (if cross-project)

   **b. Project context** — decisions, constraints, ongoing work
   - Why something was built a certain way, deadlines, who owns what
   - Things that were tried and rejected (and why)
   - Destination: project memory

   **c. User profile** — role, expertise, preferences
   - Seniority, domain knowledge, collaboration style
   - Destination: global memory (applies across projects)

   **d. References** — pointers to external systems
   - Where bugs are tracked, which dashboard to check, relevant URLs
   - Destination: project or global memory depending on scope

   **e. CLAUDE.md updates** — patterns or conventions discovered
   - New file layout, key patterns, build/test commands that changed
   - Destination: project CLAUDE.md or global CLAUDE.md

   **f. Skill updates** — feedback or workflow refinements that belong inside an existing skill's definition
   - Missed step, unclear instruction, wrong default, or a rule that should apply *every time the skill runs* (not just generally)
   - Strong signal: user corrected behavior *while running* a skill, or the correction only makes sense in that skill's context
   - Destination: the relevant `SKILL.md` (project-local or global). Prefer editing the skill over saving a feedback memory when the rule is scoped to that skill.
   - If the finding is broader than one skill, it belongs in feedback memory or CLAUDE.md instead.

   **g. Learnings** — long-form technical reference for reusable domain knowledge
   - How to do X on Windows / in framework Y / with tool Z, with code examples
   - Non-obvious behaviors discovered through trial and error (schema quirks, event-ordering, API limitations)
   - If content exceeds a paragraph or needs tables/code blocks, it belongs here rather than as memory
   - Destination: `~/.claude/learnings/<topic>.md` — topic-named, flat directory, no frontmatter, no index file
   - If an existing learning covers the same topic, update it in place rather than creating a duplicate

   The project-vs-global destinations above are a first pass, not the final call — step 5 re-checks every one that came out project-scoped.

4. **Filter ruthlessly.** Do NOT save:
   - Code patterns or architecture derivable by reading current files
   - Git history or recent changes (use `git log`)
   - Debugging solutions (the fix is in the code)
   - Ephemeral task details or in-progress work
   - Anything already captured in existing memory, learnings, or CLAUDE.md

5. **Re-check scope before anything is written project-local.** Re-examine every finding that came out **project-scoped** — memory under `~/.claude/projects/<project-id>/memory/`, or a project `CLAUDE.md` edit. Misfiling in this direction is silently expensive: a preference filed under one project is invisible from every other, so the same correction gets re-learned repeatedly and the user has to repeat themselves.

   Apply one test — **would I want this while working in a different repo tomorrow?**
   - **No** → keep it project-scoped.
   - **Yes, all of it** → make it **global**: `~/.claude/memory/<name>.md`, indexed in `~/.claude/memory/MEMORY.md`.
   - **Yes, part of it** → **split it.** The transferable rule goes global, keeping the project detail only as a one-line illustration; whatever is genuinely repo-specific stays project-local and links to the global file with `[[name]]`. Never write the same text to both — duplicated rules drift and eventually contradict each other.

   Reclassify to global when the finding:
   - states how you should work, with nothing repo-specific in it ("ask before X", "never phrase Y that way")
   - is about a tool, language, framework, OS, or service rather than this codebase
   - describes the user — role, expertise, communication style (category **c** is always global)
   - still reads correctly after deleting the project's name from it

   Keep it project-scoped when the finding:
   - names this repo's files, modules, services, schema, or deploy target
   - records a decision or trade-off made for this codebase
   - holds only because of this project's stack version, config, or constraint

   **Audit what is already stored.** Run the same test over each line of the `=== project-memory-index ===` block from Context. Read the file body before judging any entry whose index blurb is too terse to place. Raise only entries that clearly fail — leave borderline ones where they are rather than reopening the same argument every run. A promotion moves a file and rewrites two indexes, so it never happens silently: put the candidates in the step 6 gate and act only on approval.

6. **Save research findings directly; gate only feedback-derived ones.** Split the findings by where they came from, and lean toward less interactivity:
   - **Agent-research findings** — neutral technical facts and context you uncovered yourself through investigation, debugging, or trial-and-error: learnings (g), references (d), and project context (b) you discovered by reading or probing the system. **Default to saving these directly** (step 7), then reporting them — they're your own observations, not claims about the user, so an approval gate just adds friction.
   - **Feedback-derived findings** — anything that encodes what the user wants, prefers, corrected, or decided: feedback (a), user profile (c), and any CLAUDE.md (e) or skill (f) change that stems from a user correction. These change how you'll behave or assert something about the user, so present them for approval.
   - **Scope promotions** — existing project memories step 5 flagged for promotion or splitting. These move or rewrite files you did not create this session, so they are gated too, however clear-cut the call looks. A *new* finding rerouted to global by step 5 is not a promotion — gate it on its own category, as above.

   When there ARE gated findings, present them as a numbered list showing **Category** (feedback / project / user / reference / CLAUDE.md update / skill update / learning / scope promotion), **Destination** (which file will be created, updated, or moved), **Content preview** (the text to be written, or a summary for long docs), and whether it's a **new entry**, an **update**, or a **promotion** (name both the old and new home). Then ask: "Save these? (all / numbers / none)". When there are none, skip the gate — save the research findings and go straight to the report.

7. **Save the items** (auto-saved research findings and any approved gated items). For each:
   - Memory files: write with proper frontmatter (name, description, type), then add/update the index entry in the relevant MEMORY.md
   - Learning files: write directly to `~/.claude/learnings/<topic>.md` as long-form markdown. No frontmatter. No index update (the flat directory uses filenames as the index).
   - CLAUDE.md updates: edit the relevant section in place
   - Skill updates: edit the target `SKILL.md` in place. Keep edits minimal and consistent with the surrounding style; don't rewrite sections that aren't affected by the finding.
   - Promotions: write the file to `~/.claude/memory/<name>.md`, add its line to `~/.claude/memory/MEMORY.md`, then delete the project copy and remove its line from the project `MEMORY.md`. A promotion is a move — finish with the entry in exactly one index. Listed in both, it reads as two separate rules that are free to drift.
   - Splits: write the global file first, then rewrite (don't delete) the project file down to its repo-specific remainder, pointing at the global one with `[[name]]`. If nothing repo-specific survives the trim, it was a promotion — remove the project file and its index line.
   - Writing to `~/.claude/memory/` or `~/.claude/CLAUDE.md` goes through a symlink, which Write/Edit refuse. Resolve with `readlink` and pass the real path — the same rule step 2 applies to project memory.
   - Check that no duplicate index entries or same-topic learning files are created

8. **Report** what was saved and where. If nothing was worth saving, say so — a clean conversation with no new learnings is fine. List any promotions or splits separately from new saves, naming both homes, since those changed files from earlier sessions.

## Important

- Save agent-research findings (learnings, references, discovered project context) directly, then report them; only feedback-derived findings — feedback, user profile, feedback-driven CLAUDE.md/skill changes — and scope promotions of existing memories need the user's approval before saving
- Mentioning this project does not make a finding project-scoped. The test is whether it would be useful in a different repo tomorrow; if only part of it would be, split it rather than filing the whole thing locally or copying it to both homes
- Convert relative dates to absolute dates (e.g. "Thursday" to "2026-04-17")
- Use the memory frontmatter format: name, description (one-line, specific), type (user/feedback/project/reference)
- Keep MEMORY.md index entries under 150 characters each
- If a finding updates an existing memory, edit the existing file rather than creating a duplicate
- Do not save information the user explicitly asked you not to remember
