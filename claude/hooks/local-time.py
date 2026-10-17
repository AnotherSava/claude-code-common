#!/usr/bin/env python3
"""PostToolUse: remind the model to convert to local time when a tool's output carries a foreign-zone timestamp.

Logs, git's ISO formats and most JSON store UTC, and these machines run hours behind it. The rule to
convert before reporting is in an always-loaded memory (`feedback_local_time_timestamps.md`) and is still
missed: the raw `12:45:41Z` gets reformatted into a friendly "12:45" without the shift. A rule has to be
remembered at the moment of writing; this repeats it the moment a foreign-zone value enters the context,
scoped to what the user is told, since the same value written into a file or a fixture must keep its zone.

Registered on `^(Bash|Read|Grep)$` with no `if`, because nothing in a command's text predicts whether its
output carries a timestamp. So it starts on every call of those tools and must stay cheap: one regex pass
over a bounded slice of the output, no IO. Silent unless a timestamp with an explicit zone other than the
local one is found.

It sees only timestamps that say their zone (a trailing `Z`, `UTC`/`GMT`, or a numeric offset), in the
forms `STAMPS` lists. A log that writes UTC with no marker, and Unix epoch numbers, are indistinguishable
from local times and integers here and raise no reminder.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Iterator

# Enough for any log excerpt a model reads; a Read of a huge file is truncated by the harness anyway.
SCAN_LIMIT = 2_000_000

MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
DAYS = "Mon|Tue|Wed|Thu|Fri|Sat|Sun"
# Every form a tool here prints with its zone stated: ISO 8601 and git's `--date=iso`; git's default
# `Thu Oct 16 12:45:41 2026 +0000`; and the RFC 2822 form of HTTP and mail headers, `Thu, 16 Oct 2026 12:45:41 GMT`.
STAMPS = [
    re.compile(
        r"\b(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})[T ](?P<hour>\d{2}):(?P<minute>\d{2})(?::(?P<second>\d{2})(?:[.,]\d+)?)?"
        r" ?(?P<zone>Z|UTC|GMT|[+-]\d{2}:?\d{2})(?![\w:])"
    ),
    re.compile(
        rf"\b(?:{DAYS}) (?P<mon>{MONTHS}) {{1,2}}(?P<day>\d{{1,2}}) (?P<hour>\d{{2}}):(?P<minute>\d{{2}}):(?P<second>\d{{2}})"
        r" (?P<year>\d{4}) (?P<zone>[+-]\d{4})(?![\w:])"
    ),
    re.compile(
        rf"\b(?:{DAYS}), (?P<day>\d{{1,2}}) (?P<mon>{MONTHS}) (?P<year>\d{{4}}) (?P<hour>\d{{2}}):(?P<minute>\d{{2}}):(?P<second>\d{{2}})"
        r" (?P<zone>GMT|UTC|[+-]\d{4})(?![\w:])"
    ),
]


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _parse(match: re.Match) -> datetime | None:
    parts = match.groupdict()
    zone = parts["zone"]
    month = parts["month"] if "month" in parts else str(MONTHS.split("|").index(parts["mon"]) + 1)
    if zone in ("Z", "UTC", "GMT"):
        tz = timezone.utc
    else:
        digits = zone[1:].replace(":", "")
        offset = timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
        tz = timezone(-offset if zone[0] == "-" else offset)
    try:
        return datetime(int(parts["year"]), int(month), int(parts["day"]), int(parts["hour"]), int(parts["minute"]), int(parts["second"] or 0), tzinfo=tz)
    except ValueError:
        return None  # a digit run shaped like a date that is not one, e.g. month 13


def _foreign(text: str) -> bool:
    for pattern in STAMPS:
        for match in pattern.finditer(text):
            stamp = _parse(match)
            # Compared at the stamp's own date, so a winter stamp is judged against standard time.
            if stamp is not None and stamp.astimezone().utcoffset() != stamp.utcoffset():
                return True
    return False


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(data, dict):
        return 0

    response = data.get("tool_response")
    if isinstance(response, dict):
        # A Bash call that changes files carries their diff hunks here, which are the model's own writing.
        response = {key: value for key, value in response.items() if key != "bashEditDiff"}
    text = "\n".join(_strings(response))[:SCAN_LIMIT]
    # Every form has a `:` clock, so text without one cannot hold a stamp.
    if ":" not in text:
        return 0
    try:
        if not _foreign(text):
            return 0
    except Exception:
        return 0

    offset = datetime.now().astimezone().strftime("%Z, UTC%z")
    zone = offset[:-2] + ":" + offset[-2:]
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"This output contains timestamps in UTC or another zone that is not the user's. When telling the user "
                f"one of these times, convert it to their local zone ({zone}). When writing it into a file, code, or a "
                f"message to another agent, keep the stored value and state its zone."
            ),
        },
        "suppressOutput": True,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
