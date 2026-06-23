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

Clean up the spawned instance when done (it's a dedicated temp-profile process, safe to kill). On Windows you can't `kill` the `&` job (each Bash call is a fresh shell, so the job isn't tracked), and `taskkill /im chrome.exe` would kill the user's real Chrome — target only the throwaway by its profile:

```powershell
Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Where-Object { $_.CommandLine -like '*<profile-dir>*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

## Driving interactive sites (headed)

For real-world sites (quote tools, forms, anything that may bot-gate), launch **headed**, not headless — the visible window lets the user step in, and some sites behave differently headless:

```powershell
Start-Process "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList '--remote-debugging-port=9222',"--user-data-dir=$env:TEMP\claude-chrome-<task>",'--no-first-run','about:blank'
Start-Sleep 3; (Invoke-WebRequest http://localhost:9222/json/version -UseBasicParsing).Content
```

Gotchas learned driving Craftcloud/Treatstock quote flows:

- **`fill` appends** to an input that already holds a value (it types into the field). Clear first via `evaluate_script` with the native setter, then `fill`:
  ```js
  (el) => { const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; s.call(el, ''); el.dispatchEvent(new Event('input', { bubbles: true })); }
  ```
- **Huge pages**: pass `filePath` to `take_snapshot` and Grep/Read the saved file — inlining a 700-line a11y tree into context per interaction step burns context fast.
- **CAPTCHAs**: don't solve them. The headed window is on the user's desktop — ask the user to click through (AskUserQuestion works well); the session cookie persists for the rest of the flow.
- **`upload_file`** accepts any element that opens a file chooser (an "Upload files" button works), not just a literal `<input type=file>`.
- Snapshot `uid`s go stale after the page re-renders (e.g. a price list recomputing); on "uid no longer exists", re-snapshot rather than retrying.
- **`drag` dispatches native HTML5 drag events** — it won't trigger pointer-sensor libraries (dnd-kit, react-dnd), so the call appears to do nothing. To test those, `evaluate_script` real `PointerEvent`s instead: `pointerdown` on the source → several `pointermove`s crossing the activation distance → `pointerup` over the target. Synthetic events work (libraries don't check `isTrusted`).

## One-off visual check without the MCP

For *visually* eyeballing rendered output — an icon, a component, a layout — at a real pixel size (as opposed to measuring or interacting), skip the MCP and the debug port entirely. Headless Chrome renders a file and saves a screenshot in one shot, which you can then Read:

```bash
"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless=new --disable-gpu --hide-scrollbars \
  --window-size=560,420 --screenshot="$PWD/out.png" "file:///abs/path/page.html"
```

(macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.) The screenshot captures the viewport at `--window-size`. JS in the page runs before capture, so a throwaway HTML can build candidates dynamically.

Useful pattern for icon/SVG design: render several candidate SVGs at multiple sizes (e.g. 11/16/24/48px) on the target background colour, screenshot, Read the PNG, pick/iterate. This is the only reliable way to judge small-icon legibility (an 11px inline SVG) before committing — you can't eyeball raw path data. Generate fiddly path strings with a small Node/Python helper (round coords to 2 decimals). Clean up the temp HTML/PNG afterward.
