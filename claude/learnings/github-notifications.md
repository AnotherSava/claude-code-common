# GitHub notifications

## Owning a repo does not notify you about its issues

Repository ownership carries no subscription. Delivery requires either an explicit watch or *participation* (mentioned, assigned, commented, authored). An account with **Automatically watch repositories** turned off in Settings → Notifications accumulates repos that silently swallow every issue a stranger opens — and nothing surfaces the gap, because the repos still look normal.

Audit what is actually watched:

```bash
gh api "user/subscriptions?per_page=100" --paginate --jq '.[].full_name'
```

Compare against the repos that can genuinely receive an issue. Archived repos are read-only and forks usually have issues disabled, so both are noise in the diff:

```bash
gh repo list OWNER --limit 300 --json nameWithOwner,hasIssuesEnabled,isFork,isArchived
```

## The subscription API is all-or-nothing

`PUT /repos/{owner}/{repo}/subscription` accepts only `subscribed` and `ignored`:

```bash
gh api -X PUT repos/OWNER/REPO/subscription -F subscribed=true -F ignored=false --jq .subscribed
```

`subscribed: true` means **all activity** — issues, PRs, releases, discussions. The UI's Custom → Issues dropdown is backed by a `thread_types` array (`Issue`, `PullRequest`, `Release`, `Discussion`, `SecurityAlert`) on an internal endpoint the REST API does not expose, so issues-only cannot be scripted. On a solo repo the practical difference is small: GitHub does not email you about your own actions by default, so "all activity" effectively means "someone else did something".

The endpoint does not work with fine-grained PATs, GitHub App user tokens, or installation tokens — it needs a classic token or OAuth with `repo`.

## Email delivery hangs on an account-level toggle with no API

Settings → Notifications → Subscriptions → **Watching → Email** decides whether watched-repo events reach the inbox at all. No REST endpoint exposes it. It is account-wide, so it is a one-time check rather than something to verify per repo — but a skill that sets subscriptions is worthless if it is off.

### Verify it from the inbox, not the settings page

Every GitHub notification email carries a `cc` recording *why* it was sent: `subscribed@`, `author@`, `mention@`, `push@`, `ci_activity@`, all at `noreply.github.com`. `subscribed@` exists only for watched-repo events, so any recent mail carrying it proves the Watching → Email toggle is on:

```
cc:subscribed@noreply.github.com in:anywhere newer_than:1y
```

Cheaper than driving a browser to the settings page, and it still works when browser automation is broken. It also separates causes that otherwise look identical: `ci_activity@` mail arriving while `subscribed@` mail doesn't means Actions notifications are on but watching isn't — a repo can send CI-failure email while staying silent about issues, because workflow-run notifications are governed by a different setting than watching.

Checking spam is worth folding into the same pass; a notification path can be intact at GitHub's end and still be filtered on arrival.
