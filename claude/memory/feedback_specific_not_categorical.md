---
name: Generated descriptions must be specific, never categorical
description: Never render a statement about an item's category as its description — it repeats identically down a list or restates the name
type: feedback
---

A description generated for an item must say something about **that item**. A statement about its *category* is not a description, and it fails in two shapes:

- **Generic** — the same sentence renders under every item of the type. "Made to be looked at." appeared on all 17 artworks in a city shortlist.
- **Tautological** — it restates what the name or an adjacent label already says. "St. Andrew's Wesley Church" described as "church building", directly above a tag reading `religious`.

**Why:** a category sentence answers "what kind of thing is this", which the reader already knows from the name and the label beside it. It displaces the answer they actually want and reads as padding. Both corrections came in one session, from a user reviewing rendered output — *"'Made to be looked at.' is such a stupid description"* and *"I understand that St. Andrew's Wesley Church is a church building, what else could it be, but why should I go there?"*

The trap is that it looks like reasonable content in code review. It only becomes obviously wrong when seen repeated down a rendered list, so review the rendered surface, not the string.

A second trap: one string cannot serve as both the maintainer's rationale for a rule and the user-facing text for an item. Those are different audiences and different jobs — the first explains why a class carries a weight, the second explains why to care about one thing. Keep them in separate fields.

**How to apply:** order the sources by specificity and fall through rather than substituting a class statement. If no source has anything item-specific to say, show nothing and let an empty state or confidence marker carry it — do not manufacture filler. A class statement is acceptable only as a genuine last resort, and if it fires often that is a signal the data layer is missing a source, not that the wording needs rewriting.

Related: [[feedback_about_what_not_how]] — the same instinct applied to About-dialog copy.
