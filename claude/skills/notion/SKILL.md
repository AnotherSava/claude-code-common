---
name: notion
description: >-
  Work with Notion through the right API — the MCP integration by default, and the internal v3 API
  (token_v2 cookie, /api/v3/) for the operations MCP provably cannot do: select-option recolor/removal,
  date formats, reminders, conditional row colours, grouped views, bulk row writes, and anything
  destructive.
  TRIGGER when: reading or writing Notion pages, databases, rows, schemas or views; an
  mcp__plugin_Notion_notion__* call failed, was rejected, or silently did nothing; or the user asks to
  change how a Notion table looks.
  DO NOT TRIGGER for Notion-adjacent work that never calls an API (writing prose destined for Notion),
  or when a task-specific skill already owns the database (flightradar24, update-conventions) — start
  there and come here only for the underlying technique.
---

# Notion: two APIs, one decision table

Notion is reachable two ways, and picking wrong is the usual failure. **Default to MCP.** Drop to the
internal v3 API only for an operation on the closed list below — not on the first error.

## Context
- Toolbox tooling: !`python -c "import notion_tools,pathlib;print(pathlib.Path(notion_tools.__file__).resolve().parents[3])" 2>/dev/null || echo MISSING`
- Notion token: !`T=$(python -c "import notion_tools,pathlib;print(pathlib.Path(notion_tools.__file__).resolve().parents[3])" 2>/dev/null) && ( cd "$T" && doppler secrets --only-names 2>/dev/null | grep -q NOTION_TOKEN_V2 && echo PRESENT || echo MISSING ) || echo NO-TOOLING`

If **Toolbox tooling** is `MISSING`, only the MCP half of this skill is available: the v3 client is the
`notion_tools` package from the user's `toolbox` repo, installed with `pip install -e .`. If **Notion
token** is `MISSING`, v3 cannot authenticate — see *Running a v3 call* below.

## Which surface

| Operation | Surface | Why |
|---|---|---|
| Read rows, filter, aggregate | **MCP** `notion-query-data-sources` | Real SQL. Avoids the v3 view-id trap entirely. |
| Read a page, resolve ancestry, get inline image URLs | **MCP** `notion-fetch` | Returns pre-signed S3 image URLs needing no cookie — v3 needs the proxy dance. |
| Edit page properties (under ~50 rows) | **MCP** `notion-update-page` | Safer, no transaction to hand-assemble. |
| Create a database with a simple schema | **MCP** `notion-create-database` | One DDL string vs. hand-building collection + block + `listAfter`. |
| Create/repoint a view (coarse config) | **MCP** `notion-create-view` / `notion-update-view` | Type, name, `CALENDAR BY`, `SORT BY` all work. |
| Create rows in bulk (plain values) | **MCP** `notion-create-pages` | Takes up to 100 rows under one parent per call — twice v3's batch. |
| Comments, teamspaces | **MCP** only | v3 has no comment endpoint, and v3 `getTeams` is dead. |
| Enumerate workspace users | **MCP** `notion-get-users` | Cursor-paginated, lists guests. v3 reads a single `notion_user` via `syncRecordValues` but cannot list members. |
| **Recolor or remove a select option** | **v3** | MCP columns can be added/dropped/renamed, but its *options* are add-only: `Cannot update color of select with name: X`. |
| **Date format on a column** | **v3** | Schema-level `date_format`; not exposed by MCP. |
| **Date reminders** | **v3** | Lives inside the date property value. |
| **Conditional row colours / banding** | **v3** | `format.conditional_color_rules` on the view. |
| **Column widths, group entries** | **v3** | `format.table_properties[i].width` and the `format.collection_groups` array. Plain grouping and property visibility are **MCP** — `GROUP BY` / `SHOW` / `HIDE`. |
| **Trash a row, page or view** | **v3** | MCP has no verb that trashes an individual row, page or view — though it *is* destructive elsewhere, see below. |
| **Bulk row edits (50+), or rows needing rich-text values** | **v3** | `notion-update-page` is one call per page; v3 batches ~50 per transaction. |

Two things are impossible on **both** surfaces — stop looking: **column text alignment** (every field
name persists, none renders; it is UI-only) and **enabling Sub-items** (a UI toggle; afterwards the
paired relation properties *are* writable via v3).

