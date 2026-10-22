---
name: user_screenshot_location
description: "\"See the screenshot\" with nothing attached means the newest PNG on the Desktop, or in ~/CropStage on Windows"
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

The space before `AM`/`PM` in that name is U+202F (narrow no-break space), not an ASCII space, so a path typed out by hand fails with `No such file or directory` even though `ls` printed it. Match it with a glob instead: `ls ~/Desktop/Screenshot\ 2026-10-21\ at\ 8.53.06*.png`. Measured 2026-10-21, on an `scp`.

Only a session started locally can read `~/Desktop`. Over ssh, macOS privacy protection answers `Operation not permitted`, so a session on the other machine cannot fetch a screenshot itself. It has to ask the Mac's live session to copy the file across.

## On Windows they are staged elsewhere

A crop tool writes captures to `~/CropStage/`, named `YYYY-MM-DD HH-MM <window title>.png` rather than
the macOS `Screenshot …` form. Check the newest there as well as the Desktop before saying no image
arrived:

```bash
ls -lt ~/CropStage ~/Desktop 2>/dev/null | grep -iE "\.(png|jpg|jpeg)$" | head -5
```

Observed 2026-09-02, six images handed over from that directory in one message.
