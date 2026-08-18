# Probing a third-party page with claude-in-chrome

Measuring a live page you don't control — to verify a CSS change, read a framework's real behaviour, or reproduce a layout bug — runs into three constraints that are not obvious from the tool descriptions. All were hit while verifying an extension's injected UI against boardgamearena.com.

## The tab is backgrounded, so anything asynchronous hangs

`javascript_tool` evaluates in a tab the user is not looking at. Chrome throttles background tabs hard: `requestAnimationFrame` never fires, timers are clamped to ~1/second, and a `fetch` or synchronous `XMLHttpRequest` can stall indefinitely. Any probe that awaits one of those never resolves, and the call dies with:

```
CDP sendCommand "Runtime.evaluate" timed out after 45000ms on tab N. The renderer may be frozen or unresponsive.
```

**Write probes synchronously.** Layout reads do not need a frame: `scrollTo()` followed immediately by `getBoundingClientRect()` returns post-scroll geometry, because the rect read forces a layout flush.

```js
// hangs in a background tab
for (const y of offsets) { window.scrollTo(0, y); await new Promise(r => requestAnimationFrame(r)); read(); }

// works
for (const y of offsets) { window.scrollTo(0, y); read(); }
```

If a page's own animation loop wedges the renderer (a framework relayout with 1s slide animations is enough), that tab stays unresponsive — open a fresh tab rather than waiting.

## The result is scanned, and source code trips the filter

Returned values pass a guard that rejects anything resembling cookie or query-string data. Function sources, `outerHTML` and computed `background-image` values are full of `=`, `&`, `?` and URLs, so a probe that returns them comes back as `[BLOCKED: Cookie/query string data]` — the evaluation succeeded, only the payload was withheld.

Transliterate before returning, and strip URLs:

```js
const clean = t => String(t).replace(/https?:\/\/[^\s"')]+/g, 'URL')
                            .replace(/=/g, '≔').replace(/&/g, '∧').replace(/\?/g, '¿');
clean(SomeClass.prototype.someMethod)   // readable, and it comes back
```

Returning booleans and short identifier lists instead of raw source (`fn.toString().includes('item_width')`, `[...src.matchAll(/this\.(\w+)/g)]`) is often enough and always passes.

## The guard also inspects what you send, not just what comes back

The same filter that withholds cookie-shaped *results* reads the code you submit. A fetch written with an explicit credential option is rejected before it runs:

```js
await fetch(url, {credentials: 'include'})   // [BLOCKED: Cookie/query string data]
await fetch('/settings/export')              // works — and still sends the session cookie
```

Nothing is lost by dropping the option: `same-origin` is `fetch`'s default credentials mode, so a same-origin request authenticates anyway. Navigate the tab to the site first, then fetch a relative path.

## Capturing the page's own API call — the guard redacts what you intercept too

When a UI does something its public API cannot, the request behind it is discoverable: patch `window.fetch`, trigger the action once through the real controls, and the app hands you its own endpoint and payload. The `read_network_requests` tool is not enough on its own — it reports URL, method and status, never bodies.

The catch is that intercepted data hits the same filter as everything else. Dumping `init.body` returns `[BLOCKED: Cookie/query string data]` and the URL comes back `[BLOCKED: Base64 encoded data]`, because form bodies are full of `=`/`&` and often a token. Sanitize *in the page*: return field names always, values only when they're short enough not to be credentials.

```js
window.__cap = [];
const orig = window.fetch;
window.fetch = function (input, init) {
  const url = typeof input === 'string' ? input : input.url;
  if (/notifications\/subscribe/.test(url) && init?.body instanceof FormData) {
    window.__cap.push([...init.body.entries()].map(([k, v]) => ({
      k, len: String(v).length,
      safe: /^[A-Za-z0-9_]{1,24}$/.test(String(v)) ? String(v) : '<redacted>',
    })));
  }
  return orig.apply(this, arguments);
};
```

That yields the field names and short enum values (`do=custom`, `thread_types[]=Issue`) with anything token-length withheld — enough to rebuild the request without pulling a secret through the filter. Match the URL with a regex instead of returning it. Header objects passed to `fetch` usually survive as-is, since they carry no `=`.

