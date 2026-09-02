# Shipping a test build from a branch with a tag-triggered release workflow

The common release workflow shape — build on `main`, publish on `v*` tags:

```yaml
on:
  push:
    branches: [main]
    tags: [v*]
  pull_request:
    branches: [main]
```

with every publish/package/release step gated on `if: startsWith(github.ref, 'refs/tags/v')`. Three things about it are worth knowing before you try to get one unreleased build to one person.

## A PR build produces nothing to download

The `pull_request` trigger runs build and test, but the publish/package/`upload-artifact` steps are all tag-gated, so a PR run leaves no artifact. Don't plan on grabbing a zip from a PR unless the workflow deliberately uploads on non-tag runs.

The same gate has a second consequence that is easier to miss: **a change to those steps is unverified until you tag.** Editing the packaging commands or bumping `upload-artifact`/`download-artifact` and pushing to `main` gets a green run that skipped every line you touched, so the change first executes during a real release. Confirm what actually ran before calling it verified — see `github-action-version-bumps.md` for the `skipped`-count query.

## A tag fires the workflow from any branch

`on: push: tags:` does not care which branch the tagged commit is on — the trigger is the ref, not the branch. So tagging a feature branch's tip does run the full release pipeline. That is the easy way to get a real, tested, packaged build out of a branch.

## But the release will claim to be Latest

`gh release create` marks a release as **Latest** unless told otherwise, so a tag off a branch displaces the last stable release on the repo front page and in the "latest release" API. Anyone downloading normally gets your unvalidated branch build.

GitHub excludes prereleases from Latest, so pass `--prerelease`. Making it automatic on any semver prerelease suffix takes one line:

```yaml
        run: >
          gh release create "${{ github.ref_name }}"
          --title "${{ github.ref_name }}"
          --generate-notes
          ${{ contains(github.ref_name, '-') && '--prerelease' || '' }}
          *.zip
```

`v1.6.0-rc1` → `--prerelease`; `v1.6.0` → an empty string (a harmless extra space in the folded command). Verify the folding with `npx js-yaml <file>` — it prints the parsed `run` as a single string, which is the only way to be sure the `>` block and the expression compose the way you expect.

## The workflow that runs is the one at the tagged commit

This is the one that bites. Adding `--prerelease` on `main` does nothing for a tag you push on a branch — Actions checks out the workflow file **as of the tagged ref**. The fix has to be in the branch's own history before the tag points at it. Sequence: commit the workflow change on the branch → push → tag the branch tip → push the tag.

Same trap for any workflow edit meant to affect a tag build: fixing it after tagging requires deleting and re-pushing the tag.
