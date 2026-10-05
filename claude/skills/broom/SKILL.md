---
name: broom
description: >-
  Reclaim disk space on this machine and keep it from filling again — run the reclaim report, decide
  the rows that need a human, and hunt for consumers no rule covers yet. Owns
  `claude/scripts/reclaim-disk.sh` (the deterministic sweeps and the low-space alarm) and the
  judgment the script cannot encode: classifying a consumer nobody has seen before, and deciding
  whether prevention beats sweeping.
  TRIGGER when: the volume is low or a command failed with ENOSPC; a build directory, cache or VM
  image has grown large; the low-space alarm fired; a new machine needs the alarm installed; or the
  user asks how to stop something filling the disk again.
  DO NOT TRIGGER when: the task is uninstalling an app and its data (that is `cleanup`), removing a
  Docker volume for a project (that is the project's own concern), or deleting a file the user named
  — just delete it.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# broom

Two halves, and the split is deliberate: **the script decides nothing a rule has not already
settled, and this skill decides everything else.**

- `~/.claude/scripts/reclaim-disk.sh` — report, `--apply`, `--alarm`, `--install`. Deterministic,
  auditable, runnable with no agent in the loop. Its header documents every guard and why it exists.
- This skill — run it, read it, settle the rows it refuses to settle alone, and look for what no
  rule covers. A script cannot classify a consumer it has never heard of; that is the work here.

## Running it

```bash
bash ~/.claude/scripts/reclaim-disk.sh            # report, deletes nothing
bash ~/.claude/scripts/reclaim-disk.sh --apply    # remove the FREE and REBUILD rows
```

Read the report before applying, every time, and read it *to the user* rather than summarising it as
a total: the totals are the least trustworthy part (see the clonefile note below). Each row carries a
class, and the class is the whole argument for touching it:

| Class | Means | Who decides |
| --- | --- | --- |
| `FREE` | Regenerable, nothing live depends on it | `--apply` |
| `REBUILD` | Regenerable, but only by compiling — the command is printed | `--apply`, counted separately so the price shows first |
| `RUNNING` | Regenerable, but something live depends on it now | the user, and usually the answer is no |
| `REFUSED` | A guard said no; the reason is on the line | nobody overrides this without reading the guard |

`REBUILD` is swept by `--apply` as well, and the class survives only to price it: a cold Rust
rebuild of a Tauri app is minutes and two differently-fingerprinted compiles before the commit gate
goes green once, so the summary counts those bytes apart from the free ones. Read that number before
typing `--apply` on a project you are about to build.

## Prevention beats sweeping — check this first

Before reclaiming anything, ask what is *making* the bytes. The case this was written for: a 42 GB
`target/debug` in a Tauri project whose `Cargo.toml` had no `[profile]` section at all, so every
object file carried full DWARF — 82.8% of object-file bytes, measured over 300 `.rcgu.o`. Four lines
removed roughly two thirds of all future growth:

```toml
[profile.dev]
debug = "line-tables-only"

[profile.dev.package."*"]
debug = 0
```

Clean **before** editing a profile, not after: a profile change alters every unit's metadata hash, so
a rebuild writes new filenames beside the old ones instead of replacing them, and the transient spike
lands exactly when free space is already short.

Three levers that look like the answer and are not, so do not spend a round on them: `split-debuginfo`
is already Cargo's macOS default wherever debuginfo is on, `incremental = false` trades disk for
rebuild time on the wrong axis, and `strip` does nothing for the dev profile's object files.

## When the report misses something

This is the part the script cannot do. Find the consumer, then decide where it belongs:

1. Measure honestly. `df -k /System/Volumes/Data` field 4 for free space — never a `du` total, and
   never a sum of file sizes without deduping on `(st_dev, st_ino)`, because cargo hard-links
   heavily enough to read 2.3x its allocated bytes.
2. Classify with the same three questions the script asks: does `git check-ignore -q` call it
   disposable (exit 128 means *outside any repo* — unanswered, not a yes); has anything touched it
   recently; does a live process hold a file inside it.
3. Decide the home. **A consumer that will come back gets a rule in the script. One that cannot
   recur gets deleted by hand and nothing else** — a recurring sweep for a one-off is apparatus for
   an event that will not happen again.

## Facts that cost something to learn

- **`du` cannot measure a clonefile.** macOS copies an app's signed bundle into the per-user scratch
  tree on validation and leaves the old ones behind; the clones share extents, so `du` charges each
  of Chrome's 52 clones its full 2 GiB and totals 106 GB where the volume holds about 25. Report
  those sizes as apparent and take the real figure from the `df` delta.
- **An empty `lsof` answer is two different answers.** `lsof -- <dir>` on a clone directory returns
  zero lines while Chrome is executing out of a file inside it; only `lsof +D` (recursive) sees it,
  and the COMMAND field contains a space, so parse `-Fcn` rather than columns. Ask lsof a question
  whose answer is known before trusting a negative.
- **An age gate can fail open.** `find -newermt` with a pre-1970 cutoff matches nothing, which is
  indistinguishable from a directory nothing has touched in years. That read three live caches as
  dead and deleted them. The predicate now runs a control first and treats an unusable answer as
  "live".
- **APFS frees a large delete lazily.** A 15 GiB removal showed 9.8 GiB free immediately and 37 GiB
  twenty minutes later, so a `df` delta taken straight after is a floor.
- **The scheduled half only measures.** `--alarm` reads `df` and sends one Telegram message below
  15 GiB; it never deletes. The threshold is absolute rather than a percentage because what fails is
  a build, not a ratio — 10%-free on a 228 GiB volume is 22.8 GiB, a level that is genuinely fine,
  so it would fire once and then be ignored.

## Installing the alarm on a machine

```bash
bash ~/.claude/scripts/reclaim-disk.sh --install    # LaunchAgent, daily + at login
bash ~/.claude/scripts/reclaim-disk.sh --uninstall
```

It runs `--alarm` only. The credentials come from the dashboard's `config.json` on that machine, read
by python so the token never becomes a shell word — so a machine with no Telegram configured gets a
`WARN` line and a non-zero exit rather than silence.

macOS only today. The script refuses to run anywhere else rather than guessing at a Windows
equivalent, and the Windows half is unwritten.