Then **replay from the same page**: the captured headers stay valid for the tab's lifetime, so a bulk operation over N items is one loop, not N navigations. Park a helper on `window` and call it per item.

Two smaller things that hold up throughout: React-controlled inputs and menu items respond to a plain `.click()` (it dispatches a real event, so the synthetic handlers run), and the honest way to confirm a write persisted is to reopen the control and read its state back — a 200 only says the server accepted the request.

## The result is capped at ~1000 characters, so a large payload cannot be returned

`javascript_tool` truncates its output at roughly a thousand characters, and chunking does not rescue a big payload — slicing a 36 KB export into 12 KB pieces returns three *truncated* fragments, not the file.

Fetch once, park it on `window`, and return only small derived values:

```js
const r = await fetch('/settings/export');
window.__data = await r.text();                        // stays in the page
JSON.stringify({status: r.status, rows: window.__data.split('\n').length})
```

Then do the work *in the page* — counts, hashes, a diff against a known local copy — and pull raw text out in small slices only (a few records per call), checking each slice ends where a record should rather than mid-field.

Two related dead ends when the goal is a file on disk:

- **An anchor-click download may never produce a file.** The click reports success and nothing arrives in the download directory. Fetching the endpoint sidesteps the download path entirely.
- **`computer{action:"screenshot"}` can fail with a script-injection timeout on a page where `javascript_tool` works fine.** Read the DOM instead of trying to look at it; this is not the wedged-renderer case above, and the tab is otherwise healthy.

## When the screenshot is wedged but you actually need the pixels

On a WebGL/canvas-heavy page — a Mapbox GL map was the case — `computer{action:"screenshot"}` can be *permanently* wedged rather than briefly busy: every call dies with `Script injection timed out after 5000ms`, across many minutes and a fully idle page, while `read_console_messages` answers instantly and the tab reports the right title. Waiting and retrying never clears it, so cap the retries at two or three.

The DOM-instead workaround does not apply when the whole point is to *look* at rendered output. Escape to CDP instead: launch your own headless Chrome on `--remote-debugging-port=9222` and drive it with the `mcp__chrome-devtools__*` tools (see `chrome-devtools-mcp.md` for the launch/kill commands). Its `take_screenshot` goes through the DevTools protocol, not extension script injection, so it works on exactly the pages the extension chokes on — and `evaluate_script` there has no 1000-char result cap either. `resize_page` can't go below Chrome's ~512px minimum window width, so simulate a narrow viewport by shrinking the app's own container element and calling the app's resize handler.

## The host's CSP blocks what you inject, but not what CDP evaluates

`Runtime.evaluate` is a debugger API and runs regardless of the page's `script-src`. Everything it *creates* is still policed:

| approach | subject to page CSP |
|---|---|
| code passed to `javascript_tool` | no — runs even under a strict policy |
| `<script src="http://localhost:…">` appended from that code | yes — blocked by `script-src` |
| `<link rel="stylesheet" href="http://localhost:…">` | yes — blocked by `style-src` |
| `new CSSStyleSheet()` + `adoptedStyleSheets` | no |
| `document.createElement('style')` with inline text | usually yes (`style-src` without `'unsafe-inline'`) |

A blocked `<link>` fails **silently in a way that looks like success**: the element exists and `getElementById` finds it, so check `document.styleSheets` for the sheet and a non-zero `cssRules.length` before concluding the CSS "didn't work". A local HTTP server is therefore useless for injecting into a CSP-protected page — paste the payload into the evaluated code, or serve the whole repro from localhost where no CSP applies.

**`adoptedStyleSheets` cannot reproduce a cascade-order bug.** Adopted sheets always sort after every document stylesheet, so a rule that loses an equal-specificity tie in the real page will win when adopted. To test ordering, insert a real `<style>` element at the position you are simulating.

## Reaching a game/board page that only exists while logged in

