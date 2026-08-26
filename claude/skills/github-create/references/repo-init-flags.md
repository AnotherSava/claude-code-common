# Why the repo is created empty, and what breaks otherwise

Background for when step 5–7 misbehaves. The happy path doesn't need this.

## `gh repo create --license` does not reliably create a commit

GitHub's `POST /user/repos` applies `license_template` only while auto-initialising, and `gh`
sets the `auto_init` field solely from `--add-readme` (`pkg/cmd/repo/create/http.go`, where
`InitReadme bool` carries the `auto_init` JSON tag). So `--license mit` on its own can produce a
repo with no commit and no LICENSE.

The obvious repair — adding `--add-readme` — makes the initial commit contain `README.md`
alongside `LICENSE`. Almost every project this skill runs in already has a README, so that
trades a rare collision for a near-certain one.

`--source` is not an option either: `gh` rejects it outright with *"the `--source` option is not
supported with `--clone`, `--template`, `--license`, or `--gitignore`"*.

For the all-rights-reserved kind the flag is not merely unreliable but inapplicable: GitHub's
license catalogue (`gh api licenses`) lists open-source licenses only, so there is no template
to name. `seed-license.sh` therefore carries that text itself.

Hence: create the repo with no init flags at all, then commit `LICENSE` through
`PUT /repos/{owner}/{repo}/contents/LICENSE`. That endpoint is GitHub's documented way to
bootstrap an empty repository, and it commits exactly the one path given. The low-level Git
Database endpoints (blob → tree → commit → ref) cannot be used here: they return 409 on a repo
with no commits, because there is no parent to build on.

Cost of this approach: commits made through the Contents API are not signed, so the root commit
shows as unverified. Only that one commit is affected.

## Failure matrix for `git pull --rebase origin <default>`

Measured against a simulated remote whose only commit adds `LICENSE`:

| Local state | Result |
|---|---|
| Commits, no LICENSE | Clean rebase. LICENSE becomes root, local commits on top. |
| Commits, LICENSE **committed** | `CONFLICT (add/add): Merge conflict in LICENSE`, rebase halts |
| No commits, untracked files only | Works. LICENSE arrives, untracked files untouched. |
| No commits, LICENSE untracked on disk | `error: The following untracked working tree files would be overwritten by merge` |
| Commits + modified tracked file | `cannot pull with rebase: You have unstaged changes` (exit 128) |
| No commits + staged index | `fatal: Updating an unborn branch with changes added to the index` (exit 128) |
| Local `master`, remote `main` | Rebase succeeds *onto `master`* — the remote default stays separate, so the first push creates a second branch |

Two rules fall out, both enforced in the skill:

- **Any `git status --porcelain` entry that is not `??` blocks the rebase.** Untracked files never do.
  Staged-only changes block it just as modified tracked files do.
- **Rename the local branch to the remote default *before* pulling.** Renaming afterwards leaves the
  rebase already applied to the wrong branch name.

## The keep-local-license branch leaves the remote at zero commits

Step 4's "keep the local license" option skips the seeding step, so the repo stays exactly as
`gh repo create` left it: **no commits at all**, not one. Two consequences follow, and both are
easy to misreport as success:

- `git fetch origin` succeeds and creates no `origin/<default>` ref, because there is none. The
  API answers a read of the default branch's tree with HTTP 409 `Git Repository is empty`.
- `git branch --set-upstream-to=origin/<default>` therefore fails, so step 7.6 cannot run and the
  branch has no upstream. `/commit` reads unpushed work by comparing against the upstream, so
  until the first push it cannot tell what is unpushed.

Neither is a fault to repair — the first push creates the branch, the ref and the tracking
together. It just has to be *said*, or the report reads as the normal one-commit end state.

## Recovering a halted rebase

`git rebase --abort` returns the tree to its pre-pull state; the remote is unaffected because
nothing was pushed. The repo and its LICENSE commit still exist on GitHub, so after clearing the
blocker, resume from step 7 — do not re-run steps 5 and 6, which would fail on an existing repo
and an existing file.

## `gh api` endpoints need no leading slash

On Windows Git Bash, MSYS path translation rewrites a leading-slash endpoint into a filesystem
path: `gh api /licenses/mit` fails with *"invalid API endpoint: C:/Program Files/Git/licenses/mit.
Your shell might be rewriting URL paths as filesystem paths."* Write `gh api licenses/mit`. The
same applies to every `gh api` call in this skill.
