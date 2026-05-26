# Tauri release pipeline on GitHub Actions

Operational notes for shipping a Tauri v2 app via `tauri-apps/tauri-action` + GitHub Releases. Captures behaviors that are not obvious from the action's README and that you only discover when something goes wrong.

## Version is pinned in three places

For a Tauri project with both JS and Rust crates, the version lives in:

- `src-tauri/tauri.conf.json` `"version"` — drives the bundle/asset filenames.
- `src-tauri/Cargo.toml` `[package] version` — drives the Rust binary metadata. If your project uses a Cargo workspace, this may instead be `[workspace.package] version` in the root `Cargo.toml`; check both.
- `package.json` `"version"` — drives npm metadata.

All three must be in sync before tagging. `tauri-action` does not auto-bump them from the tag — if you push `v0.2.0` but `tauri.conf.json` still says `0.1.0`, the artifacts will be named `..._0.1.0_...` and the release will be confusingly mismatched.

After editing `Cargo.toml`, regenerate `Cargo.lock` so the lockfile picks up the new version:

```bash
cargo update -p <crate-name> --manifest-path src-tauri/Cargo.toml
```

Otherwise CI will fail with a lockfile-out-of-date error.

## Bundle target choices

`tauri.conf.json` `bundle.targets` controls which platform packages are produced. Common values:

- `nsis` — Windows NSIS installer (`.exe`). User-facing.
- `msi` — Windows MSI installer. User-facing alternative to NSIS.
- `dmg` — macOS disk image (`.dmg`). User-facing.
- `app` — macOS `.app.tar.gz` archive. **Updater-only** — Tauri's auto-updater consumes this format. If you are not running an updater feed, this artifact is dead weight on the release page; users won't know what to do with it. Drop it from `targets` unless you've wired up the updater plugin.
- `appimage`, `deb`, `rpm` — Linux formats.

A `.dmg` internally wraps a `.app`, so producing only `dmg` (without `app` in targets) still yields a working macOS installer. The `app` target adds a *separate* tarball archive on top.

## Asset filenames have spaces converted to dots

GitHub Releases normalises spaces in attached asset filenames to dots. A `productName` of `Claude Code Dashboard` produces:

- `Claude.Code.Dashboard_0.2.0_x64-setup.exe`
- `Claude.Code.Dashboard_0.2.0_aarch64.dmg`

This matters when writing release notes templates — the download table needs to use the dotted form, not the literal product name with spaces.

## Matrix runners and draft releases

`tauri-action` with `releaseDraft: true` plus a matrix strategy works as expected, but the mechanism is non-obvious:

- The **first** matrix job to reach the action creates the draft release.
- The **second** job finds the existing draft (matched by `tagName`) and *appends* its assets.
- Both jobs must use the same `tagName` expression — typically `${{ github.ref_name }}` for tag pushes.

Because the assemblage happens via the GitHub API, there's no asset-collision concern between platform builds (Windows builds `.exe`, macOS builds `.dmg` — disjoint filenames).

The release stays a **draft** until something explicitly publishes it. To finalise after CI:

```bash
gh release edit v{version} --draft=false
```

## `includeUpdaterJson` semantics

`tauri-action`'s `includeUpdaterJson: true` emits a `latest.json` manifest pointing at the updater-only artifacts (`.app.tar.gz`, `.nsis.zip`, etc.) and their minisign signatures. Setting it to `true` only makes sense when:

1. You have wired up `@tauri-apps/plugin-updater` in the app, and
2. You have configured `plugins.updater.endpoints` to point at this manifest URL.

Otherwise the `latest.json` is published but never consumed. Leave it `false` until the updater is actually in use.

## Tag-triggered workflows re-fire on force-push

The standard release workflow trigger is:

```yaml
on:
  push:
    tags: ['v*']
```

This fires on **any** push of a `v*` tag — including a force-push that rewrites the existing tag SHA. So if you need to rewrite a tag (e.g. to convert a lightweight tag into a signed annotated one), naively force-pushing will trigger a full rebuild + a second tauri-action invocation that will either fail (release already exists) or upload duplicate assets.

To avoid this, disable the workflow temporarily:

```bash
gh workflow disable release.yml
git tag -s -f v{version} -m "v{version}"   # recreate locally as signed
git tag --verify v{version}                # confirm before pushing
git push origin v{version} --force         # force-update remote tag
gh workflow enable release.yml
```

`gh workflow disable` only suppresses *future* triggers; in-flight runs continue. The disable/enable pair is a no-op for the existing release and a clean way to avoid an unwanted rebuild.

## Lightweight vs signed annotated tags

`git tag v{version}` creates a **lightweight** tag — a bare ref pointing at the commit, with no tag object, no message, and no signature. GitHub will not show a "Verified" badge on a lightweight tag, even if the commit it points at is GPG-signed.

For a "Verified" badge on the tag itself, you need a **signed annotated** tag:

```bash
git tag -s v{version} -m "v{version}"
git tag --verify v{version}   # locally verify the signature is good
git push origin v{version}
```

`-s` signs with `user.signingkey`; `-m` is required because annotated tags must have a message.

After pushing, you can confirm GitHub recognises it:

```bash
gh api repos/{owner}/{repo}/git/refs/tags/v{version} --jq '.object.sha' \
  | xargs -I{} gh api repos/{owner}/{repo}/git/tags/{} --jq '.verification'
```

`.verification.verified: true` + `.verification.reason: valid` means the badge will render.

## macOS runner: x86_64 is gone

GitHub retired the `macos-13` standard runner on **December 4, 2025**. It's still available as a paid larger runner, but for free CI (including public repos), there is no x86_64 macOS option as of 2026.

For Intel Mac coverage, build a universal binary on `macos-latest` (Apple Silicon) instead:

```yaml
- run: rustup target add x86_64-apple-darwin
- uses: tauri-apps/tauri-action@v0
  with:
    args: --target universal-apple-darwin
```

This produces a single fat `.dmg` that runs natively on both arches. Costs: macOS build wall-clock roughly doubles (compiles for both targets), DMG file size ~1.5–1.8x.

If you don't expect Intel users (Apple stopped selling Intel Macs in late 2022), skipping universal and shipping `aarch64`-only is a defensible default — add universal later if anyone asks.

## Release page ordering

The GitHub `/releases` page sorts releases by `created_at` descending (the timestamp the release entity was first created, including as a draft), not by `published_at`. This means:

- Late-publishing an old draft does not reorder it to the top — its `created_at` remains the original draft creation time.
- Force-pushing a tag does not reorder the associated release.
- If you do see ordering wrong by `published_at`, you can refresh it with a draft cycle:

```bash
gh release edit v{version} --draft=true
gh release edit v{version} --draft=false --latest=true
```

This advances `published_at` to now without affecting `created_at`. The release page briefly shows the release as drafted between the two commands (~1 second).

## Re-publishing a draft has a quirk in the gh CLI output

When toggling `--draft=true` on an already-published release, `gh release edit` prints a URL of the form `.../releases/tag/untagged-<random>` — the URL a draft uses when it has no tag binding. This is just the draft-mode URL; the release entity still exists and its tag binding returns when you flip `--draft=false`. No clean-up needed.
