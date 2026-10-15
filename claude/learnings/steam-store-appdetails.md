# Steam store appdetails: looking up a game's name by appid

The store's public endpoint returns a game's display name with no API key:

```
https://store.steampowered.com/api/appdetails?appids=<appid>&filters=basic
```

The response is keyed by the appid as a string:

```json
{"620": {"success": true, "data": {"name": "Portal 2", "type": "game", "...": "..."}}}
```

`filters=basic` keeps the payload to the basic block, which is all a name lookup needs. Ask for one
appid per request; the multi-appid form is not something to rely on with `filters=basic`.

## Parsing defensively

Walk it with a kind check at every level rather than deserialising into a fixed type. An appid the
store does not know answers `{"<appid>": {"success": false}}`, and a parser should also survive a
bare `null`, a `null` entry under the appid, and a `data` that is an array instead of an object.
Treat every one of those as "no name", not as an error that stops a batch.

## The names are marketing strings

Store names carry `™`, `®` and `©` and some are stylised in capitals. For display beside folder names
and in reports, strip the three marks and collapse the space they leave; keep the casing, since
title-casing a stylised name gets acronyms and deliberate lowercase wrong.

## Caching

A name almost never changes, so cache it on disk keyed by appid and look up only what the cache
lacks. Write the cache through a temp file and a move so an interrupted write cannot leave it
truncated, and re-apply the cleaning rule when loading so entries written before a rule change get
it too. Put the cache somewhere a reinstall or deploy does not wipe, or expect to refetch after one.

A failed request (network error, timeout, bad JSON) should cost that one name, not the batch, and a
lookup started during shutdown should stop quietly when its client is disposed.
