---
name: feedback_clone_folder_matches_repo
description: Name every local clone's folder after its GitHub repo; fix a mismatch by renaming with /move-project, never by aliasing in the relay
metadata:
  type: feedback
---

A local clone's folder is named after its GitHub repo, on every machine. Cross-machine agent messaging addresses a project by folder name, so two clones under different names cannot reach each other. When they differ, rename the folder with `/move-project`, which carries the Claude Code history, memory and dashboard row. Do not build aliasing (display-name or origin-URL matching) in the relay instead.

**Why:** decided 2026-10-06. A display-name fallback was built in the dashboard relay, verified live, reviewed and withdrawn: each alias scheme added failure modes, and renaming makes the folder-name assumption true instead of working around it. The dashboard-side record is `relay_target_aliasing_rejected.md` in the dashboard repo's project memory (`.claude/memory/`).

**How to apply:** when a post-push pull or a relayed message is refused `unknown_project` because the two clones are named differently, propose a `/move-project` rename of the clone whose folder differs from the repo name, run from that project's own session.
