---
name: Native OS dialogs render plain text — no clickable links
description: tauri-plugin-dialog and equivalent native message dialogs don't support inline links; use a custom Tauri webview window when the dialog body needs an a href
type: feedback
---

Native OS message dialogs render their body as plain text on every platform — Windows `MessageBox`, macOS `NSAlert`, the Tauri `tauri-plugin-dialog` plugin that wraps them. A URL pasted into the body is literal text, not a hyperlink. Right-click-to-open-link or similar OS affordances are inconsistent and shouldn't be relied on.

**Why:** I tried adding a Documentation URL to an About dialog via `tauri-plugin-dialog`'s `message().show()`. User asked for the URL to be clickable. The only workarounds inside the dialog plugin were either (a) an "Open docs" button via `OkCancelCustom("Open docs", "Close")` or (b) accepting the URL as static text. Neither is a real link.

**How to apply:** When the dialog body needs clickable content (link, copyable address, multi-element formatting), skip the dialog plugin and build a small Tauri webview window:

```json
// tauri.conf.json windows entry
{
  "label": "about",
  "title": "About",
  "decorations": true,
  "resizable": false,
  "minimizable": false,
  "maximizable": false,
  "center": true,
  "skipTaskbar": true,
  "visible": false,
  "alwaysOnTop": true,
  "theme": "Dark",        // Windows DWM immersive dark mode + macOS hint
  "parent": "main"        // owned-window relationship for modal-feel
}
```

Plus a one-screen Svelte component as the window's content, an `open_about` Tauri command that shows the window, and a window label entry in `capabilities/default.json`. The link is a real `<a>` whose click handler invokes `open::that(url)` from Rust so it lands in the default browser, not the webview.

Tauri 2's config-level `parent` gives an *owned* window, not a strict modal — parent input isn't blocked while child is open. If true modal blocking is required (rare for About-style dialogs), that needs OS-specific programmatic input disabling.