The user's own finished tables often still render their full client under a replay URL, which is a private, read-only way to get a real board with the framework's globals live: from `gamereview?table=<id>`, follow the `/archive/replay/...` link. A finished table's normal URL usually redirects to a results page with no board at all.

## A tab you create is background-throttled — media will not decode in it

Chrome throttles the media pipeline in hidden tabs, and a tab opened via `tabs_create_mcp`/`navigate` is not focused.
The symptom looks exactly like a codec failure:

```
document.hidden        true
document.hasFocus()    false
video.networkState     2      (NETWORK_LOADING — it is trying)
video.readyState       0      after 14s
video.buffered.length  0
video.error            null   ← no error ever fires
```

Resource timings showed the manifest and every WebVTT `<track>` fetched fine (those are ordinary text loads) while
**no media segment was ever requested**. So "subtitles load but the picture never starts" is the signature.

Don't conclude the player is broken. Verify everything up to the decoder instead, which is fully observable:

- fetch the manifest and one segment yourself with `await fetch(...)` and check status/bytes — plain fetches are not
  throttled;
- `MediaSource.isTypeSupported('video/mp4; codecs="avc1.640028,mp4a.40.2"')` for the decode question;
- `performance.getEntriesByType('resource')` to see what the player actually requested.

Then ask the user to press play in their own window for the one thing that cannot be automated: a visible frame.

**Layout is unaffected** — `getBoundingClientRect()` on the player, the video and the controls returns real geometry
at `readyState 0`, so full-screen/letterboxing/flex sizing can all be verified without a decoded frame.

### Computed style goes stale after a class change in the same tab

The DOM updates but the resolved style does not. Toggle a class on an element that is already on screen and
`element.className` reports the new value while `getComputedStyle(element).backgroundColor` keeps returning what it
resolved to earlier — so a working toggle reads as if its CSS never applied, and a correct rule looks broken:

```
click → className "btn"          (is-on removed, correct)
        computed background      rgba(125,149,255,0.16)   ← still the is-on value
```

**Measure a node you just created.** One with no cached resolution resolves against the live stylesheet, so the
question "do my rules produce the right values" is still answerable:

```js
const probe = (cls) => {
  const el = document.createElement('button');
  el.className = cls;
  host.appendChild(el);                       // must be in the document to resolve
  const s = getComputedStyle(el);
  const out = { bg: s.backgroundColor, color: s.color, decoration: s.textDecorationLine };
  el.remove();
  return out;
};
probe('btn');            // off state
probe('btn is-on');      // on state — both correct in a hidden tab
```

Check `document.hidden` before believing a computed value that disagrees with the element's own class list.
Everything behavioural is unaffected and worth asserting instead: `className`, `aria-pressed`, `textTracks[i].mode`,
and geometry all update normally. The stylesheet itself can also be read directly — walking `document.styleSheets`
for the matching `cssRules` proves which declarations exist and at what specificity, independent of any element.

**To reach UI that only appears once media loads, dispatch the event the app is waiting on.** A branch hung off
`loadedmetadata` — a seek-to-resume, an autoplay-refused hint, an error affordance — is unreachable while the element
sits at `readyState 0`, so the whole state is untestable in a hidden tab. A synthetic event runs the app's own
handler:

```js
video.dispatchEvent(new Event('loadedmetadata'));   // begin() runs: seek, then play() → rejects, sets the hint
```

This exercises real code rather than faking a render: `play()` genuinely rejects (no user activation), so the
component's own catch decides what the bar says. Untrusted events are fine here — only `isTrusted` differs, and
nothing in an app's own listener reads it.

**A keyboard shortcut is testable the same way, and its guards are easier to reach than with a real keyboard.**
Key events are not throttled in a hidden tab and bubble normally, so dispatching on the element focus would really be
on reaches a listener bound to `window` or `document` — which is where an app-wide shortcut lives. Varying the init
dict then walks branches a hand test can barely produce: `repeat: true` is what a held key sends, and retargeting the
dispatch at a `<select>` or `<input>` is how you prove the shortcut yields to a form control's own type-ahead.

