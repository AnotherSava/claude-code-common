---
name: live-values-source-of-truth
description: Live/mutable values (rates, prices, config, deployed state, secrets) — read them from the running system; never quote a document's number for a live value as if current
metadata:
  type: feedback
---

Classify a fact before citing it, and read *live* facts from the system — never quote a document's number for a live value as if it were current.

**Why:** I cited a draft decision brief's PLA price ($150/kg) as the current *prod* price. The real value lives in the DB and had changed (dev was $105). A document is only a **snapshot** of anything that can change without a git commit — treating the snapshot as current is how stale numbers get asserted as fact.

**How to apply:**
- **Live** — changes without a commit → source of truth is the **running system**. Rate cards / prices / tax, stock & availability, admin settings, the deployed commit, runtime config, secret *values and locations*, DNS. To answer a question about one, **read the live source** — a DB query, `curl` the live page, `doppler`, `git`/ssh on the box — or explicitly hedge: "as of <date>, per <doc> — may have changed."
- **Settled** — a doc *can* be authoritative: architecture and *why*-we-chose-X decisions, fixed reference sets, past incidents/history.
- **Heuristic:** if a value can change without a git commit, a document is only a snapshot of it — go read the live source.
- **Your own earlier probe is a snapshot too.** A reading of live state expires — re-take it before asserting it, especially late in a long session. Real case 2026-09-14: an adapter listing taken 25 minutes earlier was cited as "the VPN is disconnected"; it had connected in between, and the user had to correct it. Re-running the one-line check costs nothing.
- **A third-party tool's capabilities are live too, and your own notes are the snapshot.** Real case 2026-09-18: a local reference said the hook `if` field had no form for matching a Bash command, and a design was recommended against on that ground; the upstream docs carried a whole Bash matching table. Read the vendor's current docs before concluding a capability does not exist — a feature set changes with no commit to your repo.
- A "decision brief" / "calibration" / "seed values" / "current values" doc holds *inputs to a choice*, not the resulting live state; its numbers were meant to be superseded. Mark such docs point-in-time with a pointer to the live source of truth.

Close cousins: [[feedback_no_guessed_facts]] (guess-vs-known) and [[feedback_verify_before_justifying]].
