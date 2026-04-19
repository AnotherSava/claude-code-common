# Chrome Extension Learnings (Manifest V3)

Practical lessons from building a Chrome extension with Vite, TypeScript, a side panel UI, content script injection, and service worker orchestration. Everything here is general-purpose — not specific to any particular domain.

## Manifest V3

**Service worker must declare `"type": "module"`** to use ES module imports:
```json
"background": { "service_worker": "dist/background.js", "type": "module" }
```

**`host_permissions` wildcard `*.domain.com` does not match the bare domain.** You need both patterns:
```json
"host_permissions": ["https://example.com/*", "https://*.example.com/*"]
```

**`icons` vs `action.default_icon`:** Both must be declared separately. `icons` is the store/extensions-page icon; `action.default_icon` is the toolbar button.

**`web_accessible_resources` glob `assets/*` does not match subdirectories.** Use `assets/**/*` or list paths explicitly. Extension pages (side panel, popup, background) can access their own assets via `chrome.runtime.getURL()` without declaring them here — `web_accessible_resources` is only for assets injected into web pages by content scripts.

**`homepage_url`** in the manifest becomes the "Website" link on the Chrome Web Store listing.

**Manifest paths are relative to the manifest file.** Chrome does not allow `..` in manifest paths. If icons or other assets live outside the manifest's directory, copy them into the build output at build time (e.g., a Vite `writeBundle` plugin).

**`minimum_chrome_version`** — bump this when using newer APIs. For example, `chrome.sidePanel.close()` requires Chrome 129+; the side panel API itself was added in Chrome 114.

## Commands and Keyboard Shortcuts

**`_execute_action` ignores the `description` field** — it always shows "Activate the extension" in the Chrome shortcuts page. Use a named command instead for a custom description:
```json
"commands": { "toggle-sidepanel": { "description": "Toggle side panel" } }
```

**`suggested_key` is not active by default.** `chrome.commands.getAll()` returns an empty `shortcut` string until the user explicitly sets a binding on `chrome://extensions/shortcuts`. Show the `suggested_key` value as a hint in your UI; update via `chrome.action.setTitle()` once a shortcut is confirmed.

**No dynamic shortcut registration API exists.** Users must visit `chrome://extensions/shortcuts`. You can open it from extension code via `chrome.tabs.create({ url: "chrome://extensions/shortcuts" })` — this works because `chrome.tabs.create` can open `chrome://` URLs (unlike `window.open` which cannot).

**Don't provide a `suggested_key` unless you're sure it won't conflict.** An unbound-by-default shortcut is safer — users set their own binding. Show the bound shortcut in the toolbar tooltip via `chrome.action.setTitle()`.

## Side Panel

**`sidePanel.open()` requires a user gesture context.** If you `await` anything before calling it, the gesture expires:
```ts
// WRONG — gesture lost after await
chrome.action.onClicked.addListener(async (tab) => {
  const details = await chrome.tabs.get(tab.id!);
  await chrome.sidePanel.open({ tabId: tab.id! }); // throws
});

// RIGHT — open first, then do async work
chrome.action.onClicked.addListener(async (tab) => {
  await chrome.sidePanel.open({ tabId: tab.id! });
  const details = await chrome.tabs.get(tab.id!);
});
```

**`sidePanel.close()` does NOT require a user gesture.** Call it freely from any async context.

**User gesture context does not transfer across `chrome.runtime.sendMessage()`.** A content script cannot ask the background to call `sidePanel.open()` — the gesture is lost at the message boundary. Valid triggers: toolbar icon click, keyboard shortcut, context menu item, button click on an extension page.

**Track side panel open/close state via port connection.** There is no direct API for "is the side panel open?" The side panel calls `chrome.runtime.connect({ name: "sidepanel" })` on load; the background tracks open state in `onConnect` and clears it in `port.onDisconnect`.

**`openPanelOnActionClick: true` suppresses `action.onClicked`.** When set, Chrome auto-opens the panel on icon click and the `onClicked` event never fires. Set it to `false` if you want to control open/close logic yourself (e.g., toggle behavior). When `false`, you must call `sidePanel.open()` synchronously in the `onClicked` handler — see the user gesture rule above.

**Use port messaging (`port.postMessage`) instead of `chrome.runtime.sendMessage` for background→side panel.** `sendMessage` broadcasts to all extension pages and can fail silently if the service worker needs to wake up. Port messaging is direct and reliable since the connection is already established. Route all background→sidepanel communication through the port; use `sendMessage` only for sidepanel→background requests that need `sendResponse`.

