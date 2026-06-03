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

## One-off visual check without the MCP

For *visually* eyeballing rendered output — an icon, a component, a layout — at a real pixel size (as opposed to measuring or interacting), skip the MCP and the debug port entirely. Headless Chrome renders a file and saves a screenshot in one shot, which you can then Read:

```bash
"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless=new --disable-gpu --hide-scrollbars \
  --window-size=560,420 --screenshot="$PWD/out.png" "file:///abs/path/page.html"
```

(macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.) The screenshot captures the viewport at `--window-size`. JS in the page runs before capture, so a throwaway HTML can build candidates dynamically.

Useful pattern for icon/SVG design: render several candidate SVGs at multiple sizes (e.g. 11/16/24/48px) on the target background colour, screenshot, Read the PNG, pick/iterate. This is the only reliable way to judge small-icon legibility (an 11px inline SVG) before committing — you can't eyeball raw path data. Generate fiddly path strings with a small Node/Python helper (round coords to 2 decimals). Clean up the temp HTML/PNG afterward.
