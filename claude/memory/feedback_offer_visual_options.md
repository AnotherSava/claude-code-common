---
name: feedback_offer_visual_options
description: For visual/UI design choices, render multiple labeled options at real target sizes and let the user pick — don't unilaterally choose
metadata:
  type: feedback
---

For visual/UI design choices with real design latitude (a border, icon, layout, color treatment), render **multiple variants** and let the user choose rather than picking one yourself. Present them in a single labeled image, rendered at the **real target sizes** on a **representative background**.

**Why:** visual results are hard to judge from prose, and the user wants to see them at the actual rendered sizes before committing. In the tray-badge context-border work, the user explicitly asked: "offer me multiple options … show icon with border on a black background; mind the icon size limitations for both windows and macos."

**How to apply:** when about to bake in a visual treatment, pause and offer rendered options first (e.g. tray icon at 16/32/36px — Windows is 16px×DPI = 16/24/32, macOS is 18pt×backing scale ≈ 36 — composited on the background it'll actually sit on, like black for a dark tray). Label each option and ask which to use. Also prefer a cheap parametric/precomputed shape over per-render pixel processing (the user flagged a per-frame geometric pixel scan as "obviously an overkill"). Relates to [[feedback_run_deploy_directly]].
