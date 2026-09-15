# Memos

Off-task ideas captured during sessions, to revisit later. Managed by `/memo`; open items resurface at session start, task completion, and commit.

_No open memos._

- [x] 2026-06-30: Pin the docs theme to a tag — an unpinned `remote_theme` rebuilds from the theme's default branch, so a rendered page can change with no commit here
- [ ] 2026-07-14 09:02 — Collapse the duplicate retry helper in the fetch wrapper
* [ ] 2026-07-19 19:57 — Widen the status row so a long branch name stops wrapping
-  [x] 2026-08-02 11:40 — Stop the nightly job mailing an empty report when nothing changed
- [ ] 2026-08-21 07:15 — The transcode cache grows without bound on the media box and nothing
  prunes it: one directory per play survives a job that exits on its own, while a job stopped
  from the client logs a delete and leaves nothing behind. Decide between a periodic sweep and
  a scheduled cleanup task before the volume fills.
- [ ] 2026-09-03 22:11 — Give the importer a dry-run flag
