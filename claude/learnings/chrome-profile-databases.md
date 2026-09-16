# Reading and backing up Chrome's profile databases

Chrome keeps the address bar's state in several SQLite files inside the profile directory — under
`AppData/Local/Google/Chrome/User Data/<Profile>` on Windows, `Library/Application Support/Google/Chrome/<Profile>`
on macOS. Verified 2026-09-16 against Chrome 152 on Windows 11.

## Chrome holds them exclusively, so SQLite's own backup routes all fail

While Chrome is running, every SQLite-level route is refused with `database is locked`:

- `VACUUM INTO 'copy.db'`
- the Python `sqlite3` connection backup API
- even a plain read-only connect, `sqlite3.connect("file:<path>?mode=ro", uri=True)`

What does work is a **file-level copy of the database together with its `-wal` and `-shm` sidecars**, then
opening the copy. Copying the main file alone can miss everything still sitting in the write-ahead log.

```python
for suffix in ("", "-wal", "-shm"):
    source = profile / f"History{suffix}"
    if source.exists():
        shutil.copy2(source, target / f"History{suffix}")

connection = sqlite3.connect(target / "History")
print(connection.execute("PRAGMA integrity_check").fetchone()[0])
```

Two properties worth knowing:

- **Opening the copy checkpoints it.** SQLite folds the `-wal` into the main file and drops the sidecars on
  a clean close, so each backup ends up as a single self-contained file.
- **Verify rather than trust.** The three files are read at slightly different instants, so running
  `integrity_check` against the copy is the only thing that proves they were caught in a consistent state.
  Retry the copy once if it comes back bad.

163 MB of profile copies out in about two tenths of a second, so there is no reason to be selective.
*Writing* to any of these needs Chrome fully closed — the same lock applies.

## Which file holds what

| File | Holds |
|---|---|
| `History` | 19 tables. `urls` (url, title, visit_count, typed_count, last_visit_time), `visits` (one row per visit, carrying `from_visit` / `opener_visit` / `segment_id` self-references), `keyword_search_terms`, `segments` + `segment_usage`, the Journeys tables (`clusters`, `clusters_and_visits`, `content_annotations`, …), `downloads` |
| `Shortcuts` | `omni_box_shortcuts` — the omnibox's trained shortcuts. A **separate** database |
| `Favicons` | the icons drawn beside each omnibox row |
| `Top Sites` | new-tab tiles |
| `Network Action Predictor` | the omnibox's own typed-prefix → URL scoring |

Each carries a schema version in its `meta` table (`History` was at 70 on Chrome 152), which is what tells a
later restore whether the archive still matches the Chrome about to read it.

## History and shortcuts are separate stores, and clearing one barely touches the other

A shortcut is keyed on **the text the user typed**, not on the URL, and matches when the stored key *starts
with* the input — so one trained on `boardgamearena` also answers `b`, `bo`, `board`. `ShortcutsProvider`
then promotes every hit to a flat 1414, above almost everything else. That is why a handful of junk
shortcuts can dominate a prefix no matter how little the underlying pages were visited.

`ShortcutsBackend::OnHistoryDeletions` branches:

- `deletion_info.IsAllHistory()` → `DeleteAllShortcuts()`. **A full history clear destroys every trained
  shortcut**, and they are per-machine and never sync. Back up `Shortcuts` — it is under a megabyte —
  before any clear.
- otherwise → drops only shortcuts whose `destination_url` **equals** one of the deleted rows.

That equality is stricter than it looks. Measured on a real profile: of 703 Google-search URLs in history,
**none** was the destination of any shortcut, because Chrome rewrites its own tracking parameters between
the URL a suggestion carries and the URL history records. Deleting all 703 removed exactly 10 shortcuts and
left 391 behind, every one pointing at a URL that no longer existed. An orphaned shortcut still appears in
the dropdown, because the provider serves from its own database and never consults history.

So clearing search *history* does not clear search *shortcuts*. Doing that means writing to `Shortcuts`
directly with Chrome closed, and there is no extension API for it:

```sql
DELETE FROM omni_box_shortcuts WHERE id = ?   -- select the ids in code, not with LIKE
```

## Other things that bite

- **Chrome expires history at 90 days on its own.** A diff of the profile against a backup taken hours
  earlier showed 35 unrelated URLs gone; every one had last been visited exactly 90 days before. Check ages
  before concluding your own tool deleted something.
- **`chrome.history.search()` returns fewer rows than the `urls` table holds** — 12,644 against 15,676 on
  one profile, the difference being entries with no visit rows and non-http schemes. An extension cannot
  reach them, so an API-driven cleanup always leaves a remainder.
- **`urls` rows are unique URLs, not visits.** 704 distinct search URLs accounted for 912 visits, and only
  83 had ever been run twice — which is why a search-heavy history is far smaller than it feels.
