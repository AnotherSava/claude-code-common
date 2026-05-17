---
name: generalize-global-skills
description: Generalize a too-specific global skill rather than forking a project-local one with the same name — name collisions silently load the wrong skill body
metadata:
  type: feedback
---

When a global skill (`~/.claude/skills/<name>/SKILL.md`) is too tied to one project type, **generalize the global in place** rather than forking a project-local copy at `.claude/skills/<name>/SKILL.md`.

**Why:** project-local and global skills with the same name collide. The harness silently picks one (observed in May 2026: when both `release` skills existed, the global won every time the user invoked `/release`). The "wrong" SKILL body loads, the user can't tell which one ran without inspecting the loaded markdown, and the project-local variant is effectively dead code.

**How to apply:** before writing a project-local SKILL.md that duplicates an existing global skill's name (`release`, `deploy`, `build`, etc.), try the **deploy skill's dispatch pattern** instead — it's the canonical model in this dotfiles repo:

1. **Context section runs project-type probes** — `test -f manifest.json`, `ls src/*.csproj`, `test -f Cargo.toml`, etc. — and exposes each result as a named field.
2. **Step 1 picks the matching flow** based on the flags. Errors loudly with an "add a new branch if your stack isn't here" message if none match. Asks the user when multiple match.
3. **Stack-specific behavior inlined** in the remaining steps — different defaults, different env-key prompts, different version-source files, different release-notes sections.
4. **Heavy per-stack work delegated** to underlying scripts in `~/.claude/skills/<name>/scripts/<TARGET>.sh` if the lifting is mostly bash (deploy does this). For instruction-heavy skills (release), inline branching is fine — no scripts needed.

Only fork project-local if the skill is **genuinely project-specific** — a project's bespoke workflow with no parallel in other projects, where shoving it into a global with dispatch would be more confusing than helpful.

Pattern reference: `~/.claude/skills/deploy/SKILL.md` for Context-probe-and-dispatch (Tauri / IntelliJ plugin / .NET branches), and `~/.claude/skills/release/SKILL.md` for the same applied to release tagging (Chrome extension / .NET branches).
