#!/usr/bin/env python3
"""Relative timestamps for a generated HTML page: "3h ago" in the text, the exact stamp on hover.

A page written to disk renders once, so an interval baked in when the file is written goes on asserting the age it
had at that moment: a report generated eight minutes ago went on claiming "8 mins ago" indefinitely. `rel_time`
therefore puts the epoch on the element, and `LIVE_TIME_SCRIPT`, placed once at the foot of the page, recomputes
every such element on load, every thirty seconds, and whenever the tab comes back into view. The text `rel_time`
writes is the fallback for a page whose script does not run, correct at the instant of writing.

`compact_age` and the script's `formatInterval` are one function in two languages, ported from `formatInterval` in
the What's Next repo (web/src/lib/format.ts) rather than rewritten, so every surface that shows an interval agrees
on where the boundaries fall. A change to one is a change to both.
"""

from __future__ import annotations

import html
import time
from datetime import datetime

# A page built with str.format must take this through a slot rather than inline it: format reads every brace in a
# script as a field and fails on the first one.
LIVE_TIME_SCRIPT = """<script>
(() => {
  const formatInterval = (ms) => {
    const min = Math.floor((ms > 0 ? ms : 0) / 60000);
    if (min < 60) return `${Math.max(1, min)}m`;
    const hrs = Math.floor(min / 60);
    if (hrs < 24) return `${hrs}h`;
    const days = Math.floor(hrs / 24);
    if (days < 30) return `${days}d`;
    if (days < 365) return `${Math.floor(days / 30)}mo`;
    return `${Math.floor(days / 365)}y`;
  };
  const tick = () => {
    const now = Date.now();
    for (const el of document.querySelectorAll('.rel[data-ts]')) {
      const ts = Number(el.dataset.ts);
      if (!Number.isFinite(ts)) continue;
      el.textContent = formatInterval(now - ts) + (el.dataset.suffix || '');
    }
  };
  tick();
  setInterval(tick, 30000);
  // A backgrounded tab throttles timers hard, so a page returned to after hours
  // would show whatever it last managed to render. Recompute on the way back in.
  document.addEventListener('visibilitychange', () => { if (!document.hidden) tick(); });
})();
</script>"""


def local_stamp(epoch: float) -> str:
    """An absolute timestamp in this machine's local time, for hover text.

    Epochs are absolute, so a peer's timestamp converts correctly here even
    though it was taken under a different clock and time zone.
    """
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M") if epoch else ""


def compact_age(seconds: float) -> str:
    """Format a delta as 5m / 3h / 2d / 4mo / 1y.

    A delta at or below zero returns empty, which callers read as "just now".
    """
    if seconds <= 0:
        return ""
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{max(1, minutes)}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    if days < 30:
        return f"{days}d"
    if days < 365:
        return f"{days // 30}mo"
    return f"{days // 365}y"


def rel_time(epoch: float, suffix: str = " ago") -> str:
    """A relative timestamp the page keeps current by itself, as an HTML span; empty when there is no epoch."""
    if not epoch:
        return ""
    return (f'<span class="rel" data-ts="{int(epoch * 1000)}" data-suffix="{html.escape(suffix)}"'
            f' title="{html.escape(local_stamp(epoch))}">{html.escape(compact_age(time.time() - epoch))}{html.escape(suffix)}</span>')
