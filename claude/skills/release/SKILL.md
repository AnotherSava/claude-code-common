---
name: release
description: Tag a new version, push to trigger CI, monitor the build, and verify the GitHub release
allowed-tools: AskUserQuestion, Read, Edit, Bash(git status --porcelain), Bash(git branch --show-current), Bash(git rev-parse *), Bash(git fetch origin *), Bash(git rev-list *), Bash(git describe --tags *), Bash(git log *), Bash(git tag *), Bash(git push origin *), Bash(git add *), Bash(git commit -S -m *), Bash(gh run list *), Bash(gh run watch *), Bash(gh run view *), Bash(gh release view *), Bash(gh release edit *), Bash(gh release create *), Bash(gh repo view *), Bash(node -p *), Bash(sed *), Bash(ls *), Bash(test *), Bash(grep *)
---

# Release

Tag the current `main` commit as `vX.Y.Z` and let the project's CI workflow build the artifact(s) and publish a GitHub Release. Supports multiple project stacks via dispatch — same shape as the global `deploy` skill.

## Context

### Git state (universal)
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Working tree clean?: !`git status --porcelain`
- Current branch: !`git branch --show-current`
- Fetch remote: !`git fetch origin main 2>/dev/null || true`
- Unmerged remote commits: !`git rev-list HEAD..origin/main --count 2>/dev/null || echo 0`
- Unpushed local commits: !`git rev-list origin/main..HEAD --count 2>/dev/null || echo 0`
- Latest tag: !`git describe --tags --abbrev=0 2>/dev/null || echo "(none)"`
- Repo: !`gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || echo unknown`

