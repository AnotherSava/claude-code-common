---
name: feedback-no-permanent-logic-for-one-time
description: Don't add durable production surface (flag, helper, export, class, branch) to serve a one-time operation — do it as a throwaway and delete it
metadata:
  type: feedback
---

Don't grow a tool's permanent interface to handle a one-off. If a task runs once — a data backfill, a migration, seeding a couple of records — do it with a throwaway script/command and delete it. Don't add a flag, helper, export, or branch to production code that then lives forever to serve a single run.

**Why:** Twice in one day (2026-06-26) I added durable surface for an ephemeral need — production logic for a one-time data-setup task in a project, and an `--at "<ts>"` override on the `/memo` helper purely to backfill two existing memos. I justified the `--at` flag with "single source of logic," but that principle governs *durable parallel call sites*, not a one-time task. A throwaway that duplicates a few lines and is then deleted has zero drift risk precisely because it doesn't survive; permanent surface does. Reaching for a durable-code rule to rationalize durable surface for an ephemeral job is the tell.

**How to apply:** Before adding a flag/param/helper/export/branch, ask "is this serving a recurring need, or just this one run?" If one run: script it inline or in scratch, execute, delete — the persistent artifact is the *result* (the backfilled file, the seeded rows), not the tool that made it. "Handy for future backfills/imports" is speculative (YAGNI); wait for the second real instance to justify durable surface. Related: [[feedback-no-premature-abstraction]] (don't abstract on one example) and [[feedback_research_to_production_cleanup]] (delete helpers whose rationale lives in docs).
