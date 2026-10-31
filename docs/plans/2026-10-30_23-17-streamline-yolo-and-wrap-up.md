# Replace /commit with /yolo, /wrap-up and shared commit steps

Closing a piece of work takes four separately invoked skills (`review-auto`, `review-manual`, `/commit`, `/wrap-up`)
and about six approval points, and pushing something only to test it costs a full pass of `/reflect`, `/clean-code`
and `/docs-relevance`. The cause is structural: `/wrap-up` calls `/commit` as a whole, so the two guess at each other
through the transcript (`/commit` skips `/reflect` when it sees an earlier run, `/wrap-up` announces that `/commit`
already ran), and every other skill that commits either runs raw `git commit` or hands off to `/commit` and inherits
its gates.

This plan removes `/commit` as a skill and replaces it with two entry points built from the same shared steps:

- **`/yolo`** — the quick path: commit what is there and push it, so it can be tested. No review, no reflection, and no
  questions unless something is wrong.
- **`/wrap-up`** — the full path: review, reflect, commit and push, with one approval.

Every push, from either path or from a plain `git push`, gets a privacy scan in the global `pre-push` hook.

## The rule that prevents the old coupling

**No skill invokes another top-level skill to do part of its job.** Entry points call shared steps; shared steps
call scripts. A step needed by two callers lives under `claude/skills/shared/`, never inside one caller's `SKILL.md`.
Sub-skills that already stand alone and are called as units (`/reflect`, `/clean-code`, `/docs-relevance`,
`/screenshot-relevance`, `/pull`) keep that role; they are steps, not entry points.

## Shared steps

Each step has one input and one output, so a caller never has to know what the step did internally.

| Step | Form | Input → output | Source |
|---|---|---|---|
| **sync** | script | branch → `current`, `fast-forwarded`, `diverged`, or `FETCH-FAILED` | `/pull`'s procedure, already scripted in parts |
| **privacy scan** | script | paths + the unpushed range → findings or clean, exit code | `scan-commit-confidentiality.py`, unchanged |
| **gate** | script | repo → pass/fail, recorded tree | `gate_pushed_tree.py`, unchanged |
| **group** | document | change set → commits (paths + message each) | `/commit` steps 6 and 8, moved to `shared/commit-grouping.md` |
| **commit** | script + document | one commit's paths + message → sha, or refusal | new `shared/commit.py`; judgement half in `shared/commit-grouping.md` |
| **push** | script | repo → push result, bookmark pushed, peer notified, bookmark status line | new `shared/push.py`, folding four calls from `/commit` step 9 |
| **handoff** | script + one message | session → repos written outside this one, each routed to its owner | `peer_repo_changes.py`, unchanged |

**`shared/commit.py`** is the only place a commit is made. For each call it clears the index, stages exactly the paths
given (or, with `--reviewed`, stages them from the recorded review tree through `review_scope.py stage-reviewed`),
checks the message with `check-commit-message.py`, runs the privacy scan on those paths, makes a GPG-signed commit,
and verifies the commit holds those paths and nothing else. It never pushes. A refusal names the failing check, and
the caller decides what to do.

**`shared/push.py`** records where the remote stood, pushes, runs `review_scope.py push`, sends
`notify_peer_pull.py`, and prints the `review_scope.py status` line last. It prints a CI line only when the repo has
workflows (the rule changed this session in `/commit` step 9 moves here with it).

## The two entry points

**`/yolo`** runs sync, gate, group, commit (once per group) and push, then handoff. It asks nothing in the normal case.
It stops and asks only for:

- a privacy-scan finding,
- a failing gate,
- a branch that has diverged from its upstream,
- a file in the change set that another live session may still be writing.

"YOLO mode" is Claude Code's common name for skipping permission checks, so the skill's description must say what
it skips (review and reflection) and what it never skips (the scan, the gate, the stops above); a session reading the
skill list sees only that description.

Before grouping, it removes debug output added during the work (`print()`, `console.log()` and the like — `/clean-code`'s
first step, on its own). A print stays only when the session needs it to read the result of the test it is pushing
for, and the report names each one kept, so the next `/wrap-up` knows to remove it.

