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

**A `web_accessible_resources` change needs a full extension reload — a service-worker or page reload silently keeps the old manifest.** The manifest is read once when the extension loads, so newly listed assets stay unreachable from host pages until you reload the extension itself at `chrome://extensions`, no matter how many times the page or the worker restarts. The symptom points the wrong way: your injected markup renders with broken-image placeholders, which reads as a bad path, a build that didn't copy the assets, or the host's CSP. Diagnose it in one shot from the host page — load one asset that was *already* listed and one that is newly listed, and compare:

```js
const base = 'chrome-extension://<extension-id>/';
for (const path of ['assets/already-listed.webp', 'assets/newly-listed.png', 'manifest.json']) {
  const img = new Image(); img.src = base + path; document.body.appendChild(img);
}
// then, in a later call: img.complete && img.naturalWidth > 0
```

If the already-listed asset loads and the new one fails exactly like the deliberately-unlisted control (`manifest.json`), it is the stale manifest, not CSP and not the path. For an unpacked extension you can derive the id without the UI — it is the SHA-256 of the extension's absolute directory path, first 32 hex digits mapped `0-f` → `a-p`.

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

**The side panel header (icon + extension name) is rendered by Chrome, not your HTML.** The strip above `sidepanel.html` showing `[icon] Extension Name` is Chrome's own chrome — it reads the text from `manifest.name` and the icon from `manifest.action.default_icon` (with fallback to `manifest.icons`). Updating these in `manifest.json` and reloading the extension updates the header automatically; no JS or HTML change in the side panel is needed. The HTML body renders below this Chrome-owned strip.

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

**Reloading the extension does NOT refresh an already-open side panel.** The open panel keeps running its previously-loaded `sidepanel.js`; a rebuild won't appear until you close and reopen the panel (a fresh page load). When testing UI changes, toggle the panel off/on — don't just hit "Reload" on the extensions page, or you'll keep debugging stale code (a real time-sink — symptoms look like "my fix didn't take").

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

**`chrome.scripting.executeScript({ target, func })` injects a function inline** — no separate content-script file or `web_accessible_resources` entry needed. Useful for one-off UI interactions (e.g. clicking a button on a third-party SPA). Requires the `scripting` permission plus host_permissions for the target URL (or `activeTab`). The injected function runs in the ISOLATED world by default — pass `world: "MAIN"` to access page-script globals. The function's return value is available in `results[0].result`, so you can detect failure (e.g. selector returned nothing) and fall back to a heavier strategy like `chrome.tabs.reload`.

**`executeScript` awaits a returned Promise — in both worlds (and for `files:` injections).** If the injected function (or the completion value of a `files` script) is a Promise, Chrome waits for it and `results[0].result` is the *resolved* value (which must be structured-cloneable). This is how an injected func/file does async work — an in-page `fetch`/XHR, a page `ajaxcall` — and hands the data back synchronously to the caller.

**To read a site's *authenticated* API, inject into the page — don't `fetch` from the service worker.** A `fetch()` from the SW to `https://thesite.com/api/...` is a *cross-site* request from the extension's origin: the site's `SameSite=Lax/Strict` session cookie and any per-request CSRF/security token are not attached, so the site rejects it (often returning a generic error envelope — keys like `status/exception/error/code` — rather than the data). Instead `executeScript` a small probe into the page (`world: "MAIN"`) that calls the page's own API helper (which adds the token) or does a same-origin `fetch`, and return the result. Keep that probe a **separate** `executeScript` call, decoupled from your main extraction, so a failure or hang in it can never break the core extraction.

**The page's globals may live in an *iframe*, not the top frame — inject with `allFrames: true` and pick the right frame.** `tab.url` and a default `executeScript({ target: { tabId } })` only see the **top** frame. A site can serve a shell page (e.g. a "table view" / app wrapper) whose real content — and JS globals — run in a same-origin child iframe at a *different* URL. Then top-frame URL-matching fails (the slug/id you need is in the iframe URL, not `tab.url`) and a top-frame probe finds nothing, so the extension silently shows its empty/help state. This is exactly what broke a working extension when **Board Game Arena moved the game board into an iframe under a `/tableview?table=<id>` shell** (the classic `/<gameId>/<slug>?table=<id>` board became the iframe `src`). Fix: inject with `target: { tabId, allFrames: true }`; `executeScript` then returns one `InjectionResult` per frame. Have the injected probe return that frame's own `location.href` + the state you care about, and select the frame where the global is actually present (e.g. `gameui` defined). Works uniformly for both layouts — legacy top-level pages are just the case where the chosen frame is the top one. Caveats: gate the probe on a cheap top-URL check (a real frame-bearing page) so you don't inject into every tab; the iframe loads *after* the top frame's `onUpdated status:complete` and sub-frame loads don't re-fire `tabs.onUpdated`, so **retry the probe a few times** (or use `chrome.webNavigation.onCompleted`, which fires per-frame) to catch the late iframe; and a declarative `content_scripts` entry with `"all_frames": true` runs *inside* each frame natively, which is why such extensions survive the change while background-orchestrated top-frame injection breaks.

**Detect the page-type by the *resolved frame's* data, not the tab URL, once content can be iframed.** If the shell URL lacks the identifier you'd normally parse (game slug, doc id), don't classify supported/unsupported from `tab.url`. Inject, let the in-frame script report what it found (its own URL, the app's globals), and decide from that. Keep a coarse `tab.url` gate only for "is this worth probing at all" and for synchronous needs like auto-hide.

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

## Background-tab throttling & keeping a live view fresh

