---
created: 2026-11-04 05:01:17
---

# Design a push workflow that runs the gate on both Windows and macOS before pushing

The commit gate (.claude/commit-checks.sh, run by gate_pushed_tree.py in /yolo and /wrap-up) runs only on the machine doing the push. On 2026-11-03 c64a4db added claude/tests/session-scan.py, which faked a home with HOME only; Python's expanduser reads USERPROFILE on Windows, so the test failed 10 cases on Windows while passing on the Mac that pushed it. Nothing noticed until a /wrap-up on Windows on 2026-11-04, a day and several pushes later, when it blocked an unrelated change. Next step: design a pre-push step that also runs the gate on the other machine (over SSH per the machine-coordinates memory, or via its live session through the peer skill) against the exact commit being pushed, and refuses or warns when the other platform fails or is unreachable. Decide what an unreachable peer means (NOT COVERED, not a pass), how long it may take, and whether it gates every push or only those touching cross-platform code.