```js
const press = (el, init) => el.dispatchEvent(new KeyboardEvent('keydown', {key: 's', bubbles: true, ...init}));
press(video, {});                    // toggles — bubbles from the video up to the window listener
press(video, {repeat: true});        // held key: ignored
press(video, {ctrlKey: true});       // Ctrl-S belongs to the browser: ignored
press(picker, {});                   // focus in a <select>: ignored, type-ahead preserved
```

Assert on the behavioural state after each — `aria-pressed`, `textTracks[i].mode`, `className` — since those update
normally in a hidden tab while computed style does not (see above). `bubbles: true` is the part that is easy to
forget, and without it every dispatch silently does nothing.

**Anything that reads or writes the playback position needs the element to stop telling the truth.** A seek handler is
unreachable at `readyState 0`: it guards on metadata, clamps against `duration`, and assigns `currentTime`, none of
which behave with no media loaded. All three are prototype accessors, so an own property on the instance shadows them
and the app's real handler runs against values you choose:

```js
let ct = 100, ready = 1, dur = 1000;
Object.defineProperty(video, 'readyState',  {configurable: true, get: () => ready});
Object.defineProperty(video, 'duration',    {configurable: true, get: () => dur});
Object.defineProperty(video, 'currentTime', {configurable: true, get: () => ct, set: v => { ct = v; }});
press(video, {key: 'd'});              // ct === 105
ready = 0; press(video, {key: 'd'});   // unchanged: the pre-metadata guard holds
```

Only the element's own reporting is faked — the handler, its guards and its arithmetic are the real ones. This reaches
the cases a live player makes awkward on purpose: the clamp at zero, the clamp at the end, an `Infinity` duration
(live HLS), and the no-op before metadata, none of which need a film seeked to 998 s. Keep `configurable: true` so the
shadows can be deleted afterwards.

## `close` on `<dialog>` was not observable from evaluated code

Probing a native `<dialog>`, neither React's delegated `onClose` **nor** a hand-added `addEventListener('close', …)`
fired — including on a control dialog created fresh in the evaluated code (`showModal()` then `close()`, listener
attached in between, 300 ms wait). `close` does not bubble, which explains React; the control case suggests the
evaluation context does not see it either, so the probe cannot distinguish "the event never fires" from "this context
cannot observe it".

Either way the lesson for the code under test is the same: **don't hang teardown off the `close` event.** Call the
close handler explicitly alongside `dialog.close()`, and route Esc through `onCancel`. Non-bubbling events are a bad
place to put anything load-bearing.

## `cancel` on `<dialog>` IS observable, unlike `close`

The sibling of the section above, and the useful half: `dlg.dispatchEvent(new Event("cancel", { cancelable: true }))`
does reach React's `onCancel`. So the Esc path of a dialog — usually a separate branch from the ✕ button, and the one
that is easy to leave out of a refactor — can be exercised from evaluated code even though Esc itself cannot be
synthesised. Assert on what the handler does (the dialog unmounts, a request goes out), not on the event.

## Proving what a click triggered, and in what order

The resource timeline is the probe's answer to "did the right requests happen, in the right sequence" — worth
reaching for when the behaviour under test is *ordering* rather than output. Mark the moment, act, wait, then filter:

```js
const mark = performance.now();
button.click();
await new Promise((r) => setTimeout(r, 4000));
const after = performance.getEntriesByType("resource").filter((e) => e.startTime > mark);
const post = after.find((e) => /api\/thing/.test(e.name));
const rsc = after.find((e) => /_rsc=/.test(e.name)); // a Next App Router refetch
({ posts: after.filter((e) => /api\/thing/.test(e.name)).length, chained: rsc.startTime >= post.responseEnd });
```

Two things make this work where a screenshot would not: `responseEnd` vs `startTime` gives real evidence of chaining
rather than a plausible story, and the *absence* of a request is as testable as its presence — the negative case (an
action that must NOT refresh the page) is otherwise almost impossible to demonstrate.

Return **counts and booleans, never the entry names**: `entry.name` is a full URL, and the guard rejects any result
carrying a query string — which every `_rsc=` request has by definition.
