---
name: feedback_fixture_must_exceed_the_cap
description: A fixture smaller than a threshold cannot exercise the threshold and reports success — size it past every cap, page size and top-N in the code under test
metadata:
  type: feedback
---

A test fixture sized below a cap never reaches the branch the cap guards, and the run passes. Grep the code under test for every cap, page size, top-N, truncation limit and `MAX_*` constant, and size the fixture past each one before calling the verification done.

2026-09-15: a new `platform:` tag for the memo backlog was verified end-to-end on a scratch repo holding **three** memos — CLI, the status-bar hook's three modes, and four mutations of the new code, all green. The status bar renders `memos[:MAX_SHOWN]` with `MAX_SHOWN = 3`, so truncation never fired in the fixture. On the real nine-memo backlog the two tagged memos sat sixth and eighth, and the bar showed no tag at all — on the one surface the whole field had been justified by. Nothing in the suite, the mutation pass or the scratch run could see it; it was found by re-reading the session transcript afterwards.

**Why:** a cap turns the fixture size into a silent precondition. Every instrument reports on what it reached, and none of them reports what it did not — so a fixture at exactly the boundary is the worst case of all, since it looks like full coverage of a list.

**How to apply:** count the constants first, then pick the fixture size, rather than picking a convenient small number and checking the output looks right. Two elements above each cap is enough. Sibling of [[feedback_not_run_is_not_pass]] — there the check cannot tell success from never-ran, here the branch is never reached at all — and of [[feedback_sample_level_miss_edge]], which is the same blindness in time rather than in size.
