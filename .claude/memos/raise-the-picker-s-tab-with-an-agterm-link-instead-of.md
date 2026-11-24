---
created: 2026-11-24 16:15:15
platform: macos
---

# Raise the picker's tab with an agterm:// link instead of session and window select

In remote-session/mac/pick-session.py, main loops over ("session","select","--target",session) and ("window","select",window) to raise an existing tab. agterm v0.44.0 registers agterm:// with macOS, and open "agterm://session/<SESSION_ID>" selects the session and raises its window in one step, with no window id, and brings agterm to the front, which a cmd+shift+r picker wants. The comment above that loop about the two calls taking their ids differently goes with it, and the window lookup feeding window may then be droppable; attached_tabs still needs window list + tree --window to find the tab.

Testable only once the running agterm is v0.44.0 or later: on 2026-11-24 the app bundle held a v0.44.1-based build but the running instance was 0.40.0 until a relaunch. open takes no --socket; it reaches the Release app (Debug builds claim agterm-debug:), which is the instance pick-session.py targets. Proposed by the agterm session.
