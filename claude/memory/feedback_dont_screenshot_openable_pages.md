---
name: feedback_dont_screenshot_openable_pages
description: Once the user has a running server and its address, hand over the URL instead of screenshotting the page for them
metadata:
  type: feedback
---

**Once the user has a running server and its address, stop screenshotting it.** They can open the page faster
than a screenshot round-trip, and at full fidelity instead of a compressed image. Give them the URL and let
them look. The address itself is [[feedback_local_deploy_give_url]] — this rule is what follows from it.

Screenshots are for when they genuinely cannot look:

- the server is down, or has never been started
- the user asked what something looks like before knowing there was a URL
- the thing is not a page — a native window, a PDF, a generated image
- verifying something *for myself* mid-task, which does not need to be shown to them at all
- they explicitly asked for a picture

**Why:** a screenshot substitutes my framing for their eyes. It shows one viewport at one width with whatever
was on screen when I took it, and it invites reading my caption instead of the page. Handing over the URL is
both cheaper and more honest — they see everything, including whatever I did not think to look at.

**How to apply:** when reporting UI work on a running server, describe what changed and where to look, then
stop. If the point genuinely needs an image — a layout comparison, a rendering bug — say why a screenshot
rather than the URL.
