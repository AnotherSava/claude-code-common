---
name: feedback_realism_before_hardening
description: Before building for an edge case a review found, rate how realistic it is; a rare scenario that is harmless or cheap to handle by hand is reported with its rating and gets at most a warning or a doc sentence — not code
metadata:
  type: feedback
---

**Before building for an edge case a review found, rate its realism.** Who hits it — a known
writer, a user report, a documented path? What does it cost when unhandled? A scenario that is rare
**and** harmless or cheap for the user to handle by hand is still reported, with its rating, and
gets at most a log warning or a sentence in the docs, never code. Code is for data loss, crashes,
lost or duplicated core output, and leaks of the user's own identity.

**Why:** seen 2026-09-26/27 in achievement-overlay. Eight fix-and-review rounds each ended with a
fresh "found and not fixed" list, the user said "y" to each next round, and the fixes added about
2,500 lines of source and tests: a watcher retarget for a sub-second window, millisecond timestamps
no emulator writes, network-share paths, junction detection. The user judged two scenarios
impractical. On a game with folders in two GSE Saves paths, whose redesign had been parked, they
said "it feels like not a practical scenario — should we just add a warning", and the warning that
replaced it gained junction detection. On games installed on a network share they said "if 1 out of
1000 users does this, and it happens that they need to file a report, and it happens that they want
to hide that particular game — they will just remove it by hand". Then they asked "are there any
other weird use cases you've build logic around?". An audit against that standard removed about a
thousand of those lines again.

**How to apply:**
- Every "found and not fixed" list carries a realism rating per item (common / plausible / rare /
  theoretical) and what goes wrong if it stays unhandled. Present it as a triage, not a to-do list.
- Don't offer "run another round" by default when what is left is rare; say the rest is edge cases,
  and name the ones worth code.
- A reviewer confirming that the code mishandles a scenario is not evidence that anyone will be in
  it. Ask for the writer or the report before building.
- **Realism rates an edge case, never a duplication.** A rare scenario earns a warning instead of
  code because the scenario is what costs little. Two copies of one function cost whatever the next
  divergence costs, whoever hits it, so "the divergence is unreachable today" does not license
  parking the consolidation — it is what makes consolidating cheap and safe right now. Seen
  2026-10-09: three sites resolved a project root by two different rules, the divergence measured
  unreachable on every configured project on this machine, and it was offered as a memo on exactly
  that ground; the user asked "why don't we consolidate it right away", and one shared function plus
  a seven-case test replaced all of it. CLAUDE.md's **Single Source of Logic** governs that call,
  not this memory.
- This narrows [[feedback_loud_errors]] beside its self-healing exception: a rare case that is cheap
  to handle by hand gets a log line and a docs sentence without the in-UI error row. Loud surfacing
  still applies to a failure the user cannot notice and act on, and a case whose unhandled path
  would silently lose or corrupt core output is not harmless — it belongs in the code list above.
- **A rare case may fail fast, but only with its explanation in the log.** Ending startup or
  throwing on a rare bad input is acceptable when the log names what was wrong and where — the
  setting and the entry, not a framework message through a stack trace. Check it by producing
  the failure and reading the line. Seen 2026-09-28 in achievement-overlay: a path entry whose
  variable expanded to spaces logged only `ArgumentException: The path is empty` through a
  getter's stack; the user's bar was "fail fast is ok if log contains enough details to explain
  it", and the check moved into config validation, which names both.

**When review rounds stop shrinking, triage against practice before fixing.** On 2026-09-28 four
adversarial rounds over the docs-relevance skill confirmed 9, 23, 21 and then 31 findings: each round
reviewed code the previous fixes had added, so the count never converged. Checking each finding with
the session that actually ran the tools, and against its transcript, sorted the 31 into real ones a
committed frame or a real caller hits, cheap ones, and theoretical ones no caller reaches — one of
whose proposed repairs would have broken a committed capture step. So after a second round that does
not shrink, classify every finding as fix / theoretical / wrong against real callers, committed
artifacts and the owning session's own record; fix the real ones, and memo the theoretical ones with
their evidence instead of hardening against them.

**An automated review-and-fix loop counts as presenting findings, so the gate goes into its prompts.**
A workflow that verifies and fixes on its own shows its findings to nobody, which is the one moment the
rest of this memory is written for, and its subagents see this memory only as one index line in
`CLAUDE.md` — an explicit prompt saying "fix these confirmed defects" overrides it. So the verify
prompt asks for evidence that something reaches the case and rates frequency and cost, the fix prompt
receives what earns code plus the rare cases with an instruction to add only a log line or a doc
sentence, and the loop stops when a round finds nothing that earns code. The verify prompt also asks
whether the finding is a duplication, and that flag sends it to the fix list whatever its frequency and
without waiting for anything to reach the divergence — the copies are in the source either way —
so *Realism rates an edge case, never a duplication* applies where nobody is reading the list either;
the fix prompt tells the fixer to answer such an item with one definition every site calls rather
than by patching the copies. Run such loops
through the saved `review-and-fix` workflow (`claude/workflows/review-and-fix.js`, called as
`Workflow({name: "review-and-fix", args: {scope, lenses, context, gate}})`), which carries all of it and
returns the triage table to present. The `workflow-realism.py` hook warns when a workflow's inline
script, or the file a `scriptPath` run names, fixes findings and mentions none of `frequency`, `reached_by` or `review-and-fix`; any
mention of those words silences it, so its silence does not prove a realism gate exists. Seen 2026-10-02 in tauri-dashboard: 8 workflows, 347 agents and 10 review
rounds confirmed 125 findings, 85 of them rated low, and coded every one; a post-review found the
fixes had bloated the prompt-origin code and parts of the label and attention code. Its verify prompts
refuted only what "cannot happen, is already handled, or is a deliberate documented limit" — truth,
never realism.

Related: [[feedback_complexity_may_be_self_imposed]], [[feedback_no_defensive_fallbacks]],
[[feedback_check_the_limit_is_real]], [[feedback_loud_errors]].
