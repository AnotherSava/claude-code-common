# Keeping a page server-rendered while small client islands drive it

Patterns from building a dense, interactive list page (filters, hover preview, inline confirmations) in the Next App Router without turning the page — or the components that format dates — into client components. The through-line: the island owns *state*, the server owns *markup*, and they meet through a `data-*` attribute or a passed-in node.

## Style a server-rendered ancestor from a client island: `data-*` + `:has()`

A client component can only re-render itself. But it can toggle an attribute, and CSS can look **upwards** from that:

```tsx
// client island
<form data-pending={pending ? '' : undefined}>…</form>

// server-rendered ancestor, elsewhere in the tree
<div className="group">
  …
  <div className="transition-opacity group-has-data-pending:opacity-50">{results}</div>
</div>
```

Tailwind v4 compiles `group-has-data-pending:` to `:is(:where(.group):has([data-pending]) *)`. Uses this bought: dimming results while a filter navigation is in flight, tinting a whole row red while a confirmation inside it is armed (`has-data-arming:bg-soldout-bg` on the `<li>`), and keeping hover-revealed controls visible while they are mid-question.

Name the group when rows have their own hover state — `group/row` + `group-hover/row:` — or an unnamed inner group silently answers to the outer one.

## Hand server-rendered nodes to a client component as props

A client component that needs to *choose* between server-rendered things does not need to be able to *build* them. Passing React nodes as props keeps their dependencies server-side:

```tsx
// server page
const panels = days.map((day) => ({ day, label, grid: <CalendarGrid … /> }));
<ShortlistPanel days={panels} defaultDay={today} />   // client: picks which grid to show
```

The grids are rendered on the server (Luxon, DB types, server actions and all) and arrive in the RSC payload; the island renders `shown.grid`. Switching between them costs no round trip and no client-side date library. Server actions can be threaded through the same way — pass the action as a prop and use it in a nested `<form action={…}>`.

Corollary: precompute anything positional on the server. Sending `{ day, startMinute, endMinute }` per row let a hover preview place a block with arithmetic alone, instead of shipping a timezone library to work out where "09:00 at the venue" is.

## One delegated listener beats a component per row

For a 100-row list, wrap the list once and read the row off the event target — `mouseover` bubbles, `mouseleave` on the container gives the "left the list" edge:

```tsx
const from = (target: EventTarget | null) =>
  show(slotOf(target instanceof HTMLElement ? target.closest<HTMLElement>('[data-preview]') : null));
<div onMouseOver={(e) => from(e.target)} onMouseLeave={() => show(null)}>{children}</div>
```

Rows carry their payload as one JSON `data-preview` attribute, so both sides share a shape rather than a naming convention. Clear on leaving the *list*, not on leaving a row, or moving between rows blinks the state off and on.

**Gotcha:** a computed-key spread (`{...{ [CONST]: '' }}`) did not reach the DOM in React 19 — the attribute was simply absent, while a literal `data-truncates=""` rendered. Write data attributes literally.

## `<details>` as a dropdown, controlled

Controlling `open` from state gives an exclusive accordion for free (one `openMenu` key), keeps the panel server-renderable, and needs no popover library.

**The trap:** the `toggle` event is asynchronous. Opening menu B closes menu A, and A's handler then reports "I closed" *after* B has recorded itself — clearing the state B just set, so both end up closed. The close handler must only clear when it is still the menu on record:

```tsx
onOpenChange={(open) => setOpenMenu((current) => (open ? key : current === key ? null : current))}
```

Light dismiss is a `pointerdown` listener on `document` while something is open, ignoring targets inside the open menu (`closest('[data-filter-menu="…"]')`), plus Escape.

## Hover-only affordances need a pointer test

Hiding row actions until hover strands them on touch devices, where nothing hovers. Gate the *hiding* on the pointer, not the reveal:

```
className="… focus-within:opacity-100 pointer-fine:opacity-0 pointer-fine:group-hover/row:opacity-100"
```

Tailwind v4 emits `@media (pointer: fine)` around the hide, and nests `@media (hover: hover)` around the reveal itself. Keep `focus-within:` outside both so the keyboard path works everywhere.

## Measuring these in a background tab

Automated checks against a tab that is not frontmost see frozen animations: `getComputedStyle(el).opacity` stays at the *start* of a transition forever, so a working reveal reads as broken. Set `el.style.transition = 'none'` before sampling, and note that `setTimeout` is throttled to ~1s, which stretches any debounce assertions.
