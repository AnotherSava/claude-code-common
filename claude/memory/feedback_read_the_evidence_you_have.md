---
name: feedback_read_the_evidence_you_have
description: Before proposing a cause, read the evidence already in hand — output you captured but never printed, the log the failing thing wrote for exactly this purpose, and output you produced earlier in the same session
metadata:
  type: feedback
---

A root cause is something you **read**, not something you construct. Before offering one, spend the
cheap move: look at the evidence already in hand. Three sources get skipped, and all three were sitting
there during the same failure.

- **Output you captured and never printed.** `subprocess.run(..., capture_output=True)` then logging
  only the return code is the canonical form. The error was in the variable.
- **The log the failing thing wrote for exactly this purpose.** A script that fails closed usually says
  *why* — and a script written for a scheduler says it in a **file**, not on stderr, because stderr is
  discarded where it runs. So empty streams beside a non-zero exit are a hint to go read the log, not
  evidence that the failure was silent.
- **Output you produced earlier in the same session.** The answer is often already in your own scrollback,
  from a probe run for a different reason.

**Why:** on 2026-09-03 I reported a root cause three times from inference — a nested credential wrapper,
then a package-layout theory — and got it only by running `uname -a` inside the process that failed,
which settled it in one command. Both wrong causes were confident and plausible, and the second one
propagated: a peer wrote code against it. Throughout, the drill script held the captured stdout and
stderr I never printed, and the project's own log file held the literal sentence naming the cause.

**How to apply:** when something fails, ask what the failing thing already told you before asking what
might be true. Print what you captured. Read the log the script maintains. Re-run the failing step with
one probe *inside* it — `uname`, `printenv`, `command -v` — rather than reasoning about what its
environment must contain. And treat plausibility as a warning sign rather than support: a cause that
explains everything without being checked is the one most likely to be repeated to someone else. Related:
[[feedback_no_guessed_facts]] for asserting an unverified fact, and [[peer_messaging]] for the same error
committed in the other direction, accepting a cause instead of checking evidence you already produced.
