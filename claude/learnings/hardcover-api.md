# Hardcover API — matching books, and what its terms ask of a public site

Hardcover is a books catalog with a GraphQL API (Hasura), usable with a personal token. It is the cleaner alternative to Open Library for works, editions and series. These notes come from building a Goodreads import and a book search against it in 2026-10.

## Access

- Endpoint `https://api.hardcover.app/v1/graphql`, header `authorization: Bearer <token>`. Tokens are made at `hardcover.app/account/api` with an expiry and scopes; **`read:catalog` alone is enough** for search, `books`, `editions` and `book_mappings`.
- The API is labelled beta: the docs say it may change without notice and tokens may be reset, so a 401 is an expected event that means "replace the token".
- Limits on the free plan: 60 requests a minute, a burst of 10, 5,000 a day. **Each top-level field in a request costs one**, nested selections are free, and a request with more top-level fields than the burst is refused outright with a 403. `RateLimit` / `Retry-After` headers come back on every response.
- Query-level failures (missing scope, bad field) arrive as **HTTP 200 with an `errors` array** — check it, or a failure parses as empty data.
- `_like`, `_ilike`, `_regex` and friends are disabled; text matching goes through the `search` field. Search has a 2-second timeout.
- Queries must run server-side; the docs forbid shipping a token to a browser.

## Search returns everything a catalog row needs

`search(query: "...", query_type: "Book", per_page: N) { results }` returns `results.hits[].document` with `id` (a string), `title`, `release_date`/`release_year`, `description`, `pages`, `image.url`, `contributions[{author{name}, contribution}]`, `genres`, `featured_series{position, series{name}}`, `isbns`, `alternative_titles`. Adding a book from a search hit takes no second request.

A search for a translated title often finds the original work (its `alternative_titles` carry translations), but for less-known books in another script it returns nothing by that author. Combining a Cyrillic title with a Latin author name in one query did worse than the title alone.

`contributions` include translators and illustrators; a missing `contribution` role means the primary author, so filter on `!contribution || contribution === "Author"`.

## Matching an exact edition: `book_mappings`

Hardcover records other platforms' ids for its editions in `book_mappings`, and **platform 1 is Goodreads**:

```graphql
query ($e: String!) { book_mappings(where: {platform_id: {_eq: 1}, external_id: {_eq: $e}}, limit: 1) { book_id edition_id } }
```

A Goodreads export's `Book Id` is an edition id, so this resolves the exact edition on the shelf, translated editions included. On a 457-book library it placed 380 books exactly, where ISBN lookup plus title search had placed fewer and guessed wrong on translations. Order that worked: Goodreads id → `editions(where: {isbn_13: {_eq}})` → `editions(where: {isbn_10: {_eq}})` → search accepting only a same-titled book by the same author. `platforms(limit: 50) { id name }` lists the other platform ids (librarything 2, openlibrary 3, …).

Book-level fields worth fetching by id: `books(where: {id: {_in: $ids}}) { id title release_date release_year description pages image { url } cached_contributors cached_tags featured_book_series { position series { name } } }`. Genres are in `cached_tags.Genre[].tag`.

## A public site showing its covers needs a DMCA policy

Covers on Hardcover are uploaded by its users, and its API terms tell any public site using its images to publish a DMCA takedown policy (and a commercial one to register a DMCA agent). A personal site with public catalog pages counts. Covers are served from `assets.hardcover.app`, which a Next.js app has to add to `images.remotePatterns`.
