# jsdom testing gaps

jsdom (via vitest's `environment: "jsdom"`) implements enough of the DOM to test structure and
event wiring, but several CSS and platform features are missing entirely. The dangerous ones are
those that **fail silently in the direction of "test passes"** — the test is green while the
browser is broken.

Always **probe the capability first** rather than assuming. A throwaway test with a `console.log`
settles it in seconds and is far cheaper than shipping a test that proves nothing.

## What it does support

**Cascade specificity.** Id/class/element specificity resolves correctly, so this works:

```js
style.textContent = `#hdr #view { width: 33px } #view { width: 20px }`;
getComputedStyle(view).width;  // "33px" — correct
```

## What it does not support

**`all: unset`.** Not implemented. jsdom reports the reset properties as if the declaration were
absent:

```js
style.textContent = `
  #hdr button { all: unset; }        /* (1,0,1) — should win */
  #view { width: 20px; background-image: url("data:..."); }
`;
getComputedStyle(view).width;  // "20px" in jsdom; "auto" in Chrome
```

A real specificity bug — a broad `all: unset` out-specifying an id rule and stripping an icon's
size and artwork — therefore **passes** in jsdom.

**Popover API.** `element.showPopover` is `undefined`; `:popover-open` does not match. Anything
gated on the top layer cannot be exercised.

**Layout.** Every element has a zero-size `getBoundingClientRect()`, and `offsetWidth` /
`offsetHeight` are `0`. Geometry code must have its inputs stubbed to be testable at all.

## Testing strategy when the feature is missing

Split the test in two, and be explicit about which half is real:

1. **Behavioural half — test your own logic with the platform call stubbed.** Delegation,
   which element is resolved, the order of operations, the arithmetic of a position
   calculation. This is genuine coverage of code you own:

   ```js
   tip.showPopover = vi.fn();
   tip.matches = (sel) => sel === ":popover-open" ? open : Element.prototype.matches.call(tip, sel);
   card.getBoundingClientRect = () => ({ top: 100, bottom: 120, left: 500, ... });
   Object.defineProperty(tip, "offsetWidth", { value: 375, configurable: true });
   ```

2. **Structural half — assert against the stylesheet source** for the cascade facts jsdom cannot
   evaluate. A proxy, but it guards regressions that are otherwise invisible to the suite, and it
   documents *why* the rule is shaped the way it is:

   ```js
   const css = readFileSync(sheetPath, "utf-8");
   const rules = css.replace(/\/\*[\s\S]*?\*\//g, "");  // strip comments first
   expect(rules).not.toMatch(/#hdr button/);
   ```

   **Strip comments before matching.** These guards typically name the very selector they forbid
   in an explanatory comment, so a raw-text assertion matches its own prose and fails (or, worse,
   passes because the real rule was commented out).

## Rule of thumb

If a test would pass with the feature entirely removed from the browser, it is testing nothing.
Either stub the platform call and test your own logic around it, or assert structurally — but do
not write a rendering assertion against an unimplemented feature.
