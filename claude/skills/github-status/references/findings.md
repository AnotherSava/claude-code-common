# github-status — findings

Background context for `scripts/repos-status.py`. None of this is what makes the script work — it
explains *why* the defaults look the way they do.

## Repository discovery rules

The script walks `PROJECTS_ROOT` (resolved from env var → `config/config.env` → SKILL.md first-run
prompt) to a depth of 4. The user's deepest repo root is at depth 2 (`games/<repo>/`, `3d/<repo>/`),
so depth 4 (i.e. `<repo>/.git/`) is generous.

Hard exclusions:
- `_archive/` — user's archived projects, not active.
- `node_modules/` — defensive; rarely contains `.git` but cheap to filter.

## Ownership filter

Origin URL must match `github.com[:/]AnotherSava/`. This automatically filters out third-party clones
that happen to live under the projects root:

| Path | Origin |
|---|---|
| `games/achievement-watchdog` | `50t0r25/achievement-watchdog` |
| `games/gbe_fork` | `Detanup01/gbe_fork` |
| `games/gse_fork` | `alex47exe/gse_fork` |
| `games/ingame_overlay` | `Nemirtingas/ingame_overlay` |

Forks owned by AnotherSava are still counted as the user's repos even when they have an `upstream`
remote pointing at the original author. Known forks at time of writing: `claude-mermaid-fix`
(`upstream`: `veelenga`), `InverseCSG` (`upstream`: `yijiangh`).

## Explicit exclusions

The `EXCLUDED` set filters out repos owned by the user that they don't want in the report. Rationale
was not given in the conversation that introduced them — they were removed by user request:

- `notion`
- `claude-mermaid-fix`

Edit the `EXCLUDED` set in `scripts/repos-status.py` to add or remove entries.

## Why the peer is scanned by piping the script over stdin

The alternatives were copying the script to the peer's temp directory, or running the copy already
installed there. Both were rejected:

- **Running the installed copy** re-opens version skew. The two ends exchange a JSON snapshot, so
  their field names have to agree; the installed copy is whatever the peer's clone last pulled, which
  is exactly the state the report exists to tell you about. Piping the running file guarantees both
  ends execute the same bytes.
- **Copying to a temp path** needs the peer's temp directory resolved first (another round trip,
  through `cmd.exe` quoting on a Windows peer) and leaves a file to clean up.

`ssh <peer> "<python> - --json"` with the file on stdin costs one round trip and leaves nothing
behind. Measured on a Windows peer: the non-ASCII source (box-drawing characters, `·`, `✓`) survives
the hop intact in both directions, because Python reads stdin source as UTF-8 and the script
reconfigures its own streams to UTF-8 before printing.

Two things the peer invocation must therefore tolerate, both of which it does:

- **`__file__` is the literal string `"<stdin>"`** under `python -`, not a path. Anything resolving
  paths from it has to check `Path(__file__).is_file()` first, or it silently resolves against the
  current directory.
- **Config cannot be found relative to the script**, since there is no script on disk. The peer falls
  back to `~/.claude/skills/github-status/config/config.env`, the conventional install path, which is
  what lets each machine own its own `PROJECTS_ROOT` instead of having it declared from the far side.

`PEER_PYTHON` exists because there is no interpreter name common to both platforms: a Windows install
has `python` and no `python3`, a Homebrew macOS install has `python3` and no bare `python`.

## Why repos merge on the origin slug

The clone path is not an identity across machines. `AnotherSava/jsonl-logs-intellij-plugin` is checked
out as `jsonl-logs-intellij-plugin` on the Mac and `intellij-jsonl-extension` on the Windows box, and
`AnotherSava/claude-code-common` is checked out as `claude` on both. Keying on the path would split
the first into two rows and mislabel the second; keying on `OWNER/REPO` gets both right.

The *display* name is still the clone path, because that is what the user calls it — taken from the
local machine wherever it has the repo, and shown per-machine in the HTML report wherever the two
disagree.

## Open issues are a repo property, not a machine property

The count is fetched with `gh issue list --repo OWNER/REPO` on each machine, and the merge takes the
first machine that could answer. This matters because `gh` is authenticated per machine and its token
can lapse on one while the other keeps working — a per-machine column would then show a blank that
reads as "no open issues", which is the wrong answer rather than a missing one.

Taking the first answer is not quite enough on its own. A repo cloned **only** on the peer gets asked
only by the peer, so a lapsed token there leaves it at `None` — and since the display filter keeps a
clean repo solely on its issue count, a clean-but-ticketed repo would vanish from the report rather
than appear with a blank cell. `gh issue list --repo OWNER/REPO` needs no clone, so those slugs are
re-asked from the local machine after both scans return.

`--repo` is passed explicitly because without it `gh` auto-resolves a fork to its `upstream` parent
and reports the wrong project's issues.

## Two subprocess traps that cost a whole scan each

Both were live in the script and both were caught by review rather than by a run, because each needs a
condition the developer's machine does not have.

- **`subprocess.run(timeout=…)` raises, it does not return non-zero.** `fetch_one` and `pull_one` set
  a timeout and had no `except`, so one stalled remote out of forty aborted the run — and on the peer
  that surfaced as the whole machine reported `NOT REACHED`, discarding every repo it had already
  read. Catching `subprocess.SubprocessError` (the base class of `TimeoutExpired`) is what makes the
  "failures are swallowed" promise true.
- **`text=True` decodes with the *locale* codepage, not UTF-8.** The peer's locale is cp1251, and git
  emits commit subjects and branch names as raw UTF-8 without the escaping it applies to paths. A real
  subject reading `Awaiting→Blocked` came back as `Awaitingв†’Blocked`; a byte cp1251 leaves undefined
  raises `UnicodeDecodeError` and takes the peer scan down. `encoding="utf-8", errors="replace"` is
  the fix, and it is what `git_z` beside it was already doing by hand.

## "Behind" and "ahead" semantics

`unpushed` counts commits in `@{upstream}..HEAD`; `behind` counts `HEAD..@{upstream}`. Each run
fetches origin per repo in parallel before reading, so both reflect the current remote at run time.

Branches with no upstream report zero for both and appear only if they have uncommitted changes.

If the network is down or a remote is dead, fetches fail silently and the displayed counts fall back
to whatever the local tracking refs already knew. No error is surfaced — the script always exits 0 on
fetch failure, since one bad remote shouldn't kill the report.

`behind` is deliberately **not** zeroed after an auto-pull. The pre-pull count is what the ✓ marker
annotates, so the run that pulls four commits says "4 pulled" rather than showing nothing where four
commits arrived.
