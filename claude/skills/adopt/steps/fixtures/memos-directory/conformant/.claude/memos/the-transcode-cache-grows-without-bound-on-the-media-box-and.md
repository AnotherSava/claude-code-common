---
created: 2026-08-21 07:15:00
---

# The transcode cache grows without bound on the media box and nothing prunes it: one…

The transcode cache grows without bound on the media box and nothing prunes it: one directory per play survives a job that exits on its own, while a job stopped from the client logs a delete and leaves nothing behind. Decide between a periodic sweep and a scheduled cleanup task before the volume fills.
