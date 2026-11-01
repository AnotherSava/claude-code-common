# Reading a Playnite library and a Goodreads export

Two personal-library exports read for an import in 2026-10, and the traps in each.

## Playnite

Playnite has no export command. Its library is a set of **LiteDB v4** files (`library/games.db`, `completionstatuses.db`, `sources.db`, `platforms.db`, …), which its own backup zips together with `config.json` and the cover images under `libraryfiles/`. A file starts with `** This is a LiteDB file`, and `library/database.json` holds `{"Version":4}`.

- **Read it with .NET.** LiteDB has no maintained reader outside .NET. A tiny console project with the `LiteDB` 4.1.4 package (`dotnet add package LiteDB --version 4.1.4`) opens each file `Mode=ReadOnly` and serialises every collection with `JsonSerializer.Serialize(doc, false, true)`. NuGet warns about a known vulnerability in 4.1.4 (deserialising untrusted data), which does not matter for reading your own library; 5.x cannot open v4 files.
- The output is LiteDB extended JSON: ids are `{"$guid": "…"}`, dates `{"$date": "…"}`, and 64-bit numbers `{"$numberLong": "12780"}` — `Playtime` (seconds) arrives that way. A game with no source has `SourceId` set to the all-zero guid, not null.
- Zip entry names use forward slashes (`library/games.db`), though `unzip -l` on Windows prints them with backslashes, and a Git Bash `unzip 'library/*'` pattern matched nothing. Python's `zipfile` and .NET's `ZipFile` read them fine.
- Useful game fields: `Name`, `SourceId` → `sources` (Steam, Epic, GOG, Amazon, Battle.net), `GameId` (the store's own id — Steam app id, GOG product id, Epic catalog id), `CompletionStatusId` → `completionstatuses` (Not Played, Played, Plan to Play, Playing, On Hold, Completed, Beaten, Abandoned), `ReleaseDate` (`"2017-2-24"`, unpadded), `UserScore` (0–100), `Playtime`, `LastActivity`, `Favorite`.
- **There are no completion dates.** `LastActivity` is the last launch, not when a status was reached.
- **Don't assume `Favorite` means favourite.** One owner used it purely as a filter for Playnite's default view: it covered every planned, playing and completed game and almost none of the store giveaways. Check how it distributes across statuses before importing it as anything.
- The same game owned on two stores is two entries with the same title; dedupe on the matched catalog id, not the name.

## Goodreads export

`My Books → Import and export` produces a CSV with one row per shelved edition.

- `Book Id` is the **edition** id. Other catalogs can resolve it: Hardcover's `book_mappings` with platform 1 (see `hardcover-api.md`).
- ISBNs are wrapped for spreadsheets: `="0857664018"`, `="9780857664013"`, and `=""` when absent. Strip the wrapper.
- `Exclusive Shelf` holds only the three built-ins (`read`, `currently-reading`, `to-read`). A custom shelf such as "unfinished" appears in `Bookshelves` (comma-separated) **while the book's exclusive shelf stays `read`**, so a custom "abandoned"-style shelf has to override the exclusive one.
- `Date Read` and `Date Added` are `YYYY/MM/DD`; there is no start date. `Read Count` > 1 still carries a single `Date Read`.
- `My Rating` is whole stars 1–5, `0` for unrated.
- Titles carry the series in parentheses — `Apex (Nexus, #3)` — which has to be stripped before comparing titles.
- A translated edition keeps its translated title while the `Author` column is often the Latin-script name, so a title search on another catalog mixes scripts.
