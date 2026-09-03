---
name: publish-chrome-extension
description: >-
  Republish a new release of an existing Chrome extension to the Chrome Web Store: downloads the
  release zip from GitHub, checks what changed since the version the store already holds, uploads
  the zip via the Web Store API, and submits it for review.
  TRIGGER when: the user wants to publish, republish, or upload a new extension version to the
  Chrome Web Store, typically right after /release.
  DO NOT TRIGGER when: creating a brand-new store listing, editing store listing content
  (description, screenshots), or building/tagging a release (use /release for that).
allowed-tools: AskUserQuestion, Read, Write, Edit, Bash(bash ~/.claude/skills/publish-chrome-extension/scripts/cws.sh:*), Bash(gh release download:*), Bash(gh release view:*), Bash(unzip -p:*), Bash(mkdir -p /tmp/cws-publish:*), Bash(ls /tmp/cws-publish:*), Bash(git diff:*), Bash(git log:*), Bash(git tag:*), Bash(git fetch --tags:*)
---

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.

## Context
- Chrome extension: !`test -f manifest.json && echo yes || echo no`
- Manifest version: !`sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' manifest.json 2>/dev/null | head -1`
- Repo: !`gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || echo NONE`
- Latest release: !`gh release view --json tagName --jq .tagName 2>/dev/null || echo NONE`
- Release zip assets: !`gh release view --json assets --jq ".assets[].name" 2>/dev/null || echo NONE`
- API credentials: !`test -f ~/.claude/skills/publish-chrome-extension/config/cws.conf && echo PRESENT || echo MISSING`
- Extension ID: !`grep -rhoE 'chromewebstore\.google\.com/detail/[^/]+/[a-p]{32}' --include='*.md' --exclude-dir=node_modules . 2>/dev/null | grep -oE '[a-p]{32}' | head -1 || echo NONE`

## 1. Check preconditions

- **Chrome extension** must be `yes` — otherwise **STOP**: this skill republishes Chrome extensions (`manifest.json` at the repo root) and nothing else.
- **Repo** must not be `NONE` — the zip comes from a GitHub release, so the repo needs a GitHub remote.
- **Latest release** must not be `NONE` — if it is, tell the user to run `/release` first and stop.

## 2. First-time credential setup

If **API credentials** is MISSING, walk the user through the one-time OAuth setup in
`references/cws-api-setup.md` (Google Cloud project, Chrome Web Store API, Desktop-app OAuth
client, then `cws.sh init` / `auth` / `exchange`). Do not proceed until `cws.conf` exists.

If `cws.sh` later fails with a missing/expired `REFRESH_TOKEN` error, re-run only the
`auth` + `exchange` steps from that reference — the client credentials stay valid.

## 3. Resolve the extension ID

**Extension ID** in Context is scraped from the project's own Web Store install link — the
32-character trailing segment of `https://chromewebstore.google.com/detail/<slug>/<ID>`, which a
published extension normally puts in its README or docs. That link is user-facing, so it cannot go
stale unnoticed the way a private copy would.

If it is `NONE`, ask the user for the ID (the same trailing segment, also visible in the Developer
Dashboard edit URL). Offer to add the install link to the README while you're there, so the next
run finds it.

This skill deliberately stores **nothing** about the listing. The dashboard-only fields — single
purpose, permission justifications, store description, data usage, privacy policy URL — cannot be
read back through the API, so any repo copy of them is an unverifiable cache that drifts silently
the moment someone edits the dashboard directly. The dashboard is the authority; step 6 derives
what needs checking from git and the store instead. Do not reintroduce a listing file.

## 4. Pick the release

- Default to **Latest release** from Context; if the user named a different tag when invoking the
  skill, use that instead.
- Cross-check: the tag (`vX.Y.Z`) should match **Manifest version** (`X.Y.Z`) — after a normal
  `/release` flow they agree. On mismatch, warn the user and ask whether to continue (they may be
  intentionally republishing an older tag).
- **Release zip assets** must contain exactly one `.zip` for that release; if several, ask which.

## 5. Download and verify the zip

