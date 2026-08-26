---
name: feedback_empty_state_names_the_filter
description: An empty state behind a filter must name the filter as the cause, never assert that nothing happened
metadata:
  type: feedback
---

When a filtered view has nothing to show, say what was **filtered out**, never that nothing exists. Two
successive attempts at one string were both false while the filter was hiding a row about exactly the thing
being denied: "Nothing has happened to the listings you marked", then "No change recorded here alters a plan of
yours". The version that holds names the cause and claims nothing else — "Every change recorded so far is one
this filter hides".

**Why:** the way back out of the filter is usually a link inside the same sentence, so any claim of absence is
disproved by one click. The user reads "nothing happened", clicks "show everything", and the first row is the
thing that happened, stamped today. That is a worse failure than an unhelpful message, because it is the UI
telling a checkable lie about the user's own data.

It also has to survive the genuinely-empty case: the same string renders when the filter is on and the
underlying collection is empty. A statement about what was filtered is vacuously true there, which is fine — a
statement about what does not exist is either false or accidentally true, and you cannot tell which by reading
it.

**How to apply:** write the message as a fact about the filter's criteria, not about the world. Resist the pull
toward restating the criteria in full — every clause is another thing that has to stay true as the predicate
evolves, and a two-branch rule rarely survives compression into one sentence. Prefer naming the filter and
offering the way back over enumerating what it excluded. Keep the two emptinesses distinct: "nothing matched
this filter" and "this collection has never had anything in it" need different words, and saying the wrong one
reads as a bug in the data.

Beware the same shape in tooltips and docs that describe the filter: an inclusion criterion ("shows what is
still open") is a checkable claim that drifts the moment the predicate changes, while a description of what is
dropped tends to stay true. Related: [[feedback_live_values_source_of_truth]], [[feedback_no_guessed_facts]].
