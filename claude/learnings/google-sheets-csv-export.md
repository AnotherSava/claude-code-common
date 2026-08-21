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