**A DOM `MutationObserver` on a host page is not a reliable live-update trigger once the tab can be hidden.** An extension that mirrors a live-updating site (a game log, a chat) by watching the host's DOM and re-extracting on mutation silently goes stale when the tab is backgrounded — for three compounding reasons:
- **The host often stops mutating the DOM while hidden.** Animation-driven UIs (e.g. Board Game Arena's `gameui.notifqueue`, which advances only as each notification's animation completes, and animations are paint-gated) freeze their own rendering in a hidden tab and rapid-replay on return. No mutation → the observer never fires. The data still arrives on the socket; only the *rendering* pauses.
- **`setTimeout`/`setInterval` in the page (and in ISOLATED-world content scripts, which share the page's event loop) are background-throttled**: clamped to ≥1/s when hidden, and to ~1/min after 5 minutes hidden ("intensive throttling"). A debounce timer that gates the notify is delayed accordingly. `requestAnimationFrame` is paused outright while hidden.
- **Throttling keys on visibility, not focus.** A tab that is *visible but unfocused* (second monitor, side-by-side) is treated as foreground and is NOT throttled; only a truly hidden tab (another tab in front, window minimized, or fully occluded — Chrome's native window-occlusion sets `document.hidden` on Windows) is. So "it goes stale when I look away" usually means the window got covered/minimized, not merely lost keyboard focus.

**Catch up with a page-side `visibilitychange` signal, not the worker's focus bookkeeping.** Have the injected watcher also `document.addEventListener("visibilitychange", …)` and, when `document.visibilityState === "visible"`, message the SW to re-extract. Why this beats relying on `chrome.windows.onFocusChanged` / `tabs.onActivated`: (1) it fires straight from the page, so it still works after the SW was **evicted** while the tab was hidden (the page-side watcher survives SW death; the SW's in-memory `liveTabId`/`lastResults` do not); (2) it covers the occluded-window case a window-focus event can miss; (3) it's immune to the SW's own teardown branches (many extensions call a `stopLiveTracking()` when focus moves to a non-target tab, nulling the live-tab id and dropping all further mutation messages via a sender-tab gate — so the fast path is already dead by the time you look back). `visibilitychange` fires on nested iframe documents too, reflecting the top-level tab's visibility, so a watcher injected into an iframed board still gets it. Gate the SW handler on: a consumer exists, no extraction already running, and a minimum interval since the last one (so it isn't doubled when a focus event refreshed at the same moment). Note this is *catch-up-on-return*, not *live-while-hidden*; genuine live-while-hidden needs a `chrome.alarms` poll (≥30s floor) since page timers are throttled and the SW may be evicted.

## Message Passing

**Fire-and-forget messages:** Use `chrome.runtime.sendMessage().catch(() => {})` when sending from background to side panel. If the panel isn't open, `sendMessage` throws — the `.catch` silences it.

**Push-based > request/response** for background → side panel communication. The cache manager pushes results via a callback whenever data is available (after setFilterConfig, label indexed, scope fetched, cache complete, refresh). The service worker relays each push as a single `filterResults` message. The side panel never requests data — it renders whatever arrives. Include a `partial` flag to distinguish intermediate results (initial build, invalidated labels) from final results.

## Presence & Idle Tracking (`chrome.idle`, `chrome.alarms`, window focus)

Building idle-aware play-time tracking (a session = the focused game tab; pause on AFK/sleep) exposed a cluster of MV3 quirks. The symptom that led here: a run of **0-length sessions spaced ~3 minutes apart** in history while the user was away from the keyboard.

**`chrome.idle.onStateChanged` does NOT replay the last transition to a freshly-restarted SW.** When the service worker is torn down and cold-restarts, `onStateChanged` only fires on *future* state changes — it does not re-deliver the already-past `"idle"` transition to the new instance. So any startup-path code that assumes "the user is active" is wrong if they're actually idle. A session started blindly at SW startup never receives an idle event, freezes, and is finalized as a 0-length row on the next restart — looping once per restart. **Fix:** gate startup work on the *live* idle state, not just on "is there a session":
```ts
if (!(await hasActiveSession()) && (await chrome.idle.queryState(IDLE_DETECTION_SECONDS)) === "active") {
  startSession(...);
}
```
Use `chrome.idle.queryState()` to read the current state on demand; use `onStateChanged` only for live transitions while the SW is alive. Detection interval floor is **15 seconds** (`setDetectionInterval`); states are `"active" | "idle" | "locked"` (`"locked"` covers screen-lock/sleep); requires the `"idle"` permission.

**MV3 SWs cold-restart constantly; alarms wake them but delivery is throttled to ~minutes when the SW is dormant** — even if you asked for a 60s period. This is why the phantom 0-length rows were ~3 min apart, not 1 min. Every module-level statement re-runs on each cold start, so "initialize on startup" code fires repeatedly, not once. Design startup code to be idempotent and to re-derive state from `chrome.storage`, never to assume it runs once.
- Heartbeat pattern: run a periodic alarm *only while a session is open* (create on session start, clear on session end) so the SW isn't woken when there's nothing to track. Requires the `"alarms"` permission.
- Belt-and-suspenders: drop nonsensical results at the storage boundary (e.g. discard a session whose `end <= start`) so residual startup/finalize races can't litter persisted data.

**`tab.active` is NOT "the user is looking at this tab".** It only means "selected tab *within its own window*" — it stays `true` when that window is **minimized** or sitting **behind another window/app**. A heartbeat that checks only `tab.active` keeps counting an idle/backgrounded tab as live. For genuine presence, check the focused window:
```ts
const win = await chrome.windows.getLastFocused({ populate: true });
if (win.focused) {                       // a Chrome window currently holds OS focus
  const activeTab = win.tabs?.find((t) => t.active);  // the tab the user actually sees
}
// also require win.state !== "minimized" if you queried a specific window
```

