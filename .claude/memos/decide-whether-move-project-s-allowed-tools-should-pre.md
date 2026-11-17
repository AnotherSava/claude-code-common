---
created: 2026-11-08 09:37:29
---

# Decide whether move-project's allowed-tools should pre-authorize ports.py

claude/skills/move-project/SKILL.md step 4 runs python3 ~/.claude/skills/ports/scripts/ports.py list, check, check --repo and (since 2026-11-08) reads dev-use-case claims, but its allowed-tools frontmatter lists only Read, Glob and a few read-only Bash prefixes, so each ports.py call goes through the normal permission prompt. Raised by the review-auto docs-relevance polish on 2026-11-08; the gap predates that change. Decision for the user: add Bash(python3 ~/.claude/skills/ports/scripts/ports.py:*) and the Windows python variant to allowed-tools (only list/check are read-only; release and amend write the registry, so a narrower prefix per subcommand may be wanted), or keep the prompt.

Bears on the decision (added 2026-11-17): a skill's allowed-tools grant lasts only the turn that invoked the skill (claude/learnings/claude-code-auto-mode-permissions.md, under "A skill's `allowed-tools` grant lasts one turn"). An entry for ports.py pre-approves step 4's calls only if step 4 runs before move-project first waits for a typed reply; an answer given through AskUserQuestion keeps the grant, and after a typed reply the calls go through the normal permission check whatever the list says. So check where step 4 falls in a real run before adding the entry.
