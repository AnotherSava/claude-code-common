# Listing the commits a push actually publishes

A pre-push check that inspects "the new commits" has to compute that set from the refs git hands it on
stdin, and the obvious range is wrong for every ref except the branch whose history it is.

## Exclude what the destination already holds, not just the ref's old value

Git gives the hook `local_ref local_sha remote_ref remote_sha` per ref. The natural range,
`remote_sha..local_sha`, lists everything between the ref's old and new values, which is only the new
work when that ref is the one carrying it. Any other ref that moves over already-published commits
re-checks all of them: a bookmark ref such as `refs/review/last` advancing past `main` lists every commit
already on `origin/main` since the bookmark last moved. A check that cannot pass on those commits on
this machine (a signature made on another machine whose key this one cannot verify reads as `%G?` = `E`)
then refuses a push that publishes nothing new.

Add the destination's remote-tracking refs as exclusions:

```bash
git rev-list "$remote_sha..$local_sha" --not --remotes="$remote_name"
```

Git passes the remote's name as the hook's `$1`, or the URL when the push names no remote. A URL
matches no tracking ref, so `--remotes=<url>` excludes nothing: a new branch pushed by URL would then
have its whole history checked. Fall back to a bare `--remotes` when `$1` is not a configured remote
(`git remote | grep -qxF -- "$1"`).

Scope it to the destination with `--remotes=<name>` rather than a bare `--remotes`. A bare one also
excludes every other remote's commits, so whatever `refs/remotes/upstream/*` holds passes unchecked,
even in a clone whose `upstream` remote is not one you mean to trust.

## A second --not flips the refs after it back to included

`--not` toggles the sign of every revision that follows it, so two in one argument list cancel out:

```bash
git rev-list A..B --not --remotes=origin --not --remotes=upstream   # upstream refs are POSITIVE here
git rev-list A..B --not --remotes=origin --remotes=upstream         # both excluded
```

This bites when the exclusions are assembled from variables, such as a range string that ends in
`--not …` followed by an optional `$exempt` that carries its own `--not`. Keep the `--not` in one
place and make each optional fragment a bare ref list.

The flip does not always show up as extra commits, because rev-list excludes a commit if any negative
ref reaches it, whatever the positive ones say. So `L --not --remotes --not --remotes=upstream` still
lists nothing from upstream: the bare `--remotes` already excluded those commits before the flip
re-added them as positives. The flip only adds commits once the earlier exclusion is narrowed to
something that does not cover them, which makes it a trap that springs on a later, unrelated edit.
