---
name: review-auto-revert-and-agent-type
description: review-auto keeps a whole polish revert and the default agent type, both decided 2026-11-18; don't re-propose either without a new measurement
metadata:
  type: project
---

Two review-auto suggestions were put to the user on 2026-11-18 and declined.

- **Per-file polish revert:** declined. A clean-code edit can span files, such as a rename, so reverting only the
  file a failing finding names can leave the tree broken. The polish still reverts whole.
- **A slimmer agent type for reviewers and verifiers:** deferred. Custom agent types still load the global
  `CLAUDE.md`, and the built-ins that skip it, such as Explore, would review without its rules. After the CLAUDE.md
  cut a fresh agent's first request was 47.7k tokens (`claude/learnings/claude-code-subagent-context-cost.md`).

**How to apply:** raise either again only with a measurement the 2026-11-18 one did not have.
