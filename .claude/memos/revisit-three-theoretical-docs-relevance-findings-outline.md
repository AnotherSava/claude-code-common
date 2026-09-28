---
created: 2026-09-28 05:02:54
---

# Revisit three theoretical docs-relevance findings: outline stem cuts, keyed-frame edge checks, keep_raw copy

Three findings from the 2026-09-28 fourth review of the docs-relevance skill were judged real in code but reached by no caller, so they were left alone. Revisit them when a real capture hits one.

1. outline.py --clean keeps a cut that splits a glyph stem lengthwise (F1). _straddles takes each pixel's reference from the modal of a 17-px window along the cut line, so a stem of 9+ px running along a left/right cut (l, n, h, |, d) reads as background and scores 0, tying a clean line; ties go to the smaller move. Reproduced on synthetic Consolas text and on a crop of intellij-jsonl-extension's raw align-none.png. The proposed repair (a 2-D modal over a box straddling the cut) BREAKS the committed context-menu-filter step there (--reach 4 on an 867 px crop: scores 867 at 39 and picks 866), so any fix has to be tested against that step and re-run through intellij's capture.py as a regression set. No committed cut splits a glyph today.

2. hairline.py on keyed frames with a transparent margin (F2, F4). _assert_bordered reads the raw canvas pixel at each edge midpoint and ignores alpha, so hairline --require refuses a keyed frame whose midpoints are transparent (bga's nucleum-*.png would fail it, exit 1, nothing written). has_edge can also miss hairline's own inward ring on a keyed frame with a soft outer row and content within 20 levels of #BDBDBD, giving a false NO EDGE. Fix both together by walking inward from the midpoint to the first pixel with alpha >= OPAQUE_SILHOUETTE, as _side_share does. No caller sends such a frame: bga and achievement-overlay use their own border helpers.

3. v12 step 2 and tauri-dashboard's keep_raw (F11). The step tells an agent to add loud failure to new raw copies but only to move keep_raw, which warns and carries on; a failed copy would then leave a stale committed raw beside a new frame. keep_raw already mkdirs the directory, so the realistic failure is rare. Settle it when tauri adopts v12, in that repo.
