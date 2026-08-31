---
name: Report timestamps in local time
description: Convert stored UTC timestamps to the machine's local time before showing them; never quote a UTC clock reading for something that happened on this machine
type: feedback
---
When reporting *when* something happened on this machine — a log line, a commit, a state transition, a file mtime — convert the timestamp to the machine's **local time** before showing it. Say `05:45:41` when the log holds `2026-08-30T12:45:41Z` and the machine is on PDT. Add the zone abbreviation when a reader could reasonably wonder (`05:45 PDT`).

**Why:** most machine-readable logs store UTC, and this user's machines run several hours behind it — so a UTC reading is off by a full working-day-shaped amount and cannot be matched against what they actually saw on screen. It also silently breaks the reasoning built on it: an event quoted at `12:45` when the user was looking at `05:45` reads as a completely different moment, and a "you can't have seen it" argument built from that is wrong. (Established 2026-08-30, after a `widget.jsonl` investigation was reported entirely in UTC.)

**How to apply:**
- `widget.jsonl`, git's `%aI`, and most JSON logs are UTC — check for the trailing `Z` and convert; never paste the raw field.
- Get the offset from the machine rather than assuming: `date "+%Z %z"`, or format the stored value directly (`date -j -f "%Y-%m-%dT%H:%M:%S" "$ts" "+%H:%M:%S"` on macOS).
- Keep UTC only where it is the point — comparing across machines, or when the user asked for it. Then label it `UTC` explicitly.
- Relative phrasing ("3 minutes ago") sidesteps the whole problem and is often the better answer; see [[feedback_relative_timestamps]].
- Applies to durations' endpoints too, not just instants — a window quoted as "12:45 to 12:46" has the same defect.
