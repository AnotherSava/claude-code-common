# Syncing before a commit run, and what follows the push

The steps either side of committing that `/yolo` and `/wrap-up` both take. Each skill links here rather than
restating them, and says only how it raises a diverged branch to the user.

## Sync

Run `git fetch` and `git rev-list --left-right --count @{upstream}...HEAD`, then act on what they say:

- **Behind only:** bring the branch up to date by following the `pull` skill's procedure
  (`~/.claude/skills/pull/SKILL.md`), which moves aside only the local edits the incoming files collide with.
- **Both sides non-zero:** the branch has diverged, and a rebase is the user's call. The calling skill says how it
  puts that to them.
- **No upstream** (`rev-list` cannot resolve `@{upstream}`): continue; `push.py` sets one up on the first push.
- **A fetch failure:** say so in the report and continue, since the push itself refuses a stale branch.

## After the push

- **CI.** For each `ci:` line `push.py` printed, make one `run_in_background` Bash call with the command it names, and
  report each result when it arrives. A `ci:` line saying no run is listed yet, or fewer runs than workflow files,
  means re-query `gh run list --commit <sha>` until every workflow a push triggers appears, then watch the new runs
  too: the list can answer with a subset, and a run missing from it is a result nobody reads.
- **Other repos.** Run `python3 ~/.claude/skills/shared/peer_repo_changes.py`. For each repo with a `session: <name>`
  line, send that session one message naming the files this session wrote there and asking it to commit them under
  its own review. For `session: none` or `UNMEASURED`, name the repo and its files in the report, since no session
  will pick them up. Print nothing for `peer-repos: none`.
