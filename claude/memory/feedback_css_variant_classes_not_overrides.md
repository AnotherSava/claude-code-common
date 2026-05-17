---
name: feedback-css-variant-classes-not-overrides
description: Compose CSS via base class + sibling variant classes; don't override base layout for specific cases
metadata:
  type: feedback
---

For shared component CSS, put layout-agnostic properties (padding, border, hover, gap, display) on the base class. Put view-specific layout (grid templates, column shapes) on sibling variant classes. Don't override the base class from a scope-specific selector.

**Why:** I made `.summary-row` declare a 3-column grid template (`minmax(80px, 22%) 1fr auto`) for Deals, then added `#sub-reminders .summary-row { grid-template-columns: 1fr auto; }` to override it for Reminders. The user pushed back: "overriding might be not a correct approach - this template should be designed to be different for different subtabs." The override bakes the first-built view's shape into the base, and every new view has to fight against it.

**How to apply:** When building multiple views that share visual scaffolding, design the base class as layout-agnostic. Each view declares its own variant class with its own `grid-template-columns` (or flex axis, or whatever defines that view's shape). Markup uses both: `class="summary-row deals-row"`. New views add their own variant class instead of patching the base.
