---
name: assumptions-vs-facts
description: Never state assumptions or inferences as facts — label them explicitly as assumptions when presenting to the user
metadata:
  type: feedback
---

Do not present assumptions, inferences, or speculation as established facts. When something is unverified, say "I assume" / "likely" / "possibly" — never state it as a conclusion.

**Why:** During a debugging session, stated an assumption ("Defender quarantined the HV drivers" causing a failure) as a fact. The user had to push back twice to get me to acknowledge it was unverified. This wastes the user's trust and time.

**How to apply:** Before stating a causal explanation, check: did I observe this directly, or am I inferring it? If inferring, label it. "Defender detected these files" (fact from the log) vs "they were quarantined and removed" (assumption I should have verified before stating).

**A cause asserted by a tool's own error text is a borrowed inference, not an observation**, and the test above answers "observed" for it, which is why it slips through. Measured 2026-10-06: a relay receipt read `refused — unknown_project` and its hint said this was "an address that names nothing here rather than a session that ended". The ruled-out cause was the cause — no session was running on the peer — and it was relayed to the user as the peer's clone sitting under a different folder name, with an offer to go hunting for its registered name. One plain retry, once the session was started, returned `written`. When a one-shot failure explains itself, retry before repeating the explanation: the retry is cheaper than the investigation the message invites, and the confident half of the message is the part most likely to be wrong.
