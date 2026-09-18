---
created: 2026-09-18 14:27:38
platform: macos
---

# Verify the github-status description cache warm-starts when the report is run from air

The per-machine description cache was added on 2026-09-18 in the dotfiles repo. Each machine stores the descriptions of its own clones in the gitignored tmp/github-status-descriptions.json of its own dotfiles clone; the peer resolves its own during the scan and ships them back inside its snapshot; and --report writes the new lines for each machine back to that machine over SSH.

Verified from chrome: chrome held 11 entries and air 5, disjoint; a scan reported 16 reused from the cache, 0 still to write, with air's five coming from the file on air; and --no-cache crossed the SSH hop, returning 0 reused rather than 5.

Not verified: the same warm start when the report is run FROM air. At the time it was built, air's checkout was still at the committed script and had none of this code, so a scan started there ignored its cache and proved nothing.

Next step on air, once its dotfiles clone has the change: run repos-status.py there and read the Descriptions line. It should say 16 reused from the cache, 0 still to write, not 0 reused. If it reads 0 reused, the likely cause is tmp_dir() resolving to a different directory when air is the reporting machine than when it is the peer. That exact mismatch was the bug found and fixed on chrome, where the peer wrote its cache beside the skill while the local run read the repo's tmp/. Compare the cache_path each machine reports in tmp/github-status-state.json against where the run on air actually looks.

The failure mode is graceful: a cold start re-describes everything, it does not corrupt anything.
