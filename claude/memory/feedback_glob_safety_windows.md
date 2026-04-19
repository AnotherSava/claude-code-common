---
name: Glob safety for numeric filenames
description: rm hex_4*.png matches hex_40, hex_400 AND hex_441 — always use explicit ranges or sequences
type: feedback
---

Shell globs like `hex_4*.png` match ANY filename starting with `hex_4` — including `hex_40.png`, `hex_400.png`, AND `hex_441.png` (no boundary between the `4` and the wildcard digits).

**Why:** During artifact asset rebuilds I deleted hex_441..499 intending to redownload, but the glob also wiped hex_40..49 and hex_400..440 (existing base/cities icons). Had to restore 61 files from git.

**How to apply:** When operating on numeric-range files, use explicit ranges (`rm hex_4{41..99}.png`) or sequences (`for i in $(seq 441 499); do rm "hex_$i.png"; done`). Check `ls hex_4*.png | wc -l` before deletion if in doubt.
