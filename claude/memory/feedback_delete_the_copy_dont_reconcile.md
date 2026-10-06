---
name: feedback_delete_the_copy_dont_reconcile
description: when one value lives in two places, delete a copy instead of building a comparison and an adoption record; the absence of the copy is then the check
metadata:
  type: feedback
---

When one value lives in two places and they can disagree, delete a copy rather than building
something that compares them. A checker over both stores, plus a record of who reconciled them last,
is apparatus around a duplication that should not exist — and once the copy is gone its absence is
the check.

**Why:** 2026-10-05, building the ports registry. A dev port sat in both the registry and the
project's own `package.json -p` flag with nothing reconciling them. The proposal was a convention
version recording that each repo had been reconciled, plus a widened comparator to keep checking. The
user replaced both: *"if port will never be hardcoded, but requested from a script instead, it would
be an easy check if port was allocated or not."* Resolving it at launch leaves no second copy, so the
check is a grep and the adoption record has nothing to record.

**How to apply:** Before writing a comparison between two stores of one value — or a flag, version or
timestamp saying which was last reconciled — ask whether the second store can read the first at the
moment it needs the value. Where it can, delete it: the check becomes "is there a copy here at all",
which holds no state and cannot pass vacuously. Where a copy genuinely cannot go (a number fixed by
an outside party, a compiled-in default, prose a human reads), declare each one with its reason in
the single source so the check allows exactly those. The Explicit State rule in `CLAUDE.md` is the
same move one size down: split a field rather than adding a discriminator for which meaning it holds.
Related: [[feedback_no_permanent_logic_for_one_time]] on apparatus built for a single run, and
[[feedback_not_run_is_not_pass]] on why a check with state can report a pass it never earned.
