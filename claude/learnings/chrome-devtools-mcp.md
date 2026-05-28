# chrome-devtools MCP: connecting & measuring layout

The `mcp__chrome-devtools__*` tools attach to an **existing** Chrome over the DevTools protocol on `localhost:9222`. They do **not** launch Chrome themselves. If no such Chrome is running, every call fails with:

> Could not connect to Chrome. Check if Chrome is running.
> Failed to fetch browser webSocket URL from http://localhost:9222/json/version

## Launch a Chrome the MCP can attach to

Start a headless instance with the debug port and a throwaway profile (a dedicated `--user-data-dir` avoids clashing with the user's normal Chrome session/profile locks):

```bash
# Windows path; on macOS use /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless=new --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  --user-data-dir="$TEMP/chrome-devtools-profile" about:blank &
sleep 3
curl -s http://localhost:9222/json/version   # confirm the WS endpoint is up
```

`--headless=new` is fine for layout measurement. Once it's up, `new_page`, `resize_page`, and `evaluate_script` all work.

## Measure rendered layout

`evaluate_script` runs a function in the page and returns JSON-serializable values. To check a computed width at a known viewport:

```js
() => {
  const el = document.querySelector('.main');
  return {
    viewport: window.innerWidth,
    rootFontPx: parseFloat(getComputedStyle(document.documentElement).fontSize),
    maxWidth: getComputedStyle(el).maxWidth,
    renderedWidth: Math.round(el.getBoundingClientRect().width),
  };
}
```

Set the viewport first with `resize_page` — responsive `max-width` rules only engage above their breakpoint, so measuring at the default headless window size can be misleading.

Clean up the spawned instance when done (it's a dedicated temp-profile process, safe to kill).
