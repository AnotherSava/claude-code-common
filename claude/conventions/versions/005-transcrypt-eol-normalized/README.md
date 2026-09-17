---
title: Transcrypt paths normalize line endings
rules: transcrypt-eol
---

## What changed

A path marked `filter=crypt` in `.gitattributes` stays plaintext in the working tree and is stored
as base64 ciphertext. Base64 **is text**, so git's line-ending conversion applies to it — and the
two machines sharing these repos disagree about what that conversion should be. The openssl build
behind transcrypt on Windows terminates its output lines with CRLF where macOS uses LF, so without a
positive normalization rule each clone commits the ciphertext in its own line endings and rewrites
the other's on the next round trip.

The plaintext is never involved in any of that. What a reader sees is a file nobody opened showing
up as a whole-file diff, on every cross-platform round trip, forever — and the diff is real rather
than cosmetic, because transcrypt derives each file's salt by HMAC over its contents
(`learnings/transcrypt-verify-before-commit.md`), so a working copy that differs by its line endings
re-encrypts to different ciphertext rather than to the same blob.

Two near-misses are what make the rule a positive spelling rather than a prohibition. Marking the
path `-text` looks right — the file is opaque, so "binary" reads as the careful choice — and it is
the worst option available: it disables normalization outright, which is exactly the churn above.
Dropping `-text` and stopping there is not enough either, because git then falls back to each
machine's own `core.autocrlf` and `core.eol`, which is the same per-machine drift by a quieter
route. So the rule is `text=auto eol=lf`, spelled per path, and this version brings every
`filter=crypt` line in a repo to it.

## Migrating an existing repo

There is work here when the repo-root `.gitattributes` carries a `filter=crypt` line whose effective
`text` attribute is not `text=auto` or whose effective `eol` attribute is not `eol=lf` — including
the `-text` spelling ruled out above, and including a line that names neither.

Read only the root file. Transcrypt writes its rules there and all five repos carrying one have it
there, while walking the tree would read a `.gitattributes` belonging to a repo shape under test as
though it were the host repo's own configuration — which made this dotfiles repo report itself as
deviating, before the scope was narrowed. A nested `.gitattributes` holding a crypt rule is the
by-hand check below.

Never rewrite a `filter=lfs` line carrying `-text`. An LFS pointer is generated text and the object
behind it is genuinely binary, so `-text` there is correct; printlab carries three such lines beside
its crypt lines, and sweeping them up would change how real meshes are stored.

Fetch first, and do not run this on a branch behind its upstream: the migration rewrites a committed
file, the other machine may have edited the same `.gitattributes`, and a rewrite of a line it also
changed merges cleanly into nonsense. Write the file with LF endings, and say so in the output when
a run had to convert CRLF lines — that conversion is the only change outside the crypt lines
themselves.

Two states stop the work rather than being fixed:

- **A `filter=crypt` rule matching a file git currently stores as binary** — the index's own
  line-ending reading, not a guess about the extension. Normalizing then stops being a statement
  about base64 and becomes a rewrite of real content, so ask rather than act: is that path meant to
  be encrypted at all, or is it binary that a crypt pattern has caught by accident? Nothing in the
  fleet is in that state, so a repo that hits it is the first; the reading it depends on is the `i/`
  column of `git ls-files --eol`, which is worth printing before answering. Where the path is
  genuinely binary, the crypt pattern catching it is the thing to fix — narrow that pattern and
  start again.
- **A line in the root `.gitattributes` that will not classify.** Print it verbatim and stop. The
  shapes to read are a blank line, a `#` comment, an `[attr]` macro definition, and a pattern
  followed by attributes where the pattern carries no quote, no backslash and no character class. A
  quoted pattern with a space in it is the realistic refusal — git accepts it, this migration cannot
  rewrite it safely, and skipping it would fix the readable rules beside it while leaving that one
  silently unchanged.

Git refusing to answer at all — an ownership refusal, a missing binary, a pathspec form this git is
too old for — is a question rather than a finding, because "no crypt-marked file is stored as
binary" and "nobody could be asked" are different facts and only the first is a reason to proceed.

What the rewrite loses, and how to compare it: `git diff @{upstream} -- .gitattributes` should show
only the crypt lines, with every comment block and every `filter=lfs` line unchanged. Read the whole
diff rather than the changed lines alone — the comment blocks above these rules carry the reasoning
per repo and several of them name `-text` explicitly, and a comment still arguing for a spelling the
line no longer uses is worse than no comment.

Afterwards:

- Look for a crypt rule this never saw, since it reads the root file only:
  `git ls-files -- '*.gitattributes'` lists every one this repo tracks, and any entry other than the
  root `.gitattributes` has to be read by hand. Nothing in the fleet has one, and transcrypt writes
  to the root, so this is a check rather than an expectation.
- Confirm the crypt files themselves survived the change unaltered:
  `git cat-file -p HEAD:<path> | head -c 10` should still read `U2FsdGVkX1`, and nothing about an
  attribute change should have touched a stored blob.
- Expect the first commit touching a crypt-marked file to carry a whole-file ciphertext change. That
  commit is where the normalization takes effect, and the churn is the one-time cost of adopting it
  rather than a fault; compare the round trip before assuming otherwise,
  `git cat-file -p HEAD:<path> | "$CRYPT_DIR/transcrypt" smudge context=default | diff - <path>`.
- Check whether this repo also wants its crypt rules covered by a pre-commit assertion. The
  attribute governs what git stores; it says nothing about whether the clone has transcrypt wired,
  and an un-initialised clone stages plaintext while reporting nothing.

## When it does not apply

The root `.gitattributes` was read and none of its rules is a `filter=crypt` line. That is positive
evidence rather than an absence: nothing here is transcrypt-marked, so there is no ciphertext for a
normalization rule to govern. A repo with no `.gitattributes` at all is the same finding — name
which of the two was found, so the reading can be checked.

Every `filter=crypt` line already ending with `text=auto eol=lf` is the other case. Four of the five
repos carrying a crypt rule were in that state when this version was written.

## Continuing rule

`transcrypt-eol` — every `filter=crypt` line in the root `.gitattributes` carries `text=auto` as its
effective `text` attribute and `eol=lf` as its effective `eol`, taking the last spelling on the line
the way git does, and git resolves each rule to exactly that with the global attributes file
suppressed and the system one disabled. The suppression is half the assertion: this machine's
`~/.gitattributes` holds `* text=auto eol=lf`, so an unsuppressed `git check-attr` answers
`auto`/`lf` for a broken line as readily as for a correct one, and no clone is obliged to carry that
file.