**Per-window port tracking for multi-window support.** A single boolean `sidePanelOpen` breaks with multiple Chrome windows. Track port state per-window using a `Map<Port, PortState>` where `PortState` includes `windowId`. The side panel reports its window via `chrome.windows.getCurrent()` after connecting. Use `windowId` to scope broadcasts and tab lookups.

## Service Worker Lifecycle

**The service worker shuts down after ~30 seconds of inactivity.** All module-level `let` variables reset on restart. Treat the service worker as stateless across time. Use `chrome.storage.session` to persist critical state (like pin mode) across SW restarts — it survives restarts but clears on browser close. Requires the `"storage"` permission.

**`setTimeout` works in service workers** as long as it fires within the ~30s lifetime window. A 2-second timeout after the last event is fine. `chrome.alarms` has a minimum of 30 seconds, so it can't replace short timeouts.

**When the SW shuts down, all open ports disconnect.** The `port.onDisconnect` event fires on the connected side (e.g., side panel). Implement a reconnect timer (~1 second) in the side panel's `onDisconnect` handler. Each `chrome.runtime.connect()` call wakes the SW, resetting its idle timer.

**SW restart causes phantom re-renders:** Every ~30s: SW dies → port disconnects → side panel reconnects → `onConnect` pushes cached results → side panel re-renders with identical data. Deduplicate by comparing message content before re-rendering.

**Distinguish SW restart from intentional reopen:** On SW restart, cached results are null (memory wiped). On user navigating to a different page and reopening, cached results may hold stale data. Use different source indicators to control whether to show a loading state.

**Initialization order matters with reconnect:** If `connectToBackground()` runs at module load time before a `let` variable it references is declared, the TDZ error is caught silently and `port.onDisconnect` is never registered, breaking reconnection permanently. Declare variables before any code that references them.

## Content Scripts — MAIN vs ISOLATED World

**`world: "MAIN"` is required to access page JavaScript objects** (game state, event listeners). The ISOLATED world has a separate JS context.

**`world: "ISOLATED"` for DOM-only watchers** that only need MutationObserver + `chrome.runtime.sendMessage()`. Safer because the content script can't be tampered with by page scripts. Note: TypeScript's type definitions may not include `"ISOLATED"` as a valid world value — cast with `as any`.

**Scripts injected via `executeScript({ files: [...] })` must not have `export` statements.** Vite outputs `export {};` by default. Strip it with a custom `generateBundle` plugin:
```ts
function stripExports(): Plugin {
  return {
    name: "strip-exports",
    generateBundle(_, bundle) {
      for (const [name, chunk] of Object.entries(bundle)) {
        if (name === "extract.js" && chunk.type === "chunk") {
          chunk.code = chunk.code.replace(/^export\s*\{[^}]*\}\s*;?\s*$/gm, "").trimEnd() + "\n";
        }
      }
    },
  };
}
```

## Message Passing

**Fire-and-forget messages:** Use `chrome.runtime.sendMessage().catch(() => {})` when sending from background to side panel. If the panel isn't open, `sendMessage` throws — the `.catch` silences it.

**Push-based > request/response** for background → side panel communication. The cache manager pushes results via a callback whenever data is available (after setFilterConfig, label indexed, scope fetched, cache complete, refresh). The service worker relays each push as a single `filterResults` message. The side panel never requests data — it renders whatever arrives. Include a `partial` flag to distinguish intermediate results (initial build, invalidated labels) from final results.

**`onMessage` handler returning `undefined` is fine** for synchronous handlers. The "return true" rule only applies if you call `sendResponse` asynchronously.

## Tab and Window Management

**`currentWindow: true` is ambiguous in a service worker.** In `chrome.tabs.query({ active: true, currentWindow: true })`, "current window" resolves to the last-focused window, not necessarily the window that triggered the event. Always use an explicit `windowId` from the event context (e.g., `tab.windowId`, `activeInfo.windowId`, or sent from the side panel via `chrome.windows.getCurrent()`).

**`chrome.tabs.onActivated` does NOT fire on window switch.** Add `chrome.windows.onFocusChanged` to cover it:
```ts
chrome.windows.onFocusChanged.addListener(async (windowId) => {
  if (windowId === chrome.windows.WINDOW_ID_NONE) return; // Chrome lost focus
  const [tab] = await chrome.tabs.query({ active: true, windowId });
  // handle tab
});
```

