---
name: feedback_sweep_the_old_wording
description: When retiring a rule, grep the abolished behaviour's wording, not the new rule's — a procedure restates the rule in words the rule never uses, and a gate list encodes it with no words at all
metadata:
  type: feedback
---

When a rule changes, sweep for the phrasing of the **behaviour being abolished**, not the phrasing of the new rule. The stale copies are written in the imperative of the old behaviour and share no vocabulary with the rule that governs them.

**Why:** a rule is stated once and *operationalized* somewhere else, in a different register. Measured 2026-09-14: `dd381c7` put "a message to another agent needs no approval to send" into `claude/CLAUDE.md` and `claude/memory/peer_messaging.md`, and left `claude/skills/commit/SKILL.md` step 10 saying "draft the message, show it verbatim, and ask before sending". No sweep of the new rule's terms — *approval*, *agent*, *draft-show-confirm* — reaches that sentence; the string that finds it is `ask before sending`, which exists only in the text being retired. A peer session hit the contradiction the next time the step ran.

**Worse, a rule can be encoded as list membership and carry no words at all.** The same file's Pacing paragraph named step 10 among "the only gates the commit skill itself owns" — the rule restated as an entry in an enumeration. Nothing textual finds that. After the text sweep, ask which lists, tables, or counts assert the thing, and read them.

**A third register is the README**, which describes the procedure to a human rather than instructing an agent: `README.md` advertised the same step as "shown for approval before any message is sent". So the sweep has to reach the docs that *describe* the behaviour, not only the ones that command it.

**How to apply:** before changing a rule, grep the sentence you are deleting, not the one you are writing; then check the enumerations, then the prose that describes the feature to a reader. When someone else reports one stale copy, treat it as a sample rather than the set — the report named one of four here. Related: [[feedback_grep_markdown_emphasis]], which covers the same sweep failing on emphasis and wrapping rather than on register.
