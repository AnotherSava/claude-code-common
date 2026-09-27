---
name: v9-stocktake-inventory-only
description: v9's commit-gate question is preceded by an inventory and nothing runs before it; running the candidates first was tried and rejected on 2026-09-26
metadata:
  type: project
---

v9's commit-gate question is preceded by an inventory (build step, tests, linters, workflows,
verifiers, each with its exact command and source) and nothing runs before it. Running the
candidates first was drafted on 2026-09-26 at a peer's suggestion and dropped by the user. Three
adversarial review rounds found 12, 11 and 11 defects, nearly all in the running: publish steps
that ship, `prettier --write` rewriting files into the adoption commit, `npm ci` under a dev
server, servers that never exit, snapshot gaps on a dirty tree, concurrent walks.

**Why:** every automatic run needed a safety rule per repo shape, and the count wasn't falling.
The existing Afterwards step already runs the chosen gate before any commit.

**How to apply:** don't re-propose running the candidates before the question. Show a broken
toolchain as inventory (tool versions, a missing wrapper). The git technique the runs would have
needed is in `claude/learnings/git-snapshot-dirty-tree.md`.
