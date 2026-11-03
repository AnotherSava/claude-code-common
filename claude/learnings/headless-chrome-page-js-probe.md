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
