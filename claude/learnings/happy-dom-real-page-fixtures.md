# Testing DOM code against saved real pages in happy-dom

A page saved from a live site is the honest fixture for code that reads that site's DOM, because a hand-written stand-in only has the structure you already believed in. Loading one into happy-dom is one assignment, but happy-dom then behaves like a browser and fetches what the page links.

## Turn off loading, or the tests go to the network

Assigning the saved HTML to `document.documentElement.innerHTML` makes happy-dom fetch every `<link rel="stylesheet">` and `<script src>` in it. The tests still pass, but each run reaches the site's CDN, and every failed or aborted fetch prints a `DOMException [NetworkError]` stack trace into the output, so the run looks broken while reporting green. Inline scripts run too.

Set the browser settings through Vitest:

```ts
// vite.config.ts (vitest/config)
test: {
  environmentOptions: {
    happyDOM: {
      settings: {
        disableJavaScriptEvaluation: true,
        disableJavaScriptFileLoading: true,
        disableCSSFileLoading: true,
        disableIframePageLoading: true,
        handleDisabledFileLoadingAsSuccess: true,
      },
    },
  },
},
```

The `disable*` flags alone still print a `NotSupportedError` ("CSS file loading is disabled") per linked file. `handleDisabledFileLoadingAsSuccess` is the one that makes a skipped load quiet. Select the environment per file with `// @vitest-environment happy-dom`, so tests that need no DOM stay in Node.

## Getting the page in the first place

A site behind a bot challenge answers `curl` with the challenge page, so a saved fixture can silently be "Just a moment…" rather than the page. Check the `<title>` of what you saved before writing a test against it. A cloud scraper's `rawHtml` format returned the real markup where `curl` got 403 (`rutracker-automation.md` has the measured case).

## Mutate the loaded page to reach the other branches

One real page covers one branch. Remove or plant elements in the loaded document to drive the rest — delete the real magnet link and plant one in a reply to prove replies are ignored, strip a class to exercise a fallback selector — rather than writing a second hand-made page, which reintroduces the stand-in problem.
