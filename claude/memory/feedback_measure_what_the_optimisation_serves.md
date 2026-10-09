---
name: feedback_measure_what_the_optimisation_serves
description: An optimisation's justification is a number about the data it operates on, not its mechanism — measure the thing it optimises and find its writer before defending it
metadata:
  type: feedback
---

An optimisation's justification is a number about the data it operates on, never the mechanism. Measure the thing it optimises, and find its writer, before explaining or defending it.

Measured 2026-10-09 in the trips project. A `?scope=database` parameter kept the attachment store out of the nightly backup artifact so restic could deduplicate it — one copy of each file across the retention ladder against seventeen. The mechanism was real and was described correctly twice, at length, in chat and in three code comments. The store held **0 files**, and the function that writes to it had no caller anywhere outside the restore itself, so nothing had ever been in it: the saving was zero. The split cost a second assembly shape, a second recovery procedure, a conditional sweep, an assertion in the backup script, and a commit-gate step holding the two ends in sync. The user's question — is this worth implementing several ways to back up and restore — is what forced the measurement.

**Why:** a correct mechanism carries its own conviction. "Seventeen copies against one" is true of the bytes and says nothing about whether any bytes exist, so the explanation gets more convincing the longer it goes while the premise stays unchecked. The same shape appears wherever a cache, an index, a pool or a dedup path is defended by how it works rather than by how much it holds.

**How to apply:** state the measured size of the thing being optimised in the same breath as the mechanism. Where it is empty, or has no writer, the optimisation is a bet on growth — say so, and put the condition for revisiting it next to the code so the next person finds the number instead of re-deriving the argument. Sibling of [[feedback_measure_the_composite]], which catches a measured unit multiplied by an assumed count; see also [[feedback_no_premature_abstraction]] and [[feedback_check_the_limit_is_real]].
