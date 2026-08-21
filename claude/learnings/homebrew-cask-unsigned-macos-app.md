# Distributing an unsigned / ad-hoc-signed macOS app via Homebrew

Verified against Homebrew 6.0.18 on macOS 26.5.1, August 2026, by shipping a real cask end to end.

## The official homebrew-cask tap is closed to this class of app

Two independent blockers, and money only clears one:

1. **Notability.** A new cask needs at least 30 forks, 30 watchers, *or* 75 stars — tripled to 90/90/225 when the repo owner submits their own app. `self_submission` is derived from the PR author in `GITHUB_EVENT_PATH`, so it only evaluates true inside a GitHub Actions `pull_request` run; a local `brew audit --new` prints the base tier. Repos under 30 days old are ineligible outright.
2. **Gatekeeper.** `brew audit --new --cask` fails with `Signature verification failed: … not signed by a distributor that meets the system Gatekeeper requirements`. Homebrew added a `fails_gatekeeper_check` reason to `deprecate_disable.rb` and is disabling casks that fail it.

Acceptable Casks also forbids requiring a Gatekeeper bypass, which is exactly what an unsigned app's install instructions ask for.

## `--no-quarantine` is gone, not deprecated

Removed from brew on 2026-07-30. `brew install --cask --no-quarantine` is now a hard error, and — worse — `HOMEBREW_CASK_OPTS="--no-quarantine"` is a **silent no-op**: it neither errors nor works. Any guide still recommending either is stale.

Homebrew applies `com.apple.quarantine` unconditionally and marks the download as a web download. There is no `quarantine` cask DSL stanza. So a cask *by itself* buys an unsigned app nothing — the user hits the identical "damaged and can't be opened" wall they'd get from the DMG.

## A third-party tap is the route, with one caveat

- Repo must be named `homebrew-<name>`; casks live under `Casks/` at any depth. The `Casks/<letter>/<token>.rb` nesting is enforced only for Homebrew's own tap.
- Install is a one-liner that auto-taps and auto-trusts that single cask: `brew install --cask <owner>/<tap>/<token>`.
- Notability is **not** tap-scoped — it's `--new`-scoped. `audit_github_repository` has no official-tap guard.
- The signing audit *is* effectively tap-scoped: `cask/audit.rb` has `return if !cask.tap&.official? && !signing?`. But `signing?` defaults to `new_cask`, so `--new` re-enables it anywhere.

**Therefore: never run `brew audit --new` on a personal tap.** And note that `brew test-bot` appends `--new` for newly added casks in any tap, so the CI that `brew tap-new` scaffolds fails out of the box. Write your own CI calling `brew style --cask` and `brew audit --cask --strict --online` explicitly.

## Stripping quarantine, correctly

Use the modern declarative form, not the legacy Ruby flight block (`rubocops/cask/install_steps.rb` carries `# odeprecated: remove the official-tap scope`):

```ruby
postflight_steps do
  run "/usr/bin/xattr", args: ["-dr", "com.apple.quarantine", "{{appdir}}/Some App.app"]
end
```

- `appdir` is in `ABSOLUTE_TEMPLATE_TOKENS`, and step `args` are template-expanded, so `{{appdir}}` resolves.
- `cask/artifact/install_steps.rb` already does `sandbox.allow_write_path cask.config.appdir`, so no `writable_paths` declaration is needed.
- **`-dr`, not `-cr`.** Homebrew writes the attribute onto every file in the bundle, so the strip must recurse; and `-c` clears *all* attributes including `com.apple.provenance`. Verified after install: recursive quarantine count 0, provenance intact.

This is a real Gatekeeper bypass — the cask's `sha256` becomes the only integrity check — so say so in `caveats` rather than doing it silently.

## Ad-hoc signing breaks upgrades in a way the strip can't fix

An ad-hoc bundle's designated requirement is `cdhash H"..."`, which changes every build. Homebrew's upgrade approval inheritance returns `:signer_changed` on every `brew upgrade --cask`, and macOS treats each version as a new app, so TCC and firewall grants reset per release. Only a stable Developer ID identity fixes that.

## zap ordering is by key, not by file position

Homebrew runs zap keys in a fixed order: `launchctl` → `script` → `delete` → `trash`. So a cleanup that must happen before deletions goes in `script:`, regardless of where you write it. This matters when the app installs privileged artifacts whose *recovery paths* are the files being deleted.

## Automation

- `livecheck` with `url :url` + `strategy :github_latest` reads `tag_name` from the API, so odd asset filenames don't matter. It **cannot see draft releases** — key bump automation on `release: published`, never on build completion.
- Fetch the checksum without downloading: `gh api repos/OWNER/REPO/releases/tags/vX.Y.Z --jq '.assets[]|select(.name|endswith(".dmg")).digest'`. The published digest matches the real file.
- Cross-repo `repository_dispatch` needs a PAT or App token — the built-in `GITHUB_TOKEN` cannot reach another repository.
- Commit the bump through the Contents API (`gh api --method PUT .../contents/<path>` with `sha` from `git rev-parse HEAD:<path>`) and it lands GitHub-verified with no signing key in CI.

## Notarization, if you go that way

Tauri already sets `--options runtime` unconditionally, so hardened runtime is typically on even in an ad-hoc build. A local HTTP listener, an accessory/agent activation policy, and WKWebView need no entitlements (`network.server` is App Sandbox, not Hardened Runtime). An ad-hoc-signed app cannot be notarized — a hardcoded `signingIdentity: "-"` must be removed first, or the bundler's identity check hard-fails. The long pole is Apple enrollment, not code.
