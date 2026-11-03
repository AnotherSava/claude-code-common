---
created: 2026-11-03 08:35:46
---

# Show the /wrap-up summary as an interactive HTML page, and add an output-style rule to consider HTML for verbose output the user must answer

Agreed 2026-11-03 as the next task after that day's wrap-ups.

The pieces: claude/scripts/review_picker.py already shows /review-manual's findings as a blocking agterm HTML overlay (session overlay open --html --block; Apply calls session.overlay.submit and the answer comes back as JSON), and outside agterm (agwinterm, a plain terminal) publishes the same page on the tailnet with a Copy answer button whose JSON the user pastes into the chat. /wrap-up's summary is the second real case for generalising it.

Plan:
1. Generalise review_picker.py to rows with a per-row choice control (answer / memo / ping / drop for Q C M P items; save / skip for S; the item's own pair for R) preset to the recommendation, plus an optional note per row, and read-only blocks above (the Review triage table, the Commits list ending with the review bookmark line). Submit = go with the overrides.
2. Change wrap-up step 7 to write that page and run the picker, keeping the chat prompt as the fallback for exit 2/3/1, as /review-manual's step 5 does.
3. Add a rule to the output style through /tune-output (not a skill: a skill only fires when its description matches the request, and verbose output needing a response comes up mid-task): when a reply would be long structured data the user has to act on, prefer an HTML page shown in an agterm overlay or published on the tailnet, pointing at the shared picker for the mechanics.
4. Update skill-outputs' collect.py: summaries rendered as HTML no longer appear as chat text, so its detector needs the new source.
