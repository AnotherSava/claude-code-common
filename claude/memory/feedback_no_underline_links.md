---
name: no-underline-links
description: Text-control affordances — strip RESTING underlines; distinguish by shape (link=hover-underline, toggle=chevron, action=+, all icon/pill not underline); links keep HOVER-underline for WCAG 1.4.1
metadata:
  type: feedback
---

Distinguish clickable text controls by **shape, not a shared underline**. The rule: **underline = "takes me to info," an icon = "does something here."** Accent/blue = interactive stays; what changes is that underline is reserved for genuine links.

**The failure mode this fixes:** links, disclosure toggles, and actions all sharing "accent text + underline-on-hover," so the user can't predict what a control does before clicking (real case: `Why?` link, `Advanced options` toggle, `Add a note` action all looked identical).

Tiers:
- **Link** (navigate / reveal reference) — accent colour + weight, `text-decoration: none` **at rest** (a resting underline reads as cluttered/dated — the user's aesthetic, surfaced tuning the Vancouver Print Lab quote email). **Keep the underline on HOVER**, though: a bare accent word in running text is distinguished by colour *alone*, which fails **WCAG 1.4.1** (colour-vision deficiency, ~1 in 12) and is easy to mistake for emphasis. Hover-underline costs nothing at rest and restores the affordance on probe. (Zero-underline look: keep a *persistent* underline only on links inside dense prose; leave standalone links bare — but never colour-only in body text. A link carrying a leading link-glyph is exempt: the icon, not colour, signals it.)
- **Disclosure toggle** (expand / collapse in place) — trailing chevron that rotates when open; hover = soft-fill pill (`--accent-soft`), **never underline**.
- **Action** (create / add / trigger) — leading `+` (or a relevant icon); hover = soft-fill pill, **never underline**.
- **Primary action** — filled accent button.
- **Quiet variant** (low-priority control) — drop the accent: `--ink-2` text + `--ink-3` icon, grey `--paper-3` hover pill.

Pill hover without layout shift: `padding: 4px 8px; margin: -4px -8px` — the negative margin cancels the padding so the margin-box is unchanged.

**How to apply (links):** `text-decoration: none` at rest + accent (optionally bold); underline on `:hover`. For content a mail/browser client would AUTO-link (a bare email/URL in an email), render an explicit styled `<a>` so the client's default blue-underline is suppressed. Origin of the tiering: Claude Design "link-vs-button" handoff, 2026-07-13.
