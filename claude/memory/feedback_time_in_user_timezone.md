---
name: feedback_time_in_user_timezone
description: report times in the user's local zone (America/Los_Angeles), never UTC and never a vague time-of-day word borrowed from a server log
metadata:
  type: feedback
---

When referring to time in anything the user reads — timestamps, "this morning", "an hour ago", how long a soak ran — express it in **their** local timezone, `America/Los_Angeles` (PDT/PST). Read it from the machine (`date "+%Y-%m-%d %H:%M %Z"`) rather than assuming.

**Why:** said "tonight's findings" at **17:26 PDT**, which is late afternoon. Two things caused it, and the second is the one that recurs. First, a vague time-of-day word was reached for instead of a clock reading nobody had checked. Second, and worse: the work involved servers and logs that emit UTC — the box's own verdict line read `2026-08-27T02:09:38+00:00` — and reasoning in the timestamps in front of you silently adopts their zone. `02:09` UTC is `19:09` the **previous evening** in PDT, so quoting a server time verbatim can misdate an event by a day, not just an hour.

**How to apply:** convert before quoting — a UTC timestamp from a container, a git commit, a cert `notBefore`, or a remote log is not in the user's zone. When precision matters, give the clock time with its abbreviation (`17:26 PDT`) rather than "tonight" or "just now"; the abbreviation also stays honest across a DST boundary, where a raw offset does not. Session transcripts carry timestamps, so elapsed time is observable — compute it instead of estimating. Related: [[feedback_timezone_is_not_a_location]] for the converse error, and [[feedback_no_guessed_facts]] — an unchecked "tonight" is a guessed fact like any other.
