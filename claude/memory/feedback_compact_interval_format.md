---
name: feedback_compact_interval_format
description: Preferred compact elapsed-time format — largest unit only, "5m"/"3h"/"12d"; min "1m", no seconds, unbounded days
metadata:
  type: feedback
---

For UI that shows an elapsed / relative duration — a "how long ago" age, a dwell timer, a since-column — default to this compact **single-unit** format. The user uses this representation often and wants it consistent across projects. Origin: printlab's `fmtStopwatch` (admin orders "Timer" column, `web/src/app/admin/(panel)/_components/orderState.tsx`).

**Spec** — input is a duration in **milliseconds**; output is the largest whole unit only:
- `< 60 min` → `"{minutes}m"`, floored, **clamped to a minimum of "1m"** — a sub-minute, zero, negative, or NaN interval reads `"1m"`, never `"0m"`.
- `< 24 h` → `"{hours}h"`, floored (minutes remainder dropped).
- otherwise → `"{days}d"`, floored (hours remainder dropped). **Days are unbounded** — no weeks/months/years, so ~3 years reads `"1060d"`.
- No seconds unit. The value is a **bare magnitude** with no suffix — callers append "ago", "left", etc. as the context needs.

```ts
export function formatInterval(ms: number): string {
  const min = Math.floor((ms > 0 ? ms : 0) / 60000);
  if (min < 60) return `${Math.max(1, min)}m`;
  const hrs = Math.floor(min / 60);
  if (hrs < 24) return `${hrs}h`;
  return `${Math.floor(hrs / 24)}d`;
}
```

**Why:** it's terse and scannable in dense lists/columns where "2 days ago" or a full timestamp is too wide, and the user reaches for it repeatedly.

**How to apply:** prefer this over `Intl.RelativeTimeFormat` / "N days ago" / full timestamps for compact age or dwell values. Keep the exact date/time in a `title`/tooltip when precision matters. In a React component, don't call `Date.now()`/`new Date()` in the render body (React 19 / Next 16 purity lint flags it) — snapshot "now" once via a lib helper (e.g. a `nowMs()` next to `todayISO()`) or in the data layer and pass it in; see [[nextjs16-prisma7-scaffold]]. For a live-ticking timer, refresh the "now" snapshot on an interval instead.
