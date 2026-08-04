# Claude model context-window defaults by generation

Claude 5 generation (Opus 5, Sonnet 5, Fable 5) ships a 1M-token context window
as the **default**, not a beta opt-in. This differs from the 4.x generation
(Sonnet 4.5, Opus 4.5), where 1M is available only via a beta header over a
200k default — same nominal max, different activation.

Claude Haiku, across generations including 4.5, stays at a 200k window with no
1M option.

## Practical implication

Any tool that infers a model's context window from its model id (to compute,
e.g., "% of context used") needs a family-**generation**-specific entry, not a
blanket family-name prefix. A prefix like `claude-sonnet` would wrongly apply
the 5-generation's 1M default to 4.x sonnet sessions that are actually still on
the 200k default (no way to tell from the model id alone whether the 1M beta
header was used for those).

## Sources

- platform.claude.com model docs ("What's new in Claude Sonnet 5" / "Introducing
  Claude Fable 5 and Claude Mythos 5")
- morphllm.com/claude-context-window

Checked 2026-07-31.
