---
created: 2026-09-19 17:06:06
platform: windows
---

# Verify the peer cache write reaches air when the report runs from chrome

The peer description-cache write was reimplemented on 2026-09-19 in commit 147a72a, fix(github-status): write the peer cache via stdin. It no longer sends `mkdir -p '<dir>' && cat > '<path>'`, which cmd.exe rejected on every run with "The syntax of the command is incorrect."; it now pipes a generated Python program to `<PEER_PYTHON> -` with the destination path and the JSON payload inlined as literals.

Verified in one direction only: air writing to chrome. Byte-exact (sha256 equal, non-ASCII payload included), chrome's cache went from 11 to 12 entries, and the next scan served 10 of them back.

Not verified: chrome writing to air, which the same commit also changed. chrome's config.env sets PEER_SSH to air and PEER_PYTHON=python3, so the program will be piped to `python3 -` there. It cannot be tested from air — claude/learnings/windows-openssh-over-tailscale.md records that a session reaching chrome over SSH cannot exercise chrome's own outbound ssh, so the only honest test is a report started on chrome itself.

Next step on chrome, once its dotfiles clone has 147a72a: run repos-status.py --report and watch stderr for 'WARNING: air's descriptions could not be stored on it'. Its absence is the pass. Then confirm air's tmp/github-status-descriptions.json actually gained the entries, rather than trusting the silence.

The failure mode is graceful: the warning prints and the cache is re-read next run. Nothing is corrupted either way.
