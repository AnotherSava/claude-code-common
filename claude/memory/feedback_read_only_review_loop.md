---
name: feedback_read_only_review_loop
description: Run adversarial review read-only, and answer findings by deleting rather than adding another gate
metadata:
  type: feedback
---

**Run the review read-only, and answer it by deleting rather than gating.** When a change set
needs adversarial review, separate *collecting findings* from *changing code*: give every
reviewer an absolute read-only constraint and let the round return a report. Mixing the two is
what stops the loop converging. Over eight rounds on one feature the reviewers found real
defects every time, and three times the blocking defect was something introduced by the previous
round's *fixes*. Oleg named it directly: "i'm worried that you try to avoid review; why not run
read-only review - to collect feedback without any changes?" The first read-only round found
five defects that seven mixed rounds had missed.

**Why:** arguing against review-and-patch reads as arguing against review, and the objection is
worth removing rather than defending. Read-only is also strictly better evidence, because
nothing moves under the reviewers mid-round.

**How to apply:**

- Every fix that held across those rounds was a **deletion or a revert**; every one that broke
  something was a **new mechanism**. When a finding lands, ask first whether something should
  come *out*.
- **A gate added per objection is the failure mode**, not the remedy. Three rounds were spent
  adding one guard per complaint; the round that converged replaced the rule instead.
- **A safety net placed inside the path it guards shares that path's bug.** One backstop was
  written to bound a clearing defect, stamped its evidence on the very branch that refuses to
  clear, and so cleared exactly what that branch protects.
- **Prefer measurement to argument where the question is empirical.** The two worst defects were
  never-fires that no reviewer caught and a live probe found in minutes; running the thing
  settled in seconds what static review had been approximating for rounds.

See [[feedback_instrument_first_fragile]] for the sibling rule about capturing a repro before
shipping a speculative fix.
