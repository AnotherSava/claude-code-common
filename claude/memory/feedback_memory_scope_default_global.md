---
name: Memory scope is decided by reuse, not by where it came up
description: A finding surfacing in one repo doesn't make it project-scoped; the test is whether it would help in a different repo tomorrow, and mixed findings get split
type: feedback
---
When saving a memory, the fact that something came up while working in a given project is not what makes it project-scoped. Ask instead: **would I want this while working in a different repo tomorrow?** Yes → global (`~/.claude/memory/`, indexed in `~/.claude/memory/MEMORY.md`). No → project memory. Only partly → split it.

**Why:** Misfiling in this direction fails silently. A preference stored under one project is invisible from every other, so the same correction has to be given again in the next repo, and there's no signal that a copy is sitting somewhere unreachable. Two real cases: a note on detecting the real terminal width (a Claude Code/PowerShell fact with nothing repo-specific in it) and a rule about actually running a script's non-authoring platform branch — both had been filed under a single project despite applying everywhere.

**How to apply:**
- Reclassify to global when the finding states how to work with nothing repo-specific in it, is about a tool/language/framework/OS rather than a codebase, describes the user, or still reads correctly once the project's name is deleted from it.
- Keep it project-scoped when it names that repo's files, modules, schema or deploy target, records a trade-off made for that codebase, or holds only because of its stack version or config.
- For a mixed finding, put the transferable rule global with the project detail demoted to a one-line example, and leave only the genuinely repo-specific remainder local, linked with `[[name]]`. Never write the same text to both homes — duplicated rules drift and end up contradicting each other.
- The `/reflect` skill enforces this at reflection time (its step 5, which also audits already-stored project memories); this memory covers ad-hoc saves made outside it. See [[feedback_depersonalize_memory]].
