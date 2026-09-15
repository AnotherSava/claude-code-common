---
created: 2026-04-09 15:55:02
---

# Collapse the duplicate retry helper in the fetch wrapper

two call sites grew their own copy, and only one of them backs off
