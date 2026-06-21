---
name: feedback_default_cursor_noninteractive
description: Non-interactive text/chrome (brand wordmarks, labels) uses cursor:default — not the text I-beam, not pointer; don't make decorative wordmarks clickable unless asked
metadata:
  type: feedback
---

Non-interactive text elements — brand wordmarks, static labels, decorative chrome — should use `cursor: default`, not the text I-beam and not `cursor: pointer`. Reserve `cursor: pointer` for actual clickables. Also: don't make a brand/logo wordmark clickable-to-home in an operator/admin panel unless asked.

**Why:** the user disliked a non-clickable admin wordmark showing the text-selection (I-beam) cursor, and earlier asked to make that same wordmark non-clickable. Treat decorative chrome as decorative — no fake interactivity, no selectable-text cursor.

**How to apply:** when an element is a label/wordmark (not a link/button), set `cursor: default` (optionally `user-select: none` so it reads as a label). Only links/buttons get `cursor: pointer`.
