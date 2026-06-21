---
name: feedback_probe_before_infeasible
description: Before telling the user a data-driven feature is impossible, probe what the runtime/library/data actually exposes
metadata:
  type: feedback
---

Before telling the user a data-driven feature can't be done, probe what the runtime, library, or source data actually exposes — confirm absence empirically instead of asserting it.

**Why:** In the travel-map session I twice declared per-city label sizing infeasible ("we have no per-city prominence data") and proposed compromises; the user pushed back ("I'm not sure that statement is correct") and showed a counterexample. The base Mapbox tiles had exposed `symbolrank` per city via `querySourceFeatures` all along — the data was reachable, I just hadn't checked.

**How to apply:** When tempted to say "X can't be done" or "we don't have the data for X," first query/inspect the available APIs and source data (dump feature properties, read the docs, run a probe) and verify the gap is real before presenting infeasibility as a conclusion or asking the user to pick a lesser workaround.

Related: [[feedback_assumptions_vs_facts]], [[feedback_no_bluffing_external_uis]], [[feedback_verify_before_justifying]].
