# gh CLI

## `gh issue list` / `gh pr list` resolve a fork to its upstream parent

Run inside a fork that has an `upstream` remote, `gh issue list` (and `pr list`, `issue view`, etc.) auto-resolves to the **parent** repo, not your fork — so it reports the upstream's issues. This is silent and easy to miss.

**Fix:** pin the repo explicitly to your origin: `gh issue list --repo OWNER/REPO …`. Derive `OWNER/REPO` from the origin URL rather than relying on cwd resolution:

```bash
slug=$(git remote get-url origin | sed -E 's#^.*github\.com[:/]##; s#\.git$##; s#/$##')
gh issue list --repo "$slug" --state open --json number
```

A fork with issues disabled returns the message *"the 'OWNER/REPO' repository has disabled issues"* — handle that as "no issues" (blank/zero), not an error.

Discovered building the `github-status` skill's open-issue count: `InverseCSG` (fork of `yijiangh/InverseCSG`) showed the upstream's issue count until the query was pinned to `AnotherSava/InverseCSG`.

## Pushing a workflow file needs the `workflow` scope

`gh auth login` grants `repo`, `read:org`, `gist` — **not** `workflow`. Since gh installs itself
as git's credential helper, an HTTPS `git push` carrying any commit that creates or edits
`.github/workflows/*` is rejected:

```
! [remote rejected] main -> main (refusing to allow an OAuth App to create or
  update workflow `.github/workflows/publish.yml` without `workflow` scope)
```

The commits are fine — only the push is blocked. Check with `gh auth status` ("Token scopes"),
and grant it once:

```bash
gh auth refresh -s workflow
```

