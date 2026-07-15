# Plex Media Server — read-only library API

How to read a Plex library over HTTP and match it against an external catalog (TMDB/TVDB/IMDB ids) — e.g. to mark which titles of a tracked collection you actually have in Plex, and pull their watch state. Observed mid-2026 against a local Plex Media Server. Every endpoint here is read-only; none mutate Plex.

## Auth + base

- Base URL: `http://<host>:32400` (a local server is `http://localhost:32400`).
- Token: send `X-Plex-Token: <token>` as a **header** (a `?X-Plex-Token=` query param also works, but the header keeps it out of URLs/logs).
- Ask for JSON with `Accept: application/json` — otherwise Plex returns XML.
- Every response is wrapped in a top-level `MediaContainer` object.

### Getting a token without the account OAuth flow

Modern Plex writes a **local admin token** to a file — no `Preferences.xml` scraping needed:

- Windows: `%LOCALAPPDATA%\Plex Media Server\.LocalAdminToken`
- (Older Plex stored `PlexOnlineToken="…"` as an attribute in `Preferences.xml` in the same dir.)

Read that file and use its contents as `X-Plex-Token` for a server on the **same machine**. For a remote/VPS deploy, use a stable account token instead (see https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/) — `.LocalAdminToken` is machine-local and can rotate.

## Endpoints

| Endpoint | Returns | Key fields |
|---|---|---|
| `GET /identity` | server identity (**unprotected** — needs no token) | `MediaContainer.machineIdentifier` (stable server id), `version`, `claimed` |
| `GET /library/sections` | the libraries | `MediaContainer.Directory[]`: `key`, `type` (`show`/`movie`/`artist`/…), `title` |
| `GET /library/sections/{key}/all?includeGuids=1` | all items in a library | `MediaContainer.Metadata[]`: `ratingKey`, `type`, `title`, `year`, `childCount` (# seasons), `viewCount`, `lastViewedAt`, `Guid[]` |
| `GET /library/metadata/{ratingKey}/children` | a show's seasons | `Metadata[]`: `index` (**= season number**), `title`, `leafCount`, `viewedLeafCount`, `ratingKey` |
| `GET /library/metadata/{ratingKey}/allLeaves` | every episode of a show | `Metadata[]`: `parentIndex` (season), `index` (episode), `viewCount`, `lastViewedAt` |

- `includeGuids=1` is **required** to get the `Guid[]` array on the section-item listing.
- `X-Plex-Container-Size=<n>` pages results — pass a large value (e.g. `5000`) to get a whole library in one call.

## Matching to an external catalog — by ID, never by title

Every movie/show carries a `Guid[]` of external ids:

```json
"Guid": [{ "id": "imdb://tt0944947" }, { "id": "tmdb://1399" }, { "id": "tvdb://121361" }]
```

Parse `scheme://value` and match against your catalog by **tmdb, then tvdb, then imdb** — exact, no fuzzy title matching. Items Plex couldn't identify have an **empty `Guid`** (loose/untagged files); skip them as unresolvable.

```ts
function parseGuids(item: { Guid?: { id: string }[] }) {
  const out = { tmdb: null as number | null, tvdb: null as number | null, imdb: null as string | null };
  for (const g of item.Guid ?? []) {
    const [scheme, value] = g.id.split("://");
    if (!value) continue;
    if (scheme === "tmdb") out.tmdb = Number(value) || null;
    else if (scheme === "tvdb") out.tvdb = Number(value) || null;
    else if (scheme === "imdb") out.imdb = value;
  }
  return out;
}
```

## Watch state

- `viewCount > 0` = watched at least once (both movies and episodes). `null`/absent = unwatched.
- `lastViewedAt` is a **Unix epoch in SECONDS** — convert with `new Date(lastViewedAt * 1000)`.
- Season roll-ups: `viewedLeafCount` / `leafCount` on the season object. Per-episode watch state comes from `allLeaves`; match it to your catalog by `(parentIndex, index)` = `(season, episode)` number.
- Season `index` uses the metadata agent's numbering (usually TMDB's), so it lines up with a TMDB-derived catalog's season numbers.

## Deep-linking to watch an item

To open an item's page in the Plex web app (where the user clicks Play), build an `app.plex.tv` link from the server's `machineIdentifier` (from `/identity`) + the item's `ratingKey`:

```
https://app.plex.tv/desktop/#!/server/{machineIdentifier}/details?key=%2Flibrary%2Fmetadata%2F{ratingKey}
```

- URL-encode the `key` value: `/library/metadata/{ratingKey}` → `%2Flibrary%2Fmetadata%2F{ratingKey}`.
- Opens the show/movie **details page**; Plex's own Play button honors the saved playback offset, so it **resumes** a partly-watched episode/movie from where you left off (not a restart). So the **item-level** `ratingKey` is enough — no need to resolve a per-episode ratingKey, which also keeps you off the `/allLeaves` fetch (and any per-show episode cursor you built to avoid it).
- Routes to the user's own server (via `machineIdentifier`) from any device signed into plex.tv.
- Caveat: the `#!/…?key=…` fragment is the Plex web app's own routing convention (same shape as its "Get Link" share URLs), **not** a formally published/stable spec — verify against a real share URL if it ever breaks.

## Gotchas

- The `?X-Plex-Container-Size=0` "just give me `totalSize`" trick often returns `totalSize: null` on recent Plex — count `Metadata.length` from a real fetch instead.
- **Multiple libraries can share a `type`** (e.g. two `movie` sections — a main one and a private/adult one). Don't assume one library per type: filter by section `title` via an allowlist so you don't scan (or surface titles from) libraries the user doesn't want tracked.
- Some real items still have an empty `Guid` (Plex couldn't match them) — they're indistinguishable from junk files at the API level; treat "no external id" as unresolvable uniformly.