### Project type probes
- Chrome extension: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && test -f "$R/manifest.json" && test -f "$R/package.json" && grep -q '"manifest_version"' "$R/manifest.json" 2>/dev/null && echo yes || echo no`
- .NET project: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && ls "$R"/src/*.csproj 2>/dev/null | grep -q . && echo yes || echo no`
- Tauri project: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && test -f "$R/src-tauri/tauri.conf.json" && echo yes || echo no`

### Stack-specific data
- Manifest version: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && node -p "require('$R/manifest.json').version" 2>/dev/null || echo n/a`
- Package version: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && node -p "require('$R/package.json').version" 2>/dev/null || echo n/a`
- AssemblyName: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && sed -n 's/.*<AssemblyName>\([^<]*\)<.*/\1/p' "$R"/src/*.csproj 2>/dev/null | head -1 || echo n/a`
- Has signing policy section: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && grep -q "Code signing policy" "$R/README.md" 2>/dev/null && echo yes || echo no`
- Tauri config version: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && node -p "require('$R/src-tauri/tauri.conf.json').version" 2>/dev/null || echo n/a`
- Tauri Cargo version: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && sed -n 's/^version = "\([^"]*\)".*/\1/p' "$R/src-tauri/Cargo.toml" 2>/dev/null | head -1 || echo n/a`

## Working directory

All file paths in this skill body (`manifest.json`, `package.json`, `src-tauri/tauri.conf.json`, `src-tauri/Cargo.toml`, `src-tauri/Cargo.lock`, `README.md`, `src/*.csproj`) are relative to **Repo root** from Context. The cwd may be a subdirectory — prefix every Read/Edit call with the Repo root value, and pass `git add` paths from Repo root so the staging path matches. Bare paths are cwd-relative.

## 1. Detect project type

Pick the matching flow based on the **Context** flags:

- **Chrome extension** is yes → use Chrome-extension flow
- else **.NET project** is yes → use .NET flow
- else **Tauri project** is yes → use Tauri flow
- else → **STOP**. Tell the user:
  > The `release` skill recognizes Chrome extensions (`manifest.json` + `package.json`), .NET (`src/*.csproj`), and Tauri (`src-tauri/tauri.conf.json`) projects. None was found in the current directory. To support a new stack, extend this skill's Context probes and add a stack-specific branch to each step.

If more than one flag is yes (mixed repo), ask the user which stack to release — do not guess.

## 2. Check preconditions

Run **all** of these checks (do not skip any) and **stop with an error** if any fail. Do NOT assume state from earlier in the conversation:

Universal:
- Working tree must be clean (**Working tree clean?** empty)
- Must be on `main` (**Current branch** = `main`)
- Local main must be in sync with remote (**Unmerged remote commits** = 0 AND **Unpushed local commits** = 0)

Stack-specific:
- **Chrome extension**: **Manifest version** must equal **Package version**
- **Tauri**: **Tauri config version** must equal **Tauri Cargo version** (and **Package version**) — the bundle version comes from `tauri.conf.json`, so all version files must agree

## 3. Determine version

1. Read the latest tag (Context) and the current source-of-truth version:
   - **Chrome extension**: source-of-truth = **Manifest version**
   - **.NET**: ask the user — version is injected from the tag into the build (no version file to read), so the tag is the source of truth
   - **Tauri**: source-of-truth = **Tauri config version** (`tauri.conf.json`)
2. List commits since the latest tag: `git log <latest-tag>..HEAD --oneline`. If no prior tag, list all commits.
3. Recommend patch / minor / major based on commit subjects (`feat:` → minor, `fix:`/`chore:`/`refactor:` → patch, breaking change → major).
4. Decision:
   - **Chrome extension**: if **Manifest version** > latest tag's version, the bump is already committed — use it and skip step 4. Else proceed to step 4 with the recommended version (or user override).
   - **.NET**: ask user for new version (default = recommended bump). Skip step 4 — version is tag-injected.
   - **Tauri**: if **Tauri config version** > latest tag's version, the bump is already committed — use it and skip step 4. Else proceed to step 4 with the recommended version (or user override).

Tag format is always `vX.Y.Z`.

## 4. Bump version (Chrome extension and Tauri)

Skip this step for .NET.

For Chrome extension:
- Edit `manifest.json` `"version"` field → new version
- Edit `package.json` `"version"` field → new version
- Stage and commit (GPG-signed): `git add manifest.json package.json && git commit -S -m "chore: bump version to X.Y.Z"`
- Push: `git push origin main`

For Tauri, bump **all four** version references so they stay in sync (the bundle version comes from `tauri.conf.json`; the others must match):
- Edit `src-tauri/tauri.conf.json` `"version"` field → new version
- Edit `package.json` `"version"` field → new version
- Edit `src-tauri/Cargo.toml` `[package]` `version` field → new version
- Edit `src-tauri/Cargo.lock` — the package's own entry (find the `[[package]]` block whose `name` matches the crate, bump its `version`; leave dependency entries untouched)
- Stage and commit (GPG-signed): `git add src-tauri/tauri.conf.json package.json src-tauri/Cargo.toml src-tauri/Cargo.lock && git commit -S -m "chore: bump version to X.Y.Z"`
- Push: `git push origin main`

Use the Edit tool — do not regenerate any file. Read `Cargo.lock` before editing it (Edit requires a prior Read).

## 5. Compile release notes

### What's new (universal)

Build bullets from `git log <prev-tag>..HEAD --oneline` (or all commits if no prior tag):
- Base each bullet on the actual commit message — do NOT rephrase or reinterpret
- Strip the conventional-commit prefix (`feat:`, `fix:`, `refactor:`, etc.) and capitalize the first letter
- Group closely related commits into a single bullet if obvious
- Skip pure-internal commits with no user-visible effect (CI tweaks, doc-only changes, internal refactors)

Group the bullets under emoji-prefixed `###` headings by kind, in this order, omitting any heading with no bullets:
- `### ✨ Features` — `feat:` commits
- `### 🐛 Fixes` — `fix:` commits
- `### ⚠️ Breaking changes` — any breaking change

Normal `feat:`/`fix:`/breaking bullets always go under their heading, even when the release has only one kind (e.g. a features-only release still uses `### ✨ Features`). Bullets that don't fit any of the above (rare) go under the closest-fitting heading — or, only when the entire release consists of such non-fitting items and headings add no clarity, as a plain un-headed list.

Never add a `**Full Changelog**: …/compare/…` line — GitHub auto-renders a compare link on every release page, so it would just duplicate that. This applies to all stacks.

### Stack-specific sections

**Chrome extension:**

Add at the end:

```
Download the zip from this release and upload to the Chrome Web Store Developer Dashboard.
```

**.NET:**

Put the changelog first (the `###` Features/Fixes groups from the generic step above — no `## What's new` parent heading, which GitHub would render with an underline rule). Then append a single combined `> [!NOTE]` callout holding **both** the SmartScreen first-run note and the download guidance — one colored box, not two separate sections. Do NOT list filenames or sizes (GitHub auto-renders the Assets section below); explain only the build *difference* so the reader picks the right asset. For the new release the box is **expanded** (older releases get it collapsed — see step 8). The box is release-independent except `{owner}/{repo}`:

```
### ✨ Features
- …

### 🐛 Fixes
- …

<br>

> [!NOTE]
> The executable is not code-signed yet, so Windows SmartScreen may show a warning on first run. Click **More info** → **Run anyway** to proceed. See [Code signing policy](https://github.com/{owner}/{repo}#code-signing-policy) in the README.
>
> **Which download should I pick?** Both builds are the same app and differ only in whether the .NET runtime is bundled:
> - **Framework-dependent** — only a few hundred KB, but needs the [.NET Desktop Runtime 10](https://dotnet.microsoft.com/download/dotnet/10.0) preinstalled.
> - **Self-contained** — bundles the .NET runtime; larger, but runs anywhere. Pick this if unsure.
```

If **Has signing policy section** is no, drop the SmartScreen sentence and the blank `>` line after it, keeping just the "Which download" box. Do NOT add a "Building from source" section — build instructions belong in the README, not in every release's notes.

**Tauri:**

`release.yml` builds a per-OS matrix via `tauri-action` and creates a **draft** release with the installers attached (Windows NSIS `.exe`, macOS `.dmg`). GitHub auto-renders an Assets section at the bottom of every release with filenames and sizes, so the notes should NOT include a Downloads table — it would just duplicate that.

End the notes with a code-signing NOTE callout: the installers aren't signed, so the user hits a first-launch warning on each platform the release ships. Give the concrete bypass step per OS (drop the line for any OS this release doesn't build), and link to the project's install guide for full steps. Omit the `{install-url}` link only if the project has no install-guide page. Do NOT add a Downloads table.

```
> [!NOTE]
> The installers aren't code-signed. On **Windows**, SmartScreen shows "Windows protected your PC" — click **More info** → **Run anyway**. On **macOS**, first launch is blocked ("damaged"/unidentified developer) — open **System Settings → Privacy & Security** and click **Open Anyway**. Full steps in the [installation guide]({install-url}).
```

Present the full draft to the user and ask them to confirm or request edits. Do not push the tag until approved.

## 6. Create and push tag

Only after the user confirms:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

The tag push triggers the project's CI workflow (`.github/workflows/build.yml` or equivalent), which builds the artifact(s) and creates the GitHub Release.

## 7. Monitor CI

Poll the workflow run until it completes:

```bash
gh run list --branch vX.Y.Z --limit 1 --json databaseId,status,conclusion
gh run watch <run-id>
```

If the run fails, show the failed logs and stop:

```bash
gh run view <run-id> --log-failed
```

## 8. Verify release and finalize notes

Once CI succeeds:

1. Confirm the release exists with the expected assets attached:
   ```bash
   gh release view vX.Y.Z --json tagName,assets
   ```

2. Stack-specific finalization:

   **Chrome extension**: replace the auto-generated notes with the drafted notes — no asset-size filling needed.
   ```bash
   gh release edit vX.Y.Z --notes "..."
   ```

   **.NET**: replace the auto-generated notes with the drafted notes — no asset-size filling needed (the `[!NOTE]` box explains the build difference rather than listing sizes; the Assets section auto-renders exact filenames and sizes).
   ```bash
   gh release edit vX.Y.Z --notes "..."
   ```
   Then **collapse the previous release's note box** so only the latest release shows it expanded. Find the prior tag (`git tag --sort=-v:refname | sed -n '2p'`), fetch its body (`gh release view <prev> --json body --jq .body`), and wrap the `> [!NOTE]` box's inner content in a collapsed `<details>` — turn:
   ```
   > [!NOTE]
   > <inner lines…>
   ```
   into:
   ```
   > [!NOTE]
   > <details>
   > <summary>First-run &amp; download info</summary>
   >
   > <br>
   >
   > <inner lines…>
   > </details>
   ```
   Leave the "What's new" section untouched, then write it back with `gh release edit <prev> --notes "..."`. Skip if the previous release has no `[!NOTE]` box (predates this format) or already collapsed.

   **Tauri**: `tauri-action` creates the release as a **draft** with auto-generated notes. Replace those notes with the drafted "What's new" content from step 5 — the Assets section is auto-rendered, no filename/size filling needed:
   ```bash
   gh release edit vX.Y.Z --notes "..."
   ```
   Then **collapse the previous release's note box** so only the latest release shows the signing warning expanded — the box is byte-for-byte identical on every release, so leaving them all expanded clutters the releases list. Find the prior tag (`git tag --sort=-v:refname | sed -n '2p'`), fetch its body (`gh release view <prev> --json body --jq .body`), and wrap the `> [!NOTE]` box's inner content in a collapsed `<details>` — turn:
   ```
   > [!NOTE]
   > <inner lines…>
   ```
   into:
   ```
   > [!NOTE]
   > <details>
   > <summary>First-run info</summary>
   >
   > <br>
   >
   > <inner lines…>
   > </details>
   ```
   Leave the "What's new" section untouched, then write it back with `gh release edit <prev> --notes "..."`. Skip if the previous release has no `[!NOTE]` box (predates this format) or is already collapsed.
   Then publish the draft (confirm with the user first if they want to review the draft before it goes public):
   ```bash
   gh release edit vX.Y.Z --draft=false --latest
   ```

3. Print the release URL:
   ```bash
   gh release view vX.Y.Z --json url --jq .url
   ```

## Checklist

Before tagging:
- [ ] Working tree clean, on main, in sync
- [ ] Project type detected unambiguously
- [ ] Stack-specific preconditions met (Chrome ext: manifest version == package version; Tauri: all version files in sync)
- [ ] Release notes drafted and reviewed

After tagging:
- [ ] CI workflow green
- [ ] GitHub Release created with expected asset(s) attached
- [ ] Release notes replaced via `gh release edit`
- [ ] (Chrome ext) Zip downloaded and ready for Chrome Web Store upload
- [ ] (.NET / Tauri) Previous release's NOTE box collapsed into `<details>`
- [ ] (Tauri) Draft release published via `gh release edit --draft=false`