**It needs a real TTY.** Run it non-interactively (Claude Code's `!` prefix, a script, CI) and
it fails with `--hostname required when not running interactively`; supplying `-h github.com`
gets past that message but the device flow still wants a terminal. Run it in Terminal/iTerm.

**There is no "app" to install.** The flow prints a one-time code in the terminal and opens
github.com/login/device, whose prompt — *"Enter the code displayed in the app or on the device
you're signing in to"* — means gh itself. If gh errored before printing a code, that page has
nothing valid to accept; don't go hunting for an authenticator app.

**SSH sidesteps it entirely**, since OAuth scopes don't apply to SSH keys. A one-off
`git push git@github.com:OWNER/REPO.git main` works with no config change and no re-auth —
useful when the interactive refresh isn't practical, though granting the scope is the durable
fix since it recurs the first time any project gains a workflow.

## `gh api` endpoints must not start with a slash on Git Bash

MSYS path translation rewrites a leading-slash argument into a filesystem path before gh ever sees it:

```
$ gh api /licenses/mit
invalid API endpoint: "C:/Program Files/Git/licenses/mit". Your shell might be
rewriting URL paths as filesystem paths. To avoid this, omit the leading slash
from the endpoint argument
```

Write `gh api licenses/mit`. The error names the fix, but the symptom reads like a wrong endpoint rather than a shell problem, and the same command works unchanged on macOS — so it only breaks on one of two machines. Applies to every `gh api` call; drop the leading slash unconditionally and it's portable.

## An error body goes to stdout, and `--jq` is not applied to it

On a 4xx, `gh api` prints the error JSON to **stdout**, not stderr, and skips the `--jq` filter entirely. So the two obvious ways to test a response both misfire:

```bash
resp=$(gh api "repos/$r/subscription" --jq '.subscribed' 2>/dev/null)
[ -z "$resp" ]        # expected: true on 404. Actually false —
                      # resp holds {"message":"Not Found",...,"status":"404"}
[ "$resp" = "true" ]  # also false, so every repo falls to the else branch
```

A loop written that way reports every item as the *unexpected* case, which reads as "the change didn't apply" rather than "the check is broken" — the failure is uniform and confident-looking. Match on the body, or branch on the exit status:

```bash
case $(gh api "repos/$r/subscription" 2>/dev/null) in
  *'"status":"404"'*)     ... ;;
  *'"subscribed":true'*)  ... ;;
esac
```

Redirecting stderr does not help, because the payload was never on stderr. `--silent` suppresses the body but not the exit code, so `gh api ... --silent; [ $? -eq 0 ]` is the terse form when only success matters.

## `gh config get git_protocol` returns the wrong value without `--host`

The bare form reports the **global** default; git actually uses the per-host setting:

```
$ gh config get git_protocol                      # https
$ gh config get git_protocol --host github.com    # ssh
```

`gh auth status` prints the host-scoped one ("Git operations protocol: ssh"), which is why the two can disagree unnoticed. Reading the global value when constructing a remote URL yields an HTTPS remote in an account where every existing repo is SSH — it works, so nothing fails loudly, it just drifts.

## `gh repo create --license` can leave the repo empty

GitHub's `POST /user/repos` applies `license_template` only while auto-initialising, and gh sets the `auto_init` field solely from `--add-readme` (`pkg/cmd/repo/create/http.go`, where `InitReadme bool` carries the `auto_init` JSON tag). So `--license mit` on its own can produce a repo with no commit and no LICENSE.

Adding `--add-readme` does force the initial commit, but puts `README.md` in it — which collides with the README an existing project already has. `--source` is no escape either: gh rejects it with *"the `--source` option is not supported with `--clone`, `--template`, `--license`, or `--gitignore`"*.

For an initial commit containing **only** a license, create the repo bare and commit the file through the Contents API:

```bash
gh repo create OWNER/NAME --public
gh api -X PUT repos/OWNER/NAME/contents/LICENSE -f message="Initial commit" -f content="<base64>"
```

`PUT /contents/{path}` is GitHub's documented way to bootstrap an empty repo. The Git Database endpoints (blob → tree → commit → ref) can't do it — they return 409 with no parent commit to build on. Cost: Contents-API commits aren't signed, so that root commit shows unverified.

`--license` also cannot express **all rights reserved**, and no flag can. `gh api licenses` returns 13 keys — `agpl-3.0 apache-2.0 bsd-2-clause bsd-3-clause bsl-1.0 cc0-1.0 epl-2.0 gpl-2.0 gpl-3.0 lgpl-2.1 mit mpl-2.0 unlicense` (checked 2026-08-26) — every one of them open-source or a public-domain dedication. A reservation notice is not a template you can name; it has to be supplied as content through the same Contents API call. `github-create`'s `scripts/seed-license.sh` therefore carries that text itself and takes the license kind as a fourth argument.

One more trap in that skill's flow: if the local project already has a LICENSE and you choose to keep it, the seeding step is skipped and the remote stays at **zero** commits, not one. `git fetch` then creates no `origin/<default>` ref, `git branch --set-upstream-to` fails, and the branch has no upstream until the first push — at which point `/commit` cannot tell what is unpushed. Nothing to repair, but it has to be said, or the run reports the normal one-commit end state.

The `github-create` skill implements this; its `references/repo-init-flags.md` carries the full failure matrix for rebasing an existing local project onto such a commit.

## Forks and stars say nothing about who copied a repo — `traffic/clones` does, for 14 days

Before concluding that a repo nobody starred was never taken, check the traffic API. Forks and stars measure
*social* engagement; a mirror, an archiver or a crawler clones without touching either.

```bash
gh api repos/{owner}/{repo}/traffic/clones     # needs push access
```

Returns `count` (total clones) and `uniques` (distinct cloners), plus a per-day breakdown. Real case: a personal
repo with **0 stars, 0 watchers, 0 forks** had been cloned **115 times by 58 unique cloners** in a fortnight.

Three properties that decide how you use it:

- **The window is the last 14 days**, updated hourly. There is no way to ask for more. If the period you care
  about is about to roll out of it, snapshot the JSON — the data is simply gone afterwards.
- **Making a repo private erases the star and watcher counts** (GitHub's own doc for
  `setting-repository-visibility` says so). So a private repo's zeros are an artefact of the transition and carry
  no information at all. `forks_count` / `network_count` survive and stay meaningful.
- **Fetches and pulls are not counted** — only full clones. Identity and IP are never exposed, so you learn that
  copies were taken and nothing about by whom.

Cross-check for a durable public copy with Software Heritage, the main systematic archiver of public GitHub:
`https://archive.softwareheritage.org/api/1/origin/https://github.com/{owner}/{repo}/get/` — `NotFoundExc` means
no archived snapshot.
