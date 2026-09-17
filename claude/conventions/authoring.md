# Authoring a convention

Read this in the session that is changing a convention, not in one adopting it somewhere. Adopting
is `/adopt`'s job and needs none of this.

## First, decide whether anything is owed

The test is narrow: **a repo already conforming to the previous version must now do something.**
Doing something means performing a migration, or taking on a rule it was not being checked against
before. A reworded guideline is neither. A rule no repo currently violates still qualifies, because
a rule runs only where the adopted number is at or above the version introducing it — shipped
without a version, it would be enforced nowhere.

A convention no check can read is not a version at all. It belongs in `not-versioned.md` with its
reason, so that "current" keeps meaning *every versionable convention has been decided*. A
convention a check can read but no single number could ever be true of is not a version either, and
the next section says what it is instead.

## Then decide which of the three you are writing

Most changes are one of the first two. Some are both, and then one version carries both halves. The
third is rarer than either and has its own test, last of the paragraphs under the table.

| | Migration | Continuing rule | Universal rule |
|---|---|---|---|
| Answers | did this repo change shape | is this repo in that shape now | is it in that shape here, on this machine, now |
| Runs | once, in the repo that is behind | at every commit, forever | at every commit, in every repo, forever |
| Gated by | its own number, against the repo's record | the version that introduced it | nothing |
| Lives in | `versions/NNN-slug/README.md` | `rules/<name>.py` | `universal/<name>.py` |
| Changes by | a later version; never an edit | editing the rule file | editing the rule file |

A version folder is frozen the moment any repo runs it. Two repos run the same number at different
times, so editing one gives them different behaviour under one name, and the earlier one will never
re-run it to find out. A rule is the opposite: a better way of spotting the same violation should
reach every repo at once, including ones that adopted long ago.

So a **stricter** rule is a new version, and a **better-detecting** rule is an edit to the rule
file. The first changes what a repo is required to be; the second changes only how accurately the
requirement is measured, and a repo that starts failing on it was mismeasured rather than changed.

A **universal** rule is for the property no number could ever be true of, because it is not about
the repo alone. The one in the set is the memory-cache link: `claude/scripts/link-project-memory.sh`
points this machine's Claude memory cache at the repo's committed `.claude/memory/`, and that is
per-machine work — the same repo arrives on the second machine with it genuinely not done, and it
breaks years after any adoption from a cleared cache, a moved checkout, or a Git Bash `ln -s` that
made a copy. It was a version until it was not, and the per-repo machine record that tried to carry
it is gone with it.

The price is the one the versioned half exists to avoid: a universal rule reaches every repo the
moment it is committed, with no adoption in between, and fails that repo's commit gate on the same
exit code 1 as any other rule — in a session that never asked for it and is in the middle of
something else. An exempt repo runs it too, since nothing gates it. So the bar is high and the class
is small on purpose: where a repo could sensibly adopt the property, write a version.

## The version folder

Create `versions/NNN-slug/`, where `NNN` is `max + 1` zero-padded to three digits. The number lives
in that name and nowhere else. It is the one ordering in these repos that sits in a filename rather
than in a field: the number and the slug both come from that name, so the two can never disagree —
everywhere else, use a field.

Retiring a version is where that ordering is paid for, and it has been paid once: the folder goes,
every number above it moves down one, and every committed record naming one of those numbers is
rewritten by hand, in the repo that holds it. Nothing automates that last part, and a number in a
commit message, a memo or a transcript older than the change still points at the migration it named
then. So retire a version only when it has stopped being a migration at all — which is what happened
to the memory-cache one, now a universal rule. A version that is merely wrong is superseded by a
later one.

The folder holds a `README.md` opening with frontmatter — `title` required, `affects` and `rules`
optional — then four sections, in order:

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

## Writing a rule

One file — `rules/<name>.py` for a rule a version introduces, `universal/<name>.py` for one nothing
gates — exposing exactly:

```python
def check(root: str) -> list[str]:
    """Every violation as one human-readable line. Empty list means the rule holds."""
```

A rule that cannot establish the answer raises. The runner reports it unmeasured and exits
non-zero, because a rule that could not look must never read as a rule that passed. Rules detect
and never mutate. Both directories are on the import path, so either kind imports the shared
helpers beside the versioned rules — `_git` above all — by bare name.

A universal rule also defines `FIX`, a module-level string naming the command that repairs what it
found, which the checker prints as a `fix:` line under the finding. It is mandatory there and the
gate refuses a universal rule without one: a repo meets such a rule already failing, with no version
README anywhere to read, so `FIX` is the whole of what that session is told to do. A versioned rule
may carry one and does not have to, because its version's folder is where its migration is written.

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
a file and every rule file is named by some version, that no universal rule is also named by a
version and no filename sits in both rule directories, that every universal rule names a `FIX`, and
that each rule holds on a conforming tree, fails on one that is not, and raises rather than passing
when git cannot answer. A rule this file builds no trees for prints as NOT COVERED, counted nowhere:
that is the gate asking for a case, not passing the rule. This repo's `.claude/commit-checks.sh`
runs it, so a rule that would run in every other repo cannot be committed here untested.
