---
name: memory-index-single-source
description: Why CLAUDE.md's global memory list is generated from claude/memory/MEMORY.md, and the two alternatives rejected on 2026-09-15
metadata:
  type: project
---

`claude/memory/MEMORY.md` is the single authored index of every global memory; the list inside
CLAUDE.md's `## Global Memory` section is generated from the entries marked `{always}` by
`claude/scripts/render-memory-index.py`, and `.claude/commit-checks.sh` fails on a stale block.

The problem it replaced, measured 2026-09-15: the two indexes were both maintained by hand and had
drifted to 68 entries in CLAUDE.md against 141 in MEMORY.md, sharing only 16 — and of those 16, seven
disagreed on wording. CLAUDE.md is injected into every session; nothing reads MEMORY.md except
`/reflect`'s `gather-context.sh`. So the 125 entries that existed only in MEMORY.md never reached a
session at all, and the 52 that existed only in CLAUDE.md were invisible to `/reflect`'s
already-stored check, which is how one rule gets written twice under two names.

**Two alternatives were considered and rejected**, so they do not need re-deriving:

- **`@`-importing MEMORY.md into CLAUDE.md**, giving one file and no generator. Rejected on two
  counts: it puts the whole index — then ~40 KB against the block's 15 KB — into every session, and
  no CLAUDE.md in this repo has ever used an `@`-import, so the mechanism was unverified at the
  moment of choosing. If the context cost ever stops mattering, this is the simpler design and is
  worth re-testing rather than dismissing.
- **Keeping two hand-maintained tiers plus a drift checker.** Rejected because it detects the
  divergence instead of preventing it, and leaves the unmarked majority still never firing.

The `{always}` marker is the only per-memory decision: it buys presence in every session at roughly
200 bytes each, and leaving it off still leaves the memory findable by anything that reads the index.
See [[project-memory-versioning]] for the separate question of how *project* memory is stored.
