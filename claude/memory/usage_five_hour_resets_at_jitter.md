---
name: usage_five_hour_resets_at_jitter
description: five_hour_resets_at jitters ±1min between polls — never use it as a window-reset signal; use the pct drop
metadata:
  type: project
---

In `usage_history.jsonl`, the 5h limit is a **fixed** window (`five_hour_resets_at` stays constant for hours until a real reset), but the stored value **jitters by ±1 minute between consecutive polls** (e.g. 13:09 ↔ 13:10 flipping back and forth) even with no reset. Meanwhile `five_hour_pct` is a clean monotonic cumulative counter within the window.

**Why:** An early version of `build_week_chart` (work-intensity chart) detected resets via `resets_at` changing (`a != b`). Because of the jitter that fired on *every* poll, so each step was mis-classified as a reset and attributed the **absolute** pct instead of the increment — producing absurd 1000%+ daily totals and 100–155% single-bucket peaks. Validated against the real ~2400-record file.

**How to apply:** Detect a real 5h-window reset by the **pct dropping** (`cur_pct < prev_pct`), not by `resets_at` changing. The intensity metric is simply `max(0, cur_pct - prev_pct)` per consecutive pair — a real reset shows as a large drop that clamps to 0 (negligible ~once-per-5h undercount). Do not reintroduce a `resets_at`-based reset signal without a large-jump tolerance. See `build_week_chart` in `src-tauri/src/usage_history.rs` and the `resets_at_jitter_without_pct_drop_is_normal_accumulation` regression test.
