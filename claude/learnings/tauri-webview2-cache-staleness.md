# Tauri WebView2 runtime cache staleness (Windows)

After a redeploy or app update, the webview can keep running **old frontend JS even though the freshly built binary embeds the new bundle**. This is a *runtime* WebView2 HTTP-cache problem, distinct from the *build-time* embed staleness in `tauri-frontend-embed-staleness.md` — both can bite the same "edit UI → deploy → still see old UI" loop, and both can be present at once.

## Symptom

- Binary is freshly built and confirmed to contain the new code (e.g. `grep` the new string in the `.exe`, or its mtime is newer than the fix). The deployed `dist/index.html` references the new content-hashed bundle, and that bundle contains the new code — yet the webview runs old code.
- The app still behaves as the old frontend. Backend command handlers that the new frontend would call are **never invoked** (no log line for them).
- Clearing `%LOCALAPPDATA%\<bundle-id>\EBWebView` (the WebView2 user-data folder) and relaunching → fresh JS runs **for that launch**.
- **The staleness recurs on the *next* launch** (reboot, autostart, plain restart) even with no code change. Only the single launch immediately after a cache wipe is fresh; the cache re-poisons itself. This is the key fact that defeats any "clear once / clear on change" strategy — see below.

## Why

- Vite content-hashes asset filenames (`index-ABC123.js`), so the JS/CSS *URLs* change every build and bypass URL caching. **But `index.html` has a fixed URL** (`http://tauri.localhost/index.html` on Windows). WebView2 heuristically caches that response, and the cached `index.html` still references the **previous** bundle hash — so the hash-busting protects everything *except* the one document that points at it.
- The cache lives in the WebView2 user-data folder, which persists across app updates (same bundle identifier → same folder), so a production version update strands users on stale frontend too, not just dev redeploys.

## Diagnosis tell

Instrument `onMount` (or equivalent) so the order of log lines reveals which code is running. The giveaway: a log emitted from a **later** line in the init flow fires, while a log from an **earlier** line is absent. With sequential `await`s that's impossible for the new code — it proves the running JS is an **older** bundle that lacks the earlier log call. (Here: a frontend `usage_limits_updated` listener — registered after `getSetupState()` — logged events, but a debug log placed right after `getSetupState()` never appeared. → stale JS.)

## Approaches that do NOT work

- **`app.security.headers` in `tauri.conf.json`** rejects `Cache-Control`: the `headers` field is a fixed allowlist (CORS `Access-Control-*`, `Cross-Origin-*`, `Permissions-Policy`, `Timing-Allow-Origin`, `X-Content-Type-Options`, custom `Tauri-*`). Setting `Cache-Control` fails schema validation: `… is not valid under any of the schemas listed in the 'anyOf' keyword`.
- **`additionalBrowserArgs: "--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection --disable-http-cache"`** (note: you must repeat wry's default `--disable-features=…` because the arg *replaces* it). It compiles in and is embedded in the binary, but `--disable-http-cache` does **not** evict an already-cached `index.html` — the stale entry is still served. Verified ineffective; not worth the risk of overriding wry defaults.
- **Fingerprint-gated wipe** (clear `EBWebView` only when the build's `FRONTEND_FINGERPRINT` changed). Tempting and cheap, but **wrong**: the staleness recurs *within* a single build — the launch right after the wipe is fresh, but the next reboot/autostart re-poisons the cache with the same build's fingerprint, so the gate sees "unchanged" and never re-clears. The reported symptom (onboarding panel reappears after every Windows restart) is exactly this. A build-identity signal can't gate a within-build problem.

## Fix: wipe `EBWebView` unconditionally on every startup

Because the cache re-poisons itself within a build, the clear cannot be gated on anything build-derived — it must run every launch. The frontend is embedded in the binary (served from memory, no network), so the WebView2 cache buys nothing; deleting it every startup costs only a re-parse of a small bundle. Run it **at the very top of `run()`, before `tauri::Builder`** — config-defined windows begin loading `index.html` during the Builder's app construction, so clearing inside `setup()` is too late.

```rust
/// Windows WebView2 caches the fixed-URL `index.html`; a redeploy/update that
/// only swaps the content-hashed bundle leaves it pointing at the old JS, and
/// the staleness recurs on every launch within a build. The cache buys nothing
/// for a binary-embedded frontend, so wipe it on every startup.
#[cfg(windows)]
fn clear_webview_cache() {
    let Ok(local) = std::env::var("LOCALAPPDATA") else { return };
    // Mirrors `identifier` in tauri.conf.json — Tauri derives EBWebView from it.
    let webview = std::path::Path::new(&local)
        .join("com.example.myapp")
        .join("EBWebView");
    let _ = std::fs::remove_dir_all(webview);
}

#[cfg(not(windows))]
fn clear_webview_cache() {}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    clear_webview_cache(); // before Builder — webviews load index.html immediately
    tauri::Builder::default()
        // …
}
```

Windows-only: the macOS WKWebView custom-scheme asset handler doesn't exhibit this staleness, so the non-Windows arm is a no-op.

**Caveat — locks:** WebView2 spawns `msedgewebview2.exe` children that can outlive the parent and hold locks on `EBWebView`. On a real reboot/cold boot (the case that matters) nothing is running, so `remove_dir_all` succeeds. On a *quick manual* restart, lingering children may make the delete partially fail (ignored — the next clean launch fixes it). Don't try to delete only `Default/Cache`/`Default/Code Cache` unless you've verified that subset evicts the stale `index.html`; the whole-folder delete is the proven operation.

## Verify

The decisive test is a launch that is **not** immediately after a deploy (i.e. a plain restart / simulated reboot), since the fingerprint approach passed the post-deploy test but failed here:
- Deploy with a debug log line in `onMount`, then **kill and relaunch without redeploying** (kill lingering `msedgewebview2` children for your profile first, to mimic a clean boot). The relaunch must emit the debug line — proving every startup loads fresh, not just the post-deploy one.
- Repeat the kill+relaunch once more; each launch's `mount snapshot`/debug log timestamp should advance, confirming it's repeatable.