Beyond that it runs none of `/reflect`, `/clean-code`, `/docs-relevance` or `/screenshot-relevance`. Skipping review is safe
because the review bookmark already covers every commit pushed since the last recorded review: the next `/wrap-up`
reviews what `/yolo` sent.

**`/wrap-up`** runs `review-auto` (fix mode) over everything since the bookmark, then the transcript review, then drafts
the `/reflect` saves, then groups the change set, honouring the reviewed/follow-up split when a review was recorded.
It stops **once**, on one summary holding the review's triage table, the open items from the transcript with their
recommended dispositions, what `/reflect` would save, and the commit plan. One answer applies dispositions, saves,
commits and pushes; an answer can override any line. After the push it offers deploy, publish and release as today.
The same four hard stops as `/yolo` interrupt it when they occur.

`review-manual` stays as the path for choosing fixes by hand. Its reviewed commit goes through `shared/commit.py
--reviewed`, and it leaves the push to `/yolo` or `/wrap-up`.

## review-auto must finish with a recorded review

A run that reaches its round cap currently stops with its last fixes unreviewed, so no review is recorded, the
polish never runs, and `/wrap-up` cannot split reviewed from follow-up commits. Change the cap so that the final
round is a **verify-only round**: it reviews the last fixes and reports findings without fixing them. If it finds
nothing at the bar the run fixes at, the review is recorded; otherwise the findings join the triage table and the
bookmark stays unrecorded, as now.

## Privacy scan on every push

Add the scan to the global `git/hooks/pre-push`: run `scan-commit-confidentiality.py` over the commits being pushed
and refuse the push on a blocking finding. Only a repo carrying a `.claude/conventions` record is held to it, matching
the hook's message check, so third-party clones are untouched.

A gate nobody answers has to be quiet, so the scanner changes in three ways:

- **It scans only the lines a commit adds** (`--staged` for the index, `--range` for commits), never whole files.
- **It splits its categories into two kinds.** Blocking findings stop `/yolo` and the hook:
  - a private key,
  - an absolute path naming this machine's home user,
  - a name from the private machine-coordinates file,
  - a tailnet hostname that is not a placeholder,
  - an IPv4 address other than loopback and `0.0.0.0`,
  - an email address outside the reserved example domains, other than `git@github.com`.

  Review findings (credential words, public domains, `ssh host` shapes, `.local` names, other absolute paths) are
  printed, triaged by the agent, and listed in `/wrap-up`'s summary; the hook ignores them.
- **A machine name that is also an ordinary word** is marked review-only inside the private coordinates file, so the
  marker publishes nothing.

Measured on the last 300 commits of this repo, added lines only: blocking on every category would have stopped about
one commit in six; the blocking set above stops 3, at least one of them a real leak.

The hook cannot ask, so a remaining false positive needs a way through: a committed per-repo allow-list,
`.claude/confidentiality-allow`, one fingerprint per line. The scanner prints each blocking finding's fingerprint, a
hash of its path and line text, so the entry never contains the value. The refusal message names the file to edit.

Memo 9 ("Teach the global pre-push hook to run a repo's commit-checks.sh") is the same kind of change; decide while
building this whether to include it.

## Where each part of /commit goes

Every step of `claude/skills/commit/SKILL.md` gets a destination. Dropped items say why.

| /commit step | Destination |
|---|---|
| 1 remote sync check | **sync** step |
| 1 phantom-modification fix | **commit** step (`git add` refresh before staging) |
| 1 scope guard, inbound peer writes, duplicate inbound file | **group** document; the busy-peer check is a hard stop in both entry points |
| 1 junk artifacts, orphaned data | **group** document, surfaced in `/wrap-up`'s summary; `/yolo` leaves both alone and says so |
| 1 executable-mode check | **commit** step, mechanical (shebang or `git/hooks/` path → mode `755`) |
| 1 untracked-skill audit | `/wrap-up` only |
| 1 audit of unpushed commits' messages | `pre-push` hook already refuses them; dropped from the skill |
| 1 open-issue triage | `/wrap-up` summary |
| 2 reflect | `/wrap-up` only |
| 3 change scope, clean-code | `/wrap-up` only, still gated by `change_scope.py` |
| 4 docs-relevance, screenshot-relevance | `/wrap-up` only, same gating |
| 5 confidentiality | **privacy scan** step, plus the `pre-push` hook |
| 6 project commit-checks | **gate** step |
| 6 reviewed/follow-up split (`layout`) | **group** document + `commit.py --reviewed` |
| 6 implemented memos | **group** document (closing moves are follow-up paths) |
| 6 finished plans | **group** document, proposed in `/wrap-up`'s summary; never moved by `/yolo` |
| 6 plan files with their implementation | **group** document |
| 6 project memory wiring | `/wrap-up` only |
| 6 message drafting and check | **group** document + **commit** step |
| 7 plan filename validation | **group** document |
| 8 plan presentation | `/wrap-up` summary; `/yolo` reports after the fact |
| 9 commit execution, advance | **commit** step; `advance` runs after the last commit |
| 9 gate before push | **push** step (`gate_pushed_tree.py`, which skips over an unchanged tree) |
| 9 push, bookmark push, peer pull, CI watch | **push** step |
| 10 peer-repo handoff | **handoff** step, both entry points |
| 11 bookmark status | **push** step's last line |

