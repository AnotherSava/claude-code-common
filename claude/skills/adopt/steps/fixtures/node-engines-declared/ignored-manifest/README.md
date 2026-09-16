# Fixture: the only manifest is one git hides

A scratch clone under a gitignored `tmp/` is not a project of this repo's, and the global
convention puts scratch exactly there — so this shape is a designed condition rather than an
accident. `tmp/scratch/package.json` declares no `engines.node` and has an `.nvmrc` beside it,
which is the one shape v7 will write into, so a walk that read it would insert a range into a
tree nobody maintains and then record `applied` on the strength of it.

The walk narrows on what git hides, not on the directory's name: `tmp/` is a convention and
not a rule, and a repo may hide a manifest anywhere it likes.
