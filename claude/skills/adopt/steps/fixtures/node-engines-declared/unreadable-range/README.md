# Fixture: a range written in a form this step does not read

`lts/*` is a real thing to write in an `.nvmrc` and is not a semver range, so whether the
pin beside it agrees was never established. An unasserted line must not read as a passed
one, so v7 reports it and writes nothing.
