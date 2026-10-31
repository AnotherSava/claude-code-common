# Turning a change set into commits

The judgement half of committing, read by every skill that groups a change set: `/yolo` and `/wrap-up` for a whole
tree, `/pr-create` after its soft reset. The mechanical half — staging, the checks, the commit itself — is
`commit.py`, and nothing here runs `git add` or `git commit` directly. Each group this produces is one
`commit.py` call: its paths and a message file.

Read `commit-message-rules.md` before drafting a message.

## What belongs in the change set

Start from `git status --short` and `git diff HEAD`, with untracked files included: they are part of the commit, and
`git diff --stat` leaves them out.

- **Only this repository's files.** A file the session wrote in another repo is handed to that repo's session
  (`peer_repo_changes.py`, then one message), never committed here.
- **A path this session never wrote may belong to a live peer still writing it.** For each path you cannot account
  for, search the transcripts under `~/.claude/projects/` for a tool call naming it, and run `ListAgents`: a peer
  reported `busy` may be mid-file. Never date the write from the path's mtime — a sibling's `git stash` round trip
  rewrites it, so hours-old content reads as touched minutes ago (`learnings/git-dating-a-file-from-history.md`).
  Commit an unclaimed file only once its author has handed it over or is idle; otherwise hold it back and name it.
  This is a hard stop for `/yolo`: ask rather than guess.
- **An inbound file can duplicate one already in the tree.** Two documents on one subject share no heading and
  conflict in no line, so nothing else reports it. Read an inbound learning or memory's title against the existing
  filenames on the same subject, and put a duplicate in front of the user rather than committing both.
- **Junk and orphaned data.** Delete untracked crash dumps (`*.stackdump`, `core`) with `rm`. Data that outlived the
  code that produced it — a tool's cache left after the tool was removed — is surfaced and kept until the user says
  otherwise. `/yolo` names either in its report and leaves them alone; `/wrap-up` asks in its summary.
- **A phantom modification** — a path `git status` lists whose content matches HEAD — stays out of every group,
  since `commit.py` refuses a whole commit that names a path with no change.

## Grouping

- **One commit per feature, fix or refactor.** No file belongs to two groups, and each group can be committed on its
  own.
- **A file holding changes that belong to different commits goes whole into the group it fits best**, and the plan
  says so. Never split a file across commits: the gate reads the working tree, so a commit holding some of a file's
  hunks holds a tree no check has read.
- **Tests and documentation go with the change they cover**, unless there is a real reason to separate them.
- **A plan under `docs/plans/` goes with the implementation it describes**, matched by slug and keywords against the
  changed paths. A plan commits alone (`docs(plans):`) only when it is the only change.
- **A plan needs a top-level `# H1`**, since the plan-archive hook takes its filename slug from it. A plan without
  one, or starting with the `<!-- plan-archive: no ...` marker, is raised before committing: suggest a slug and a
  title.
- **A finished plan moves to `docs/plans/completed/`** — one whose body, with fenced code blocks stripped, carries
  `<!-- plan-archive: done -->`, or has at least one `- [x]` and no `- [ ]`. Propose the `git mv` and move it only on
  confirmation, in the same commit as the work; `/yolo` never moves one.
- **A memo the change set delivers is closed** with one `memos.py done <n> [<n> …]` call naming all of them (two calls
  close the wrong memo, since closing renumbers), and both paths of the move go in the commit that delivers it.

## A recorded review

Run `python3 ~/.claude/scripts/review_scope.py layout` before grouping. When its first line names a reviewed tree, a
completed `review-auto` run covered exactly that tree, and the commits split in two:

- **Reviewed commits come first** and hold only the paths under `reviewed`, committed with `commit.py --reviewed`,
  which stages their reviewed content whatever the disk copy holds now. The last of them ends at exactly the
  reviewed tree.
- **Follow-up commits hold the paths under `after the review`**: everything changed once the review finished. They
  commit from the working tree as usual, with messages describing what each actually changed.
- **A path in both lists** is committed twice, its reviewed version first.
- **A confidentiality fix is the one later change allowed into a reviewed commit.** Content that must not be
  published cannot enter history even for one commit. For a path whose disk copy is the reviewed one, fix the file and
  pass it as a plain path in that commit; for a path also edited after the review, write the reviewed version out
  (`git show <tree>:<path>`), redact it, and pass `--from-file <path>=<file>`.
- **A path held back** (a peer still writing it) stays out of both lists.

Where a confidentiality fix or a held-back path changes what the reviewed commits hold, no commit ends at the
reviewed tree and `advance` leaves the bookmark where it was; say so in the plan. Run `review_scope.py advance` after
the last commit either way.

A line beginning `reviewed tree: none` means there is nothing to split; group as usual.

## Messages

Draft each message to a file under the repo's gitignored `tmp/` and pass it to `commit.py -F`, which runs
`check-commit-message.py` and refuses a failing message. What the checker cannot judge stays yours: the imperative
mood, a body that restates a comment the diff already carries, and a reason that is not yours to give. Most commits
need no body.
