# Fixture: a repo whose second manifest names no Node anywhere

`web/` is in the target shape. The scraper beside the skill that runs it declares no
`engines.node` and has no `.nvmrc` to derive one from, so v7 must stop rather than write the
web app's major into a helper nobody said targets it.
