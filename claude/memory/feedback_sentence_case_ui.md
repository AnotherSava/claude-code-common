---
name: UI text in sentence case
description: Default to sentence case for all user-facing UI labels (menu items, buttons, dialog titles, tooltips); reserve Title Case for proper nouns and acronyms only.
type: feedback
---

Use sentence case for user-facing UI text. Capitalize only the first word and proper nouns/acronyms.

**Examples**
- "Open config file" not "Open Config File"
- "Reload config" not "Reload Config"
- "Hide with Esc" — Esc is an acronym, keep capitalized
- "Start with Windows" — Windows is a proper noun
- "Quick-save area select" — hyphenated compounds lowercase the second element

**Why:** User prefers modern UX convention used by macOS (since Big Sur), Material Design, GitHub, and most contemporary web apps. Less visually shouty, easier to localize, and more consistent with surrounding prose. User made this decision explicitly and asked that future work default to it.

**How to apply:** Any time you write or edit a user-visible string — tray menus, buttons, dialog titles, balloon notifications, tooltips, settings labels — default to sentence case. When modifying a codebase that mixes conventions, realign affected labels in the same change. Only keep Title Case when required for proper nouns (product names, OS names) or established acronyms (Esc, URL, API).
