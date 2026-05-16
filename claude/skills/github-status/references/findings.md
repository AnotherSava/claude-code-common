# github-status — findings

Background context for `repos-status.sh`. None of this is load-bearing
for the script — it explains *why* the defaults look the way they do.

## Repository discovery rules

The script walks `PROJECTS_ROOT` (resolved from env var → `config/config.env` → SKILL.md first-run prompt) at `find -maxdepth 4`.
The user's deepest repo root is at depth 2 (`games/<repo>/`, `3d/<repo>/`),
so depth 4 (i.e. `<repo>/.git/`) is generous.

Hard exclusions:
- `_archive/` — user's archived projects, not active.
- `node_modules/` — defensive; rarely contains `.git` but cheap to filter.

## Ownership filter

Origin URL must match `github.com[:/]AnotherSava/`. This automatically
filters out third-party clones that happen to live under the projects root:

| Path | Origin |
|---|---|
| `games/achievement-watchdog` | `50t0r25/achievement-watchdog` |
| `games/gbe_fork` | `Detanup01/gbe_fork` |
| `games/gse_fork` | `alex47exe/gse_fork` |
| `games/ingame_overlay` | `Nemirtingas/ingame_overlay` |

Forks owned by AnotherSava are still counted as the user's repos even when
they have an `upstream` remote pointing at the original author. Known
forks at time of writing: `claude-mermaid-fix` (`upstream`: `veelenga`),
`InverseCSG` (`upstream`: `yijiangh`).

## Explicit exclusions

The `EXCLUDED` array filters out repos owned by the user that they don't
want in the report. Rationale was not given in the conversation that
introduced them — they were removed by user request:

- `notion`
- `claude-mermaid-fix`

Edit the `EXCLUDED` set in `scripts/repos-status.py` to add or remove entries.

## "Last pushed" semantics

The pushed-date column is the committer date of `HEAD` of the local
tracking ref `@{upstream}`. Each run fetches origin per repo in parallel
before reading, so this reflects the current remote at run time.

`unpushed` counts commits in `@{upstream}..HEAD`; `behind` counts
`HEAD..@{upstream}`.

Branches with no upstream show empty fields and sort to the bottom.

If the network is down or a remote is dead, fetches fail silently and
the displayed counts fall back to whatever the local tracking refs
already knew. No error is surfaced — the script always exits 0 on
fetch failure, since one bad remote shouldn't kill the report.
