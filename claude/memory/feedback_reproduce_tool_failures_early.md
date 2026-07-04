---
name: feedback_reproduce_tool_failures_early
description: When an external tool keeps failing through code-side fixes, reproduce with the real artifact early instead of theorizing
metadata:
  type: feedback
---

When an external tool (slicer, compiler, packager, CLI) keeps failing **through several code-side "fixes"**, stop theorizing about its internals and **reproduce with the actual artifact early** — inspect the file it produced and run the real command yourself.

**Why:** static reasoning about another program's internals is low-yield and easy to get confidently wrong. One real reproduction collapses the guesswork.

**How to apply:** after the second failed fix to a tool-invocation bug, switch modes — (1) inspect the exact artifact the pipeline produced (unzip it, print the relevant fields/coordinates), and (2) run the tool's real command on that artifact and read the *full* output (apps often truncate the captured error). Only then form the fix.

Real case (printlab, 2026-06-27): a multi-plate-3MF slice kept failing "no object inside print volume" through an arg-reorder fix, a prune fix, and a recenter fix. Inspecting the stored plate file (build transform at x=435, off-bed) and reproducing the exact `docker run … orca-slicer` slice made the cause unambiguous — and ultimately revealed the failing plate was genuinely unsliceable geometry, a different problem than assumed. Builds on the global "Research before trial-and-error" rule: that's about web research; this is about local reproduction.
