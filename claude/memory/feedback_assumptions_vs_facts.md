---
name: assumptions-vs-facts
description: Never state assumptions or inferences as facts — label them explicitly as assumptions when presenting to the user
metadata:
  type: feedback
---

Do not present assumptions, inferences, or speculation as established facts. When something is unverified, say "I assume" / "likely" / "possibly" — never state it as a conclusion.

**Why:** During a debugging session, stated an assumption ("Defender quarantined the HV drivers" causing a failure) as a fact. The user had to push back twice to get me to acknowledge it was unverified. This wastes the user's trust and time.

**How to apply:** Before stating a causal explanation, check: did I observe this directly, or am I inferring it? If inferring, label it. "Defender detected these files" (fact from the log) vs "they were quarantined and removed" (assumption I should have verified before stating).