**Focus / idle event coverage — what fires when:**
- **Switch tab** → `chrome.tabs.onActivated`
- **Same-tab navigation / SPA pushState** → `chrome.tabs.onUpdated` (full load: `status` goes `loading`→`complete`; SPA: only `url` changes, no `status` field)
- **Close tab** → `chrome.tabs.onRemoved`
- **Switch Chrome window / minimize / switch to another app** → `chrome.windows.onFocusChanged`; `windowId === chrome.windows.WINDOW_ID_NONE` means *no* Chrome window has focus.
- **AFK with the tab still focused, screen lock, sleep** → *no* tab/window event fires at all; only `chrome.idle` catches these. `chrome.idle` is **system-wide** (any input, any app), so it composes with the focus events: alt-tab to another app and `onFocusChanged` already closed the session; keep Chrome focused but stop typing and `chrome.idle` is the only signal.

**Bounding sessions across crash/quit (no end-write on shutdown).** On a hard quit the SW can die before writing the session end. Persist a `lastSeen` timestamp (refreshed by the heartbeat while active) and an `idleSince` (set when idle begins). On the next startup, run a recovery pass *before* re-establishing the current session: finalize an orphaned session at `idleSince` (if it had gone idle) or at `lastSeen` (crash) instead of stretching it to "now" — otherwise one session balloons to cover the entire time the browser was shut.

**`onMessage` handler returning `undefined` is fine** for synchronous handlers. The "return true" rule only applies if you call `sendResponse` asynchronously.

**A "broadcast once" flag in the background can leave the side panel stuck if the panel ever wipes local state.** If the background sets `labelsPushed = true` (or similar) after pushing data and only resets it on account change or explicit reset, then a side panel that clears its cache for any other reason (e.g., on a transient `notOnGmail` signal) will never receive that data again — background thinks the panel has it, panel thinks background will re-push. Remedies, most to least robust: (1) give the receiver a **pull** path — when it activates without the data, send an explicit `requestX` and have the background answer from its live state; this self-heals regardless of which path wiped the receiver's copy, including reconnects. (2) drop the once-flag (re-push on every relevant event). (3) don't reset receiver state for transient conditions — keep cached data valid until you actually know it's stale (account change, explicit cache reset). Path-by-path patches of (3) tend to recur: a new trigger leaks through the same hole. Prefer (1) when the data has a single activation chokepoint to hook the pull into.

