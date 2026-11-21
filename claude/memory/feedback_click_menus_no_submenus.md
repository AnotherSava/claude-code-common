---
name: feedback_click_menus_no_submenus
description: An item's action menu opens on click, not hover, and holds no submenu for a handful of choices; states are an inline toggle group, the destructive action sits apart at the foot
metadata:
  type: feedback
---

An action menu attached to an item (a calendar block, a card, a row) opens on a click or a tap on every device, and
closes on a press elsewhere or Escape. It never opens on hover. Inside it there are no cascading submenus when the
choices number a handful. A choice of state is shown inline as a vertical toggle group with the current state filled.
The action that deletes or removes sits at the foot, set apart by a divider, and still asks before acting.

This is about a menu that opens over its item. Controls that sit inside a row and appear on hover are a different
thing: the same day the user reported such controls staying up after a click and had that fixed, with the hover
reveal left as it was.

**Why:** the user chose this on 2026-11-14 for the scheduler's calendar blocks. They had asked for a hover menu with
a status submenu, saw a first draft whose submenu opened to the left, and wrote: "i'm not sure about submenu items
showing up on the left - can you research on the best practices regarging this whole hover over menu item on web
pages". Shown the findings, they picked the menu that opens on click over the one that keeps hover, and the states
inline over a submenu, adding the note "vertical toggle group". The click option was put to them as sparing them
menus that open by accident and cover the blocks being scanned. Reading that choice as the rule for any per-item
menu is the scheduler session's interpretation, which the user approved saving that day.

What the research found: Nielsen Norman Group's menu-design checklist advises click-activated over hover-activated
submenus, and advises against multilevel cascading menus, which users "fall out" of. Material Design places a
cascading menu to the right or left of its parent, wherever there is room, and draws it to the right.

The closing rule covers a page's own menu too: on 2026-11-20 the trips page's Add menu, first built as a native `<details>`, stayed open on Escape and on a click outside, and the user asked for both. `<details>` does neither, so a menu needs a menu component (React Aria's `MenuTrigger` there).

**How to apply:** when designing a per-item menu, start from click-to-open, one column, no submenus; show a short set
of states as a toggle group, not behind a "current state ›" item. For a menu with more choices than a column holds,
the research's answer is a submenu that opens on click, to the right, flipping at the edge; the user has not been
asked about that case. Related: [[feedback_no_underline_links]] for how each control's shape signals what it does.