1. Run: `mkdir -p /tmp/cws-publish`
2. Run: `gh release download <tag> --pattern "*.zip" --dir /tmp/cws-publish --clobber`
3. Verify the package version inside the zip matches the tag:
   `unzip -p /tmp/cws-publish/<asset>.zip manifest.json` — check its `"version"`. On mismatch,
   **STOP** and report: the release asset doesn't contain what the tag claims.

## 6. Review listing info for staleness

The dashboard blocks submission when the listing info doesn't cover the new package, and the API
cannot fix it. Catch the gaps now, before the upload — by diffing what the package claims against
the version the store already holds:

1. **Read the store's current version.** Run:
   `bash ~/.claude/skills/publish-chrome-extension/scripts/cws.sh status <extension-id>`
   - `crxVersion` is the version the store holds — call it LIVE.
   - `uploadState` says what LIVE is: `NOT_FOUND` means no draft is pending, so LIVE is the
     published package. Anything else means LIVE is a draft that was uploaded and never submitted;
     say so, because the real published version is then older.
   - If no `v<LIVE>` tag exists locally, run `git fetch --tags` and retry. If it still doesn't
     exist, ask the user which tag corresponds to the store version.
2. **Diff the manifest since LIVE.** Run: `git diff v<LIVE>..HEAD -- manifest.json`
   - **Permission added** to `permissions` or `host_permissions` → the dashboard has no
     justification for it and will reject the submission. Draft one with the user, grounded in
     what the code actually uses the permission for, and have them paste it into the dashboard's
     Privacy practices tab and **Save draft** there before continuing.
   - **Permission removed** → tell the user to delete its now-orphaned justification in the
     dashboard.
   - **`description` changed** → the store Description usually mirrors the manifest's, and the
     Single purpose statement usually mirrors both. Show the diff and ask whether the dashboard
     text (and the project's README/docs tagline) needs the same edit.
3. **Single purpose.** Show the user-visible changes since LIVE — `git log v<LIVE>..HEAD --oneline`,
   `feat:` subjects — and ask whether the dashboard's Single purpose statement still covers
   everything the extension now does. Read the current statement from the dashboard rather than
   from anything in the repo; if it needs changing, draft the new text together and have the user
   paste it in.
4. **Data usage.** If the release introduces remote code or starts collecting/transmitting any
   user-data category (rare), the dashboard's Data usage form needs updating to match.
5. Wait for the user to confirm every dashboard edit is saved before continuing.

## 7. Upload

1. Present the plan — extension ID, tag, zip filename, version — and ask for confirmation.
2. Run: `bash ~/.claude/skills/publish-chrome-extension/scripts/cws.sh upload <extension-id> /tmp/cws-publish/<asset>.zip`
3. Inspect the JSON response `uploadState`:
   - `SUCCESS` → continue
   - `IN_PROGRESS` → the upload is processing server-side; continue (publish will pick it up)
   - `FAILURE` / `NOT_FOUND` → show every `itemError` entry and **STOP**

## 8. Submit for review

1. Ask the user to confirm submitting the uploaded draft for Web Store review (this is the
   point of no return — a submitted version can only be cancelled from the dashboard).
2. Run: `bash ~/.claude/skills/publish-chrome-extension/scripts/cws.sh publish <extension-id>`
3. Report the response `status` (e.g. `OK`, `ITEM_PENDING_REVIEW`) and `statusDetail` verbatim.
   A 400 "Publish condition not met … Privacy practices" means step 6 missed something — fix it
   in the dashboard and re-run the publish command.

## 9. Report

Print:
- the dashboard URL: `https://chrome.google.com/webstore/devconsole` (review progress lives there)
- the public listing URL: `https://chromewebstore.google.com/detail/<extension-id>`
- a reminder that review typically takes from a few hours to a few days; the new version goes
  live automatically once approved
- that `cws.sh status <extension-id>` reports what the store actually holds — it is the answer to
  "which version is published", so nothing needs recording in the repo

## Out of scope

- Do NOT create a new Web Store listing — the extension must already exist in the dashboard
- Do NOT edit store listing content in the dashboard itself — every dashboard change is the
  user's manual step (the API has no endpoint for it)
- Do NOT store a copy of the listing text or the published version in the repo — see step 3
- Do NOT bump versions, build zips, or create tags/releases — that's the `/release` skill
- Do NOT monitor the review — it can take days; the skill ends at submission
