---
name: no-underline-links
description: Text-control affordances — strip RESTING underlines; distinguish by shape (link=hover-underline, toggle=chevron, action=+, option=soft-fill hover); links keep HOVER-underline for WCAG 1.4.1; button labels unselectable; a button whose content is replaced keeps one size; text buttons on a page share one height; confirm only what cannot be undone on the spot
metadata:
  type: feedback
---

Distinguish clickable text controls by **shape, not a shared underline**. The rule: **underline = "takes me to info," an icon = "does something here."** Accent/blue = interactive stays; what changes is that underline is reserved for genuine links.

**The failure mode this fixes:** links, disclosure toggles, and actions all sharing "accent text + underline-on-hover," so the user can't predict what a control does before clicking (real case: `Why?` link, `Advanced options` toggle, `Add a note` action all looked identical).

Tiers:
- **Link** (navigate / reveal reference) — accent colour + weight, `text-decoration: none` **at rest** (a resting underline reads as cluttered/dated — the user's aesthetic, surfaced tuning the Vancouver Print Lab quote email). **Keep the underline on HOVER**, though: a bare accent word in running text is distinguished by colour *alone*, which fails **WCAG 1.4.1** (colour-vision deficiency, ~1 in 12) and is easy to mistake for emphasis. Hover-underline costs nothing at rest and restores the affordance on probe. (Zero-underline look: keep a *persistent* underline only on links inside dense prose; leave standalone links bare — but never colour-only in body text. A link carrying a leading link-glyph is exempt: the icon, not colour, signals it.)
- **Disclosure toggle** (expand / collapse in place) — trailing chevron that rotates when open; hover = soft-fill pill (`--accent-soft`), **never underline**.
- **Action** (create / add / trigger) — leading `+` (or a relevant icon); hover = soft-fill pill, **never underline**.
- **Option group** (segmented toggle, choice pills) — the selected option is filled; an unselected one gets a slight
  hover highlight, `background: var(--accent-soft); color: var(--accent)`, so the option about to be picked stands out
  before the click. The selected and disabled options get no hover. Selector, from printlab's segmented controls:
  `button:not(.on):not(:disabled):hover`.
- **Primary action** — filled accent button.
- **Quiet variant** (low-priority control) — drop the accent: `--ink-2` text + `--ink-3` icon, grey `--paper-3` hover pill.

**Every button-like control's label is unselectable**: `user-select: none` on buttons, disclosure `<summary>`s and `[role=button]`, so a quick double-click never highlights the word or its chevron/`+` glyph. Set it once as a base rule, since a class per element misses the next control added. Links keep selectable text, since a link's words are often worth copying. A link drawn as a button (a bordered pill) is a button to the user: give it the same unselectable label and no hover underline, through one shared class, since no selector tells it apart from a prose link.

**A button whose content is replaced keeps one size**: a toggle's label ("Hide calendar" ↔ "Show calendar") or a busy state ("Refresh now" ↔ "Refreshing" + spinner; a spinner already says "in progress", so the label drops the ellipsis). Stack every variant in one grid cell (`display: inline-grid`, each label `grid-area: 1 / 1`, the inactive one `visibility: hidden` and `aria-hidden`), so the button is as wide as the longest variant in every state. Otherwise the press resizes the button and shifts every control beside it, moving the target out from under the pointer. A fixed width guessed from one label breaks on the next font or wording change. Centre the variants when they are different words; when they share a leading word ("Refresh now" / "Refreshing"), start-align them and put a spinner after the text, since centring or a leading spinner makes the shared word jump sideways on every press.

**Every text button on one page has the same height**: the same font size, line height, vertical padding and border, whether it is a `<button>`, a `<summary>` or a link drawn as a button. Buttons that sit side by side or in one header row at mismatched heights read as unrelated controls. A button inside a container that sets a smaller font (a `<details>` or form at 11px) inherits it unless the button names its own size. Real case: scheduler's Refresh now and Legend were 11px/`py-0.5` beside 12px/`py-1` Subscribe and Hide calendar.

**Confirm only what cannot be taken back on the spot.** Ask "Remove?" first when the action makes the thing vanish from where it was clicked, so undoing it means going somewhere else to find it again: removing an event from a calendar sends the user back to search the catalog. A toggle that stays in place, where one more click restores the state, gets no confirmation. Ask in place (the button turns into the question and YES/NO), never in a modal.

Pill hover without layout shift: `padding: 4px 8px; margin: -4px -8px` — the negative margin cancels the padding so the margin-box is unchanged.

**How to apply (links):** `text-decoration: none` at rest + accent (optionally bold); underline on `:hover`. For content a mail/browser client would AUTO-link (a bare email/URL in an email), render an explicit styled `<a>` so the client's default blue-underline is suppressed. Origin of the tiering: Claude Design "link-vs-button" handoff, 2026-07-13.
