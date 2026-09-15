# before

Five lines here belong in the global excludes file instead: two OS/editor entries, the
machine-local settings file, the per-machine deploy paths, and a bare `scripts/` rule that floats
over the global file's root-anchored wrapper entries.

Two lines that look similar stay. The `.env` entry is one every contributor should keep, so the
project copy is the one that travels. The `config/deploy.env` line in `web/.gitignore` is anchored
to `web/` and hides `web/config/deploy.env`, which the global entry — anchored to the repo root —
never reaches.
