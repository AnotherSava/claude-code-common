---
name: project-render-cache
description: Thumbnails are keyed on content hash plus width, so a re-crop invalidates one entry rather than a whole folder
metadata:
  type: project
---

The cache key is the content hash and the requested width, not the file path. A re-crop
changes the hash and therefore invalidates exactly one entry; moving a file invalidates
nothing, which is the behaviour the gallery relies on when it reorders.
