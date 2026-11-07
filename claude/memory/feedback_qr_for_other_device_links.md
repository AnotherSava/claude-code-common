---
name: feedback_qr_for_other_device_links
description: A link meant for the phone or iPad goes over as a published QR page beside the URL, because the user does not type URLs on those devices
metadata:
  type: feedback
---

When a link is meant to be opened on another device — the phone, the iPad — hand over a QR page as well as the
URL: a small HTML page showing the URL as a QR code, published with `tailnet_publish.py publish` and linked in chat,
so the user opens it on this machine's screen and points the device's camera at it.

**Why:** the user said "how do i open this link on ipad? i don't want to type it" (2026-11-06), and asked to see
the QR page again twice in the same session. A tailnet URL in chat is only clickable on the machine running the
terminal.

**How to apply:** whenever the next step is "open this on your phone/iPad", build the page in the project's `tmp/`
(the `qrcode` Python package renders the image), publish it, and give its link next to the URL. Keep the page
around for the session, since it gets asked for again. Related: [[feedback_review_on_the_local_server]].
