# v3 recipes

Every snippet assumes the bootstrap from `SKILL.md` (subshell into the toolbox dir, `doppler run --`,
heredoc, `PYTHONIOENCODING=utf-8`) and this preamble:

```python
import uuid
from notion_tools.client import create_client, unwrap_record
c = create_client()
```

`COLL` is a collection id, `SPACE` a space id, `PAGE` a page/row block id — all dashed UUIDs. Notion
colours everywhere: `default, gray, brown, orange, yellow, green, blue, purple, pink, red`.

## Read a collection schema (needed by almost everything below)

Property keys in the schema are rarely the display name. Notion generates opaque 4-char keys (`?YWO`,
`bhVo`) for columns created in its UI; a collection you build through v3 keeps whatever keys you chose
(`date_sort`, `rtm_series`). The title column is always the literal key `title`. Either way, resolve
by name:

```python
r = c.post("syncRecordValues", {"requests": [{"pointer": {"table": "collection", "id": COLL}, "version": -1}]}).json()
schema = unwrap_record(r["recordMap"]["collection"][COLL])["schema"]
key = next(k for k, v in schema.items() if v.get("name") == "Status")
```

## Select options — add, recolor, remove

MCP is add-only. Write the **whole** options array, preserving the `id` of every option you keep
(match by `value`) so existing cell values stay bound; new options get a fresh `uuid`.

```python
desired = {"To do": "default", "Doing": "blue", "Done": "green"}   # order here is display order
by_value = {o["value"]: o for o in schema[key].get("options", [])}
new_opts = [{**by_value.get(v, {"id": str(uuid.uuid4()), "value": v}), "value": v, "color": col}
            for v, col in desired.items()]
c.post("saveTransactionsFanout", {"requestId": str(uuid.uuid4()), "transactions": [
    {"id": str(uuid.uuid4()), "spaceId": SPACE, "debug": {"userAction": "set_options"},
     "operations": [{"id": COLL, "table": "collection", "path": ["schema", key, "options"],
                     "command": "set", "args": new_opts}]}]}).raise_for_status()
```

Any value **absent** from `desired` is dropped. Removing an in-use option does **not** clear the cells
that referenced it — pages store the option by its string `value`, leaving orphans. Null those cells
first, then drop the option.

## Date format on a column

Both the fixed enum (`relative`, `MM/DD/YYYY`, `DD/MM/YYYY`, `YYYY/MM/DD`, empty = "Full date") and
custom moment-style strings work — `MMM d` renders "Jul 25". The *shortcut* tokens `ll`/`LL` are
accepted but silently fall back to Full date, so never use them.

```python
ops = [{"id": COLL, "table": "collection", "path": ["schema", k, "date_format"],
        "command": "set", "args": "MMM d"} for k, v in schema.items() if v.get("type") == "date"]
c.post("saveTransactionsFanout", {"requestId": str(uuid.uuid4()), "transactions": [
    {"id": str(uuid.uuid4()), "spaceId": SPACE, "debug": {"userAction": "date_fmt"},
     "operations": ops}]}).raise_for_status()
```

## Date reminder

Not exposed by MCP. The value is the mention form; the `reminder` object goes inside the inner `d`.

```python
val = [["‣", [["d", {"type": "date", "start_date": "2027-05-15",
                     "reminder": {"unit": "week", "value": 1, "time": "09:00"}}]]]]
# operation: {"id": PAGE, "table": "block", "path": ["properties", date_key], "command": "set", "args": val}
```

`unit` is `day` or `week`; `time` is `HH:MM`.

## Trash a row, page, inline table, or view (recoverable, 30 days)

**Confirm with the user first.** Each case needs its pointer *and* its detach step — flipping `alive`
alone leaves the thing still rendering, because its id is still in a parent's list.

A row or page — one op, nothing to detach:

```python
# operation: {"id": PAGE, "table": "block", "path": [], "command": "update", "args": {"alive": False}}
```

An inline table (the `collection_view` **block** that embeds it) — detach from the host page's
`content`, or Notion renders a ghost table forever:

