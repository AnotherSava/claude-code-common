---
name: feedback_delete_the_copy_dont_reconcile
description: when one value lives in two places, delete a copy instead of building a comparison and an adoption record, then assert that the consumer asks the source — absence on its own is half a check
metadata:
  type: feedback
---

When one value lives in two places and they can disagree, delete a copy rather than building
something that compares them. A checker over both stores, plus a record of who reconciled them last,
is apparatus around a duplication that should not exist — and once the copy is gone, what remains to
check is that the consumer asks the source for the value.

**Why:** 2026-10-05, building the ports registry. A dev port sat in both the registry and the
project's own `package.json -p` flag with nothing reconciling them. The proposal was a convention
version recording that each repo had been reconciled, plus a widened comparator to keep checking. The
user replaced both: *"if port will never be hardcoded, but requested from a script instead, it would
be an easy check if port was allocated or not."* Resolving it at launch leaves no second copy, so the
check reads the repo and the adoption record has nothing to record.

**How to apply:** Before writing a comparison between two stores of one value — or a flag, version or
timestamp saying which was last reconciled — ask whether the second store can read the first at the
moment it needs the value. Where it can, delete it.

**Then assert what replaced it, because absence is only half a check.** "There is no copy here" is
also what a consumer that was never wired up looks like, so a check reading absence alone passes the
one case it exists to catch. The second half is positive: this consumer asks the source for the value.
Measured 2026-10-05, in the ports rule written from this very memory — it reported zero port literals
for two projects whose port resolved nowhere at all, taking a framework default and drifting on a
collision, which is worse than the copy it was looking for. Read the positive half off the single
source rather than guessing from the consumer: the registry already knew which repos it assigned a
port, so the question "does this repo fetch it?" had a defined set to ask about, while "does this
script need a port?" had no answer a rule could reach.

Where a copy genuinely cannot go (a number fixed by an outside party, a compiled-in default, prose a
human reads), declare each one with its reason in the single source so the check allows exactly those.
The Explicit State rule in `CLAUDE.md` is the same move one size down: split a field rather than adding
a discriminator for which meaning it holds.
Related: [[feedback_no_permanent_logic_for_one_time]] on apparatus built for a single run, and
[[feedback_not_run_is_not_pass]] on why a check with state can report a pass it never earned.
