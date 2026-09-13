---
name: feedback_peer_register_not_support
description: Technical correspondence with another developer is written peer to peer, not support-agent to user
metadata:
  type: feedback
---

Write to another engineer as a peer, not as a support agent handling a ticket. The correction came on a GitHub issue reply, verbatim: *"write it as a message from one sde to another, not from a support agent to a user."*

What actually changed, so the difference is reproducible rather than a vibe:

- **Drop bolded UI labels.** `**Achievement text**`, `**Report a problem…**` is documentation formatting. In conversation you just name the thing.
- **Replace request framing with the need.** Not "Could you upgrade to v1.10.0 and paste…?" but "Before I pick a fix I need to know whether your schema has Russian in it" — followed by the two branches that answer decides. The ask stops being a favour and becomes the reason the next step exists.
- **A regression you caused is an apology, not a disclosure.** "So v1.9.1 fixed the icons and broke the language for you in the same release. Sorry about that." — not a paragraph formally announcing that an uncomfortable corollary is about to be stated.
- **Name the mechanism once, by its symbol.** They read code. Explaining the same ternary twice reads as writing down to them.
- **Short everywhere except the mechanism they have to act on.** Asked to condense, the same reply went 350 words to 150 by dropping the defence of a reversed decision, an unrelated mirror case, a nicety and the thanks — then, asked again ("just a bit more details on…"), spent 55 of those words back on the one paragraph stating the new rule. Cutting is not uniform: the explanation of *why you were right* goes first, and the description of *what now happens* goes last.

**Why:** the reporter in that thread had filed a correct diagnosis of the bug himself. Support register aimed at someone like that costs credibility, and it buries the one question you actually need answered under politeness.

Related: [[feedback_overused_phrases]] — the "Worth stating plainly" family of self-announcing openers is the same instinct showing up at sentence level. [[feedback_use_the_tool_you_built]] came out of the same reply.
