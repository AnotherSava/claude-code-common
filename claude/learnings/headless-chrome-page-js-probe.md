# Testing a static page's script with headless Chrome and no driver

When a generated HTML page carries behaviour (a form, a picker, a Copy answer button) and nothing on the machine
drives a browser (no Playwright, no Puppeteer), the installed Chrome can still run the page's script and report what
it did. `--dump-dom` prints the DOM after the script has run, so the probe writes its result into the DOM.

## The recipe

1. Copy the rendered page and insert a probe `<script>` just before `</body>`, so it runs after the page's own
   script has wired its handlers.
2. In the probe, drive the page with real events: set a value and `dispatchEvent(new Event('input'))`, set a radio's
   `checked` and dispatch `change` with `{bubbles: true}` (a listener on the row or table only sees bubbling
   events), and call `.click()` on buttons.
3. Stub what headless cannot do. `navigator.clipboard` is replaced with
   `Object.defineProperty(navigator, 'clipboard', {value: {writeText: (v) => { copied = v; return Promise.resolve(); }}})`.
   Plain assignment does not work, since the property is a getter.
4. Write the result into an attribute after a short `setTimeout`, so promise callbacks have run:
   `document.body.setAttribute('data-result', JSON.stringify({...}))`.
5. Run and grep:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu \
  --user-data-dir="$PWD/tmp/probe-profile" --virtual-time-budget=2000 \
  --dump-dom "file://$PWD/tmp/page-probe.html" 2>/dev/null \
  | grep -o 'data-result="[^"]*"' | sed 's/&quot;/"/g'
```

`--virtual-time-budget` lets timers fire before the dump. The attribute comes back HTML-escaped, so `&quot;` has to
be turned back into quotes before the JSON parses. A dedicated `--user-data-dir` keeps the run off the user's
profile; the process exits on its own after the dump, so check with `pgrep -f <that dir>` that nothing is left and
then delete the directory.

## What it cannot do

It reads the DOM only. A URL changed with `history.pushState`, or anything that arrives after the time budget, is
invisible to it (`google-maps-link-coordinates.md` has a case). For that, use CDP through `puppeteer-core` against
the installed Chrome.

## What CDP adds: real keys, a drop, and a clipboard of its own

Driven through `puppeteer-core`, the installed Chrome takes trusted input, which a probe script's own events are
not. Measured 2026-11-14 with Chrome 157 on Windows and puppeteer-core 25, launched headless with a profile
directory of its own, on a page served from loopback with focus emulation switched on
(`Emulation.setFocusEmulationEnabled`); neither condition was tried without.

- **Keys:** pressing Enter in a text field with `page.keyboard.press` submitted the form around it, and Tab moved
  focus to the next control.
- **Replacing a field's text:** `page.click(selector, { clickCount: 3 })` did not select the whole value of an
  input styled `field-sizing: content` (measured 2026-11-20, same setup), so the text typed next went in at the
  caret and left the old value around it, which then saved. Click the field, then press Ctrl+A
  (`keyboard.down('Control')`, `press('a')`, `up('Control')`) before typing; that replaced it every time.
- **A drop:** three `Input.dispatchDragEvent` calls (`dragEnter`, `dragOver`, `drop`) at the field's coordinates,
  each carrying a `text/plain` item in `data.items`, put the text into an input.
- **The clipboard:** headless Chrome keeps one of its own. Once `browserContext.overridePermissions` had granted
  the clipboard permissions, `navigator.clipboard.readText()` gave an empty string while the system clipboard
  held text. After a `writeText()`, Ctrl+V key presses pasted that text into a field, and the system clipboard's
  sequence number (`GetClipboardSequenceNumber`) had not moved. A paste can be tested without touching what the
  user has copied.
- **Accessibility:** a node's entry from `Accessibility.getPartialAXTree` says whether it is ignored and why. The
  call takes an object id from the CDP session it is sent on: an id taken from the page's element handle was
  refused by a session made with `createCDPSession()`, and resolving the node with `Runtime.evaluate` on that
  session worked.
