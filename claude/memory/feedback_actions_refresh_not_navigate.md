---
name: actions-refresh-not-navigate
description: Side-panel actions refresh the host page in place; only explicit user intent navigates
metadata:
  type: feedback
---

Side-panel actions refresh the host page in place; only explicit user intent navigates.

When the user clicks a sub-tab or selects a label in the side panel, that's explicit navigation intent — drive the host page to match. When the user performs an action with side effects (archive, delete, undo, etc.), that's an implicit consequence — refresh whatever the host page is currently showing rather than redirecting them.

**Why:** Redirecting the user out of their current view (a message they were reading, an inbox they were scrolling) on every action is jarring. Refreshing in place lets them see the change without losing context. The user explicitly called this out when archive was forcing Gmail to the filter URL: "if gmail page doesn't show search, archive and delete actions should not lead to the search page, just refresh gmail side in place."

**How to apply:** Model "navigate host page to filter" and "refresh host page's current view" as two distinct messages in the side panel ↔ background channel, not as a single message with a flag. The two operations have different inputs (one needs a URL/query, the other doesn't) and different effects (navigation changes state; refresh is idempotent). See [[chrome-extension]] for the Gmail-specific refresh-button injection trick that avoids a heavy `chrome.tabs.reload`.
