---
name: github-create
description: >-
  Create a GitHub repository for a local project that already has content but no
  remote yet. Picks a name, creates the repo (public by default), seeds a
  LICENSE-only initial commit, wires origin, rebases local history onto that
  commit, and enables email notifications for new issues. Never commits or pushes
  the project's own files.
  TRIGGER when: user asks to "create a github repo", "publish this to github",
  "put this project on github", or runs /github-create in a project with no origin.
  DO NOT TRIGGER when: the project already has an origin remote (use /commit to
  push), the user wants to clone or fork an existing repo, or the user wants to cut
  a release (use /release).
allowed-tools: AskUserQuestion, Read, Bash(git init:*), Bash(git rev-parse:*), Bash(git status:*), Bash(git log:*), Bash(git rev-list:*), Bash(git branch:*), Bash(git remote:*), Bash(git fetch:*), Bash(git pull:*), Bash(git config:*), Bash(git rm:*), Bash(gh auth status:*), Bash(gh config get:*), Bash(gh repo create:*), Bash(gh repo view:*), Bash(gh repo list:*), Bash(gh api:*), Bash(bash ~/.claude/skills/github-create/scripts/seed-license.sh:*), Bash(rm LICENSE:*)
---

# Create a GitHub repository

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Folder name: !`basename "$PWD"`
- Is a git repo: !`git rev-parse --is-inside-work-tree 2>/dev/null || echo NO`
- Current branch: !`git branch --show-current 2>/dev/null || echo "(none)"`
- Commit count: !`git rev-list --count HEAD 2>/dev/null || echo 0`
- Blocking changes: !`git status --porcelain 2>/dev/null | grep -v '^??' || echo "(none)"`
- Existing remotes: !`git remote -v 2>/dev/null | grep . || echo "(none)"`
- LICENSE on disk: !`test -f LICENSE && echo PRESENT || echo MISSING`
- README opening: !`head -n 5 README.md 2>/dev/null || echo "(no README.md)"`
- Manifest name field: !`grep -m1 '"name"' package.json 2>/dev/null || grep -m1 '^name' pyproject.toml Cargo.toml 2>/dev/null || echo "(none)"`
- Top-level entries: !`ls -A1 2>/dev/null | head -n 30`
- GitHub account: !`gh api user --jq .login 2>/dev/null || echo NOT-AUTHENTICATED`
- Git protocol: !`gh config get git_protocol --host github.com 2>/dev/null || echo https`
- Copyright holder: !`git config user.name 2>/dev/null || echo "(unset)"`
- Existing repo names: !`gh repo list --limit 200 --json name --jq '.[].name' 2>/dev/null || echo "(unavailable)"`

## End state

When this skill finishes:

- A GitHub repo exists whose entire history is one root commit, `Initial commit`, containing only `LICENSE`.
- Local commits (if any) sit on top of that root commit, rebased, **unpushed**.
- `origin` is wired and the local branch tracks it.
- The repo is subscribed for email notifications.

The project's own files are never committed or pushed. Pushing is a separate, explicitly-requested step (`/commit`).

## Working directory

File paths in this skill (`LICENSE`, `README.md`) are relative to **Repo root** from Context. The cwd may be a subdirectory — prefix Repo root when calling Read or removing a file, and note that the `LICENSE on disk` and `README opening` context lines were evaluated against the cwd, so re-check them against Repo root if the two differ.

## 1. Preflight

Check these against Context and stop with a plain explanation if any fails:

| Check | Data | Failure |
|---|---|---|
| Authenticated | **GitHub account** | `NOT-AUTHENTICATED` → tell the user to run `gh auth login` in a terminal, then stop |
| No remote yet | **Existing remotes** | anything containing `origin` → this project already has a remote; stop and point at `/commit` |
| Copyright holder known | **Copyright holder** | `(unset)` → ask the user for the name to put in the license |

If **Is a git repo** is `NO`, run `git init -b main`. Do not create any commit.

## 2. Choose the repository name

