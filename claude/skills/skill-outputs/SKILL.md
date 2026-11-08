---
name: skill-outputs
description: >-
  Collect what a skill actually printed across every project's sessions since a given moment and
  show it on one tailnet page, one tab per run and a toggle per section, so a change to a skill's
  output format can be judged against real runs. Supports /wrap-up's summary so far.
  TRIGGER when: the user wants to see, compare or review a skill's real outputs across sessions or
  projects, such as "show every wrap-up summary since we changed it".
  DO NOT TRIGGER when: the question is about one session's transcript, which is read directly, or
  about Claude's reply style in general (that is `tune-output`).
allowed-tools: Bash(python3 ~/.claude/skills/skill-outputs/scripts/collect.py:*), Bash(python ~/.claude/skills/skill-outputs/scripts/collect.py:*), Bash(python3 ~/.claude/skills/shared/tailnet_publish.py:*), Bash(python ~/.claude/skills/shared/tailnet_publish.py:*), Bash(git -C ~/.claude/skills/wrap-up log:*), Read, Edit, Write
---

# Skill outputs

Put every run of a skill's output since a moment side by side, so a format change is judged on what the skill
really wrote rather than on what its SKILL.md asks for.

## Context
- Changes to /wrap-up's summary step: !`git -C ~/.claude/skills/wrap-up log --format='%h %aI %s' -s -n 8 -L '/^### 7\./,/^### 8\./:SKILL.md'`

## Process

1. **Name the skill.** `/wrap-up` is the only skill `scripts/collect.py` recognises. For any other, stop here and
   generalise the script against that skill first: replace the `"wrap-up"` passed to `invokes_skill()` and
   `_is_wrap_up_summary()` with what identifies the new skill's output, worked out from its real transcripts, and
   extend this file's Context and steps to match. Do not generalise for a skill nobody has asked about yet.

2. **Pick the moment.** Use what the user named — a commit, a date, "since we changed X". When they named a change
   rather than a moment, take it from **Changes to /wrap-up's summary step**: the newest commit there whose subject is
   that change, and its author date with offset. Say which commit and time you used. When the format change is still
   uncommitted, no run has used it yet; say so and stop.

3. **Collect.** `python3 ~/.claude/skills/skill-outputs/scripts/collect.py --since <ISO time with offset>` (`python`
   on Windows). It prints one line per run found and the page's path, in the dotfiles repo's gitignored `tmp/`.

4. **Check what was left out.** A `/wrap-up` run that stopped before its summary — a failing gate, a review that never
   recorded — has no summary to collect. When the user expects a run that is missing, find its transcript under
   `~/.claude/projects/` and say why it is absent rather than widening the detector.

5. **Publish** the page with `python3 ~/.claude/skills/shared/tailnet_publish.py publish <path>` and hand over the URL
   it prints as a Markdown link, with the number of runs, the projects they came from, and the moment used.

## Out of scope
- Do NOT edit the skill whose output is being reviewed; this skill only shows its runs.
- Do NOT read the other machine's transcripts. The page covers this machine's sessions, and the report says so.
