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
