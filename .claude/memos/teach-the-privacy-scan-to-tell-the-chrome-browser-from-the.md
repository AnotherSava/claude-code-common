---
created: 2026-11-16 14:31:30
---

# Teach the privacy scan to tell the Chrome browser from the machine name

The commit privacy scan flags every mention of the browser name Chrome, because that word is also a machine name the scan guards. On 2026-11-14 it raised three review findings on one commit and three more on the next two, all of them the browser or the feedback_minimal_ui_chrome memory link. The findings never block, but each one has to be read and dismissed, and learnings about headless Chrome keep coming. Next step: find where the scan matches machine names, and work out how a host-shaped match (a tailnet name, a device prefix such as CHROME/) can be told from the browser name without letting a real hostname through. The scan must keep failing closed.