**A pull/deferred reply must wait for data *readiness*, not just *existence*.** When the background answers an on-demand request by resolving a key (e.g. label name → ID) and reading its value (the cached message-ID index), replying the instant the *key* resolves — but before the *value* is populated — produces a false-empty answer ("No emails") that nothing re-triggers, because the receiver treats the reply as final. Gate the reply on the value being final: queue the request and re-evaluate it on each progress event, releasing it only once that specific datum is built (a per-key "ready" predicate) or the whole build completes. Distinguish a *genuinely-absent key* (answer immediately — it'll never exist) from a *not-yet-built value* (keep waiting). The progress callback that already fires per work-unit is the natural place to flush the queue.

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

**SPAs may rewrite the URL hash after you navigate to it.** When you `chrome.tabs.update({ url: "...#all/<id>" })`, the target page may load the resource but immediately rewrite the hash to its own internal identifier. Gmail is a notable case: navigating to `#all/<api-thread-id>` (the ID returned by `users.messages.get`) opens the correct thread, but Gmail rewrites the hash to its own web-internal ID (e.g. `FMfcgz...`) within milliseconds. Consequence: you cannot correlate Gmail's URL hash to the API thread ID — URL-based state tracking fails for individual messages. Workarounds: (a) track "what I asked the page to navigate to" as state and only clear it when the page enters a known list view (write an `isListView(url)` helper); (b) prefer search URLs when available — Gmail preserves `#search/<query>` verbatim, so URL-prefix matching works for those.

**Navigating to the same hash URL is a no-op in Gmail.** `chrome.tabs.update(tabId, { url: sameUrl })` won't make Gmail's SPA re-fetch — the URL didn't change from Chrome's perspective, and Gmail's hashchange listener ignores identical hashes. To force a refresh in place (cheaper than `chrome.tabs.reload`, which is a full frame reload), inject a script that clicks Gmail's own Refresh button via `chrome.scripting.executeScript`. Selector: `[role="button"][aria-label="Refresh"]`. Caveat: `aria-label` is localized — fall back to `chrome.tabs.reload` if the query returns nothing. Distinguish two intents at the message-passing layer: "navigate to filter" (different URL → SPA navigate) vs "refresh current view" (same or different URL → click Refresh).

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

**Chrome extension IDs are deterministic.** For unpacked extensions, Chrome derives the ID from the install path — stable per machine, varies across machines/checkouts. For CWS-published extensions, the ID comes from the public key Chrome registers on first upload. To get a single stable ID across every machine AND match the CWS-published ID, add a top-level `"key"` field to `manifest.json`. The value is the base64 public key from CWS Dashboard → **Build** → **Package** → **View public key**, with the `BEGIN/END PUBLIC KEY` markers and newlines stripped.

**The `"key"` field is safe to commit.** It's a public key — anyone with it can sideload an extension with your ID locally but cannot push CWS updates or impersonate you to the store. Google's own teams commit it (e.g. `google/chrome-ssh-agent`). The corresponding *private* key (`.pem`) is what must stay secret.

**Strip `"key"` from the CWS upload ZIP.** Whether CWS rejects or silently strips is inconsistent across sources — safer to strip in your package script before zipping:
```ts
const packagedManifest = { ...manifest };
delete packagedManifest.key;
zip.file("manifest.json", JSON.stringify(packagedManifest, null, 2) + "\n");
```

**`bad client id` with a matching extension ID = wrong "Item ID" in Cloud Console.** The extension ID Chrome reports in `chrome://extensions` is only half the equation. The OAuth client at https://console.cloud.google.com/auth/clients has an **Item ID** field that must exactly equal your extension ID. If a previous dev environment's ID got pasted there, EVERY install (including CWS end users) fails with `bad client id` regardless of which machine. Diagnose by reading the Item ID in Cloud Console — a string that isn't your CWS extension ID means update it there and wait 5–60 min for propagation.

**A single Chrome Extension OAuth client supports only one Item ID.** Google's docs explicitly say "if your app runs on multiple platforms, you must create a separate client ID for each platform." There's no UI/API affordance for multiple extension IDs per client. The canonical workaround is the `"key"` field above — make every install resolve to the same ID — not registering multiple IDs.

**Runtime detection of dev vs. published install:** `chrome.management.getSelf()` returns `installType: "development" | "normal" | "admin" | "sideload" | "other"`. `"development"` means loaded unpacked; `"normal"` means installed from CWS. **This is the one `chrome.management` method that does NOT require the `"management"` permission** — it can self-introspect freely. Useful for tailoring error messages, hints, or telemetry.

**`chrome://identity-internals` has been removed** in modern Chrome (visible in `chrome://chrome-urls` — gone). The programmatic equivalent still works from the SW devtools console: `chrome.identity.clearAllCachedAuthTokens(() => {})`. To force full re-consent, revoke at https://myaccount.google.com/permissions, then fully quit Chrome (⌘Q on macOS — not just close window) and relaunch.

**Adding or changing a manifest `key` requires a full uninstall + load-unpacked.** `chrome.runtime.reload()` — what Extensions Reloader and the "↻" button on chrome://extensions trigger — re-reads files but does NOT recompute the extension ID from the new key. The extension keeps whatever ID Chrome assigned at first install, so OAuth keeps failing with "bad client id" until you remove the extension entirely and load the dist fresh.

**Adding a new `permissions` entry to the manifest triggers Chrome's "Updated permissions" prompt.** The extension stays installed but is disabled until the user approves the new permissions on the chrome://extensions page. `host_permissions` additions are incremental and don't reset other permissions, but adding API permissions like `scripting`, `notifications`, or `tabs` blocks the extension on next reload pending approval. Bump the manifest `version` so Chrome detects the change, and warn beta users in advance — silent reloads will appear broken until they revisit chrome://extensions.

**`chrome.identity.getAuthToken` caches tokens keyed by scope set.** When you change `oauth2.scopes` in the manifest, Chrome won't return the previously-cached (narrower) token — it'll prompt the user to re-consent for the new scopes. Existing cached tokens for the old scope set become unusable; they're not auto-revoked, but they no longer get returned. If the new scope hasn't been added to Google Cloud Console's authorized scope list, the consent attempt fails with `invalid_scope` and the extension has no usable token at all. Always add the scope to GCP → Auth Platform → Data access *before* shipping the manifest change.

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

**A module dynamically imported by a page entry AND statically imported by the service worker can crash SW registration (Vite 8 / Rolldown).** Symptom: `Service worker registration failed. Status code: 15` + `Uncaught ReferenceError: document is not defined`, even though the SW's own code never touches the DOM. Cause: when a shared module (e.g. `time-tracking.ts`) is `await import()`-ed by the sidepanel page and also statically imported by `background.ts`, Rolldown builds a namespace object for the dynamic import using an `__exportAll` runtime helper — and parks that helper's definition inside the **sidepanel entry chunk**. The shared chunk then does `import { t as __exportAll } from "../sidepanel.js"`, so the SW's static import transitively pulls in `sidepanel.js`, whose top-level modulepreload polyfill / DOM bootstrap references `document`. This is open Rolldown bug [#8809](https://github.com/rolldown/rolldown/issues/8809), and there is **no config option** to control helper placement (`build.modulePreload.polyfill: false` is insufficient — the page entry's own top-level `document.addEventListener` still runs). Fix that preserves the single-pass build: make the page import the shared module **statically** (named imports) instead of `await import()` — a static import needs no namespace object, so no `__exportAll`, so the shared chunk stops referencing the entry. Rolldown then merges the now-identically-shared chunks into one (no size regression). To diagnose: load `dist/background.js` in Node with `chrome` stubbed but `document`/`window` left undefined — it reproduces the exact registration error offline. The robust-but-heavier alternative is building the SW in a separate Vite pass with `inlineDynamicImports: true` so it never shares a chunk with a page entry.

