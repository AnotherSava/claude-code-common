---
name: recover-context-from-jsonl
description: After a forced /clear (e.g., persistent image-API error), recover prior conversation from ~/.claude/projects/<id>/*.jsonl session logs
metadata:
  type: reference
---

Claude Code session transcripts are persisted at `~/.claude/projects/<project-id>/*.jsonl` — one file per session. When `/clear` was forced (e.g., a persistent "API Error: 400 Could not process image" that survived across turns), reconstruct the prior context by parsing those JSONL files.

**Project ID format:** the working directory mangled by replacing each `:`, `/`, `\` with `-`. Example: `D:\projects\chrome-assistant` → `D--projects-chrome-assistant`.

**How to apply:**
1. List the project's `.jsonl` files sorted by mtime to identify the immediately prior session (the most recent one whose mtime is *before* the current session start).
2. Parse line-by-line. Filter on `type === 'user'` / `type === 'assistant'` and `Array.isArray(message.content)`; pull `part.text` from text parts; skip `image` parts and large `tool_result` blobs.
3. Print in chronological order (entries are already in order in the file). For long sessions, slice the tail to see what was being worked on at the end.

**Why:** Lost the entire icon-design conversation on 2026-05-11 to a persistent image-processing error. Recovered all decisions (variant choice, halo geometry, name pick, file inventory) from the prior session's JSONL.
