# JavaScript date-only strings parse as UTC — persisting a date picker's value without a day-shift

The classic off-by-one: a user picks `2026-08-06` in an `<input type="date">`, you store it, and the UI renders **Aug 5**. Nothing is corrupted and the renderer is correct — the *write* path chose the wrong instant.

## The rule

Per ECMA-262, the two ISO shapes parse in **different zones**:

| Input | Parsed as |
|---|---|
| `new Date("2026-08-06")` | **UTC** midnight — date-only form |
| `new Date("2026-08-06T00:00:00")` | **local** midnight — date-*time* form without offset |
| `new Date("2026-08-06T00:00:00Z")` | UTC midnight (explicit) |

So a bare `YYYY-MM-DD` becomes `2026-08-06T00:00:00Z`. Render that back as a calendar date in any **negative** UTC offset and you get the previous day:

```js
const d = new Date("2026-08-06");                 // 2026-08-06T00:00:00.000Z
new Intl.DateTimeFormat("en-CA", { timeZone: "America/Vancouver",
  year: "numeric", month: "2-digit", day: "2-digit" }).format(d);   // "2026-08-05"  ← a day early
```

Positive offsets (Europe, Asia) mask it — UTC midnight is still the same local day there — so the bug ships from a machine in UTC+ and only shows up for users in the Americas. Month and year boundaries slip too: `2026-03-01` renders as `Feb 2026`, so a compressed "Mon YYYY" stamp is visibly wrong, not just the exact day.

## The fix: anchor a calendar date at local noon

A calendar date isn't an instant; you must pick one. **Noon** in the display zone is the safe choice — midnight is not, because some zones *skip* 00:00 on a DST-transition day (e.g. `America/Santiago`, `Asia/Beirut`), where local midnight doesn't exist and the parse lands an hour off.

```js
export function parseDateOnly(iso, timeZone) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) return new Date(iso);   // already has a time — leave it alone
  return new Date(`${iso}T${"12:00:00"}${offsetSuffix(iso, timeZone)}`);
}
```

### Don't rely on `new Date("…T12:00:00")` for this

The tempting one-liner — append `T12:00:00` and let the date-time form parse as "local" — resolves against the **process** zone (`TZ` env / system), *not* a `timeZone` you pass around. That's fine until any caller supplies an explicit zone, or a test runner pins its own; then it silently diverges from your formatters. Build the offset explicitly instead:

```js
// UTC offset (minutes) that `timeZone` is at a given instant, read off formatted parts — no Date arithmetic.
function tzOffsetMinutes(at, timeZone) {
  const p = new Intl.DateTimeFormat("en-CA", { timeZone, hourCycle: "h23",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit" })
    .formatToParts(at)
    .reduce((acc, part) => ({ ...acc, [part.type]: part.value }), {});
  const asUTC = Date.UTC(+p.year, +p.month - 1, +p.day, +p.hour, +p.minute, +p.second);
  return Math.round((asUTC - Math.floor(at.getTime() / 1000) * 1000) / 60000);
}

function offsetSuffix(isoDay, timeZone) {
  const m = tzOffsetMinutes(new Date(`${isoDay}T12:00:00Z`), timeZone);
  const s = m < 0 ? "-" : "+", a = Math.abs(m);
  return `${s}${String(Math.floor(a / 60)).padStart(2, "0")}:${String(a % 60).padStart(2, "0")}`;
}
```

Probing the offset **at noon UTC on that date** (not at "now") is what makes it DST-correct: a date in March resolves to `-08:00` and one in August to `-07:00` for US Pacific, automatically.

## Don't re-anchor strings that already carry a time

Timestamps from an external system (a media server, a webhook, an API) are **true instants** — their time of day is real data. Gate the noon-anchoring on the date-only regex, or you destroy it. This is why the shape test above matters more than it looks.

## Test the round-trip, not the value

The contract is *pick a date → store → render → get the same date back*. Assert that, across several zones and both DST transitions, rather than hard-coding one expected instant:

```js
for (const zone of ["America/Vancouver", "UTC", "Asia/Tokyo", "Asia/Kolkata"])
  for (const picked of ["2026-01-01", "2026-03-01", "2026-08-06", "2026-12-31"])
    expect(isoDate(parseDateOnly(picked, zone), zone)).toBe(picked);
```

Add the transition days for a DST zone explicitly (US Pacific 2026: forward `2026-03-08`, back `2026-11-01`) — those are where a naive `+12h` or fixed-offset implementation breaks.

Half-hour and 45-minute zones (`Asia/Kolkata` +05:30, `Asia/Kathmandu` +05:45) are worth one case each: they catch an offset formatter that assumes whole hours.

## Related trap: don't display by slicing

The mirror-image bug is rendering with `iso.slice(0, 10)` on a stored instant. A 19:50 local watch in UTC−7 is already past midnight UTC, so the slice reports **tomorrow**. Always format through `Intl.DateTimeFormat` with an explicit `timeZone`.

Note the asymmetry worth keeping straight:

- **Calendar dates** (a release date, a birthday) — store as a plain `YYYY-MM-DD` string and transform with pure string ops. Never round-trip them through a `Date`.
- **Instants** (when something happened) — store as a timestamp and always render through a zone.

Mixing the two is the root cause of nearly every off-by-one date bug.
