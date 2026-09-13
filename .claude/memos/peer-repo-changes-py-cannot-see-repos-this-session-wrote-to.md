---
created: 2026-09-13 05:56:24
---

# peer_repo_changes.py cannot see repos this session wrote to via a script

`/commit` step 10 hands off work a session left uncommitted in *other* repos, and it decides what to hand off from `peer_repo_changes.py`, which reads the session transcript for file-tool writes outside this repo. A session that wrote to a peer repo through a helper script — Bash running python, a migration, a generated sweep — is invisible to it.

Measured 2026-09-13: the memo-storage migration wrote 128 files across 11 repos from a throwaway script, and the check still returned:

    peer-repos: none — this session wrote no files outside this repository
    (transcript resolved via session-id; shell-written files are not visible to this check)

The script is honest about its own blind spot in that second line, but step 10 reads only the verdict: `peer-repos: none` means "say nothing and go to step 11". So ten repos with 63 migrated open memos sat uncommitted with nothing routing them, and the one mechanism built to prevent exactly that reported clean.

The failure shape is the one [[feedback_not_run_is_not_pass]] names: a check that cannot distinguish "nothing to hand off" from "cannot see what there is to hand off" turns an open problem into a closed-looking one. Note the perverse gradient — the more work a session does through a script rather than by hand, the less the handoff sees.

Not obvious what the fix is, which is why this is a memo and not a patch:

- Making the check scan `PROJECTS_ROOT` for dirty repos is explicitly ruled out by the design, and rightly — the global rule is that a repo nobody here touched is that project's own business, and reporting it is the unsolicited status `peer_messaging.md` forbids. Scope must stay "repos this session wrote to".
- So the gap is in *observing the write*, not in widening the net. Candidates worth weighing: parse `cwd`-changing and path-bearing arguments out of Bash tool calls in the transcript; or have the check report `NOT COVERED` rather than `none` when the session ran Bash commands it could not attribute, so the verdict stops looking clean.

Whatever it becomes, the output must stop letting "I looked and there is nothing" and "I cannot look" share a single word.
