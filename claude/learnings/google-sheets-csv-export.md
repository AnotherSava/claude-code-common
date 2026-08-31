# Reading a public Google Sheet as CSV

Two endpoints will hand you a publicly-shared spreadsheet as CSV without credentials. They are not
interchangeable, and picking the convenient one silently corrupts your header row.

## Use `/export`, not `gviz`

```
https://docs.google.com/spreadsheets/d/<spreadsheetId>/export?format=csv&gid=<gid>
```

Returns the tab byte-for-byte: every row, every header cell, in sheet order.

```
https://docs.google.com/spreadsheets/d/<spreadsheetId>/gviz/tq?tqx=out:csv&sheet=<Tab%20Name>
```

Addresses the tab **by name** — which is genuinely tempting, because a name survives the owner copying the
workbook for next year while a `gid` does not. But gviz types each column and **blanks the header label of any
column it decides is numeric**. A sheet whose first row reads

```
Game ID, Game Name, Status, ..., Min Players, Max Players, ..., Start Time (24 hour clock)
```

comes back from gviz as

```
"", "Game Name", "Status", ..., "", "", ..., ""
```

Adding `&headers=0` does **not** fix it. That flag stops gviz treating a row as headers, and the data rows do
come through complete — but the header row itself still arrives with the numeric columns blanked. If you resolve
columns by header name (rather than by fragile position), gviz has destroyed exactly the information you need,
including the id column most identity/diffing logic depends on.

So: pay the `gid`, get the truth.

Find a tab's `gid` by opening it in the browser and reading `#gid=` from the URL, or scrape the workbook's
`/htmlview` page, which embeds a `items.push({name: "<Tab Name>", ... gid: "<gid>"})` list.

## Failure responses are all HTML — sniff the content type

Every failure mode returns `Content-Type: text/html`, and several return HTTP 200 while doing it. Parsing the
body as CSV yields a handful of nonsense rows rather than an error, which is far more dangerous than a throw if
you reconcile the result against stored state.

| Situation | Status | Body |
| --- | --- | --- |
| Fine | 200 | `text/csv` (and a `Content-Disposition` naming the tab) |
| Unknown `gid` | 400 (after a 307 to `doc-*.googleusercontent.com`) | HTML |
| Unknown `spreadsheetId` | 404 | HTML |
| Not shared publicly | 200 | HTML — the sign-in page |

Check `content-type` contains `csv` before trusting a single byte. That one test catches the not-shared case,
which is the only one that looks like success.

Follow redirects: `/export` 307s to a `googleusercontent.com` host that serves the actual bytes.

## Sheets aimed at humans need a header hunt

A sheet people actually use tends to open with banner rows — instructions, merged group labels over column
ranges — before the real header row. Don't hardcode "row 2". Scan the first N rows for the one where your
required columns all resolve, and record which row that was so error messages can cite the row number a person
sees in the browser.

Related: repeated header names are normal in such sheets (helper columns named `Start`/`End` once per day). Parse
to `string[][]` and resolve headers to **indexes**, taking the leftmost match — a CSV parser's "key rows by
header name" mode keeps only the last of each duplicate and quietly loses columns.

## Linking a reader back to one row

The counterpart to reading it: sending someone to the line a row came from. The fragment Sheets' own "get link to
this cell" produces works for anyone with view access, and scrolls the target to the top of the window.

```
https://docs.google.com/spreadsheets/d/<spreadsheetId>/edit?gid=<gid>#gid=<gid>&range=12:12
```

- The `gid` genuinely goes **twice** — the query selects the tab on load, the fragment selects within it.
- `range=12:12` selects the **whole row**; `range=A12` selects one cell. Prefer the row when the point is "here is
  this thing's line", since what a reader wants is usually spread across its columns.
- Row numbers are 1-based as the browser numbers them, so keep the header-row offset from the parse: with
  `skip_empty_lines: false` and `rows = parsed.slice(headerRow + 1)`, item `i` is sheet row `headerRow + 2 + i`.
  Turning that off, or letting a parser drop blank lines, silently shifts every link below the first gap.

**Resolve the row on click, don't store it.** A row number is only true until someone inserts a line above it, so
a stored one goes wrong silently, between syncs, with nothing to notice it. Re-find the row by the source's own
id at click time — one `/export` fetch (~100KB, ~0.4s for a few hundred rows) behind a redirect route. The second
reason is worse than the staleness: if your change feed diffs stored fields, a shifted row number *is* an edit, so
reshaping the document would report every row below the insert as changed.
