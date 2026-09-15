# Fixture: a web app that pins Node in .nvmrc only

`web/package.json` declares no `engines.node` while `web/.nvmrc` beside it names the major,
so v7 derives the range rather than inventing one. The `.next/` and `node_modules/` manifests
are here because a plain `find` returns them too, and a step that counted either would pin a
tree the next build replaces.
