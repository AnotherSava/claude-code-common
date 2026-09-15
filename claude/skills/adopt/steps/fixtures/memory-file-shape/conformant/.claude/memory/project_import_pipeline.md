---
name: project-import-pipeline
description: The nightly importer reads the export bucket rather than the API, whose page cursor repeats the last row every third page
metadata:
  type: project
---

The API's cursor repeats the last row of every third page, so a row count taken from a
paginated read is not a count of distinct rows. The importer reads the export bucket
instead and dedupes on the source id before comparing anything.

Anything written against the API directly has to dedupe on that key first.
