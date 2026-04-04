---
name: release
description: Tag a new version, push to trigger CI, monitor the build, and verify the GitHub release
allowed-tools: AskUserQuestion, Bash(git status --porcelain), Bash(git branch --show-current), Bash(git fetch origin *), Bash(git rev-list *), Bash(git describe --tags *), Bash(git log --oneline *), Bash(git tag *), Bash(git push origin *), Bash(gh run list *), Bash(gh run watch *), Bash(gh run view *), Bash(gh release view *), Bash(gh release edit *), Bash(gh repo view *), Bash(sed -n *)
---

# Release

## Context
- Working tree clean?: !`git status --porcelain`
- Current branch: !`git branch --show-current`
- Fetch remote: !`git fetch origin main`
- Unmerged remote commits: !`git rev-list HEAD..origin/main --count`
- Unpushed local commits: !`git rev-list origin/main..HEAD --count`
- Latest tag: !`git describe --tags --abbrev=0`

## 1. Check preconditions

Run **all** of these checks (do not skip any) and **stop with an error** if any fail. Do NOT assume state from earlier in the conversation — always run the commands:

```bash
# Working tree must be clean (no uncommitted changes)
git status --porcelain

# Must be on main branch
git branch --show-current

# Local main must be up to date with remote — no unpushed and no unmerged commits
git fetch origin main
git rev-list HEAD..origin/main --count   # must be 0 (no unmerged remote commits)
git rev-list origin/main..HEAD --count   # must be 0 (no unpushed local commits)
```

## 2. Detect project info

Determine the project name from the `.csproj` in `src/`:

```bash
# Extract AssemblyName from csproj
sed -n 's/.*<AssemblyName>\([^<]*\)<.*/\1/p' src/*.csproj
```

If no AssemblyName, fall back to the csproj filename without extension. Also get the GitHub repo URL:

```bash
gh repo view --json nameWithOwner --jq .nameWithOwner
```

## 3. Determine version

1. Show the latest tag:
   ```bash
   git describe --tags --abbrev=0
   ```
2. List changes since that tag:
   ```bash
   git log --oneline <latest-tag>..HEAD
   ```
   If no tags exist yet, list all commits.
3. Based on the changes, recommend a version bump (patch / minor / major) with reasoning.
4. Ask the user to confirm or override the version number. The tag format is `v{major}.{minor}.{patch}`.

## 4. Compile release notes

Write release notes following this structure:

Start the notes with this SmartScreen warning (verbatim, with project-specific link):

```
> [!NOTE]
> The executable is not code-signed yet, so Windows SmartScreen may show a warning on first run. Click **More info** → **Run anyway** to proceed. See [Code signing policy](https://github.com/{owner}/{repo}#code-signing-policy) in the README.
```

If the README does not have a "Code signing policy" section, omit this note.

### What's new
- Base each bullet on the actual commit message — do NOT rephrase or reinterpret
- Strip the conventional-commit prefix (feat:, fix:, etc.) and capitalize the first letter
- Group closely related commits into a single bullet if appropriate
- Skip internal/chore commits (CI tweaks, refactors with no user-visible effect)

### Downloads

Include this table — leave sizes as placeholders to be filled in step 7:

| File | Size | Requirements |
|---|---|---|
| `{AssemblyName}-{version}-self-contained-win-x64.zip` | _TBD_ | None — single exe, just unzip and run |
| `{AssemblyName}-{version}-framework-dependent-win-x64.zip` | _TBD_ | [.NET Desktop Runtime 10](https://dotnet.microsoft.com/download/dotnet/10.0) |

### Building from source

```
Requires Windows 10+ and .NET 10 SDK.

dotnet build src/
```

**Full Changelog**: `https://github.com/{owner}/{repo}/compare/{prev-tag}...v{version}`

Present the full draft to the user and ask them to confirm or request edits.

## 5. Create and push tag

Only after the user confirms both the version and the release notes:

```bash
git tag v{version}
git push origin v{version}
```

## 6. Monitor CI

The tag push triggers the GitHub Actions `build.yml` workflow. Poll until it completes:

```bash
# Find the run triggered by the tag
gh run list --branch v{version} --limit 1 --json databaseId,status,conclusion

# Watch it (poll every 30 seconds, report status updates to the user)
gh run watch <run-id>
```

If the run fails, show the logs and stop:
```bash
gh run view <run-id> --log-failed
```

## 7. Verify release and update notes

Once CI succeeds:

1. Confirm the release exists and both assets are attached:
   ```bash
   gh release view v{version} --json tagName,assets
   ```

2. Get actual asset sizes from the release:
   ```bash
   gh release view v{version} --json assets --jq '.assets[] | "\(.name) \(.size)"'
   ```

3. Format sizes for humans (bytes → KB or MB as appropriate) and update the Downloads table in the release notes with real sizes.

4. Update the release body with the final notes (with real sizes filled in):
   ```bash
   gh release edit v{version} --notes "..."
   ```

5. Print a link to the release:
   ```bash
   gh release view v{version} --json url --jq .url
   ```