If the user passed a name as an argument, use it verbatim and skip to step 3.

Otherwise propose names via `AskUserQuestion`. Derive 3 candidates from **Folder name**, **Manifest name field**, and **README opening** — favour lowercase kebab-case, and drop generic prefixes/suffixes that carry no meaning on GitHub (`my-`, `-project`, `-app`, `test-`). Use **Top-level entries** to tell what the project actually is, so a candidate can be more descriptive than the folder name.

Exclude any candidate that appears in **Existing repo names**. Say in the question which account the repo will be created under (**GitHub account**).

Then confirm the chosen name is free:

```
gh repo view <owner>/<name> --json name
```

Success means the name is taken — go back and pick another. A `Could not resolve to a Repository` error means it's free.

## 3. Confirm visibility and description

Ask once, via `AskUserQuestion`, with **public preselected**:

- **Visibility** — public (default) or private.
- **Description** — draft a one-line description from **README opening** and **Top-level entries** and offer it; accept an edit or an empty value.

Never create a public repo without this confirmation, even when the user's request said "public" — a wrong invocation publishes a name and description immediately.

## 4. Resolve blockers

**Blocking changes.** If **Blocking changes** is not `(none)`, the rebase in step 7 will fail — `git pull --rebase` refuses with staged or modified tracked files, and on a repo with no commits it aborts with `Updating an unborn branch with changes added to the index`. Untracked (`??`) files are fine and are excluded from that context line already. Show the entries and ask the user to either commit them or unstage with `git reset`. Stop until resolved.

**Existing LICENSE.** If **LICENSE on disk** is `PRESENT`, the seeded commit will collide — an add/add merge conflict if the file is committed, or `untracked working tree files would be overwritten` if it isn't. Read the first 10 lines of the local `LICENSE`, show them, and ask via `AskUserQuestion`:

- **Use GitHub's MIT license** — delete the local file (`git rm LICENSE` if tracked, otherwise `rm LICENSE`), then continue normally. Do not choose this silently; a project may deliberately carry a non-MIT license.
- **Keep the local license** — skip steps 6 and the rebase half of step 7. The repo is created empty, `origin` is wired, and the existing LICENSE gets pushed later with everything else. Say explicitly that there will be no initial commit to rebase onto.

## 5. Create the empty repository

```
gh repo create <owner>/<name> --public --description "<description>"
```

Use `--private` instead when the user chose private. Omit `--description` when empty.

Pass **no** `--license`, `--add-readme`, `--gitignore`, or `--source`. `--source` is rejected outright alongside `--license`, and `--license` on its own does not reliably produce a commit — see `references/repo-init-flags.md` for why. The repo is intentionally created with zero commits; step 6 creates the only one.

## 6. Seed the LICENSE initial commit

Skip this step if the user chose "Keep the local license" in step 4.

```
bash ~/.claude/skills/github-create/scripts/seed-license.sh <owner>/<name> "<copyright holder>" <current year>
```

Use **Copyright holder** from Context and the current year. The script fetches GitHub's MIT template, fills the `[year]` and `[fullname]` placeholders, and commits it as `Initial commit` through the Contents API — the documented way to bootstrap an empty repo, and the only way to get a commit containing *just* the license.

It prints a commit SHA on success. If it errors, report the error and stop; do not fall back to pushing a locally-made commit, which would put the project's files on the remote.

## 7. Wire the remote and rebase

Run these as separate Bash calls, in order.

1. Read the branch GitHub actually used — do not assume `main`:

   ```
   gh api repos/<owner>/<name> --jq .default_branch
   ```

   Endpoints passed to `gh api` must have **no leading slash**. Git Bash on Windows rewrites `/repos/...` into a filesystem path and the call fails.

2. If **Current branch** differs from that default branch, rename the local branch to match:

   ```
   git branch -m <current> <default>
   ```

   Confirm with the user first. Skipping this leaves the local work on `master` while the remote is on `main`, which quietly creates a second branch on the first push.

