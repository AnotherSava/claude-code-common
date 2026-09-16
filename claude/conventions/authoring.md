# Authoring a convention version

Read this in the session that is changing a convention, not in one adopting it somewhere. Adopting
is `/adopt`'s job and needs none of this.

## First, decide whether anything is owed

The test is narrow: **a repo already conforming to the previous version must now do something.**
Doing something means performing a migration, or taking on a rule it was not being checked against
before. A reworded guideline is neither. A rule no repo currently violates still qualifies, because
a rule runs only where the adopted number is at or above the version introducing it — shipped
without a version, it would be enforced nowhere.

A convention no check can read is not a version at all. It belongs in `not-versioned.md` with its
reason, so that "current" keeps meaning *every versionable convention has been decided*.

## Then decide which half you are writing

Most changes are one of the two. Some are both, and then one version carries both halves.

| | Migration | Continuing rule |
|---|---|---|
| Answers | did this repo change shape | is this repo in that shape now |
| Runs | once, in the repo that is behind | at every commit, forever |
| Lives in | `versions/NNN-slug/README.md` | `rules/<name>.py` |
| Changes by | a later version; never an edit | editing the rule file |

A version folder is frozen the moment any repo runs it. Two repos run the same number at different
times, so editing one gives them different behaviour under one name, and the earlier one will never
re-run it to find out. A rule is the opposite: a better way of spotting the same violation should
reach every repo at once, including ones that adopted long ago.

So a **stricter** rule is a new version, and a **better-detecting** rule is an edit to the rule
file. The first changes what a repo is required to be; the second changes only how accurately the
requirement is measured, and a repo that starts failing on it was mismeasured rather than changed.

## The version folder

Create `versions/NNN-slug/`, where `NNN` is `max + 1` zero-padded to three digits. The number lives
in that name and nowhere else. It is the one ordering in these repos that sits in a filename,
because a migration sequence is never renumbered — everywhere else, use a field.

The folder holds a `README.md` opening with frontmatter — `title` and `scope` required, `affects`
and `rules` optional — then four sections, in order:

- `## What changed` — the convention as it now reads, and why it moved.
- `## Migrating an existing repo` — what an already-conforming repo has to do, addressed to the
  agent that will do it. Name the files, the transformation, and what to check afterwards. Where
  the migration deletes or rewrites a committed file, say what would be lost.
- `## When it does not apply` — each condition that makes the migration a no-op, with the positive
  evidence that settles it. "No `package.json` anywhere" is evidence; "no backlog file" is not
  evidence that a repo wants no backlog, and that case is a question to the user instead.
- `## Continuing rule` — the rule this version hands to the checker, named, or the words
  `None — this is a one-time migration.`

The default is prose and nothing else. A version may carry an `apply.py` beside its README where
the migration is genuinely mechanical and tedious; it takes the repo root, does the work, prints
what it did, and exits non-zero on anything it cannot classify.

Set `affects: <tool>` when the version reshapes data another tool reads, so that tool can ask the
adopted number rather than sniffing for the artifact a migration replaces. Asking about the artifact
answers for one migration and has to be rewritten for the next.

Anything asserted about a path outside the repo is `scope: machine`, always.

## Writing a rule

One file, `rules/<name>.py`, exposing exactly:

```python
def check(root: str) -> list[str]:
    """Every violation as one human-readable line. Empty list means the rule holds."""
```

A rule that cannot establish the answer raises. The runner reports it unmeasured and exits
non-zero, because a rule that could not look must never read as a rule that passed. Rules detect
and never mutate.

Two things every rule has to get right, both already paid for once:

- **Ask git what it hides.** A `package.json` inside a gitignored `venv/`, or a compose file in a
  scratch `tmp/`, is not something a person maintains — two repos in the fleet had their only
  manifest inside a virtualenv. Use `_git.ignored_untracked(root, paths)`, the index-consulting
  form, so a force-added file inside an ignored directory still counts. Any git exit outside
  `{0, 1}` means the question went unanswered: raise.
- **Abort rather than skip.** A parser that meets a line it cannot classify stops and prints it
  verbatim. Do not skip it, log it and continue, or fall back to a looser pattern. The reference
  case is the memo migration's first draft: it matched one checklist shape, ignored every line that
  did not match, checked the lines it had recognised, deleted the source, and reported "each
  asserted present exactly once". True of what it saw. Four shapes it never saw were gone. A parser
  that skips is a parser whose verification is scoped to its own blind spots.

## The gate

```
python claude/conventions/tests.py
```

Run it before committing. It asserts that version numbers are unique and contiguous and match their
folder names, that every README carries all four sections, that every name in a `rules:` field has
a file and every rule file is named by some version, and that each rule holds on a conforming tree,
fails on one that is not, and raises rather than passing when git cannot answer. This repo's
`.claude/commit-checks.sh` runs it, so a rule that would run in every other repo cannot be committed
here untested.