```python
{"id": CV_BLOCK, "table": "block", "path": [], "command": "update", "args": {"alive": False}},
{"id": HOST_PAGE, "table": "block", "path": ["content"], "command": "listRemove", "args": {"id": CV_BLOCK}},
```

A single **view** — note the table is `collection_view`, not `block`; a view is not a block, and the id
must also come out of the host block's `view_ids`:

```python
{"id": VIEW, "table": "collection_view", "path": [], "command": "update", "args": {"alive": False}},
{"id": CV_BLOCK, "table": "block", "path": ["view_ids"], "command": "listRemove", "args": {"id": VIEW}},
```

## Conditional row colours (banding, status tints)

Per-row `format.block_color` **does not render in table view** — the value persists and the renderer
ignores it. Row colour must come from a rule on the *view*:

```python
rules = [{"id": str(uuid.uuid4()),
          "background": {"type": "match_property_value"},
          "conditional_filter": {"filter": {"operator": "is_not_empty"}, "property": key},
          "properties_to_color": {"type": "all"}}]
# operation: {"id": VIEW, "table": "collection_view", "path": ["format", "conditional_color_rules"],
#             "command": "set", "args": rules}
```

With `match_property_value` the row inherits the colour of the select option it holds. To band rows by
an arbitrary grouping, add a binary helper property (one `default` option, one coloured) and point a
single rule at it.

## Grouped views

Needs **both** halves or the grouping silently does nothing:

- `query2.group_by` → the property key
- `format.collection_groups` → one `{property, value: {type, value}, hidden}` per distinct group value,
  **plus** a catch-all `{property, value: {type}, hidden: False}` for the unset bucket

Group display order follows the option order in the property's schema. When updating an existing
grouped view, *extend* the groups array rather than regenerating it — regenerating resets the `hidden`
flags the user set by collapsing groups.

## Create blocks that actually render

A child **of a block** needs both a parent-id chain and a `listAfter` into that parent's `content`, at
every level. Skip either and the block exists in the recordMap but is invisible:

1. create the block with `parent_id` set, then
2. `{"command": "listAfter", "path": ["content"], "args": {"id": <new_block_id>}}` on the parent.

**Collection rows are the exception.** Create them with `parent_id: COLL, parent_table: "collection"`
and no `listAfter` at all — a collection has no `content` array to append into. Body blocks *inside* a
row are back to the normal rule: `parent_table: "block"` plus a `listAfter` on the row's `content`.

Programmatically created blocks get no `created_time`. If you need stable ordering on rows you made,
set `created_time` explicitly or sort by row UUID.

## Rich text and inline formatting

A `title` property is a list of runs; each run is `[text]` or `[text, annotations]`, where annotations
is a list of `[type, ...args]`: `[["b"]]` bold, `[["i"]]` italic, `[["c"]]` inline code, `[["a", url]]`
link.

```python
[["List", [["b"]]], [": "], ["map", [["a", "https://example.com"]]]]
```

`multi_select` is the odd one out: store a **single comma-joined string** of option names,
`[["a,b,c"]]`, which Notion splits into pills. So no option name may contain a comma, and every part
must already exist in the schema or it renders empty.

## File and image upload

1. `getUploadFileUrl` with `{bucket: "secure", name, contentType, record: {table, id, spaceId}}`
2. PUT the bytes to the returned `signedPutUrl` — a real AWS-signed URL, no cookie, just `Content-Type`
3. use the returned `attachment:<uuid>:<filename>` reference as the property value, shaped
   `[[filename, [["a", attachment_url]]]]`, via `command: "set"` on `path: ["properties", key]`

Use **WebP** for image properties. Notion does not preview AVIF in gallery/card views — it stores fine
but the thumbnail stays blank.

## Batching

Put many operations in one transaction — roughly 50 rows per `saveTransactionsFanout` call is the
proven batch size (1,156 rows in ~25 calls). Remember these writes are not idempotent: a retry with
fresh uuids duplicates, so resumable jobs need a state file or a dedup key read back from the table.
