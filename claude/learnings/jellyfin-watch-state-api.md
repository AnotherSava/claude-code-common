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
