---
name: feedback_subagent_gets_its_own_scratch
description: A subagent prompt names a scratch subdirectory of its own and forbids deleting anything else; "delete your scratch in tmp/ when done" got the whole shared tmp/ removed
metadata:
  type: feedback
---

When a subagent or workflow agent needs scratch space, give it its own directory — `tmp/<label>/` — and say it may delete that directory and nothing else. Never phrase cleanup as "put scratch files in tmp/ and delete them when done".

**Why:** on 2026-09-27 a read-only investigation agent was told exactly that, and it ran `rm -rf <repo>/tmp`. The parent session's contact sheet, its builder and spec, the originals and the capture sandbox were all in that tmp/, and Git Bash `rm` bypasses the Recycle Bin. The files that came from git, or whose full text was in a transcript, were rebuilt. The rest had to be regenerated or were lost. The harness flagged the command as irreversible local destruction only after it had run.

**How to apply:** in every agent prompt that mentions scratch files, name the subdirectory and the deletion boundary, e.g. "scratch goes in tmp/wf-<label>/; delete that directory when done and touch nothing else in tmp/". A read-only investigation prompt should say that removing anything outside its own directory is forbidden, not merely that the task is read-only. Related: [[feedback_scratch_lives_in_project_tmp]].
