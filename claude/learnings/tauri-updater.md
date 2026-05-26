# Tauri auto-updater

Reference for Tauri v2's built-in auto-update plugin (`@tauri-apps/plugin-updater` + `tauri-plugin-updater` Rust crate).

## What it does

The app periodically calls a check endpoint (a URL you configure). The endpoint returns a JSON manifest describing the latest release: version, per-platform download URL, signature, release notes. If the manifest's version is greater than the running app's version, the app downloads the update package, verifies its minisign signature against an embedded public key, and applies it on next launch (or immediately with `installAndRelaunch()`).

## Required pieces

To turn it on you need all of:

1. **A minisign key pair** generated via `tauri signer generate`. The public key gets embedded in the app (`tauri.conf.json`), the private key gets stored as a CI secret and used to sign every release's update packages.

2. **`tauri.conf.json` updater config**:
   ```json
   "plugins": {
     "updater": {
       "endpoints": [
         "https://github.com/{owner}/{repo}/releases/latest/download/latest.json"
       ],
       "pubkey": "<base64 minisign public key>"
     }
   }
   ```

3. **Per-platform packages with the `app` bundle target** built into the release:
   - macOS: `.app.tar.gz` + `.app.tar.gz.sig`
   - Windows: `.nsis.zip` + `.nsis.zip.sig` (requires `nsis` updater output in addition to the installer)
   - Linux: `.AppImage.tar.gz` + `.AppImage.tar.gz.sig`

4. **A `latest.json` manifest** hosted at the URL referenced in `endpoints`. The easiest way: in your release CI step, set `tauri-action`'s `includeUpdaterJson: true`. The action will compose `latest.json` from the build outputs and attach it to the GitHub Release.

5. **Rust plugin registration** in `src-tauri/src/lib.rs`:
   ```rust
   tauri::Builder::default()
       .plugin(tauri_plugin_updater::Builder::new().build())
       // ...
   ```
   Plus the dependency in `src-tauri/Cargo.toml`.

6. **A JS check call** from the frontend:
   ```ts
   import { check } from '@tauri-apps/plugin-updater'
   const update = await check()
   if (update?.available) {
     await update.downloadAndInstall()
     await relaunch()  // from '@tauri-apps/plugin-process'
   }
   ```
   Typically wired to a "Check for updates" menu item, a startup probe, or both.

## Signing model — distinct from code signing

Tauri's updater signing uses **minisign** (Ed25519). The signing key proves "this update package was created by whoever holds the same key the previous version trusted." It has nothing to do with OS-level code signing:

- The updater signature does **not** satisfy Windows SmartScreen — that needs an Authenticode (EV or OV) certificate.
- It does **not** satisfy macOS Gatekeeper / notarisation — that needs Apple Developer ID signing + a notarisation pass through Apple's service.
- It does **not** appear in the GitHub Releases tag-verification badge — that's GPG-signed git tags.

The three signing mechanisms are independent: an unsigned-by-Apple app can still auto-update via minisign-signed packages; an Authenticode-signed `.exe` still needs minisign for the updater. You can mix and match.

## Hosting on GitHub Releases

The conventional layout:

- Endpoint: `https://github.com/{owner}/{repo}/releases/latest/download/latest.json` — GitHub serves the asset named `latest.json` from whichever release is marked "Latest".
- `tauri-action` with `includeUpdaterJson: true` attaches `latest.json` alongside the build artifacts.
- Each release must be marked latest (or your endpoint URL must point at a specific tag) for the updater to find it.

If you want pre-releases on a separate channel (e.g. beta), host a `latest-beta.json` and switch endpoints at runtime, or use multiple endpoints with priority.

## Operational cost

- **Key safekeeping**: lose the private key and you can never ship another update that existing installs will accept. The fix would require shipping a manually-installed new version with a different embedded pubkey — a hostile experience.
- **Every release must be signed**: a single missed signing step in CI breaks the update chain.
- **Backward compatibility forever**: an older client must be able to consume any future `latest.json` format. Don't break the manifest schema.
- **Trust in the endpoint**: anyone who can write to the manifest URL can ship updates to all your users. GitHub Releases inherits whatever access controls your repo has; if you self-host the manifest, you own that risk.

## When to enable

Good fit:
- Always-running tray/widget apps where users won't notice the install but do notice when they're behind.
- Fast-iteration projects where shipping fixes within hours matters.
- Anything with a non-technical user base who won't re-download manually.

Defer when:
- You have a handful of internal users who will pull new versions themselves.
- The release cadence is low (a few times a year).
- You haven't yet decided on code signing — get those in place first; users hitting a SmartScreen warning on update is worse than hitting one on a fresh install.
- The project is pre-1.0 and the surface keeps changing — you don't want to lock in a manifest schema or key yet.