**MCP is not the safe surface.** It has no verb for trashing a row, page or view, but three of its
calls destroy data: `notion-update-data-source` with `in_trash: true` ("cannot be undone without
Notion UI") or `DROP COLUMN` (wipes that column on every row), and `notion-update-page` with
`allow_deleting_content: true` on `replace_content` **or** `update_content` (deletes child pages and
databases missing from the new content). Confirm those with the user exactly as you would a v3 delete.

## Running a v3 call from any project

`notion_tools` is an editable install, so it imports from any cwd — but the token comes from Doppler,
which is bound to the toolbox directory. Derive that directory and run there:

```bash
TOOLBOX="$(python -c "import notion_tools,pathlib;print(pathlib.Path(notion_tools.__file__).resolve().parents[3])")"
( cd "$TOOLBOX" && PYTHONIOENCODING=utf-8 doppler run -- python <<'EOF'
from notion_tools.client import create_client
c = create_client()
...
EOF
)
```

Use a subshell so the `cd` does not follow you back and misdirect later file writes. Always a heredoc,
never `python -c`. `PYTHONIOENCODING=utf-8` is not optional on Windows — Notion values carry `→`, the
reminder marker `‣` and non-ASCII titles, and the default console codec crashes the script.

If the token is missing, `create_client()` exits with instructions; the fix is `doppler login && doppler
setup` in the toolbox repo, not a config file. There is deliberately no on-disk fallback.

## Anatomy of a v3 call

`NotionClient.post(endpoint, data)` prefixes bare names with `/api/v3/` and returns a raw
`requests.Response`.

**Reading** — `syncRecordValues` for known ids, `queryCollection` for rows. Every record arrives inside
a permission envelope, `{"value": {"role": ..., "value": {...}}}`. Reading one level too few raises
`KeyError` on every field. Use the shared helper:

```python
from notion_tools.client import create_client, unwrap_record
rec = unwrap_record(resp["recordMap"]["block"][block_id])
```

**Writing** — one `saveTransactionsFanout` call carries many operations:

```python
c.post("saveTransactionsFanout", {"requestId": str(uuid.uuid4()), "transactions": [
    {"id": str(uuid.uuid4()), "spaceId": SPACE, "debug": {"userAction": "<label>"},
     "operations": [{"id": TARGET, "table": "collection", "path": ["schema", key, "options"],
                     "command": "set", "args": value}]}]}).raise_for_status()
```

Four commands cover everything: `set` (write at `path`), `update` (merge at the record root, e.g.
`{"alive": False}`), `listAfter` (append an id into a `content` array), `listRemove` (detach one).

## Non-negotiables

- **Check the status before `.json()`.** Retired endpoints answer `404` with an HTML body, so `.json()`
  raises a bare `JSONDecodeError` that looks like a parse bug rather than a dead endpoint.
- **`client.post` never raises.** It has no `raise_for_status()`, so a 400 reads as success. Call
  `.raise_for_status()` on every write, and on failure print `r.text` — the useful detail is only there.
- **Writes are not idempotent.** Every `requestId`, transaction id and new record id is a client-side
  `uuid4`, so a re-run duplicates rather than reconciling. Anything resumable needs a dedup key read
  back from the collection or a state file.
- **Confirm before anything destructive**, and prefer `alive: False` (recoverable for 30 days) over
  `permanentlyDelete`. A botched write is often recoverable — see `references/reading-data.md`.
- **No request sets a timeout, and you cannot add one at the call site.** `NotionClient.post` takes
  only `(endpoint, data)` and forwards no `timeout`, so a hung call blocks forever. For a long job go
  through `c.session.post(url, json=..., timeout=...)` directly.

## Verified endpoint status

Confirmed live on 2026-08-16. Notion retires v3 endpoints without notice — re-probe before trusting an
old recipe (`references/reading-data.md` has the probe).

| Alive | Retired (404) |
|---|---|
| `loadUserContent`, `getSpaces`, `syncRecordValues`, `queryCollection`, `loadPageChunk`, `search`, `saveTransactionsFanout`, `getActivityLog`, `getUploadFileUrl`, `getSignedFileUrls`, `getBacklinksForBlock`, `getPublicPageData` | `getTeams`, `submitTransaction` |

`submitTransaction` being dead matters for [`jamalex/notion-py`](https://github.com/jamalex/notion-py),
the most complete public v3 client: it writes through that endpoint, so **its write path no longer
works**. Read it for structure, not for working code.

## References

- `references/v3-recipes.md` — copy-paste recipes: select options, `date_format`, reminders, trashing,
  conditional row colours, grouped views, blocks, rich text, file upload.
- `references/mcp-surface.md` — exact MCP call shapes and their traps (the `date:Prop:start` expansion,
  silent no-op writes, schema-extending moves).
- `references/reading-data.md` — response shapes, both `queryCollection` forms, endpoint probing, and
  recovering blocks you just trashed.

## Out of scope

- Do **not** put a `token_v2` anywhere but Doppler — no config file, no `.env`, no committed constant.
- Do **not** drop to v3 because an MCP call errored once; match the operation against the table first.
- Do **not** hand-roll a Notion client; `notion_tools` already exists.
- Do **not** run a bulk write against a live database without a dry run or a scratch page first.
