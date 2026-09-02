---
name: A probe that changes what it measures is not an observation
description: Before trusting a measurement, ask whether the act of measuring produced the value — and whether an earlier probe warmed the thing you are about to read
metadata:
  type: feedback
---

Before trusting a measurement, ask whether the act of measuring produced the value. A probe that changes the state it reads is not an observation, and it fails hardest exactly where the fault it was meant to find lives.

**Why:** I "measured" a media encoder at 28.4× real time by requesting segments further and further ahead and timing them — a fast answer looked like proof the encoder had already reached that point. It had not. The request itself made the server begin producing at that offset, so every probe returned in the ~0.5 s it takes to start encoding anywhere, and the derived speed scaled with nothing but how far I chose to probe. I reported the figure confidently and had to retract it. Worse, shipping the technique would have damaged live playback precisely when the encoder was behind, since being behind is the only condition under which a probe lands past the frontier at all. The first attempt to test the danger was itself invalid: an earlier probe had already transcoded that item, so the warm cache returned everything instantly and looked like confirmation of safety.

**How to apply:** separate reading state from causing it. If a fast response could mean either "it was already there" or "asking for it made it happen", the measurement cannot tell those apart and is not evidence — say so rather than reporting the number. Check whether an earlier run warmed what you are about to measure, and use a cold subject when it did. Prefer asking the component that already knows (a status endpoint, a session, the process itself) over inferring from response times. Related: [[feedback_not_run_is_not_pass]], [[feedback_no_guessed_facts]], [[feedback_assumptions_vs_facts]].
