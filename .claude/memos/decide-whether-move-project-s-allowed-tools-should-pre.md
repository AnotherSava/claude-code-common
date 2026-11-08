---
created: 2026-11-08 09:37:29
---

# Decide whether move-project's allowed-tools should pre-authorize ports.py

claude/skills/move-project/SKILL.md step 4 runs python3 ~/.claude/skills/ports/scripts/ports.py list, check, check --repo and (since 2026-11-08) reads dev-use-case claims, but its allowed-tools frontmatter lists only Read, Glob and a few read-only Bash prefixes, so each ports.py call goes through the normal permission prompt. Raised by the review-auto docs-relevance polish on 2026-11-08; the gap predates that change. Decision for the user: add Bash(python3 ~/.claude/skills/ports/scripts/ports.py:*) and the Windows python variant to allowed-tools (only list/check are read-only; release and amend write the registry, so a narrower prefix per subcommand may be wanted), or keep the prompt.
