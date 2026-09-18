# Dating a file from git history

Asking git when something happened to a file has two failure modes that both return a real commit with a real date, so neither announces itself. The date comes back, it is plausible, and it is the wrong event.

## The adding commit may be a restructure, not the event

`git log --diff-filter=A -- <path>` gives the commit that first put a file at that path, which is the right answer only when the path's appearance *is* the thing you are dating. A repo that reorganised a directory in one commit put every file there at once, so every file answers with that commit's date.

Group before you trust any single answer:

```
git log --diff-filter=A --format='%h %ad %s' --date=format:%Y-%m-%d -- <dir>/ | sort -u
```

One commit covering most of the directory is a restructure. Its subject says so — a restructure names the move, an ordinary change names the work it did. Measured 2026-09-18 across two repos: one commit had supplied the date for 19 of 21 files in one, and for both files in the other, while the handful added on their own carried genuine dates.

Add `-M` deliberately or not at all, and know which you want: without it, a file moved into the directory reads as added there, which is usually the event you are after; with it, git resolves the move back to the original path and answers with that file's much earlier creation.

## The pickaxe reports disappearance as readily as appearance

`git log -S"<string>"` lists every commit where the number of occurrences of that string **changed**, in either direction. So for a string in a file that was later deleted, the newest hit is the deletion, not the last time anyone wrote it — and `| head -1`, the natural thing to type, returns exactly that.

```
git log -S"<string>" --diff-filter=AM --format='%ad %h %s' --date=format:%Y-%m-%d -- <path> | head -1
```

The `--diff-filter=AM` drops the deletion and keeps everything that wrote into the file, newest first. Keep the `A`: a file can be *born* holding the string, and filtering to modifications alone then reports it as never written while the commit carrying its date sits in the log the filter excluded. Measured 2026-09-18 — one record was reported undatable by an `M`-only filter, and `AM` returned the commit that created the file with that record already marked, its subject naming the very work the record described.

The event you want may also be the deletion itself, which is the one case the filter hides. Where a file was retired by a commit that did the work its records describe, that commit is both the restructure and the close, and it is correct. So read what the deleting commit actually did before concluding a record is undatable.

Read the subject on the line before taking the date. The pickaxe matches a string, not a fact, so a hit is evidence that the string's count moved and nothing more — a subject naming unrelated work means the string is shared with something else and the search needs narrowing. Choose a string that can only exist once the thing you are dating is true: a status marker beside a record's own timestamp does it, where the record's text alone does not, because the text is there from the moment the record is written.

## A second copy of this lives in a convention version

Convention version 001-memo-backlog carries the same derivation, scoped to the memo backlog. Both
copies have already held the same `--diff-filter=M` error and needed fixing twice, so a refinement
made here is worth carrying there by hand.

Editing that README is allowed whenever no repo that already adopted the number would behave
differently afterwards — a correction that only improves future adoptions is exactly that, and the
freeze has nothing to protect. What the edit cannot do is reach a repo that already ran the
migration, because nothing re-runs a version; where such a repo is left holding the wrong result, a
later version is the instrument.

## Neither of these is dated by mtime

A filesystem timestamp is rewritten by a clone, a checkout, a rebase or a `git stash pop`, so it answers when this machine last wrote the file. Where git has never seen a file at all, its history is genuinely unreadable and the honest output is to say so — not to fall back on the one number that is always available and always about the wrong thing.
