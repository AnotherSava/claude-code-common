---
name: user_screenshot_location
description: "\"See the screenshot\" with nothing attached means the newest PNG on the user's Desktop"
metadata:
  type: user
---

When the user says "see screenshot" / "check the screenshot" and no image is attached to the message, the file is on their **Desktop** — macOS's default screenshot target, named `Screenshot YYYY-MM-DD at H.MM.SS AM/PM.png`.

Take the newest by mtime and Read it:

```bash
ls -lt ~/Desktop | grep -iE "\.(png|jpg|jpeg)$" | head -3
```

Do this before replying that no image came through — the Self-Sufficiency rule applies, and it saves a round-trip. Observed twice in one session (2026-08-02); both times the intended image was the most recent Desktop screenshot.

Worth a sanity check on the timestamp: if the newest one is hours old it may not be the one they mean, in which case ask.
