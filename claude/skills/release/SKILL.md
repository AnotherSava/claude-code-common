---
name: release
description: Tag a new version, push to trigger CI, monitor the build, and verify the GitHub release
allowed-tools: AskUserQuestion, Read, Edit, Bash(git status --porcelain), Bash(git branch --show-current), Bash(git fetch origin *), Bash(git rev-list *), Bash(git describe --tags *), Bash(git log *), Bash(git tag *), Bash(git push origin *), Bash(git add *), Bash(git commit -S -m *), Bash(gh run list *), Bash(gh run watch *), Bash(gh run view *), Bash(gh release view *), Bash(gh release edit *), Bash(gh release create *), Bash(gh repo view *), Bash(node -p *), Bash(sed *), Bash(ls *), Bash(test *), Bash(grep *)
---

# Release

Tag the current `main` commit as `vX.Y.Z` and let the project's CI workflow build the artifact(s) and publish a GitHub Release. Supports multiple project stacks via dispatch — same shape as the global `deploy` skill.

## Context

### Git state (universal)
- Working tree clean?: !`git status --porcelain`
- Current branch: !`git branch --show-current`
- Fetch remote: !`git fetch origin main 2>/dev/null || true`
- Unmerged remote commits: !`git rev-list HEAD..origin/main --count 2>/dev/null || echo 0`
- Unpushed local commits: !`git rev-list origin/main..HEAD --count 2>/dev/null || echo 0`
- Latest tag: !`git describe --tags --abbrev=0 2>/dev/null || echo "(none)"`
- Repo: !`gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || echo unknown`

### Project type probes
- Chrome extension: !`test -f manifest.json && test -f package.json && grep -q '"manifest_version"' manifest.json 2>/dev/null && echo yes || echo no`
- .NET project: !`ls src/*.csproj 2>/dev/null | grep -q . && echo yes || echo no`

### Stack-specific data
- Manifest version: !`node -p "require('./manifest.json').version" 2>/dev/null || echo n/a`
- Package version: !`node -p "require('./package.json').version" 2>/dev/null || echo n/a`
- AssemblyName: !`sed -n 's/.*<AssemblyName>\([^<]*\)<.*/\1/p' src/*.csproj 2>/dev/null | head -1 || echo n/a`
- Has signing policy section: !`grep -q "Code signing policy" README.md 2>/dev/null && echo yes || echo no`

## 1. Detect project type

Pick the matching flow based on the **Context** flags:

- **Chrome extension** is yes → use Chrome-extension flow
- else **.NET project** is yes → use .NET flow
- else → **STOP**. Tell the user:
  > The `release` skill recognizes Chrome extensions (`manifest.json` + `package.json`) and .NET (`src/*.csproj`) projects. None was found in the current directory. To support a new stack, extend this skill's Context probes and add a stack-specific branch to each step.

If more than one flag is yes (mixed repo), ask the user which stack to release — do not guess.

## 2. Check preconditions

Run **all** of these checks (do not skip any) and **stop with an error** if any fail. Do NOT assume state from earlier in the conversation:

Universal:
- Working tree must be clean (**Working tree clean?** empty)
- Must be on `main` (**Current branch** = `main`)
- Local main must be in sync with remote (**Unmerged remote commits** = 0 AND **Unpushed local commits** = 0)

Stack-specific:
- **Chrome extension**: **Manifest version** must equal **Package version**

## 3. Determine version

1. Read the latest tag (Context) and the current source-of-truth version:
   - **Chrome extension**: source-of-truth = **Manifest version**
   - **.NET**: ask the user — version is injected from the tag into the build (no version file to read), so the tag is the source of truth
2. List commits since the latest tag: `git log <latest-tag>..HEAD --oneline`. If no prior tag, list all commits.
3. Recommend patch / minor / major based on commit subjects (`feat:` → minor, `fix:`/`chore:`/`refactor:` → patch, breaking change → major).
4. Decision:
   - **Chrome extension**: if **Manifest version** > latest tag's version, the bump is already committed — use it and skip step 4. Else proceed to step 4 with the recommended version (or user override).
   - **.NET**: ask user for new version (default = recommended bump). Skip step 4 — version is tag-injected.

Tag format is always `vX.Y.Z`.

## 4. Bump version (Chrome extension only)

Skip this step for .NET.

For Chrome extension:
- Edit `manifest.json` `"version"` field → new version
- Edit `package.json` `"version"` field → new version
- Stage and commit (GPG-signed): `git add manifest.json package.json && git commit -S -m "chore: bump version to X.Y.Z"`
- Push: `git push origin main`

Use the Edit tool — do not regenerate either file.

## 5. Compile release notes

### What's new (universal)

Build bullets from `git log <prev-tag>..HEAD --oneline` (or all commits if no prior tag):
- Base each bullet on the actual commit message — do NOT rephrase or reinterpret
- Strip the conventional-commit prefix (`feat:`, `fix:`, `refactor:`, etc.) and capitalize the first letter
- Group closely related commits into a single bullet if obvious
- Skip pure-internal commits with no user-visible effect (CI tweaks, doc-only changes, internal refactors)

### Stack-specific sections

**Chrome extension:**

Add at the end:

```
Download the zip from this release and upload to the Chrome Web Store Developer Dashboard.
```

Followed by:

```
**Full Changelog**: https://github.com/{owner}/{repo}/compare/{prev-tag}...vX.Y.Z
```

**.NET:**

If **Has signing policy section** is yes, start the notes with this SmartScreen warning verbatim (substitute `{owner}/{repo}`):

```
> [!NOTE]
> The executable is not code-signed yet, so Windows SmartScreen may show a warning on first run. Click **More info** → **Run anyway** to proceed. See [Code signing policy](https://github.com/{owner}/{repo}#code-signing-policy) in the README.
```

After the "What's new" section, include a Downloads table (leave sizes as placeholders to be filled in step 8) and a Building from source section:

```
### Downloads

| File | Size | Requirements |
|---|---|---|
| `{AssemblyName}-{version}-self-contained-win-x64.zip` | _TBD_ | None — single exe, just unzip and run |
| `{AssemblyName}-{version}-framework-dependent-win-x64.zip` | _TBD_ | [.NET Desktop Runtime 10](https://dotnet.microsoft.com/download/dotnet/10.0) |

### Building from source

Requires Windows 10+ and .NET 10 SDK.

dotnet build src/

**Full Changelog**: https://github.com/{owner}/{repo}/compare/{prev-tag}...vX.Y.Z
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

   **.NET**: get actual asset sizes and fill them into the Downloads table:
   ```bash
   gh release view vX.Y.Z --json assets --jq '.assets[] | "\(.name) \(.size)"'
   ```
   Format sizes for humans (bytes → KB or MB as appropriate), substitute into the Downloads table, then update the release body:
   ```bash
   gh release edit vX.Y.Z --notes "..."
   ```

3. Print the release URL:
   ```bash
   gh release view vX.Y.Z --json url --jq .url
   ```

## Checklist

Before tagging:
- [ ] Working tree clean, on main, in sync
- [ ] Project type detected unambiguously
- [ ] Stack-specific preconditions met (Chrome ext: manifest version == package version)
- [ ] Release notes drafted and reviewed

After tagging:
- [ ] CI workflow green
- [ ] GitHub Release created with expected asset(s) attached
- [ ] Release notes replaced via `gh release edit`
- [ ] (Chrome ext) Zip downloaded and ready for Chrome Web Store upload
