---
name: reflect
description: >-
  Extract and persist conversation learnings before context loss.
  TRIGGER when: user runs /reflect, or before /clear or compaction.
allowed-tools: Bash(bash ~/.claude/skills/reflect/gather-context.sh), Read, Write, Edit, Glob, Grep
---

# Reflect

Extract durable knowledge from the current conversation and persist it to long-term memory. Run this before compacting or clearing context so insights are not lost.

## Context
- Current working directory: !`pwd`
- Project CLAUDE.md: !`cat CLAUDE.md 2>/dev/null || echo "(none)"`
- Project skills: !`ls .claude/skills/ 2>/dev/null || echo "(none)"`
- Global inventory (global CLAUDE.md, global memory index, current project ID + its memory index, global learnings, global skills), bundled into one permission-checked call: !`bash ~/.claude/skills/reflect/gather-context.sh 2>/dev/null || echo "(gather-context blocked — Process step 1 will fall back to the Read tool)"`

## Process

1. **Review pre-loaded context.** The Context section has two inventory sources:
   - **Project-local** (always available): project CLAUDE.md and project skills listing.
   - **Global inventory** (from `gather-context.sh`): parse the `=== global-claude-md ===`, `=== global-memory-index ===`, `=== project-id ===`, `=== project-memory-index ===`, `=== global-learnings ===`, and `=== global-skills ===` blocks. The script has already deduced the current project's mangled ID from CWD (replace `:`, `/`, `\` with `-`) and cat'd only *this* project's `MEMORY.md` — no directory scanning needed.

   If the global-inventory line starts with `(gather-context blocked …)`, fall back to loading each source manually:
   - Read `~/.claude/CLAUDE.md`
   - Read `~/.claude/memory/MEMORY.md`
   - Compute the current project ID by mangling CWD (replace each `:`, `/`, `\` with `-`), then Read `~/.claude/projects/<project-id>/memory/MEMORY.md`
   - Glob `~/.claude/learnings/*` (filenames are self-documenting; read bodies only when topic overlaps the current session)
   - Glob `~/.claude/skills/*/SKILL.md`

   Only read the full body of a specific memory, learning, or `SKILL.md` when its name suggests overlap with something in the current conversation.

2. **Use the pre-loaded project memory.** The `=== project-memory-index ===` block from Context already contains the current project's `MEMORY.md` (or `(none)` if the project has no memory yet). Individual memory files live at `~/.claude/projects/<project-id>/<memory-name>.md` — use the project ID from the `=== project-id ===` block when you need to read or write one.

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

4. **Filter ruthlessly.** Do NOT save:
   - Code patterns or architecture derivable by reading current files
   - Git history or recent changes (use `git log`)
   - Debugging solutions (the fix is in the code)
   - Ephemeral task details or in-progress work
   - Anything already captured in existing memory, learnings, or CLAUDE.md

5. **Present findings to the user.** For each proposed change, show:
   - **Category** (feedback / project / user / reference / CLAUDE.md update / skill update / learning)
   - **Destination** (which file will be created or updated)
   - **Content preview** (the actual text to be written, or a summary for long learning docs)
   - Whether it's a **new entry** or an **update** to an existing one

   Format as a numbered list. Ask: "Save these? (all / numbers / none)"

6. **Save approved items.** For each approved item:
   - Memory files: write with proper frontmatter (name, description, type), then add/update the index entry in the relevant MEMORY.md
   - Learning files: write directly to `~/.claude/learnings/<topic>.md` as long-form markdown. No frontmatter. No index update (the flat directory uses filenames as the index).
   - CLAUDE.md updates: edit the relevant section in place
   - Skill updates: edit the target `SKILL.md` in place. Keep edits minimal and consistent with the surrounding style; don't rewrite sections that aren't affected by the finding.
   - Check that no duplicate index entries or same-topic learning files are created

7. **Report** what was saved and where. If nothing was worth saving, say so — a clean conversation with no new learnings is fine.

## Important

- Never save without user approval
- Convert relative dates to absolute dates (e.g. "Thursday" to "2026-04-17")
- Use the memory frontmatter format: name, description (one-line, specific), type (user/feedback/project/reference)
- Keep MEMORY.md index entries under 150 characters each
- If a finding updates an existing memory, edit the existing file rather than creating a duplicate
- Do not save information the user explicitly asked you not to remember