3. Add the remote, matching **Git protocol**:
   - `ssh` → `git remote add origin git@github.com:<owner>/<name>.git`
   - `https` → `git remote add origin https://github.com/<owner>/<name>.git`

   Read the host-scoped protocol from Context, not the global `gh config get git_protocol` — they differ, and the global value can produce an HTTPS remote in an account whose every other repo uses SSH.

4. `git fetch origin`

5. `git pull --rebase origin <default>` — replays local commits on top of the LICENSE commit, making it the root of history. When **Commit count** is `0` this simply brings LICENSE into the tree and leaves untracked files alone.

6. `git branch --set-upstream-to=origin/<default> <default>` — `git pull` does not set tracking on its own, and without it `/commit` cannot tell what is unpushed.

If the rebase stops on a conflict, do not improvise: run `git rebase --abort` and report which file conflicted. See `references/repo-init-flags.md` for the failure matrix.

## 8. Enable issue email notifications

```
gh api -X PUT repos/<owner>/<name>/subscription -F subscribed=true -F ignored=false --jq .subscribed
```

Expect `true`. This subscribes the account to the repo so new issues (and PRs, releases, discussions) generate a notification. Do this explicitly rather than relying on GitHub's "Automatically watch repositories" account setting, which is off for many accounts and silently leaves new repos unwatched.

There is no *public* API for issues-only notifications — the REST subscription endpoint takes only `subscribed` and `ignored`, so `gh api` cannot express a Custom subscription. Leave the repo on plain `subscribed=true` unless the user explicitly asks to drop an event type; do not offer the fallback below as part of this skill.

When they do ask, the UI's Custom dropdown is backed by an internal endpoint that browser automation can drive:

- **Request** — `POST https://github.com/notifications/subscribe`, `FormData` carrying `do=custom`, `repository_id=<numeric id>` (from `gh api repos/<owner>/<name> --jq .id`), and one `thread_types[]` entry per event to *keep*: `Issue`, `PullRequest`, `Release`, `Discussion`, `SecurityAlert`. Omitted types are the ones switched off.
- **Auth** — no CSRF token in the body. It rides on session cookies plus the headers GitHub's own fetch wrapper sends (`GitHub-Verified-Fetch: true`, `X-Requested-With: XMLHttpRequest`, and a page-scoped `X-Fetch-Nonce`), so it is reachable only from a logged-in github.com page, never from `gh api`. Capture the headers by intercepting `window.fetch` during one real Apply, then replay for other repos from that same page.
- **Semantics** — Custom is additive on top of "Participating and @mentions", not "All Activity minus X".
- **Verify** with `gh api repos/<owner>/<name>/subscription`: a custom subscription makes it return 404, because the endpoint cannot represent one. An All Activity watch returns `subscribed: true`.

That endpoint is undocumented and can change without notice; the shape above was verified in August 2026.

Delivery also depends on one **account-level** setting with no API: Settings → Notifications → Subscriptions → Watching → Email. It is on by default and applies to every repo, so it is a one-time thing, not per-repo. Do not try to read it with browser automation as part of this skill. To confirm it cheaply, check whether past GitHub mail carries the `subscribed@noreply.github.com` cc — that cc is GitHub's marker for "you receive this because you are watching the repository", so its presence proves the toggle is on.

## 9. Report

State plainly:

- Repo URL and visibility.
- That the remote holds exactly one commit (LICENSE) and the project's files are still local and unpushed.
- The local branch name and what it tracks.
- Notification subscription confirmed.
- That `/commit` is the next step when they want to push — as a fact, not an offer.

## Out of scope

- Do NOT commit or push the project's files. The only remote commit is the LICENSE one, created server-side.
- Do NOT run `/commit`, `git add`, or `git push`.
- Do NOT add a `.gitignore`, README, or CI config the user didn't ask for.
- Do NOT create branches beyond renaming the current one to match the remote default.
- Do NOT delete or archive repositories.
- Do NOT scan the project for secrets, or gate creation on it.
- Do NOT change account-level GitHub settings.
