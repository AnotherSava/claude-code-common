---
name: feedback_use_the_tool_you_built
description: Make the instrument you just built the ask, not a fallback behind a manual substitute you guessed they'd prefer
metadata:
  type: feedback
---

When you have just built the instrument for a case, **make it the ask**. Do not relegate it to a fallback and request a manual substitute instead.

Real case: a per-game diagnostic report feature was built across most of a session for exactly one purpose — getting a bug reporter's schema, unlock file, config and log in one attachment. The reply drafted immediately afterwards asked him to hand-paste a single log line, and mentioned the feature as the fallback "if that line turns out ambiguous". The user's question was the whole correction: *"why not just post an output file?"*

The reasoning behind the mistake is the part worth keeping: *"across three issues he has attached a file zero times — he pastes excerpts."* That is a behavioural prediction about a third party, dressed up as evidence. Three days later he attached the report file on first contact, unprompted.

**Why it matters beyond the one reply:**

- **A prediction about how someone will behave loses to one measurement**, and you can usually just take the measurement — here, by asking.
- The manual substitute was also *worse*: the report carried the config, so it answered the language-setting question too. One ask instead of three, and no hand-transcription to get wrong.
- A new feature's first real use is data you only get once. Routing around it wastes the trial and leaves you still guessing whether it works.

Related: [[feedback_peer_register_not_support]] — same reply, same instinct to manage the reader instead of addressing them.