**SPA navigation fires `tabs.onUpdated` with a `url` change but no `status`.** A handler that only checks `changeInfo.status === "complete"` silently ignores History API `pushState` navigation:
```ts
const isPageLoad = changeInfo.status === "complete";
const isSpaNav = changeInfo.url !== undefined && changeInfo.status === undefined;
if (!isPageLoad && !isSpaNav) return;
```

**`tabs.onUpdated` fires for all tabs.** Filter by active tab ID to avoid reacting to background tab loads.

## Icon Management

**Chrome does not persist per-tab icon state across tab switches.** When switching tabs, Chrome shows the default icon until you call `setIcon()` again. Re-apply on `onActivated`.

**`chrome.action.setIcon` with `imageData` avoids file I/O** — useful for smooth icon animations. Preload frames at startup using `OffscreenCanvas` + `fetch`. Keys must be size strings: `{ "16": ImageData, "48": ImageData }`.

**Passing `undefined` as `imageData` throws.** Guard against edge cases in animation math (e.g., division by zero producing `NaN` frame index).

## Storage

### Comparison

| Storage | Access | Persistence | Scope | Async | Manifest permission |
|---|---|---|---|---|---|
| `chrome.storage.local` | SW + all extension pages | Survives browser restart, cleared on uninstall | Global | Yes | `"storage"` |
| `chrome.storage.session` | SW + all extension pages | Survives SW restart, cleared on browser close | Global | Yes | `"storage"` |
| `chrome.storage.sync` | SW + all extension pages | Survives uninstall, syncs across devices (falls back to local without sign-in) | Global | Yes | `"storage"` |
| `window.localStorage` | Extension pages only (NOT SW) | Survives browser restart, cleared on uninstall | Global | No (sync) | None |
| IndexedDB | SW + all extension pages | Survives browser restart, cleared on uninstall | Global | Yes | None |
| In-memory (SW) | SW only | Lost on idle shutdown (~30s) | Per-port (via `Map<Port, State>`) | No | None |
| In-memory (extension page) | That page only | Lost on page close (panel close, tab close) | Per-window (each window has its own page instance) | No | None |

### What to store where

**`chrome.storage.local`** — persistent user settings shared between SW and sidepanel. Single source of truth for configuration that both sides need. Examples: display preferences (showStarred, showImportant, concurrency, pinMode, returnToInbox), selected label, scope value, zoom levels, column count.

**`chrome.storage.session`** — transient SW state that must survive SW idle shutdown but not browser restart. Examples: current Gmail account path (so the alarm handler can restart the orchestrator after SW suspension).

**IndexedDB** — large datasets. Examples: label-to-messageId indexes (90K+ entries), fetch state, cache depth. Both SW and extension pages share the same IndexedDB origin.

**In-memory (class fields, module variables)** — derived/computed state that can be rebuilt from persistent storage. Examples: orchestrator loop state, in-flight pagination, scoped ID set caches. Accept that these reset on SW restart — reload from IndexedDB or recompute.

### Pitfalls

**No per-window or per-tab storage exists.** All Chrome storage APIs are global. If two windows need different state (e.g., different active labels), communicate via per-port messages instead of storage. For "remember last state" settings (active label, scope), global storage is acceptable — it remembers the last-used value across all windows.

**`localStorage` is inaccessible from the service worker.** Don't use it for settings the SW needs — use `chrome.storage.local` instead. Prefer `chrome.storage.local` as the single source of truth to avoid dual-write complexity.

**`chrome.storage.local` is async.** Extension pages that need settings at init time must load them before rendering. Use a single `chrome.storage.local.get(keys)` call to batch-load all settings, then initialize the UI.

**`chrome.storage.onChanged` for cross-context reactivity.** When the sidepanel writes a setting, the SW can react immediately via `chrome.storage.onChanged` listener — no port message needed. Filter by `area === "local"` to ignore session/sync changes.

## OAuth2 and Identity

**`chrome.identity.getAuthToken({ interactive: true })` handles the full OAuth flow.** The user gets a consent prompt on first use; subsequent calls return a cached token silently. The `oauth2` section in the manifest declares the client ID and scopes.

**Token refresh on 401:** Call `chrome.identity.removeCachedAuthToken({ token })` then `getAuthToken()` again. Deduplicate parallel refresh attempts with a shared promise to avoid redundant auth prompts.

**`getAuthToken` always uses the Chrome profile's primary Google account.** There is no way to scope it to a specific Gmail `mail/u/N` web session. Multi-account Gmail support would require a fundamentally different auth approach (e.g., cookie-based auth or content script extraction of the logged-in email).

