# claude-in-chrome vs. dev servers with live reload

The claude-in-chrome extension's `computer` screenshot, `read_page`, and `get_page_text` all inject a content
script that waits for `document_idle`. On a **Next.js (Turbopack) dev server** the HMR / live-reload connection
keeps that from ever firing, so every one of those calls fails with:

```
Error capturing screenshot: Page still loading (executeScript waited 45000ms for document_idle).
```

The page has actually loaded (title and DOM are present) — only the idle wait times out. Retrying doesn't help;
it's structural (a persistent connection), not transient. Any dev server with a long-lived HMR/SSE/websocket can
trip it, not just Next.

## Workarounds

- **`javascript_tool` bypasses it.** It uses a different injection path and runs regardless of idle. Read the DOM
  directly to verify a UI change:
  ```
  document.querySelector('header nav')?.innerText      // text content of a region
  document.querySelector('footer')?.innerText
  el.getBoundingClientRect()                            // geometry — confirm layout/alignment without a screenshot
  ```
  This is the go-to for verifying a change on a running dev server.
- **chrome-devtools MCP** (`mcp__chrome-devtools__*`) uses CDP and does *not* wait for idle, but it needs Chrome
  started with `--remote-debugging-port=9222`; it errors ("Could not connect to Chrome") otherwise. See
  `chrome-devtools-mcp.md`.
- **A production build has no HMR**, so `next build` + `next start` renders screenshot-able — but `next build`
  clobbers `.next` (conflicts with a running dev server) and Next refuses a 2nd dev server for the same project,
  so it's rarely worth it just for a screenshot.

Net: to verify a UI change on a running Next dev server, read DOM text + `getBoundingClientRect()` geometry via
`javascript_tool` rather than trying to screenshot.

## Verifying via curl (and the RSC-payload double-count)

When the extension is disconnected — or for a quick server-render check without a browser — `curl
http://localhost:<port>/<path>` returns the SSR HTML. Good for confirming a route renders, a section is
present/absent, or which text/glyph a server component emitted. Two caveats:

- **The dev server may not be on `:3000`.** Next's single-instance lock refuses a 2nd `next dev` for the same
  project and prints the port the existing one is on (e.g. `:3939`). Grep the dev log / `netstat` for the real
  port before curling; `:3000` may even be a *different* app.
- **Next.js App Router serializes the rendered tree into the HTML twice** — once as real DOM, once as the RSC
  flight payload (`self.__next_f.push(...)` scripts). So `curl … | grep -c 'SOMEGLYPH'` returns ~**2×** the
  on-screen count. To count actual DOM instances, grep for the **literal element markup** —
  `<span class="...">♥</span>` — because the flight payload serializes elements as JSON arrays, not literal HTML
  tags, so it won't match. (Real case: 8 favorited movies rendered 16 `♥` in raw curl output; the literal-`<span>`
  grep returned the true 8.)
