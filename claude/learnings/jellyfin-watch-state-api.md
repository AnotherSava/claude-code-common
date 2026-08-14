# Jellyfin API — set watch state (played + a specific date) and match items by provider id

How to programmatically mark Jellyfin items played with a **historical date** (e.g. replaying watch history from another source — Plex, TV Time, a personal DB) and how to resolve which Jellyfin item is which. Verified live against Jellyfin **10.11.11**.

## Mark played with a date

- **Current route (10.10+):** `POST /UserPlayedItems/{itemId}?userId={userId}&datePlayed={ISO8601}`
- **Legacy (deprecated but still works on many versions):** `POST /Users/{userId}/PlayedItems/{itemId}?datePlayed={ISO8601}`
- A script should try the new route and **fall back to the legacy on 404** — versions differ.
- **Unmark:** `DELETE` the same path (either form).
- `datePlayed` **must be passed explicitly** to write `LastPlayedDate`. Marking an item played *without* it leaves the date blank/now — Jellyfin only persists `LastPlayedDate` when the parameter is present (jellyfin#8492, #11186).
- **Format:** ISO-8601 UTC works and round-trips exactly. Sent `2025-10-23T02:35:54Z` → stored `2025-10-23T02:35:54.0000000Z`. In Node: `new Date(dbTimestamp).toISOString()`.
- The POST returns a `UserItemDataDto` (`Played`, `LastPlayedDate`, `PlayCount`) — check it, or read back with `GET /Items/{itemId}?userId={userId}` → `UserData.Played` / `UserData.LastPlayedDate`.
- Marking episodes played rolls the season/series watched state up automatically.

## Auth

- Header `X-Emby-Token: {apiKey}` (equivalently `Authorization: MediaBrowser Token="{apiKey}"`). API key from Dashboard → API Keys.
- **Caveat:** some *unstable* builds broke mark-played under a **static API key** ("Guid can't be empty" ArgumentException — jellyfin#11501). If hit, authenticate a real user token via `POST /Users/AuthenticateByName` and use that instead.

## Resolve the user

`GET /Users` → find the entry whose `Name` matches; use its `Id` as `userId`.

## Match items to external ids (the reliable way)

Match on **`ProviderIds`**, not titles. (Jellyfin file naming with `[tmdbid-N]` / `[tvdbid-N]` in folder/file names is exactly what populates these.)

- **Movies:** `GET /Items?userId={uid}&recursive=true&includeItemTypes=Movie&fields=ProviderIds&enableImages=false&limit=5000` → build `String(ProviderIds.Tmdb) → itemId`.
- **Series:** same with `includeItemTypes=Series` → `Tmdb`/`Tvdb → seriesId`.
- **Episodes:** per series, `GET /Shows/{seriesId}/Episodes?userId={uid}&fields=ProviderIds` → key by `ParentIndexNumber` (season) + `IndexNumber` (episode).
- Fetch the library once and match **in memory** — version-robust, no dependency on a server-side provider-id filter param.

## Practical notes

- **Base URL:** a bare host needs scheme + the default port: `http://{host}:8096`.
- **Node:** global `fetch` is enough. Count played items to verify a bulk run: `GET /Items?userId={uid}&recursive=true&includeItemTypes=Movie&filters=IsPlayed&limit=1` → `TotalRecordCount`.
- **Only items in the library can be marked** — the importable set is the *intersection* of your external history with what Jellyfin actually holds. Report unmatched (whole shows absent / individual episodes missing) rather than trying to create them.
- **Reversible & idempotent:** log each `{itemId, datePlayed}`; re-running re-sets the same date; `DELETE …/PlayedItems/{itemId}` clears it. A safe pre-flight is a single self-reverting round-trip on one already-unplayed item (mark → read back → unmark) to confirm the endpoint + date format on the target version before the bulk run.
- Explore any server's exact routes at `{base}/api-docs/swagger`.

---

# Reading a Jellyfin library (sync / import side)

Verified live against Jellyfin **10.11.11** on 2026-08-05. The section above covers *writing* played state; this covers reading the library to mirror it into another app.

## Accounts

`GET /Users` (needs the API key, not a user token) returns every account with `Id`, `Name`, and a `Policy` carrying `IsAdministrator` / `IsDisabled` / **`IsHidden`**. Hidden accounts are kept off the login screen but are still perfectly valid to read — so filter on `IsHidden` only for a picker's *display*, not for validity.

`GET /Users/Public` needs no auth but lists only login-screen accounts, so it silently omits hidden ones. Don't use it to enumerate.

**Watch state is per account**, so a multi-account server has no safe default. Guessing "the first user" looks like a working sync while importing the wrong (often empty) history. Fail loudly instead, naming the accounts.

Cheap way to tell accounts apart — ask for one item and read the total:

```
GET /Items?userId={id}&recursive=true&includeItemTypes=Movie&filters=IsPlayed&limit=1  →  TotalRecordCount
```

(`Episode` for episodes.) An untouched admin account reads `0m/0e` next to a real one at `22m/458e`.

## Libraries

`GET /UserViews?userId={id}` → `Items[]` of collection folders with `Name` and `CollectionType` (`"movies"` | `"tvshows"` | `"music"` | …). Needs *a* user id, so on a multi-account server list accounts first and pass any of them — otherwise choosing an account and listing libraries deadlock on each other.

## Items, in one request

`GET /Items?userId=&parentId={libraryId}&recursive=true&includeItemTypes=Movie&fields=ProviderIds,MediaSources&enableUserData=true&enableImages=false&limit=5000`

The big win over Plex: **`fields=MediaSources` returns the full `MediaStreams` in the list call**, so resolution/HDR/audio/subtitles need no per-item follow-up. Same for `GET /Shows/{id}/Episodes?fields=MediaSources` — one request gives every episode's watch state *and* its streams.

For Series, `fields=ProviderIds,RecursiveItemCount,ChildCount` gives:
- `RecursiveItemCount` — total episodes
- `UserData.UnplayedItemCount` — unwatched; **watched = total − unplayed**

Both come free with the row, which makes them ideal change-detection cursors: an unchanged pair means skip that show's episode fetch entirely.

`GET /Shows/{id}/Seasons?userId=` → `IndexNumber` = season number. Episodes carry `ParentIndexNumber` (season) + `IndexNumber` (episode) + `UserData.Played` / `UserData.LastPlayedDate` (ISO string).

## LastPlayedDate precision — and using it as a provenance signature

Reading it back gives **7 fractional-second digits** with a `Z` suffix — .NET `DateTime` tick precision (100 ns):

```
"LastPlayedDate": "2026-08-06T02:50:18.2351458Z"
```

JS `Date` holds milliseconds, so `new Date(raw)` truncates `.2351458` → `.235`. The stored value and Jellyfin's string then differ *textually* while being the same instant to the millisecond — don't treat a string mismatch as a sync bug; compare `getTime()`.

That truncation is a free **provenance signature** when auditing a mixed-origin watch log:

- **Sub-second** (`.235`) — read *from* Jellyfin; a real `LastPlayedDate` survived into your DB.
- **Whole second** (`.000`) — went the other way, or came from elsewhere. Writing played state with `datePlayed=new Date(x).toISOString()` normalizes to whole seconds, so anything you pushed *to* Jellyfin comes back whole-second, as does anything from an epoch-seconds source (Plex).

One SQL group-by over the precision therefore tells you which rows a past bulk import actually touched, and in which direction — useful when a source column was preserved on update and left no other trace.

⚠️ `LastPlayedDate` is a genuine instant, not a calendar date. In a negative UTC offset an evening watch is already "tomorrow" in UTC (19:50 Pacific → `02:50Z`), so slicing the date prefix for display reports it a day late — format through `Intl.DateTimeFormat` with an explicit `timeZone`. See `javascript-date-only-parsing-timezone.md`.

⚠️ Both list calls above take a hard `limit` with no paging in this recipe — `TotalRecordCount` is in the response, so compare it against the returned length rather than assuming you got everything.

## MediaStreams

`Type` is `"Video"` | `"Audio"` | `"Subtitle"` | `"EmbeddedImage"` — filter, or a 5000px cover-art "stream" wins a height comparison.

- **`Language` is ISO 639-2** (`"eng"`, `"rus"`, `"fre"`), not 639-1, and there is no display-name field.
- **`VideoRangeType`** carries the HDR flavour. The upstream enum (`Jellyfin.Data/Enums/VideoRangeType.cs`) has 13 members; the ones easy to forget are `DOVIWithEL`, `DOVIWithELHDR10Plus` and `DOVIInvalid` — all still Dolby Vision files, so a map that omits them reports SDR.
- Atmos shows up in `Profile` (`"Dolby Digital Plus + Dolby Atmos"`) and in `DisplayTitle`.
- **No resolution token** — only `Width`/`Height`. Derive it tolerantly: scope encodes are narrower *and* shorter than nominal (a 2.39:1 UHD is 3822×2066, a cropped 1080p is 1920×800), so match on either dimension clearing a floor rather than on exact sizes.

## ISO 639-2 → name + 639-1, with no lookup table

`Intl` handles this, including the bibliographic/terminological pairs (`fre`/`fra`, `ger`/`deu`) that trip hand-rolled maps:

```js
new Intl.Locale("eng").language                              // "en"
new Intl.DisplayNames(["en"], { type: "language" }).of("eng") // "English"
```

Guard `"und"`: `Intl.Locale("und").language` is `undefined` and `DisplayNames.of("und")` returns `"root"`. ICU also echoes an unknown tag straight back, so treat `resolved === input` as "no name".

## Deep links

`{base}/web/#/details?id={itemId}&serverId={serverId}` — no `#!`. Read out of the served client bundle rather than guessed:

```bash
curl -s "$JF/web/main.jellyfin.bundle.js" | grep -o '#/details?id='
```

`serverId` comes from `GET /System/Info` → `Id`.

## Resume position (partly-watched items)

Separate from `Played`, and what an in-app player needs to continue where a TV client stopped.

- **Read/write:** `GET|POST /UserItems/{itemId}/UserData?userId=`. The POST body (`UpdateUserItemDataDto`) takes
  `PlaybackPositionTicks`, `Played`, `PlayCount`, `LastPlayedDate`, `PlayedPercentage`, `IsFavorite`. Also readable as
  the `UserData` block on any item, or in bulk via `GET /UserItems/Resume?userId=&mediaTypes=Video`.
- **Unit: 10,000,000 ticks = 1 second.** Live sample:
  `{"PlayedPercentage":85.79,"PlaybackPositionTicks":31923138320,"PlayCount":2,"Played":false}`.
- **Do NOT report through `/Sessions/Playing*`** when authenticated with a server API key — those return 204 and write
  nothing, because the API-key session's `UserId` is the all-zero GUID and the server iterates zero users. The
  `?userId=`-taking endpoints work because an API key carries the Administrator role.

### Server-side thresholds decide what "finished" means

From `GET /System/Configuration` (defaults, confirmed on 10.11.11): `MinResumePct: 5`, `MaxResumePct: 90`,
`MinResumeDurationSeconds: 300`. `UserDataManager.UpdatePlayState` computes `pctIn = position / runtime * 100`:

| condition | result |
|---|---|
| below `MinResumePct` (5%) | position reset to 0 — no resume point |
| above `MaxResumePct` (90%), or within 1s of the end | position 0 **and** `Played: true` |
| in between, runtime ≥ 300s | position kept |
| in between, runtime < 300s | position 0 + `Played: true` |

Mirror these client-side if your app decides "watched" itself, or the two stores disagree about the same playback.
Two traps: a `Stopped` report that **omits** `PositionTicks` is treated as completion and marks the item played; and
anything under five minutes never gets a resume point at all.

### Write semantics, probed on 10.11.11

Three things worth knowing before building on these endpoints. All verified reversibly on one unwatched movie.

- **`POST /UserItems/{id}/UserData` MERGES — it does not replace.** A body of `{"PlaybackPositionTicks": N}` alone
  leaves every other field intact, so there is no read-modify-write and no race with whatever else touches the item.
  Prove this with a **non-default** canary: set `IsFavorite: true` first, then POST the position and check it
  survived. A probe that only inspects fields already sitting at their C# defaults (`false`/`0`) is worthless —
  "kept" and "reset to default" look identical.
- **`DELETE /UserPlayedItems/{id}` also zeroes `PlaybackPositionTicks`.** Clearing played leaves no stranded resume
  point, so "unwatch" really does return the item to untouched.
- **`POST /UserPlayedItems/{id}` increments `PlayCount` every call** (measured 1 → 2 → 3), including when re-posting
  the same `datePlayed`. So correcting a stored watch *date* through this endpoint inflates the count. The
  alternative is `POST /UserItems/{id}/UserData` with `{"Played": true, "LastPlayedDate": "…"}`, which sets both and —
  being a merge — leaves `PlayCount` exactly as it was. Choose by whether you care more about the count staying
  honest or about getting whatever else the server does when an item transitions to played. Marking played by either
  route clears the resume position.

Plex, for contrast: `GET /:/scrobble` and `GET /:/unscrobble`, both with
`?identifier=com.plexapp.plugins.library&key={ratingKey}`. They answer 200 with an **empty body**, so a JSON-parsing
client throws on them — issue them as bare requests. Plex has no way to say *when* something was watched; a scrobble
always stamps "now".

### `MinResumePct` is a PERCENTAGE — and it only applies on write

Easy to mirror thoughtlessly and then chase a phantom bug. 5% scales with the runtime, so on a 102-minute film the
resume floor is **5 min 06 s**: stop at five minutes and the position is discarded, by design, with no error. A
percentage is the wrong unit for "did you actually start watching this" — an absolute floor (say 60 s) matches what
a viewer expects and does not stretch with the film.

Crucially the rule is applied when a position is **stored**, never when one is read. So a client that writes
`PlaybackPositionTicks` directly (via `POST /UserItems/{id}/UserData`) may store a sub-threshold position that the
server itself would have thrown away, and **every other Jellyfin client will happily resume from it**. Diverging
downward is safe; diverging on `MaxResumePct` is not, because that one also decides "played".

