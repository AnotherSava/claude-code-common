---
name: feedback_probe_before_infeasible
description: Before telling the user a data-driven feature is impossible, probe what the runtime/library/data actually exposes
metadata:
  type: feedback
---

Before telling the user a data-driven feature can't be done, probe what the runtime, library, or source data actually exposes — confirm absence empirically instead of asserting it.

**Why:** In the travel-map session I twice declared per-city label sizing infeasible ("we have no per-city prominence data") and proposed compromises; the user pushed back ("I'm not sure that statement is correct") and showed a counterexample. The base Mapbox tiles had exposed `symbolrank` per city via `querySourceFeatures` all along — the data was reachable, I just hadn't checked.

**How to apply:** When tempted to say "X can't be done" or "we don't have the data for X," first query/inspect the available APIs and source data (dump feature properties, read the docs, run a probe) and verify the gap is real before presenting infeasibility as a conclusion or asking the user to pick a lesser workaround.

**A correct reading of the model is not an observation of the system**, and that is the harder version of this because nothing feels like a guess. In the dashboard session I concluded that a dashboard cannot observe a person reading another machine's session, since its own data model says a synced row's terminal is on the other machine. True of the model, false of the desk: the terminal had a whole workspace of SSH tabs rendering exactly those sessions, and the attention sensor was already enumerating them. The user answered with four words naming the thing that was on screen. Probing an API would not have caught it — the missing instrument was an inventory of what is *running*: the terminal's own session tree, the open tabs, the process list, the live roster. When the answer is "that kind of thing doesn't exist here", list the instances before believing it, because the model only says which kinds exist.

Related: [[feedback_assumptions_vs_facts]], [[feedback_no_bluffing_external_uis]], [[feedback_verify_before_justifying]], [[feedback_no_negative_from_partial_probe]].
