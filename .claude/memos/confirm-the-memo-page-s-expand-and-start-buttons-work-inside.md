---
created: 2026-11-17 06:29:17
platform: macos
---

# Confirm the memo page's expand and Start buttons work inside agterm on the Mac

The pick page that `/memo` opens with no arguments is drawn as an agterm HTML overlay on the Mac, and two of its controls have never been pressed there. The ▸ button on a row should open that memo's body under it. Start on a row should make that memo the one to begin (one row at a time can hold it), and once the page is applied, `/memo` prints that memo in full as a `start:` block.

On 2026-11-16 the Windows session asked for this check, after the Mac's `memo` script became the page-or-add version, and it was never answered. Next step, at the Mac: inside agterm, run `/memo` in a repo with open memos, press ▸ on one row and Start on another, then apply. If either does nothing, the page is built by `_page_spec` in `claude/skills/memo/memos.py` and shown by `claude/scripts/review_picker.py`.