**The OAuth client ID is registered once in Google Cloud Console.** Users installing the extension don't need their own project — the ID is embedded in the manifest. While unpublished, Google shows an "unverified app" warning during auth.

**Chrome extension IDs are stable only when published to the Chrome Web Store.** Unpacked extensions get a new ID on each install. The OAuth client ID registration needs the extension ID — for development, re-register or use a `key` field in the manifest to pin the ID.

**All Gmail OAuth scopes are classified Restricted by Google Cloud Console** — including `gmail.readonly`, `gmail.modify`, and `gmail.metadata`. Google's developer docs at `/identity/protocols/oauth2/scopes` call some of these "sensitive," but the Cloud Console (Google Auth Platform → Data access) groups them under "Your restricted scopes." The Cloud Console classification is what drives verification requirements. Restricted = CASA audit needed.

**Testing mode has a 100-user lifetime cap** for projects using sensitive or restricted scopes. The cap is per-project and cannot be reset. Test users are added individually by email in Google Auth Platform → Audience. Above 100 users, you must submit for verification.

**CASA Tier 2 for Gmail restricted scopes costs $540–$1,800/year** via TAC Security (Google's preferred lab partner). Much cheaper than the often-quoted $15–75k, which is Tier 3 (manual pen test, reserved for complex/backend-heavy apps). Tier 2 is automated DAST scan plus remediation review, turnaround ~1–3 weeks. Client-side-only Chrome extensions typically qualify for Tier 2.

**The "Use secure OAuth flows" warning in Cloud Console is advisory, not blocking.** `chrome.identity.getAuthToken()` with a "Chrome Extension" OAuth client type still works and passes verification. Google nudges toward PKCE + `launchWebAuthFlow` with a "Web application" client, but migrating is optional.

**Scopes must be declared both in `manifest.json` (`oauth2.scopes`) AND in Google Cloud Console (Google Auth Platform → Data access).** The manifest drives the runtime consent prompt; the Cloud Console list is what verification reviewers assess. A mismatch (scope requested but not declared in Cloud Console) can fail verification.

## Vite Build Configuration

**Multi-entry build** with fixed filenames (no hashes — manifest must reference stable paths):
```ts
rollupOptions: {
  input: {
    background: resolve(__dirname, "src/background.ts"),
    extract: resolve(__dirname, "src/extract.ts"),
    sidepanel: resolve(__dirname, "sidepanel.html"),
  },
  output: {
    entryFileNames: "[name].js",
    chunkFileNames: "chunks/[name].js",
    assetFileNames: "assets/[name].[ext]",
  },
}
```

**`base: "./"` is required** for relative asset paths to work in the extension context.

**Vite `root` option controls HTML output nesting.** When the HTML entry point is in a subdirectory (e.g., `packages/site-gmail/sidepanel.html`) but the project root is the monorepo root, Vite preserves the relative path in the output (e.g., `dist/packages/site-gmail/sidepanel.html`). Set `root` to the package directory in the vite config to get flat output (`dist/sidepanel.html`).

**Per-site vite configs for monorepo extensions.** Instead of a single config with env-var switching, give each site its own `vite.config.ts` that imports shared settings from a `vite.config.base.ts`. Build with `vite build --config packages/site-foo/vite.config.ts`. Simpler, no HTML path flattening hacks needed.

**Assets outside `src/` are not automatically included by Vite.** Copy them with a `writeBundle` plugin:
```ts
{
  name: "copy-assets",
  writeBundle() {
    cpSync(resolve(__dirname, "assets/fonts"), resolve(__dirname, "dist/assets/fonts"), { recursive: true });
  },
}
```

**Use WebP for bundled image assets.** PNG card/icon images converted to WebP at quality 85 cut file size by ~40-60% with no visible quality loss at display sizes (20px icons, 375px hover previews). This directly reduces the extension's unpacked size and Chrome Web Store package. Convert during asset pipeline (`Pillow: im.save(path, 'WEBP', quality=85)`), not at build time.

**No HMR without `crxjs/vite-plugin`.** Without it, the dev workflow is: save → build → reload extension on `chrome://extensions`.

**Broken `.bin` shims after ralphex review:** ralphex runs in a Docker container on WSL, so its `npm install` installs Linux-native optional dependencies, overwriting the Windows ones in the shared `node_modules/`. Symptom: `'vite' is not recognized` or `Cannot find module @rollup/rollup-win32-x64-msvc`. Fix: `npm install @rollup/rollup-win32-x64-msvc`, then retry the build.

## CSS in Extension Pages

**`appearance: base-select` for dark-themed dropdowns.** Native `<select>` elements flash white when opening because the OS renders the dropdown. Chrome 134+ supports `appearance: base-select` which makes the dropdown a styleable top-layer element. Apply to both `select` and `::picker(select)`. Tradeoff: the dropdown no longer auto-sizes to the widest option — set an explicit `width`. Use `width: anchor-size(self-inline)` on `::picker(select)` to lock the picker width to the button.

**`color-scheme: dark` meta tag.** Add `<meta name="color-scheme" content="dark">` in the HTML head so the browser uses dark OS styling for form elements from the start.

**DOM mutations during `base-select` picker open cause resize/flicker.** If sibling elements change (e.g., progress spinner updates), the picker may resize. Either defer DOM updates while a select is open (`document.querySelector("select:open")`), or lock the picker width with CSS.

## Chrome Web Store Publishing

**External CDN resources are rejected.** The store blocks extensions that load scripts or fonts from external domains. Bundle everything locally (e.g., `.woff2` fonts via `@font-face`).

**A privacy policy URL is required** before submission, even for hobby extensions. A GitHub Pages page works.

**Store listing descriptions are plain text only** — no HTML, no Markdown, no clickable links.

**`homepage_url` in the manifest** becomes the "Website" link on the store listing. Requires republishing to take effect.

**Store icon sizing:** A full-bleed 128px icon looks cramped after Chrome applies its badge/shadow. Use internal padding (e.g., 96px content in 128px canvas).

**Promo assets:** 440x280 small tile appears in search results. 1400x560 marquee tile is only used if Google features your extension. Neither is required.

**One-time $5 developer fee** and email verification required before publishing.

**Chrome Web Store auto-fills the Summary field from `manifest.json` `description`** (132 char max). Write the description as a user-facing pitch, not a technical blurb — it becomes the store summary shown under the extension name.

**`github.io` is on Google's Public Suffix List**, so it cannot be added as an authorized domain in Google Auth Platform → Branding (error: "must be a top private domain"). Use the specific subdomain (`username.github.io`) verified via Google Search Console. For project-pages sites (`username.github.io/project/`), verification is tricky because Search Console's HTML file or meta tag must be served from the domain root — the project site only owns its subfolder. Solved by creating a user-pages repo (`username.github.io`) that hosts the verification file at root.

**Unlisted visibility** means users with the direct CWS URL can install, but the extension doesn't appear in CWS search or browse. Combined with OAuth testing mode's 100-user cap, this is a reasonable private-beta distribution path without CASA cost — friends/beta testers install via link, authenticate only if allowlisted.

## IndexedDB in Extensions

**Service worker and extension pages share the same IndexedDB.** They're the same origin. Data written by the service worker is readable by the side panel and vice versa.

**Use IndexedDB for large datasets, localStorage for small settings.** IndexedDB handles 90K+ records efficiently; localStorage has a ~5MB limit and blocks the main thread on read/write. Extension pages have `window.localStorage`; the service worker does not.

**Full table scans are slow (~800ms for 90K records).** Avoid cursor-based filtering like `openCursor()` + `includes()` for per-label lookups. Instead, maintain a secondary index in the meta store (e.g., `labelIdx:{id}` → `messageId[]`), turning O(n) scans into O(1) key lookups + O(k) batch fetches.

**Don't overload data fields as state flags.** Using `internalDate === 0` as a "deleted" sentinel causes bugs when the field is also used for date filtering. Add an explicit `status` field (`"pending" | "fetched" | "inaccessible"`) to separate data from state.

**IndexedDB transactions auto-commit on idle.** Concurrent readonly transactions from different async operations work fine. But read-then-write patterns across separate transactions can race — a second writer may overwrite the first's changes if they read the same record before either writes.

## Service Worker as Stateless Coordinator

**The service worker should coordinate, not accumulate state.** It relays messages between the side panel and backend modules (cache, API). Avoid storing derived state in the service worker that could go stale on restart — let the cache layer be the source of truth.

**Suppress redundant events for extension-initiated navigation.** When the extension navigates Gmail via `chrome.tabs.update`, Chrome fires `tabs.onUpdated` with `status: "complete"`. Store the navigation hash (`lastExtensionNavHash`) and skip broadcasting `resultsReady` when the hash matches — the side panel already has the correct state.

**Track extension-initiated navigation with URL hash matching.** Store the decoded hash when navigating, compare with `+` → space normalization (Gmail normalizes spaces to `+` in hash fragments). Use `startsWith` for sub-path matching (pagination, email open from search).

**Distinguish list views from message views in Gmail URLs.** List views: `#inbox`, `#sent`, `#label/Name`, `#search/query`. Message views: hash ends with a 16+ character alphanumeric segment. Use this to decide whether a user navigation should trigger a tab switch.

## Cache Architecture Patterns

**Label-to-messageIds index for fast lookups.** Store `labelIdx:{labelId}` → `messageId[]` in IndexedDB meta. No per-message store needed — co-labels are computed by intersecting label indexes (Set lookups) instead of reading individual messages.

**Always fetch all time per label.** The Gmail `messages.list` API takes roughly the same time per label regardless of date filtering (~100ms per page). Scoped builds save no time but add complexity (gap-fill, expansion tiers). Fetch all-time once, then intersect with scoped ID sets locally for time-based filtering.

**Configurable concurrency for parallel fetching.** Gmail API handles 10 concurrent `messages.list` calls without 429 errors. Higher concurrency (40+) triggers rate limiting. Default to 10; make it user-configurable. With concurrency=10, 143 labels fetch in ~8s instead of ~58s sequential.

**In-memory ID accumulation across pages.** For multi-page label fetches, accumulate message IDs in memory and write to IndexedDB once when the label is complete. Avoids expensive per-page read+merge+write cycles that dominated fetch time.

**Parallel scope segment fetching.** Large scope date ranges (e.g., 5 years) take 20s as a single paginated query. Split into N segments (based on concurrency), each covering a different date range, fetched in parallel. Per-scope accumulators and segment counters track completion. Reduces 20s to ~3s.

**Refresh updates scope sets instead of clearing.** All messages from a refresh are newer than `lastRefreshTimestamp` and fall within every cached scope's time range. Add refreshed IDs to each cached scope set instead of clearing all sets and re-fetching.

**Children-before-parents cache ordering.** Sort labels so sub-labels are fetched before their parents. This ensures inclusive counts are accurate when the parent is first rendered.

**Cache freshness with format verification.** Check both timestamp (10-minute interval) AND presence of expected data (e.g., `labelIdx:INBOX` exists) before skipping a cache rebuild.



## Alarms and Keep-Alive

**`chrome.alarms` keeps the service worker alive.** Create a periodic alarm (e.g., 0.4 minutes) during long-running operations like cache builds. Clear it on completion. The alarm handler can be a no-op — the alarm firing itself prevents the 30-second idle shutdown.

**`alarms` permission is required** in the manifest. Minimum alarm period is 30 seconds for published extensions, but shorter periods work during development.

## Gmail API Patterns

**`messages.list` with `labelIds` takes ~100ms per page regardless of date range.** Adding `q=after:DATE` doesn't speed up the call — the API processes the full label index server-side. This means scoped per-label builds save no time over all-time builds.

**`has:nouserlabels` search operator.** Returns messages with no user-created labels. Useful for a synthetic "No user labels" label. Combine with `after:DATE` for scoped queries.

**`gmail.metadata` scope rejects ALL `q=` parameters at runtime** — despite Google's docs claiming operators like `after:`, `before:`, `label:`, `has:userlabels` are allowed. The API returns `403 PERMISSION_DENIED` with message `"Metadata scope does not support 'q' parameter"`. Only the dedicated parameters work (`labelIds=`, `maxResults=`, `pageToken=`). Any time-scope filtering, synthetic labels, or custom search needs `gmail.readonly`.

**Gmail API rate limit is ~10 concurrent calls.** 10 parallel `messages.list` requests work reliably. 40+ concurrent requests trigger 429 rate limit errors. The limit is per-second throughput, not per-minute — but bursting too many requests at once hits it.

**`maxResults=500` is the practical maximum for `messages.list`.** Higher values are silently capped. Each page returns up to 500 message IDs and a `nextPageToken`.

## Permissions Cheat Sheet

| Permission | Required for |
|---|---|
| `activeTab` | Temporary access to current tab after user gesture |
| `tabs` | `chrome.tabs.get()`, `tabs.query()`, `tab.url` access |
| `scripting` | `chrome.scripting.executeScript()` |
| `sidePanel` | Side panel API |
| `storage` | `chrome.storage.local`, `chrome.storage.sync`, and `chrome.storage.session` (covers all) |
| `identity` | `chrome.identity.getAuthToken()` for OAuth2 |
| `host_permissions` | Persistent `executeScript` on matching tabs without user gesture |
