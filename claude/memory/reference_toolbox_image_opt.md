---
name: Toolbox image-opt reference
description: Canonical WebP/AVIF encoding settings — check toolbox/tools/image_opt before deriving fresh image conversion params
type: reference
---

`D:/projects/toolbox/tools/image_opt/src/main.py` is the canonical source
for image-conversion defaults used across my projects (Python PIL-based).

- WebP: `format=WEBP`, `method=6`, `quality=60`
- AVIF: `format=AVIF`, `speed=2`, `subsampling=4:2:0`, `quality=60`
- Optional `--max-width=1024` resize for shrinking before upload

When implementing image conversion in another project, match these
settings first. Used recently in crop-stage's WebP screenshot path
(.NET ImageSharp port of these params — see global learning
`dotnet-imagesharp-webp.md`).
