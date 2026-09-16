# Fixture: the only manifest is one git hides

`tmp/scratch/package.json` declares `engines.node` with no `.npmrc` beside it, which is the
shape v8 creates a file for. Two repos in the fleet were measured in exactly this state —
their only manifest was `venv/Lib/site-packages/playwright/driver/package/package.json`, which
the playwright wheel ships with `engines.node` — so an approved walk would have written
`engine-strict=true` inside a virtualenv the next rebuild deletes, and recorded the convention
as applied on evidence no clone can reproduce.
