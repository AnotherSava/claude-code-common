# Clicking with claude-in-chrome: it reports success without having acted

Two independent reasons a `computer` click does nothing while the tool result says it worked. Both cost several
rounds on a local, plain, server-rendered page — no overlays, no iframes, no auth, nothing exotic. The common
consequence is the important part: **a click's tool result is not evidence that the click happened**, so verify
by its effect and never by the message.

## Screenshot coordinates are not viewport coordinates

`computer` returns a screenshot whose pixel dimensions do not match the window you sized. A window resized to
`1280x1000` produced screenshots of `1489x812` and `1353x738` in the same session — a scale factor of ~1.06
horizontally, and a different one vertically, neither announced anywhere in the result.

So reading an element's position off the screenshot and passing it as `coordinate` lands somewhere else. The
click reports the coordinates it was given and Chrome dispatches at that point, which is empty space; nothing
errors. Measured: a button whose glyph sat at screenshot x=517 was actually at viewport x≈489, and the click
fell outside it.

**Use `find` and click by `ref` instead of by coordinate** whenever there is an element to name. `find` takes a
natural-language description and returns `ref_N` handles, which resolve in page space:

```
find({ query: "Accept submit button" })     → ref_48: button "Accept" (submit)
computer({ action: "left_click", ref: "ref_48" })
```

## A `ref` click can silently no-op, and it is not deterministic

Clicking by `ref` is correct about *where* and still unreliable about *whether*. In one session five
ref-clicks on the same kind of control produced two navigations and three no-ops, each of the three returning
`Clicked on element ref_N` with no error, no console message, and a page that had not changed. The same ref,
re-found and re-clicked a moment later, then worked.

The likeliest cause is that the click is dispatched before the page has attached its handlers — a fresh
`navigate` followed immediately by `find` + click is the shape that failed, and the one that succeeded had a
screenshot (and so a round trip) in between. That is a guess; what is certain is the non-determinism and the
false success.

**So: assert the effect, not the click.** For a form that mutates something, read the mutation back rather than
trusting the response:

```bash
# before
docker exec db mongosh "$URI" --quiet --eval 'print(db.trips.countDocuments({}))'
# … click …
# after — a count that did not move means the click did not happen, whatever the tool said
```

For a navigation, compare the tab's URL or title afterwards: `tabs_context_mcp` (and the Tab Context appended
to every result) reports the current URL, and an unchanged one after a click on a link is the tell. A stale
title is the cheapest signal of all — the tab still said `GenCon · 28 Jul – 4 Aug 2026` after a click that was
supposed to leave that page.

**Re-`find` before re-clicking.** Refs are handed out per `find` call; after a failed click, run `find` again
rather than reusing the handle, because a page that re-rendered in between has invalidated it.

## Scrolling can no-op too, with the same silence

`computer({ action: "scroll", scroll_direction: "down", scroll_amount: 8 })` returned
`Scrolled down by 8 ticks` twice in a row and produced **identical** screenshots the second time, on a page
with plenty left below the fold. There was no error and no indication which of the two calls had moved
anything.

When the goal is to read content below the fold, do not scroll at all — fetch the page and read it:

```bash
curl -s http://localhost:PORT/path | python3 -c "…strip tags, print text…"
```

That reads the whole document in one call, with no dependence on scroll position, and it is how the bottom of
a long pane is best verified. Reserve scrolling for when the *rendered appearance* of a lower region is the
thing being judged, and then confirm movement by comparing consecutive screenshots rather than by the tool's
reply.
