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

A push that cannot go through `push.py`, such as a rebased branch that needs `--force-with-lease`, still owes every
step `push.py` would have taken after it: `review_scope.py push`, `notify_peer_pull.py`, and the CI watch below,
querying with `gh run list --repo <url of the remote pushed to> --commit <sha>` and re-querying until every workflow
a push triggers has a run. A single query made before the list catches up reads as "no CI" while a run fails.

- **CI.** For each `ci:` line `push.py` printed, make one `run_in_background` Bash call with the command it names, and
  report each result when it arrives. A `ci:` line saying no run is listed yet, or fewer runs than workflow files,
  means re-query with the `gh run list --repo … --commit <sha>` command it names until every workflow a push triggers appears, then watch the new runs
  too: the list can answer with a subset, and a run missing from it is a result nobody reads.
- **Other repos.** Run `python3 ~/.claude/skills/shared/peer_repo_changes.py`. For each repo with a `session: <name>`
  line, send that session one message naming the files this session wrote there and asking it to commit them under
  its own review. For `session: none`, start that repo's session and send it the same message, as the `peer` skill's
  **Find the session** section describes, ask included. When no session can be reached that way — a declined start,
  a refused open, a directory two sessions share, or `UNMEASURED` — name the repo and its files in the report
  instead. Print nothing for `peer-repos: none`.
