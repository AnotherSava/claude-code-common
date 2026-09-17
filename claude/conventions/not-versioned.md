# What can never carry a convention version

When a repo's number says it is current, that means **every versionable convention has been adopted
here** — not that everything in `claude/CLAUDE.md` is satisfied. This file is the difference: every
convention in that file which can never carry a version, and the reason. Without it, "current" reads as a
clean bill of health for the whole guidelines file, which is
`~/.claude/memory/feedback_not_run_is_not_pass.md` at fleet scale.

Five reasons, and a convention belongs here for exactly one of them. Every other convention in that file
has a version under `claude/conventions/versions/`, where what changed, how to migrate and when it does
not apply are written down — so a convention in neither place is a gap to close, not a silence to read
past. A convention that has to keep holding after its migration hands the checker a named rule, and it is
`check.py` re-running that rule on every commit which says it still holds; the version's number only ever
says the migration ran.

Being in this file says no number can hold the convention; it does not say nothing measures it.
**Per-machine, measured on every commit** is the section where something does — a rule under
`claude/conventions/universal/`, gated by no version, failing the commit gate in every repo the moment the
property breaks. Everywhere else here, enforcement is by reading: no rule can express the property, so
nothing reports on it and a commit passes either way. Those are the two cases to keep apart when a
convention is not in the version set.

## Agent behaviour

Rules about how the assistant works, not about how a repo is arranged. Nothing on disk differs between a
session that followed one and a session that broke it, so there is nothing for a rule to read.

- **Outward communication** — never publish human-facing text without confirming the specific wording;
  draft, show, confirm, send; blanket confirmations do not exist.
- **Self-sufficiency** — act rather than ask, drive a service's API instead of handing over UI steps,
  search past transcripts before asking for context, run the project's deploy yourself, never substitute
  a workaround for the path that was asked for.
- **Retrying a dropped response** — retry `Connection closed mid-response` up to three times, and never
  claim a dead turn is yours to retry.
- **Taking over the machine** — ask immediately before every burst, offer the one-click alternative
  first, research before asking.
- **Research before trial-and-error** — read `~/.claude/learnings/` before diagnosing *and* before
  writing, and search the web rather than iterating blindly.
- **Git workflow** — never commit or push unasked, surface a cross-repo change without committing it,
  check the remote after an idle gap, prefer `git status --short`.
- **Bash conventions** — forward slashes on Windows, no `cd` drift across calls, never route a plaintext
  secret through the `!` prefix, no `python -c`.
- **Background-process hygiene** — redirect stdout and stderr, kill the whole process tree by a
  distinguishing flag, clean up before reporting done.
- **The overused-phrases blocklist** and its replacements.
- **Engineering standards** — reproduce a bug at the altitude the user hits it, notice every defect and
  fix the ones inside the surface you are touching, know which command is the real gate, weigh quality
  over development cost.
- **Refactoring safety** — search every usage before a rename and re-run whatever actually gates the
  deploy, which is usually neither the tests nor the linter.
- **Best-practice adoption is an offer** — made once per project, and recorded in project memory when
  declined.
- **Memo capture etiquette** — offer rather than impose, never record silently, never start the idea,
  surface at session start, task completion and commit, and tag `platform:` only when the memo's own
  body says the work needs that box rather than because of where it was captured. The *format* is
  versioned (v1 `memos-directory`, which is why widening it is not a convention sitting in neither
  place), but nothing on disk distinguishes a session that judged that call well from one that did
  not — an untagged memo and a memo that should have been tagged are the same file.
- **Excluding `node_modules/`** from every file and content search.
- **Consulting the official Anthropic plugin and skill repositories** before reinventing one.
- **The preamble's authoring rules** — ask clarifying questions before implementing, never add
  self-promoting attribution, use a fenced code block rather than a blockquote for text meant to be
  copied, hand over an HTML artifact as a `file:///` link, and mark what the user must replace with a
  `{{placeholder}}`.
- **Resolving a symlink before writing through it** — Write and Edit refuse to write through the
  `~/.claude/` links, so the real target path is found with `readlink` first.
- **Which Node version a new project targets** — the current-LTS default is advice at scaffold time, and
  a deliberate older pin reads identically to a stale one. The version that exists asserts that
  `engines.node` and `.nvmrc` *agree*, never which number they name.

## Code content

Properties of the source a repo contains rather than of how the repo is arranged. A linter, a review or a
generation-time hook enforces these line by line; a migration cannot, because the target shape includes
every line not yet written.

