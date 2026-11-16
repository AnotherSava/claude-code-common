---
created: 2026-11-16 14:31:30
platform: windows
---

# Upgrade Git for Windows on the Windows desktop from 2.39.1

Git for Windows on the Windows desktop is 2.39.1 (git --version read 2.39.1.windows.1 on 2026-11-16), and the curl it ships is dated December 2022. On 2026-11-13 that curl was the one program that mangled non-ASCII text through the cp1251 code page, while the Windows curl, Python, Node and git passed the same text intact. Upgrading replaces Git Bash, the shell every Claude Code session on that machine runs in, so do it between sessions, then re-run the commit gate.
