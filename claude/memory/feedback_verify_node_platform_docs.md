---
name: Verify Node/platform fixes against official docs
description: Check Node deprecation list and child_process docs before defaulting to Stack Overflow workarounds like { shell: true }
type: feedback
---

Before applying a Node `child_process` or platform-specific spawn workaround, check the Node deprecation list (`https://nodejs.org/api/deprecations.html`) and the `child_process` docs for the canonical pattern. Don't default to Stack-Overflow-style "just add `{ shell: true }`" fixes.

**Why:** On 2026-04-20, while fixing a `claude-mermaid` ENOENT on Windows, I applied `{ shell: true }` without checking Node's current state. That pattern is deprecated in Node 24+ (DEP0190 — args not escaped, shell-injection risk). The user pushed back with "did you google for recommendations on what to use instead", I read the Node docs, and found the current canonical pattern is `spawn('cmd.exe', ['/c', <cmd>])`. Common workarounds can be obsolete — the easy Google answer is often from before the latest deprecation.

**How to apply:** For any fix involving `execFile` / `spawn` / `exec` or platform-specific shell-out:
1. Search Node's deprecation page for the function/option you're about to use.
2. Check the current `child_process` docs for the canonical pattern for the scenario.
3. Cite the docs URL in the commit/PR message so the reasoning survives review.
Prefer the documented pattern over community folklore — doubly so when a "common fix" is one-liner-sized and generic.
