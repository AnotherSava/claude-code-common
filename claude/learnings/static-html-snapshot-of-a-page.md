# A static HTML snapshot of a live page

When the user asks to see "how it looks now" and the agent cannot screenshot the app, the rendered page itself can be the artifact: fetch the server-rendered HTML, inline its stylesheets and fonts, strip the scripts, and publish the one file on the tailnet. It opens on every device and shows exactly the markup and CSS the app serves, not a mockup of them.

## Steps

1. **Fetch as the user who would see it.** An owner-gated page answers a plain `curl` with a redirect to the login page. Mint a session with the app's own code (for What's Next: `createSessionToken("owner")` from `@/lib/auth`, run through `npx tsx`) and pass it as the session cookie, `curl -b "<cookie-name>=<token>"`. The cookie the browser holds is httpOnly, so it cannot be copied out of a tab instead.
2. **Inline every `<link rel="stylesheet">`.** Fetch each `href` and replace the tag with a `<style>` block in `<head>`.
3. **Resolve font URLs against the stylesheet's own URL, not the page's.** Next.js emits `url(../media/<hash>.woff2)` inside `/_next/static/chunks/*.css`. A rewrite that only handles URLs starting with `/` matches none of them, and the snapshot then falls back to system fonts with no error. The first attempt here embedded 0 of 55 font files for exactly this reason. Use `urljoin(css_href, url)` and embed each as `data:font/woff2;base64,…`.
4. **Strip `<script>` tags and the `preload` / `modulepreload` links.** The result is static: checkboxes do not recompute, disclosures do not open. Say so when handing it over.
5. **Check the published page in a browser.** `document.fonts` should list the app's families as `loaded`, and the background colour should be the app's (it may live on `<html>`, not `<body>`).

Size is dominated by the fonts: one page came to 94 KB of markup and CSS plus about 1.1 MB of font subsets, since Next ships each family as several unicode-range files.

## Where the page has no data locally

A page that renders a record only production holds (a job, an order) needs that record in the dev database first. Copy its fields from production, give anything that identifies a real external object a fake value (an info-hash, a magnet), leave it unassigned to any worker so nothing acts on it, and delete it afterwards.