`/commit`'s scripts move with their steps: `change_scope.py` and `format_files.py` to `skills/shared/` (or into
`/wrap-up`), `peer_repo_changes.py` to `skills/shared/`.

## Callers to migrate

Skills that commit move onto `shared/commit.py` and drop raw `git commit`:

- `/release` — the version-bump commit.
- `/pr-create` — its re-commit after `git reset --soft`, through **group** and **commit**.
- `/review-manual` — the reviewed commit, with `--reviewed`.
- `/adopt` — its single convention commit, then hands off to `/yolo` or leaves pushing to the user.
- `/github-create` — points at `/yolo` where it now points at `/commit`.

Everything else that names `/commit` — about 40 files across skills, scripts, `review-auto.js`, `README.md` and
memories — is updated to name `/yolo`, `/wrap-up` or the shared step that now does the thing it described. Find them
with `grep -rn '/commit\b\|skills/commit/'`, and sweep for the old behaviour's words as well as the name, per
`feedback_sweep_the_old_wording`. Other repos need no convention version. Nothing in them invokes `/commit`: their `.claude/commit-checks.sh` is found
by filename, so it keeps gating under the new entry points. What remains there is prose — a commit-checks header
saying the script is "run by the /commit skill", a project skill citing `/commit` as an example — and each repo's own
session fixes that wording the next time it touches the file. Dated memories and memos that mention `/commit` stay as
written.

The memory `commit-wrapup-stay-separate` (project memory) is superseded and gets
rewritten to record this decision.

## Tests

- **No raw commits:** a test in `.claude/commit-checks.sh` fails when any skill outside `shared/commit.py` runs
  `git commit` (reference material such as `agterm/reference.md` exempt by path).
- **`shared/commit.py`:** a repo fixture asserting that each refusal fires (bad message, scan finding, stray staged
  path), that `--reviewed` stages the reviewed content while the disk copy differs, and that a clean call produces a
  signed commit holding exactly its paths. Break each check once to prove its case fails.
- **`shared/push.py`:** against a bare origin, that the bookmark is pushed, the status line is last, and no CI line
  appears in a repo without workflows.
- **pre-push privacy scan:** a pushed commit carrying a planted host refuses; the same with an allow-list entry
  passes; a repo without a conventions record is not scanned.
- **`push-notifies-peer.py`:** updated for the new push path, still failing any push-cleared skill that skips the
  notice.
- **review-auto cap:** `claude/tests/review-auto.mjs` gains a case where the capped final round verifies clean and
  records the review.

## Order of work

- [x] Write `shared/commit.py` and `shared/commit-grouping.md`, with tests.
- [x] Write `shared/push.py`, with tests.
- [x] Add the privacy scan and allow-list to `git/hooks/pre-push`, with tests.
- [x] Build `/yolo`.
- [x] Rebuild `/wrap-up` around the single summary.
- [x] Change review-auto's cap to end on a verify-only round.
- [x] Migrate `/release`, `/pr-create`, `/review-manual`, `/adopt`, `/github-create`.
- [x] Remove `claude/skills/commit/`, its `.gitignore` whitelist line and its `settings.json` permissions; add `/yolo`'s.
- [x] Sweep every remaining mention of `/commit`; rewrite the superseded memory.
- [x] Add the no-raw-commits test to `.claude/commit-checks.sh`.
