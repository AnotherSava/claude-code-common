# Reading data out of v3

## The permission envelope

Every record in a `recordMap` arrives as `{"value": {"role": "editor", "value": {...the record...}}}`.
Older responses put the record directly under `value`, so code that assumes one shape breaks on the
other. Always go through the helper:

```python
from notion_tools.client import unwrap_record
rec = unwrap_record(resp["recordMap"]["block"][block_id])
```

This is not theoretical: `get_spaces()` read one level too few and raised `KeyError: 'name'`, which
killed both `notion clear-trash` and `notion clear-teamspace` at their first call.

## `syncRecordValues` — fetch records by id

```python
c.post("syncRecordValues", {"requests": [
    {"pointer": {"table": "block", "id": bid}, "version": -1} for bid in ids]}).json()
```

`table` is `block`, `collection`, `collection_view`, `space`, or `notion_user`. Batch ~100 pointers per
call; do **not** loop one call per id. Results land in `recordMap[<table>][<id>]`.

This is also the reverse-engineering tool: configure a feature in Notion's UI, then `syncRecordValues`
the block to see exactly what shape Notion persisted. It works even on trashed blocks. Most of the
view-format knowledge in these files was discovered that way.

## `queryCollection` — fetch rows

Two calling conventions both work; they differ in argument names, reducer key, and result path.

```python
# Form A — terse
{"collection": {"id": COLL}, "collectionView": {"id": VIEW},
 "loader": {"type": "reducer", "reducers": {"collection_group_results": {"type": "results", "limit": 500}},
            "searchQuery": "", "userTimeZone": "UTC"}}
# → result.reducerResults.collection_group_results.blockIds

# Form B — the collectionId/collectionViewId spelling; `source` and `query` are both optional
{"collectionId": COLL, "collectionViewId": VIEW, "query": {},
 "source": {"type": "collection", "id": COLL, "spaceId": SPACE},
 "loader": {"type": "reducer", "reducers": {"results": {"type": "results", "limit": 10000}},
            "searchQuery": "", "userTimeZone": "UTC"}}
# → result.reducerResults.results.blockIds
```

**Filters and sorts go inside the loader, in either form** — the top-level `query` key is inert. A
`string_contains` filter placed in `query` returned all 30 rows; the same filter in the loader returned
18. Sorts behave identically. So a filter written the obvious way silently reads the whole table:

```python
"loader": {..., "searchQuery": "", "userTimeZone": "UTC",
           "filter": {"operator": "and", "filters": [...]}, "sort": [...]}
```

**`userTimeZone` is required inside the loader**; `searchQuery` is optional despite appearing in every
example (dropping it still returns 200). Omit `userTimeZone` and you get a contentless
`400 {"name":"ValidationError","debugMessage":"Invalid input."}` that names no field and reads like a
malformed query.

**`collectionViewId` must be a real *view* id, not the `collection_view` block id.** They are easily
confused: the block that embeds the table has its own uuid and a `view_ids` array, and only entries in
that array are valid. The same bare `ValidationError` is the symptom. Resolve first:

```python
blk = unwrap_record(sync_resp["recordMap"]["block"][cv_block_id])
view_id = blk["view_ids"][0]
```

Rows come back in `recordMap.block` mixed with other records — filter by `parent_id == collection_id`
and `alive`.

## Finding the collection on a page

Read the host page's `content`, batch-fetch the children in **one** call, and take the first
`collection_view` block:

```python
page = unwrap_record(resp["recordMap"]["block"][host_page_id])
space_id, content = page["space_id"], page.get("content", [])
children = c.post("syncRecordValues", {"requests": [
    {"pointer": {"table": "block", "id": cid}, "version": -1} for cid in content]}).json()["recordMap"]["block"]
for bid in content:
    blk = unwrap_record(children[bid])
    if blk.get("type") in ("collection_view", "collection_view_page"):
        collection_id = blk.get("collection_id") or blk.get("format", {}).get("collection_pointer", {}).get("id")
        if collection_id:
            view_ids = blk.get("view_ids", [])
            break
```

Both type checks matter: a **full-page** database is a `collection_view_page`, and matching only
`collection_view` silently finds nothing (the loop falls through and the next line raises `NameError`).
The `format.collection_pointer.id` fallback covers blocks that carry no direct `collection_id`.

## Pagination — there mostly isn't any

All the reliable knowledge here is negative:

- `search` caps hard at **1000 results**, and its pagination tokens *cycle*, returning duplicates
  rather than advancing. To process more, delete/handle in batches and re-query until empty.
- No proven `queryCollection` pagination idiom exists. Everything in practice asks for everything at
  once (`limit: 10000`). A collection past ~10,000 rows is unexplored territory.
- Do not assume REST-style cursors anywhere in v3. MCP *does* have real cursors — prefer it for large
  reads.

## Recovering blocks you just trashed

`getActivityLog` is the only path — `loadPageChunk` and the `BlocksInSpace` search both filter out
`alive: false` non-navigable blocks.

```python
c.post("getActivityLog", {"spaceId": SPACE, "navigableBlockId": PAGE, "limit": 500})
```

The response's `recordMap.block` includes the trashed children with `alive: false` and their original
`properties` intact — including image `source` attachment URLs, so content is reconstructable.

## Probing whether an endpoint still exists

Notion retires v3 endpoints silently. A retired one answers `404` with an **HTML** body, so `.json()`
raises `JSONDecodeError` and looks like a parse bug. Probe with a minimal body: HTML means gone, a
`ValidationError` means alive but unhappy with your arguments.

```python
r = c.post(endpoint, {})
gone = "html" in r.headers.get("content-type", "")
```

`getTeams` and `submitTransaction` were both alive in older notes and are dead now. Use MCP
`notion-get-teams` for teamspaces.

## Downloading files

`getSignedFileUrls` returns URLs that 403 from `file.notion.so` even with a valid cookie — that domain
enforces browser-session checks beyond `token_v2`. Use the image proxy instead:

```
https://www.notion.so/image/<URL-encoded attachment URL>?table=block&id=<host_block_id>&spaceId=<space_id>&width=2000&cache=v2
```

It honours the cookie and even converts HEIC to JPEG. It does **not** work for PDFs (422, `Invalid
image`) — and MCP does not rescue them either: `notion-fetch` on a file block returns a blank page, and
`notion-download-attachment` only handles small UTF-8 text. There is no known `token_v2` path to a PDF
attachment; ask the user to download it from their signed-in browser.

When caching downloads, key by the attachment UUID, not the title: two rows with the same title
overwrite each other. The `attachment:<uuid>:<filename>` reference carries a unique UUID — include its
first 8 chars in the cache filename.
