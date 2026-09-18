# Authoring a convention

Read this in the session that is changing a convention, not in one adopting it somewhere. Adopting
is `/adopt`'s job and needs none of this.

## First, decide whether anything is owed

The test is narrow: **a repo already conforming to the previous version must now do something.**
Doing something means performing a migration, or taking on a rule it was not being checked against
before. A reworded guideline is neither. A rule no repo currently violates still qualifies, because
a rule runs only where the adopted number is at or above the version introducing it — shipped
without a version, it would be enforced nowhere.

**One version, one prerequisite.** Scope a version by the condition that decides whether it applies,
not by topic. Where two changes no-op under the same condition, they are one version: a repo with no
`package.json` should answer that walk once, not three times, and a repo with a backlog should get
every transformation that backlog needs in one pass.

The corollary matters more. A version written as a follow-up to an earlier one — "now that the
directory exists, date the names in it" — assumes a repo sitting in the intermediate state. Check
that such a repo exists before writing it: where none does, the two are one version, and splitting
them invents a state nobody is in. Merging four such pairs on 2026-09-17 took the set from 14 to 9
and dissolved a real contradiction, where the later version existed partly to withdraw an escape the
earlier one allowed.

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

That makes editing a version folder a thing to avoid, not a thing forbidden. The harm is concrete and
therefore checkable: work out whether any repo that already adopted this number sees different
behaviour afterwards. Where none does — the number is unadopted anywhere, or the edit touches prose
no migration reads — the edit is safe and the freeze has nothing to protect. Removing a frontmatter
field on 2026-09-17 passed that test: the gate answered identically at every adopted number, and one
repo held a record.

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

**Per-machine is necessary and not sufficient: the failure has to be silent too.** A rule belongs
at every commit in every repo only where nothing else would report the violation. The memory-cache
link qualifies twice over — it breaks years after any adoption, from a cleared cache or a moved
checkout, and stays broken with nothing saying so. A Windows ACL that leaves tracked files writable
but not deletable is just as per-machine and does not qualify: `git mv` answers `Permission denied`
at the moment of the rename, in the session that needed it, so a universal rule would re-report an
error the action already raised. Considered and declined on 2026-09-18. What was missing there was
the reading rather than the detection — that git's refusal names an ACL and not a git bug — and
that is `learnings/windows-file-acl-delete-denied.md`, which a filename search reaches before
anyone starts theorising.

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

The folder holds a `README.md` opening with frontmatter — `title` required, `rules`
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

When a version reshapes data another tool reads, that tool gates itself on the number: it declares the
version it needs as a constant beside the code that reads the format, and calls `engine.behind`.
Changing a stored format means editing that reader anyway, so the constant is bumped in the same pass.
Sniffing for the artifact a migration replaces answers for one migration and has to be rewritten for
the next.

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
