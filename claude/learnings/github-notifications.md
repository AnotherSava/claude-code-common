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

`subscribed: true` means **all activity** — issues, PRs, releases, discussions. The UI's Custom dropdown is backed by a `thread_types` array (`Issue`, `PullRequest`, `Release`, `Discussion`, `SecurityAlert`) that the REST API does not expose. On a solo repo the practical difference is small: GitHub does not email you about your own actions by default, so "all activity" effectively means "someone else did something".

The endpoint does not work with fine-grained PATs, GitHub App user tokens, or installation tokens — it needs a classic token or OAuth with `repo`.

## Custom watch IS scriptable, just not through the API

An earlier version of this note said issues-only "cannot be scripted". It can — the UI's Custom dropdown posts to an internal endpoint that browser automation reaches from a logged-in page. Verified 2026-08-18 by intercepting `window.fetch` during one real Apply, then replaying the captured request for 20 more repos from that same page:

```js
const fd = new FormData();
fd.append('do', 'custom');
fd.append('repository_id', String(id));        // gh api repos/OWNER/REPO --jq .id
for (const t of ['Issue', 'PullRequest', 'Discussion', 'SecurityAlert']) fd.append('thread_types[]', t);
await fetch('/notifications/subscribe', {method: 'POST', body: fd, headers});
```

Four things make it work, and each is the kind of detail that turns a 200 into a no-op if guessed:

- **No CSRF token in the body.** Auth is session cookies plus the headers GitHub's own fetch wrapper sends: `GitHub-Verified-Fetch: true`, `X-Requested-With: XMLHttpRequest`, and a page-scoped `X-Fetch-Nonce`. Lift them off the intercepted call rather than hand-rolling. The nonce is reusable across many requests from one page load, so a bulk pass needs no re-navigation.
- **Listed types are the ones you KEEP.** Omitting `Release` is what switches releases off.
- **Custom is additive on top of "Participating and @mentions"**, not "All Activity minus X" — so you keep everything you're personally involved in regardless.
- **Verification is a 404.** After a custom subscription, `gh api repos/OWNER/REPO/subscription` returns `Not Found`, because the legacy endpoint cannot represent the state; an All Activity watch returns `subscribed: true`. That inversion is the cheap way to audit a bulk change from the CLI. (Watch the stdout trap in `gh-cli.md` when scripting the check.)

Undocumented and free to change. GraphQL is not an alternative — `updateSubscription` takes only `SUBSCRIBED`/`UNSUBSCRIBED`/`IGNORED`, the same all-or-nothing states as REST.

## Silencing your own releases

Two different causes, and the fix for one does nothing for the other:

- **You published it.** Settings → Notifications → **"Your own updates, such as when you open, comment on, or close an issue or pull request"**. It sits in the email-preferences block, is email-only, and has no API.
- **CI published it.** A release created by a workflow with `GITHUB_TOKEN` is attributed to `github-actions[bot]`, so it is not "your own update" and that checkbox is irrelevant — you get it as a *watcher*. Only the subscription change above stops it.

Auto-watching of new repos was deprecated on 2025-05-18, so newer accounts accumulate fewer of these; existing subscriptions persist untouched until changed.

## Email delivery hangs on an account-level toggle with no API

Settings → Notifications → Subscriptions → **Watching → Email** decides whether watched-repo events reach the inbox at all. No REST endpoint exposes it. It is account-wide, so it is a one-time check rather than something to verify per repo — but a skill that sets subscriptions is worthless if it is off.

### Verify it from the inbox, not the settings page

Every GitHub notification email carries a `cc` recording *why* it was sent: `subscribed@`, `author@`, `mention@`, `push@`, `ci_activity@`, all at `noreply.github.com`. `subscribed@` exists only for watched-repo events, so any recent mail carrying it proves the Watching → Email toggle is on:

```
cc:subscribed@noreply.github.com in:anywhere newer_than:1y
```

Cheaper than driving a browser to the settings page, and it still works when browser automation is broken. It also separates causes that otherwise look identical: `ci_activity@` mail arriving while `subscribed@` mail doesn't means Actions notifications are on but watching isn't — a repo can send CI-failure email while staying silent about issues, because workflow-run notifications are governed by a different setting than watching.

Checking spam is worth folding into the same pass; a notification path can be intact at GitHub's end and still be filtered on arrival.