- **Python style** — type hints on every parameter and return, imports at the top in stdlib /
  third-party / local groups, no early-return guard that changes nothing.
- **Explicit state over an overloaded sentinel**, and splitting a field rather than adding a
  discriminator whose only job is to say which meaning that field currently holds.
- **Single source of logic**, and confirming the path you fix is the one that actually runs.
- **Prose and UI style** — single-line expressions preferred, sentence case for UI strings, no backticked
  code opening a sentence, parallel enumerations sharing grammatical form, no claim anchored on a current
  last item or a line number.
- **No logic, data structures, classes or exports in production code that exist only to support tests.**
- **The dashboard tray icon's three machine-interaction states** — idle, request pending, interaction
  running: a feature of one app's source rather than a shape any repo can be checked for.
- **Identity, not liveness** — the co-tenancy half that asserts every *other* tenant's marker is absent.
  No rule can read whether a publish check does that, so the version covering the naming half says so in
  its prose and hands the checker only the half a rule can measure.

## Unbounded property

True of an open, growing set of files, so one pass proves nothing about the next commit. A migration
settles nothing here, and a number advanced on one would be claiming something that expires the moment
someone appends. What could hold one is a continuing rule, re-measured on every commit — none of these
has one today, so each is enforced by reading rather than by measurement.

- **No absolute paths in committed documentation, comments, memory or learnings files.**
- **A trailing empty line at the end of every file.**
- **`requirements.txt` or pyproject kept in sync with every third-party import.**
- **Crash dumps are deleted, never added to any gitignore** — `*.stackdump`, `*.dmp`, `hs_err_pid*.log`,
  core dumps. Measured clean across the fleet today, and the rule governs every crash from here on.
- **Skills live at `.claude/skills/<skill-name>/` with `SKILL.md` as the entry point** — conformant
  across every project-local skill measured, and it governs every skill written from here on.

## Global, not per-repo

One fact about this machine or this dotfiles checkout, the same answer whichever repo is open. Recording
it per repo would be one answer copied into every repo, and the ones that are checkable already belong to
`check-install.py`, which walks its fixed list of links and git settings once per session. A fact that is
per-machine *and* per-repo is none of these, and it has a home of its own below.

- **`core.hooksPath` points at `~/.git-hooks`.**
- **Everything under `~/.claude/` is a symlink from this dotfiles repo and never a copy** — already
  `check-install.py`'s job, including the Git Bash `ln -s` failure that turns a link into a directory.
- **The contents of the global excludes file itself**, located through
  `git config --global core.excludesfile` — the version covering gitignore scope compares project
  gitignores against it and never edits it.
- **Global memory lives in `~/.claude/memory/`**, indexed once in `memory/MEMORY.md`. `CLAUDE.md`'s list
  is generated from the entries marked `{always}` there and is not edited by hand.
- **Doppler holds ad-hoc secrets** — all ten project slots are taken, so a new app gets a config in an
  existing shard rather than a project of its own.

## Per-machine, measured on every commit

One fact about how *this* machine is wired for *one* repo, which no number could ever be true of. The
record is committed, so both checkouts read the same integer while only one machine has done the work,
and what was done breaks long after any adoption — a cleared cache, a moved checkout, a Git Bash `ln -s`
that made a copy. A version here would be asserting per-machine state out of a file every machine shares,
which is what the second, gitignored record file attempted and why it is gone with the machine scope that
needed it.

So these hand the checker a rule under `claude/conventions/universal/` rather than a version. No version
gates one: it runs in every repo whatever its number, an exempt repo included, it fails the commit gate
exactly as a versioned rule does, and it names in its `FIX` the command that repairs what it found. The
class is small on purpose — a universal rule reaches every repo the moment it is committed, with no
adoption in between — so a property a repo can *adopt* belongs in a version, and only what adoption
cannot settle belongs here.

- **This machine's memory cache for the repo is a link into the committed `.claude/memory/`** —
  `universal/memory-cache-linked.py`, which recommends `bash ~/.claude/scripts/link-project-memory.sh`.
  It was v4 until it was retired, and retiring it is the sequence's one renumbering: a second machine
  arrives at a repo with the work genuinely not done, so the number read as adopted where nothing was
  wired. A repo that commits no `.claude/memory/` holds vacuously, and that is positive evidence read off
  the repo rather than an absence inferred from this machine — the convention points the cache at a
  committed directory, and with no such directory there is nothing to point at.
