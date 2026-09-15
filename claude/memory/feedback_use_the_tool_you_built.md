---
name: feedback_use_the_tool_you_built
description: Make the instrument you just built the ask, not a fallback behind a manual substitute — and undo hand-done work so the tested path runs it
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

**The same rule applied to work already done by hand (2026-09-15).** Five repositories held a format migration performed by hand weeks earlier and never committed. The adoption system built to replace that hand work was deliberately designed to accept them — its check runs before its probe, so a repo already in the target shape records `applied` without re-doing anything. The instruction was to undo all five instead, so the versioned path would perform the migration itself.

Two reasons, and neither is visible from inside the cheaper option:

- **The mechanism exists because the hand version went wrong.** It missed one repo entirely and left five more uncommitted. Grandfathering the hand result records exactly the thing you stopped trusting, and records it as verified.
- **A system's first run against real data is the only test its author did not design.** Five undos bought five real exercises of a path that had otherwise seen nothing but its own fixtures — and one of them immediately exposed an ordering rule the fixtures did not encode, where two memos captured in the same minute need staggered seconds to keep their order.

Undoing is safe only where the hand result is provably reproducible from committed state. The procedure for establishing that — rebuild from `HEAD` in a scratch tree, diff, and read silence as the proof — is in `learnings/git-stash-pull-safety.md`.

Related: [[feedback_peer_register_not_support]] — same reply, same instinct to manage the reader instead of addressing them.
