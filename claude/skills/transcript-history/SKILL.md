---
name: transcript-history
description: >-
  Search and read past Claude Code conversations, this project's or any other's, and list the
  projects worked in recently — every session the private transcripts archive has captured on
  either machine, including sessions Claude Code's retention has already deleted from its own
  store, plus today's.
  TRIGGER when: the user refers to something discussed or decided in an earlier session ("what did
  we decide about X", "the script we fixed last month", "the usual config"); you need the reasoning
  behind a past change that the repo, its memory and git history do not record; or CLAUDE.md's
  rule to search past conversation before asking for missing context applies; or the user asks
  which projects they worked in recently, or when they last touched each one.
  DO NOT TRIGGER when: the answer is in the current conversation, the repo, project memory or git
  log; or the history wanted is Perplexity's, not Claude Code's.
allowed-tools: Bash(readlink -f ~/.claude/skills), Bash(test -f:*), Bash(python:*), Bash(python3:*), Read
---

# Transcript history

The archive and its query script live in the private `transcripts` repo, checked out beside this
dotfiles repo on each machine. This skill only finds that checkout and runs its script; the script's
own docstring is the reference for what it reads and why.

## Context

- Skills directory: !`readlink -f ~/.claude/skills`

## Process

1. **Locate the script.** **Skills directory** ends in `/claude/skills` inside the dotfiles repo.
   Drop those two components to get the dotfiles repo root; the script is
   `transcripts/bin/history.py` in the directory that contains that root. Run `test -f <path>`.
   If it fails, stop and tell the user the transcripts checkout is not beside the dotfiles repo on
   this machine. Do not search the disk for another copy, and do not fall back to grepping
   `~/.claude/projects`, which loses every session retention has deleted.

2. **Pick the interpreter.** Use `python3` on macOS and `python` on Windows.

3. **List the project's sessions first**, unless the user named a session:

   ```bash
   python <path> [--project <project>] [--machine local] sessions
   ```

   The project defaults to the current repo's GitHub origin (`owner/name`), or its directory name
   when it has no origin. Pass `--project` for a different one, as a folder name or `owner/name`; a
   folder name resolves to its repository, so two folders cloned from one repo give one history.
   Put it before the subcommand as shown: it and `--machine` belong to the script itself, so placed
   after `sessions`, `search` or `show` they fail as unrecognized arguments. The header names the
   repository, and every line starts with the machine it came from.

4. **Search for the topic.** Every term must appear in a turn, case-insensitively:

   ```bash
   python <path> [--project <project>] [--machine local] search <term> [<term> ...] [--limit N]
   ```

   Prefer distinctive nouns (a file name, a flag, an error string) over phrases. If a term finds
   nothing, retry it with a synonym before concluding the topic was never discussed.

5. **Read the session** whose hits look relevant. A unique id prefix is enough:

   ```bash
   python <path> [--project <project>] [--machine local] show <session-id-prefix> [--tools]
   ```

   Add `--tools` to see which tools each reply used. Results are omitted either way. A long
   session prints a lot, so pipe it through `sed -n` to read it in ranges.

6. **To list projects by last interaction instead**, skip steps 3 to 5 and run:

   ```bash
   python <path> [--machine local] recent [--days N]
   ```

   It lists every project the user typed a prompt in during the last N days (default 1, fractions
   allowed), newest first, one machine's block after the other's; the script's docstring defines
   which prompts count as typed. A row's prompt is the newest one in the window with words in it,
   so it is blank when every prompt there was a bare slash command such as `/yolo`; the row is
   still a real interaction. A project is named by its repository (`owner/name`) when one
   resolves, and otherwise by its folder name, or `?` for a record with no folder, so a bare name
   says nothing about whether the folder was ever a repository. `--project` is ignored here.

7. **Report what the history says**, citing the date, and the session-id prefix for anything found
   with `sessions`, `search` or `show` (`recent` prints none). Any timestamp you quote is already
   in local time.

## Reading the output

- Each command queries both machines by default. Pass `--machine local`, before the subcommand, to skip the other one.
- **A machine line reading `NOT COVERED` means that machine was not searched.** Say so whenever
  you report a negative result, because a topic missing from the machine you could reach may still
  exist on the other. Exit status 2 means the same thing. The other machine also reads as
  `NOT COVERED` when its `transcripts` clone is older than this one's and rejects the options
  forwarded to it, so when it was reachable, name a stale clone as the likely cause.
- The two machines are the same user's, so one project's sessions can be split between them.
  Treat the combined list as one history.

## Out of scope

- Do NOT write to, move or delete anything in the archive: it holds the only copy of some sessions.
- Do NOT read the archive's raw files directly. The script already merges the vault with the live
  store and confirms each session's project by its recorded working directory.
- Do NOT quote credentials or secrets you come across in a transcript.
