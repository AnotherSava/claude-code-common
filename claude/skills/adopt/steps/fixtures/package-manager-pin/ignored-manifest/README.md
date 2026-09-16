# Fixture: the only manifest is one git hides

`tmp/scratch/package.json` already carries a `packageManager` pin, so a walk that read it would
report the repo conformant and exit 0 without writing — a pass claimed from a file nobody
maintains and no clone receives. This tree is also where v9's second exposure shows: an ignored
manifest carrying a pin is a source `chosen()` would copy from, so a repo with one tracked
manifest missing a pin beside a hidden one would take its version from the scratch tree.
