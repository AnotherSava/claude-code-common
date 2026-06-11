---
name: publish-chrome-extension
description: >-
  Republish a new release of an existing Chrome extension to the Chrome Web Store: downloads the
  release zip from GitHub, reviews the tracked store-listing info for staleness, uploads the zip
  via the Web Store API, and submits it for review.
  TRIGGER when: the user wants to publish, republish, or upload a new extension version to the
  Chrome Web Store, typically right after /release.
  DO NOT TRIGGER when: creating a brand-new store listing, editing store listing content
  (description, screenshots), or building/tagging a release (use /release for that).
allowed-tools: AskUserQuestion, Read, Write, Edit, Bash(bash ~/.claude/skills/publish-chrome-extension/scripts/cws.sh:*), Bash(gh release download:*), Bash(gh release view:*), Bash(unzip -p:*), Bash(mkdir -p /tmp/cws-publish:*), Bash(ls /tmp/cws-publish:*)
---

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.

## Context
- Chrome extension: !`test -f manifest.json && echo yes || echo no`
- Manifest version: !`sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' manifest.json 2>/dev/null | head -1`
- Repo: !`gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || echo NONE`
- Latest release: !`gh release view --json tagName --jq .tagName 2>/dev/null || echo NONE`
- Release zip assets: !`gh release view --json assets --jq ".assets[].name" 2>/dev/null || echo NONE`
- API credentials: !`test -f ~/.claude/skills/publish-chrome-extension/config/cws.conf && echo PRESENT || echo MISSING`
- Listing file: !`test -f cws-publish.json && echo PRESENT || echo MISSING`

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

## 3. Resolve the listing file

The `cws-publish.json` file is the tracked mirror of the dashboard-only store listing data (the
API cannot read or write any of it). It lives next to `manifest.json` — the root of the unpacked
extension — so a repo hosting several extensions keeps one per extension folder. Shape:

```json
{
  "extensionId": "<32-char item ID>",
  "privacyPolicyUrl": "<the privacy policy URL set in the dashboard>",
  "singlePurpose": "<the Single purpose statement, verbatim from the dashboard>",
  "permissionJustifications": {
    "<permission>": "<justification text, one entry per manifest permission>",
    "host:<domain>": "<justification for each host permission>"
  },
  "storeListing": {
    "category": "<dashboard Store listing category>",
    "language": "<listing language>",
    "description": "<the store Description, verbatim from the dashboard>",
    "officialUrl": "<…>", "homepageUrl": "<…>", "supportUrl": "<…>",
    "matureContent": false
  },
  "dataUsage": {
    "remoteCode": false,
    "collectedDataTypes": ["<ticked categories on the Data usage form, e.g. websiteContent>"],
    "certifiedDisclosures": true
  },
  "lastPublished": { "version": "X.Y.Z", "date": "YYYY-MM-DD" }
}
```

If **Listing file** is MISSING, bootstrap it:
1. Ask the user for the 32-character item ID — it's the trailing segment of the extension's
   Web Store URL (`https://chromewebstore.google.com/detail/<slug>/<ID>`) and of the Developer
   Dashboard edit URL.
2. Ask the user to paste the dashboard's Privacy practices tab content (dashboard → item →
   Privacy practices) and parse out the **Single purpose** text, the **permission
   justifications**, the **remote code** answer, the ticked **data usage** categories, and the
   **privacy policy URL**. Drafting fresh values is fine for a listing that never had them.
3. Set `lastPublished` to the currently live version and its release date.
4. Write the file. None of it is secret — tell the user to commit it with the project.

Otherwise, Read `cws-publish.json` now — later steps use its fields.

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

The dashboard blocks submission when listing info doesn't cover the new package, and the API
cannot fix it — catch the gaps now, before the upload:

1. **Permission diff.** Compare the zip manifest's `permissions` + `host_permissions` (from
   step 5's output; key host permissions as `host:<domain>`) against the keys of
   `permissionJustifications`:
   - **Missing justification** → draft one with the user (grounded in what the code actually
     uses the permission for), add it to the file, and tell the user to paste it into the
     dashboard's Privacy practices tab and **Save draft** there before continuing.
   - **Orphaned justification** (permission no longer in the manifest) → remove it from the file
     and flag it for cleanup in the dashboard.
2. **Single purpose.** Show the stored `singlePurpose` next to the user-visible changes since
   `lastPublished.version` (`git log v<lastPublished>..HEAD --oneline`, `feat:` subjects). Ask
   the user whether the statement still covers everything the extension now does; if not, draft
   an updated text together, save it to the file, and tell the user to paste it into the
   dashboard before continuing.
3. **Store description.** Check `storeListing.description` the same way as the single purpose —
   the two usually share text; when the single purpose changes, the description (and the
   project's README/docs tagline, which it typically mirrors) needs the same update.
4. **Data usage.** If the release introduces remote code or starts collecting/transmitting any
   user-data category (rare), update `dataUsage` and the dashboard form to match.
5. If anything changed in the dashboard, wait for the user to confirm it's saved there. Update
   the file with Edit/Write as agreed — it's the record of what the dashboard should say.

## 7. Upload

1. Present the plan — extension ID (from the listing file), tag, zip filename, version — and ask
   for confirmation.
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
   in the dashboard, mirror it in the listing file, and re-run the publish command.
4. On success, update `lastPublished` in `cws-publish.json` to the submitted version and
   today's date, and remind the user to commit the file.

## 9. Report

Print:
- the dashboard URL: `https://chrome.google.com/webstore/devconsole` (review progress lives there)
- the public listing URL: `https://chromewebstore.google.com/detail/<extension-id>`
- a reminder that review typically takes from a few hours to a few days; the new version goes
  live automatically once approved.

## Out of scope

- Do NOT create a new Web Store listing — the extension must already exist in the dashboard
- Do NOT edit store listing content in the dashboard itself — the listing file mirrors it, but
  every dashboard change is the user's manual step (the API has no endpoint for it)
- Do NOT bump versions, build zips, or create tags/releases — that's the `/release` skill
- Do NOT monitor the review — it can take days; the skill ends at submission