**Vite's `<link rel="modulepreload" crossorigin>` logs a benign "cross-world extension resource mismatch" on a `chrome-extension://` page.** Distinct from the SW-registration crash above — this one breaks nothing, just noise in the console. Vite injects a `modulepreload` link for each shared chunk into an HTML entry (e.g. `sidepanel.html`), with `crossorigin`. On an extension page the actual module fetch is a same-world same-origin extension load, so the `crossorigin` preload never matches it and Chrome discards the preload as unused, logging the mismatch. The chunk still loads via its own static import, so there's no functional loss and a local extension resource gains nothing from a preload hint anyway. Silence it with `build.modulePreload: false` (this is Chrome-only, so the polyfill isn't needed either). Note this is a *different* switch from the crash entry above, where `build.modulePreload.polyfill: false` was insufficient — here the goal is to stop the link being emitted at all, which `modulePreload: false` does.

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

**Same Linux-only deps also block new package installs.** `npm install --no-save <pkg>` fails with `EBADPLATFORM` when `@esbuild/linux-x64` or `@rollup/rollup-linux-x64-musl` is in `package.json` deps but the current platform is win32. Use `--force` to install anyway — npm skips the Linux-only deps and installs your new package fine.

## TypeScript Typings (`chrome-types` vs `@types/chrome`)

**`chrome-types` (community fork) inlines callback parameter shapes as anonymous object literals — it does not export them as named interfaces.** Names you might expect from `@types/chrome` are missing:

- `chrome.tabs.TabChangeInfo` (the `changeInfo` param of `tabs.onUpdated`) — not exported; the type is declared inline in the `onUpdated` event signature.
- Similar pattern for other event-callback shapes.

If you cast a test fixture as `chrome.tabs.TabChangeInfo`, `tsc` errors with `Namespace 'chrome.tabs' has no exported member 'TabChangeInfo'`. Fixes:
- Drop the cast entirely if the receiver is loosely typed (e.g. `Function` in test mocks).
- Otherwise inline the shape: `as { url?: string; status?: string }`.

Use `@types/chrome` instead if you need the full set of named types — but be aware it may lag newer APIs.

## Injecting UI into a Host Page

**`insertCSS` and `executeScript` are independent promises — order them yourself.** Firing both un-awaited lets the injected DOM land before its stylesheet, so the UI renders as unstyled markup until the CSS catches up (and then silently "fixes itself", which makes it look intermittent). Await the CSS, then inject the DOM.

**Cache the injection *promise* per tab, not a boolean.** Marking the tab "styled" when injection *starts* lets a second push overtake the first one's CSS — the race survives a naive `await`:

```ts
let styles = inPageStyles.get(tabId);
if (!styles) {
  styles = chrome.scripting.insertCSS({ target: { tabId, allFrames: true }, css });
  inPageStyles.set(tabId, styles);
}
try { await styles; } catch { inPageStyles.delete(tabId); }  // let the next push retry
await chrome.scripting.executeScript({ ... });
```

**Injected CSS does not survive a document navigation.** A per-tab cache outlives the document, so navigating away and back renders unstyled while the cache claims otherwise. Invalidate on `chrome.tabs.onUpdated` (`changeInfo.status === "loading"`, before any active-tab guard) *as well as* `webNavigation.onCompleted` — a single path misses some ways back into a page.

**`import iconUrl from "./icon.png?inline"` embeds an asset as a data URI** at build time (Vite), letting injected UI use extension artwork with no `web_accessible_resources` entry — and therefore without exposing the extension ID to the host page. Interpolate it into the injected CSS string; a relative `url()` in injected CSS resolves against the *host page* and 404s.

**A host page's CSP can forbid `chrome-extension://` fonts in your injected CSS — `data:` is often the only way in.** `insertCSS` lands your stylesheet in the page, but the *page's* `Content-Security-Policy` still governs what it may fetch. A site whose `font-src` lists its own hosts and `data:` but no extension scheme silently refuses an `@font-face` at a `chrome-extension://` URL, and `web_accessible_resources` does not change that — that manifest field controls *your* exposure, not the host's policy. The failure is quiet and asymmetric: the sheet loads, every colour and position applies, and only the typeface falls back to the system default, which reads as "I styled the font wrong" rather than "the font never loaded". Check the header before theorising: `curl -sI <host> | grep -i content-security-policy`. Fix by inlining the font as a `data:` URI. Read the packaged file at injection time and cache the *promise* per worker lifetime rather than base64-ing it into the bundle — two woff2 files cost ~38KB of base64 against ~2KB of code. Images are usually the opposite case, and worth checking separately rather than assuming the same verdict: a page sending `img-src * data: blob:` loads `chrome-extension://` images fine even though its `font-src` refuses them, so `<img>` and `background-image` assets need only a `web_accessible_resources` entry. Chunk the encoding; a whole font spread into `String.fromCharCode(...bytes)` overflows the call stack:

```ts
let binary = "";
for (let offset = 0; offset < bytes.length; offset += 0x8000) {
  binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
}
return `data:font/woff2;base64,${btoa(binary)}`;
```

**A tie with the host's stylesheet goes to the host — an injected sheet needs to out-*specify*, not merely match.** `insertCSS` lands in the author origin, but ahead of the page's own sheets in document order, so at equal specificity the host wins every property they both set. This is invisible until the host happens to style the same class name you do: BGA's Innovation ships `.card { display: inline-block }` (0,1,0), and a shared card sheet scoped with `:where(.bgaa-cards) .card-base` — `:where()` contributing zero — tied it and lost, so the card's `display: inline-grid` never applied and every card collapsed into a tall stack of its own children. The failure reads as "fonts or positioning look off" rather than as a cascade problem, because the *two*-class rules in the same sheet (`.card.b-gray-base`, at (0,2,0)) did apply: the colours were right, which is exactly what makes the sheet look loaded and the bug look like bad geometry. Two consequences worth keeping: pick scope classes that carry weight rather than `:where()` when the sheet is destined for a host page, and when a sheet is shared between your own extension page and a host page, check the host's CSS for your class names (`.card`, `.title`, `.row` are all likely collisions) before assuming a name is yours. Verify a cascade fix with the host's real stylesheet loaded and ordered *after* yours — a repro built from a hand-written stand-in for the host's CSS will happily pass while the real page fails, and `adoptedStyleSheets` cannot reproduce it at all, since adopted sheets always cascade last.

**Injected CSS loses to the host's *inline* styles — restyle JS-managed boxes with `!important`.** `insertCSS` lands in the author origin, alongside the host's own sheets (see the specificity note above for what happens when the two tie), but it never outranks `element.style`, which JS-driven sites write constantly (sizing a bar on resize, positioning a panel). The tell is an asymmetric failure: most of your rules visibly apply — proving the sheet loaded and the selectors match — while one property refuses to move. That is not a specificity problem you can out-select; it needs `!important`. Guard the whole family at once (`height` *and* `min-height`, `top` *and* `margin`), or the host holds the box open with the one you left unguarded.

**Restyling a host's icons with `transform: scale()` silently destroys any `transform` the host was already using.** `transform` is one property, not a list you contribute to — so a scale rule wipes a host's `rotate()`, and hosts lean on rotation to derive variants from a single sprite (one arrow image serving left/right/up via `rotate(180deg)`/`rotate(90deg)`). The symptom is not a missing icon but a *wrong* one: every variant renders in the sprite's native orientation, which looks like a data bug until you diff the computed `transform`. Grep the host's stylesheet for `rotate(` before scaling anything of theirs. Composing it back is not just appending `rotate()`: if you scale from a corner (`transform-origin: top left`), a square rotated about that corner lands outside it, so a compensating translate is needed — and because a percentage translation resolves against the element's own box, it holds at any scale. Read right to left:

```css
/* origin top-left: rotate, put the box back over the origin, then scale */
transform: scale(0.5) translate(100%, 100%) rotate(180deg);   /* 180° */
transform: scale(0.5) translate(100%, 0)    rotate(90deg);    /*  90° */
/* origin bottom-left */
transform: scale(0.5) translate(100%, -100%) rotate(180deg);
transform: scale(0.5) translate(0, -100%)    rotate(90deg);
```

**Replacing a host icon's `background-image` leaves `background-position` pointing into the sheet it came from.** Hosts draw icon sets from one sprite and pick the variant with a per-colour/per-type offset (`background-position-y: -154.5px`). Override `background-image` and `background-size` and that offset survives, so your replacement is shoved clean out of a 36px box — loaded, correctly sized, hit-testable, and invisible. It looks like the image failed to load, so the instinct is to check the URL, which is fine, and to check `display`/`opacity`/z-order, which are also fine. Diagnose it by reading the *computed* `background-position`, not by staring at pixels. Always restate `background-position: center` (and `background-size`) alongside any `background-image` override of a host's sprite. The failure is per-variant: a slot that happens to sit at offset `0 0` renders correctly, so a handful of working cases is not evidence the rule is right.

Two checks that settle "is it actually painting?" without pixel-peeping:

```js
const r = el.getBoundingClientRect();
document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === el;  // topmost, unoccluded?
const img = new Image();                                                       // does the URL load?
img.onload = () => console.log(img.naturalWidth);
img.src = getComputedStyle(el).backgroundImage.slice(5, -2);
```

When you fix one of these, grep your own stylesheet for every other place you overrode a host background — this exact bug shipped twice in one session because the guard went on one rule and was forgotten on its sibling.

**Shrinking a host's elements strands everything the host sized around them.** Hosts floor containers at their own element's dimensions (`.pile { min-height: 126px }` = exactly one card), and position siblings *after* that container. Shrink the element and the floor does not follow: the container still reserves its old height, and any control that follows it — a splay arrow, a counter, a label — floats far from the thing it describes. The tell is a control that used to sit snug now separated by roughly (old size − new size). Fixing the element alone is never enough; grep the host's stylesheet for `min-height`/`min-width`/fixed `height` on the ancestors and restate each as *your* element's size. Note these live outside the element you restyled, so a custom property scoped to it will not reach them — publish the scale on `:root` and read it with a fallback.

**Never set `display` on a host element the page reveals from JS.** Hosts commonly ship a control as `display: none` in their stylesheet and show it by writing an inline `display`. Your author-origin rule outranks their stylesheet, so a `display: flex` added to centre its contents pins that control *visible on every page* in the states the host meant to hide it. Reach for `line-height`, `vertical-align`, or flex properties on the parent instead — anything but `display`.

**Move the host's nodes, don't clone them.** Rearranging a host page by copying markup breaks as soon as the host updates its own element by id: the copy goes stale while the original updates offscreen. Moving the node keeps every `$("someId").innerHTML = ...` working in its new home. To keep it reversible, leave a hidden placeholder where the node came from — a later injection has no memory of what an earlier one moved, so that placeholder is the only record of where things belong.

**Pulling a host element out of `position: absolute` makes everything inside it count.** Absolutely-positioned host blocks often contain hard-sized boxes (banner and ad slots, avatar panels) that cost nothing while out of flow. Put the block into the flow — say, to stop it overlapping something you moved — and those sizes start dictating layout, including invisible ones. A container measuring far taller than anything you can see is the signature.

**Host pages you cannot run locally are still measurable.** Fetch the host's real stylesheet and a saved DOM dump, load them in headless Chrome alongside your injected CSS, and drive your actual mount function over it — then measure with `getBoundingClientRect()` instead of reading screenshots. Two cautions: ink extents are not box extents (glyphs sit above a box's centre, so text always measures "high" from pixels), and a static dump reproduces nothing the host's JS does at runtime. When the reproduction and the live page disagree, the live page is right — get one `console.table` of the real boxes rather than guessing again.

