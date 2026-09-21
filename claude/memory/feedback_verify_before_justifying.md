---
name: Verify before justifying legacy behavior
description: When explaining why old code/docs/steps exist (especially when arguing against removing them), check the source instead of speculating defensively
type: feedback
---

When tempted to explain why a piece of legacy code, documentation, or workflow step exists — especially when the explanation defends keeping it — verify the justification has a real basis (read the source, check the spec) before stating it.

**Why**: In a track-achievements session on 2026-05-04, I claimed an outer `steam_appid.txt` step "predates achievement-overlay and is for GBE-side reasons (some games look for it at the exe location)". The user replied "is it?" — I checked GBE's `dll/settings_parser.cpp:560-643` and the claim was unfounded. GBE's lookup priority puts `steam_settings/steam_appid.txt` (#2) above the exe dir (#4), so the outer copy was redundant once GBE was loaded. The defensive guess almost preserved cruft.

**How to apply**:
- When writing "this exists because some/many/legacy X do Y" or "this is defensive against Z" — either cite the source/spec inline, or rephrase as "I'm not sure why this is here — let me check" before defending.
- The pattern is most dangerous in two situations: (1) deciding whether to remove a workaround, and (2) explaining historical decisions in code comments or docs.
- A short factual "I don't know — checking" is always better than a confident speculative justification.
- **The same applies to something you are PROPOSING, not just something that already exists.** Before listing
  the benefits of an approach, verify each one against the system as it actually is — a plausible benefit is
  usually a guess about current state. On 2026-08-19 (what-is-next) I recommended a dedicated stream-only
  Jellyfin account; asked what it bought, checking the live server killed three of four reasons (the sync account
  was already non-admin, already had content deletion disabled, and Jellyfin access tokens are already
  per-device revocable). One real benefit survived, and the honest answer was "narrow but real" rather than the
  four-point case I would otherwise have made.
- **A justification can be accurate and still wrong, when nobody measured the population it describes.** The
  bullets above are about claims with no basis; this is the harder case, where the basis is real and stale.
  On 2026-09-21 (trips) I defended an automatic trip-merge by quoting the code comment recording the defect
  it was written for — a four-day trip split in half by the order its bookings arrived. The comment was
  true. Counting the live data settled it in one query: of 107 trips, three pairs overlapped within the
  merge's day of slack and merging any of them would have been wrong, because trips there routinely abut,
  one ending the day the next begins. The rule was right for the nine bookings it was written against and
  wrong for the 298 that followed. So cite the comment to explain why something exists, and measure the
  current data before arguing it should stay — the query is usually one command, and the code cannot tell
  you what has changed around it.
