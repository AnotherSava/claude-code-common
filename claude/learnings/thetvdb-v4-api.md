# TheTVDB v4 API

Reference for integrating TheTVDB v4 (the community TV/movie database), learned building a TMDB→TVDB
metadata fallback. Base URL `https://api4.thetvdb.com/v4`. The rendered Swagger UI at
`thetvdb.github.io/v4-api` is JS-only (WebFetch sees an empty shell) — fetch the raw spec instead:
`https://raw.githubusercontent.com/thetvdb/v4-api/main/docs/swagger.yml`.

## Auth

- `POST /login` with JSON body `{ "apikey": "...", "pin": "..." }` → `{ "status": "success", "data": { "token": "..." } }`.
  Omit `pin` entirely for a licensed key.
- The bearer token is valid **~1 month**. Cache it; send `Authorization: Bearer <token>` on every other call.
  Re-login once on a 401, then retry.

## Key types (matters when applying for a key)

- **Licensed / project key**: `apikey` only. Free tier for projects under $50k revenue, **with attribution**
  (link back to thetvdb.com).
- **User-supported key**: `apikey` + each end-user's **subscriber PIN**, which requires a paid TVDB
  subscription (~$12/yr). The `/login` flow is the discriminator: pin present → user-supported.

## Response envelope

Every response is `{ status, data, links? }`. `links` (pagination) appears on list endpoints:
`{ prev, self, next, total_items, page_size }`.

## Endpoints

- `GET /series/{id}/extended` → SeriesExtendedRecord (has top-level `overview`, `image`, `firstAired`,
  `status.name`, `genres[]`, `seasons[]`, `remoteIds[]`, `averageRuntime`).
- `GET /movies/{id}/extended` → MovieExtendedRecord.
- `GET /series/{id}/episodes/{season-type}?page=N` → `{ data: { series, episodes[] }, links }`. Paginate by
  following `links.next` (or incrementing `page` until `episodes` is empty). `season-type` ∈
  default | official | dvd | absolute | alternate | regional; **"default" = aired order** (matches TV Time
  and most trackers).

## Gotchas (each caused a real bug)

1. **Season records come in every ordering type.** `SeriesExtendedRecord.seasons` contains a SeasonBaseRecord
   per ordering type, so multiple entries share the same `number` (official S1, absolute S1, dvd S1…). Matching
   a season by number alone can grab the wrong record's id/name/image. Episodes are fetched in "default" (aired)
   order, so pick the official-type season:
   ```
   seasons.find(s => s.number === n && s.type?.type === "official") ?? seasons.find(s => s.number === n)
   ```
2. **Movies have no top-level `overview`.** A movie's synopsis lives in `translations.overviewTranslations[]`,
   returned ONLY with `?meta=translations`. Series DO carry a top-level `overview`. So request
   `GET /movies/{id}/extended?meta=translations` and read
   `translations.overviewTranslations.find(t => t.language === "eng")?.overview`.
3. **Unknown dates are empty strings, not null.** `firstAired`, `first_release.date`, and episode `aired` come
   back as `""`. Use `||` (not `??`) to coerce, or a year fallback never fires and `""` poisons date comparisons.
4. **Image fields are absolute URLs** on `artworks.thetvdb.com` (occasionally a bare `/banners/...` path —
   normalize by prefixing the host). Whitelist the host if hotlinking (e.g. Next.js `images.remotePatterns`).
5. `remoteIds[]` carries external ids as `{ id, type, sourceName }` — match `sourceName` case-insensitively
   (e.g. contains "imdb").
6. TVDB `score` is its own scale — don't fold it into a field that holds a TMDB/IMDB-style rating.

## Where it fits

TVDB earns its keep as a *fallback* for niche/fan/web titles a TMDB-primary catalog can't resolve — TMDB is
generally deeper on commercial releases with richer metadata, while TVDB's community model casts a wider net on
the fringe. Keep one provider canonical per item (store an explicit source field; don't infer from which id is
null) so episode-numbering semantics stay consistent within a title.