**macOS elastic overscroll drags a stuck `position: sticky` element even though layout shows nothing wrong.** Chrome visually pulls a `position: sticky` element along during the trackpad rubber-band bounce past a scroll boundary, then springs it back — invisible to JS: `window.scrollY` and `getBoundingClientRect().top` read the correct resting value throughout, because the bounce is a compositor-only transform never surfaced to layout. `position: fixed` is exempted from this drag (Chrome M105+); `position: sticky` is not ([w3c/csswg-drafts#8309](https://github.com/w3c/csswg-drafts/issues/8309)). Fix: `overscroll-behavior-y: none` — but it must be on `<html>`/`:root`, not `<body>`. Chrome had a long-standing bug reading the *viewport's* overscroll-behavior from `<body>` instead of the spec-mandated `document.scrollingElement`; fixed in Chrome 139 (Aug 2025), so `body`-scoped `overscroll-behavior` is now a silent no-op for the viewport in current Chrome.

**Prefer temporary diagnostic `console.log` over asking the user to manually inspect DevTools.** For a bug in injected page code you can't reproduce locally (auth-gated third-party page, physical-hardware effects like trackpad bounce), add tagged `console.log` statements to the injected function, rebuild, and ask the user to reproduce and paste the output — cheaper than describing what to click through in DevTools, and gives exact values instead of a description. Remove the logging once the bug is understood.

**Prototype DOM/CSS changes live in an authenticated browser session before writing them into source.** With a tool that drives the user's actual logged-in browser (Claude in Chrome, or similar), executing a candidate DOM move / CSS rule directly via a JS-eval tool and screenshotting the result is a much faster loop than edit → rebuild → ask the user to reload the extension → ask for a screenshot. Once the live experiment confirms the approach, port the exact same logic into the source file — the live page is throwaway (reload discards it), so there's no cleanup cost to iterating there first.

**Driving the user's browser to debug an extension steals the active tab from the extension.** Automation tooling opens its tab in a new window and focuses that window on every screenshot and script call — so an extension tracking `activeTabId` through `tabs.onActivated`/`windows.onFocusChanged` now points at *your* tab, not the user's. Anything it pushes to "the active tab" lands in the automation tab. The user reports that a setting does nothing, and the code looks correct because it *is* correct. The tell is a feature that works when you inject its CSS by hand but not when toggled through the UI, with the expected state present in the automation tab and absent in theirs. Close the automation tab before asking the user to retest — and treat "only the active tab gets the push" as a design smell in its own right, since a background tab holding the same page is a real case with or without automation. Broadcast to every matching tab instead (`chrome.tabs.query({ url })`), keeping the active tab in the set unconditionally so the page in front still updates if the query fails or the permission is absent.

**A "smallest/largest value seen so far" adaptive baseline can't catch an anomaly present from the very first measurement.** Un-sticking a folded header once it grew past 3× the smallest height ever recorded broke for a host page whose own bulky content (a piece-picker, board art) lives inside what gets folded and is present from the first render — that first tall reading becomes the baseline itself, so `height > height * 3` is never true. The bug isn't in the ratio or the tracking logic; it's structural: any "learn what's normal from what I've seen" heuristic is blind to an anomaly with no prior "normal" sample to compare against. Use a fixed threshold, not a learned one, whenever the anomaly can be present at first measurement rather than only arriving via transient growth.

**Beware injecting into a container your own MutationObserver watches.** Mounting a node inside the observed subtree fires the observer and triggers whatever it drives (re-extraction, refetch) on every page load. Either mount as a sibling, or have the observer ignore records whose added/removed nodes are all yours.

**`chrome-types` declares `func?: () => void`.** The arg-taking form needs a cast: `func: myFn as unknown as () => void` with `args: [...]`.

## CSS in Extension Pages

**`display:none` `<img>` elements are still downloaded — use a CSS `background-image` to defer.** A hover tooltip built as `<div class="tip" style="display:none"><img src="big.webp"></div>` fetches every `<img>` up front, because Chrome downloads `<img>` src regardless of the ancestor's `display:none`. With hundreds of cards each embedding a ~60KB full-res face image in a hidden tooltip, that's ~25MB downloaded on every render, making "load" feel slow even though the tooltips are never opened. Fix: put the image on the tooltip element itself as a `background-image` (`<div class="tip" style="background-image:url(big.webp)"></div>` + `.tip { width; height; background-size: contain }`). Browsers do **not** fetch background images of `display:none` elements, so each face loads only when its tooltip is first shown on hover (then cached). Trade-off: a brief blank on first hover while the ~60KB loads from local disk — far better than 25MB eagerly. Diagnose with a render-side count: `(html.match(/<img /g)||[]).length` and how many reference the heavy asset. (Inline `style="background-image:url(...)"` is fine under the default MV3 extension-page CSP — inline styles are allowed; only `script-src`/`object-src` are locked to `'self'`.)

**`appearance: base-select` for dark-themed dropdowns.** Native `<select>` elements flash white when opening because the OS renders the dropdown. Chrome 134+ supports `appearance: base-select` which makes the dropdown a styleable top-layer element. Apply to both `select` and `::picker(select)`. Tradeoff: the dropdown no longer auto-sizes to the widest option — set an explicit `width`. Use `width: anchor-size(self-inline)` on `::picker(select)` to lock the picker width to the button.

**`color-scheme: dark` meta tag.** Add `<meta name="color-scheme" content="dark">` in the HTML head so the browser uses dark OS styling for form elements from the start.

**DOM mutations during `base-select` picker open cause resize/flicker.** If sibling elements change (e.g., progress spinner updates), the picker may resize. Either defer DOM updates while a select is open (`document.querySelector("select:open")`), or lock the picker width with CSS.

## Chrome Web Store Publishing

**"Impersonation and IP" rejections flag icon AND wordmark as separate violations.** When CWS rejects under this policy (e.g., "Red Nickel"), the rejection notice lists each flagged entity separately — `ICON`, plus any brand wordmark in the metadata (e.g., `GMAIL`). Each is its own violation: adding elements to a trademarked logo (overlay, recolor, partial obscuring) does not remove the trademark from the design, and leading the product name with a brand wordmark ("Gmail Assistant") is flagged regardless of how generic the rest is. Fix both: rebuild the icon with a generic visual vocabulary (a plain envelope is generic; Gmail's M-flap motif is not; Google's saturated Material palette is not), and rename with the brand as a **trailing** compatibility descriptor ("Foo for Gmail", not "Gmail Foo"). Body-text compatibility claims ("uses the Gmail API", "Browse Gmail labels") are explicitly allowed.

**External CDN resources are rejected.** The store blocks extensions that load scripts or fonts from external domains. Bundle everything locally (e.g., `.woff2` fonts via `@font-face`).

**A privacy policy URL is required** before submission, even for hobby extensions. A GitHub Pages page works.

**Store listing descriptions are plain text only** — no HTML, no Markdown, no clickable links.

**`homepage_url` in the manifest** becomes the "Website" link on the store listing. Requires republishing to take effect.

**Store icon sizing:** A full-bleed 128px icon looks cramped after Chrome applies its badge/shadow. Use internal padding (e.g., 96px content in 128px canvas).

**Promo assets:** 440x280 small tile appears in search results. 1400x560 marquee tile is only used if Google features your extension. Neither is required.

**One-time $5 developer fee** and email verification required before publishing.

**Chrome Web Store auto-fills the Summary field from `manifest.json` `description`** (132 char max). Write the description as a user-facing pitch, not a technical blurb — it becomes the store summary shown under the extension name.

**`github.io` is on Google's Public Suffix List**, so it cannot be added as an authorized domain in Google Auth Platform → Branding (error: "must be a top private domain"). For Auth Platform, verify the specific subdomain (`username.github.io`) via Search Console; this typically requires hosting a verification file at the subdomain root, which means a user-pages repo (`username.github.io`).

**Chrome Web Store "Official URL" field requires Search Console verification of that exact URL.** Pasting an unverified URL silently redirects to Search Console's welcome screen instead of saving. For a project-pages URL like `https://username.github.io/project/`, no user-pages repo is needed: add a Search Console **URL prefix** property (not Domain — DNS isn't available on github.io), choose HTML file verification, and commit the file to the GH Pages source folder (e.g. `docs/`). Jekyll passes files without YAML front matter through unchanged, so just-the-docs and default Jekyll sites need no config. Keep the file in the repo — Search Console re-checks periodically.

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

**`format=full` returns the body; `format=metadata` does not.** `messages.get?format=metadata` returns only headers, `snippet`, `internalDate`, `sizeEstimate` — no `payload.body.data`, no part contents. If you need the body text, request `format=full` (≈10× larger response, drop concurrency from ~10 to ~5 to stay under rate limits).

**`payload.body.data` is base64url-encoded.** Convert with `data.replace(/-/g,'+').replace(/_/g,'/')`, pad with `=` to length % 4 == 0, then `atob()` and decode UTF-8 via `TextDecoder`. Traverse `payload.parts[]` recursively to find a text part — multipart/alternative wraps text/plain and text/html children.

**Prefer text/html over text/plain for marketing emails.** Many promo senders (DoorDash, etc.) ship a text/html version with fully-rendered merge variables but a text/plain version with the placeholders never substituted — literal `$+` instead of `$15+`, `$).` instead of `$10).`. Preferring text/plain seems cleaner but loses the actual values. Extract text from HTML via `new DOMParser().parseFromString(html, "text/html")` then `body.textContent` — this also decodes all HTML entities (including `&#36;` → `$`) that hand-rolled regex strippers miss.

**`users.messages.batchModify` for bulk label edits.** One POST to `/messages/batchModify` with `{ ids: [], addLabelIds: [], removeLabelIds: [] }` modifies up to 1000 messages in one call. "Move to Trash" = add the system label `TRASH`; "Untrash" = remove `TRASH` (still recoverable from Gmail UI within 30 days). Archive a user-defined label by removing it. Endpoint returns 204 — no JSON body to parse. Requires `gmail.modify` scope (broader than `gmail.readonly`). Far cheaper than N per-message `users.messages.modify` calls.

**Gmail search uses space for AND, `{}` for OR.** `label:foo label:bar` (space-separated) matches messages with both labels; `{label:foo OR label:bar}` (braces) matches either. Hyphens replace slashes in label names: `label:ads/deal` is written `label:ads-deal` or quoted `label:"ads-deal"`. `formatLabelForQuery(name)` should produce `"label-with-hyphens"` (quoted, lowercased, slash → hyphen).

## Permissions Cheat Sheet

| Permission | Required for |
|---|---|
| `activeTab` | Temporary access to current tab after user gesture |
| `tabs` | `chrome.tabs.get()`, `tabs.query()`, `tab.url` access |
| `scripting` | `chrome.scripting.executeScript()` |
| `sidePanel` | Side panel API |
| `storage` | `chrome.storage.local`, `chrome.storage.sync`, and `chrome.storage.session` (covers all) |
| `identity` | `chrome.identity.getAuthToken()` for OAuth2 |
| `idle` | `chrome.idle.queryState()` / `onStateChanged` / `setDetectionInterval` |
| `alarms` | `chrome.alarms.create()` / `onAlarm` (periodic SW wakeups) |
| `webNavigation` | `chrome.webNavigation.onCompleted` / `onCommitted` / `onHistoryStateUpdated` — per-**frame** navigation events (the only way to react to a sub-frame/iframe finishing load; `tabs.onUpdated` fires for the top frame only). Same "Read your browsing history" warning as `tabs`, so adding it alongside `tabs` is free UX-wise. |
| `host_permissions` | Persistent `executeScript` on matching tabs without user gesture |
