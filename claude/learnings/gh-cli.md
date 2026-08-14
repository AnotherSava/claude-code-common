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

The `github-create` skill implements this; its `references/repo-init-flags.md` carries the full failure matrix for rebasing an existing local project onto such a commit.
