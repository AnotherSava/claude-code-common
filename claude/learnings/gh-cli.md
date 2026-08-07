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
