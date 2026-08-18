# MCP surface: exact shapes and traps

The `mcp__plugin_Notion_notion__*` tools are Notion's own OAuth-backed MCP server — **not** a thin
wrapper over the public REST API. It exposes things REST does not (SQL over data sources, a view DSL,
folders, skills), which is why the "the public API cannot create views" note below does not apply to
it. Schemas are deferred — load what you need in **one** `ToolSearch` call before use.

None of the v3 quirks apply here, and none of these calls need `token_v2` or Doppler. This is the
default surface; `SKILL.md` has the table of operations that force a drop to v3.

## Reading rows — `notion-query-data-sources`

The best tool in either API for reading. Real SQL, and it sidesteps the v3 view-id trap completely.

```json
{"data": {"data_source_urls": ["collection://<uuid>"],
          "query": "SELECT \"Name\", url FROM \"collection://<uuid>\" WHERE \"Status\" = 'Done' ORDER BY \"Name\""}}
```

The `collection://` URL appears in **both** the array and the `FROM` clause. Verified working: quoted
property names, `url` as a pseudo-column returning the page URL, `AS` aliases, `LIKE '%x%'`,
`ORDER BY`, `count(*)`, `count("Prop")`, `count(CASE WHEN "Status"='To do' THEN 1 END)`.

**The date trap:** a date property is *not* queryable by its schema name. Use the expanded columns
`date:<Prop>:start`, `date:<Prop>:end`, `date:<Prop>:is_datetime`. Notion's own data-source blob says
so: `"Main schema name not queryable."` Multi-select and checkbox values also come back oddly encoded —
inspect before parsing.

## Editing a row — `notion-update-page`

```json
{"page_id": "<uuid>", "command": "update_properties",
 "properties": {"date:Start:start": "2026-07-25", "date:End:start": "2026-08-02", "Dates": null}}
```

Dates use the same expanded keys as the SQL layer. A plain `null` clears any property.

**The response tells you nothing** — just `{"page_id": "..."}`, never the written values. A wrong
property key therefore succeeds silently. Verify with a follow-up `notion-query-data-sources` rather
than trusting the return.

Beyond properties the same tool exposes `update_content` (up to 100 `old_str`/`new_str` ops),
`replace_content`, `insert_content` (`content` plus `position: {"type": "start"}` or `{"type": "end"}`
— an object, not a string; omit to append), `apply_template`, and `icon`/`cover`.

`allow_deleting_content: true` on `replace_content` **or** `update_content` deletes child pages and
databases absent from the new content. It is not the only destructive MCP call —
`notion-update-data-source` also takes `DROP COLUMN` (destroys that column's data on every row) and
`in_trash: true` ("Cannot be undone without Notion UI"). Confirm all of these with the user.

**No bulk write exists.** One call per page: a 31-row maintenance pass cost 213 calls. Above ~50 row
edits, or when the edits must be atomic, go v3.

## Creating a database — `notion-create-database`

```json
{"parent": {"type": "page_id", "page_id": "<uuid>"}, "title": "Conventions",
 "schema": "CREATE TABLE (\"Task\" TITLE, \"Date\" DATE, \"Link\" URL, \"Priority\" SELECT('P1':red, 'P2':orange), \"Status\" SELECT('To do':default, 'Done':green))"}
```

Returns the page URL, the `collection://` data-source URL, and the resolved schema. Far less work than
the v3 equivalent (hand-built collection + `collection_view` block + `listAfter`).

`notion-update-data-source` handles DDL afterwards. Columns can be added, dropped, renamed and retyped
(`ADD COLUMN "X" SELECT('a':red, ...)`, `DROP COLUMN`, `RENAME COLUMN`, `ALTER COLUMN "X" SET ...`).
**Select options, however, are add-only:** new options can be added, but recoloring or dropping an
individual option is rejected with `Cannot update color of select with name: X`. The only way to shed
an option through MCP is `DROP COLUMN`, which destroys the whole column — so this is the single most
common reason to drop to v3.

## Views — `notion-create-view` / `notion-update-view`

```json
{"database_id": "<uuid>", "data_source_id": "<uuid>", "name": "Calendar", "type": "calendar",
 "configure": "CALENDAR BY \"Date\""}
```

`notion-update-view` takes `{"view_id": "...", "configure": "SORT BY \"Start\" ASC"}`. Both work.

Do not be misled by the note in the toolbox repo's `rtm_to_collection.py` that "the public API cannot
create views at all" — that refers to the plain REST API; the MCP layer does expose view creation.

Grouping and property visibility **are** expressible — `GROUP BY "Prop"` sets `query2.group_by`,
`SHOW`/`HIDE` set visible properties, `CLEAR GROUP BY` removes grouping. Check
`notion://docs/view-dsl-spec` before assuming a limit.

What MCP view config cannot express, all v3-only: `format.conditional_color_rules` (row banding), the
`format.collection_groups` array itself (per-group order, the catch-all bucket, the collapsed `hidden`
flags), per-column widths, and schema-level `date_format`. Drop to v3 only when you need the group
entries themselves. There is also **no delete-view tool**.

## Orientation — `notion-fetch`

Accepts a URL, a dashed uuid, or a bare 32-char id. Best tool for "what is this page, where does it
sit, what is on it". `id: "self"` returns the workspace and user identity.

It also returns inline images as markdown pointing at **pre-signed S3 URLs** (`X-Amz-Expires=300`,
no cookie needed) — strictly better than the v3 `getSignedFileUrls` → 403 → image-proxy dance. For
*reading* images, MCP wins; v3 is only needed to re-upload.

Two doc resources are published by the plugin and readable by passing the URI as `notion-fetch`'s `id`:
`notion://docs/enhanced-markdown-spec` and `notion://docs/view-dsl-spec`. They are the authoritative
answer to what MCP can express in a page body and in a view — consult them before assuming a limit.

**File/attachment blocks are the exception:** `notion-fetch` on one returns a blank page.
`notion-download-attachment` only handles UTF-8 text under 200 KiB uploaded by the same integration. A
binary attachment (a PDF) is unreachable from MCP — and v3 does not rescue it either: the image proxy
returns 422 and the signed URL 403. Ask the user to download it manually.

## Other tools worth knowing

- `notion-move-pages` — takes up to 100 ids, but **extends the destination schema** with the source's
  unmatched properties instead of dropping them. Check the target schema afterwards.
  `new_parent: {type: "workspace"}` makes pages private; the tool itself warns against it.
- `notion-duplicate-page` — asynchronous; the returned id is not immediately populated.
- `notion-get-teams` — the working replacement for v3's retired `getTeams`.
- `notion-get-comments` / `notion-create-comment` — the only *worked* surface for discussions. v3 does
  have `discussion` and `comment` record tables (`syncRecordValues` accepts both pointers), but no
  endpoint for creating or listing them is known, so use MCP.
- `notion-get-users` — real cursor pagination (`start_cursor` / `next_cursor`, `page_size` ≤ 100).
- Async writes: `allow_async: true` on `notion-update-page` / `notion-create-pages` returns an
  `async_task` with a suggested backoff, polled via `notion-get-async-task`
  (`queued|running|retrying|succeeded|failed`). This is the only retry mechanic on either surface.
- `notion-search` — `page_size` defaults to 10, max 25. Much tighter than v3's 1000-result search.

## Failure that is not Notion's

Claude Code's own auto-mode classifier can deny an MCP write. It surfaces as a refusal, not a Notion
error — re-read the message before concluding the API rejected anything.
