---
name: github-status
description: >-
  Cross-machine overview of your GitHub-owned local clones — every repo with
  pending work (uncommitted changes, unpushed commits, inbound remote commits),
  open issues, or convention versions still to adopt, merged across this machine
  and its peer, with branch, counts, age of the oldest pending work, how far
  behind /adopt each clone is, and a one-line summary per working machine. Prints a box
  table and writes a self-contained HTML report. Each run fetches every repo's
  origin on both machines so the counts reflect the current remote.
  TRIGGER when: user asks "/github-status", wants a cross-project overview of
  their repos, "which repos have unpushed commits", "what's new on remotes",
  "what have I been working on", "which repos are behind on conventions", or
  "what is uncommitted on the other machine".
  DO NOT TRIGGER when: user is asking about a single specific repo (use
  `git status` / `git log` directly).
allowed-tools: Bash(python ~/.claude/skills/github-status/scripts/repos-status.py:*), Bash(python3 ~/.claude/skills/github-status/scripts/repos-status.py:*), Bash(test -f ~/.claude/skills/github-status/config/config.env:*), Bash(grep -q PEER_SSH ~/.claude/skills/github-status/config/config.env:*), Bash(tput cols:*), PowerShell, AskUserQuestion, Read(~/.claude/skills/github-status/config/config.env), Write(~/.claude/skills/github-status/config/config.env)
---

## Context
- Config file: !`test -f ~/.claude/skills/github-status/config/config.env && echo PRESENT || echo MISSING`
- GitHub user (script default): AnotherSava — override via `GITHUB_USER` env var

## 1. Ensure the config exists

If **Config file** above is `PRESENT`, go straight to step 2. Otherwise ask the user (via one
`AskUserQuestion` call carrying both questions) for:

1. **Projects root** — the absolute path to the directory holding all their local clones. Suggest
   `$HOME/Projects` on macOS, `$HOME/code` on Linux, `D:/projects` on Windows.
2. **The other machine** — whether there is a second machine to include, and if so its SSH target
   (`user@host`). Offer "no other machine" as an option; a single-machine report is a supported
   configuration, not a degraded one.

Then write `~/.claude/skills/github-status/config/config.env`:

```
# github-status skill config — gitignored, user-specific
PROJECTS_ROOT="<absolute path>"
MACHINE_NAME="<what to call this machine in the report>"
PEER_SSH="<user@host>"
PEER_PYTHON="<the interpreter name on the peer>"
```

- Drop the `PEER_SSH` and `PEER_PYTHON` lines entirely when there is no second machine.
- `PEER_PYTHON` is `python` when the peer runs Windows and `python3` everywhere else — a Windows
  install has no `python3` on PATH, and a Homebrew macOS install has no bare `python`. Getting this
  wrong shows up as the peer row reading `not reached`.
- `MACHINE_NAME` defaults to the hostname when omitted. Set it when the hostname is long or does not
  match what the user calls the machine.

The peer needs nothing installed and nothing configured from this side beyond those two lines: the
scan is piped into its interpreter over SSH, and it reads its own `config.env` for its own projects
root. Key-based SSH must already work non-interactively (`ssh -o BatchMode=yes <user@host> true`).

## 2. Run the scan

**First, detect the terminal width** so the table fills the screen. The script's stdout is piped,
which hides the real width from it, so determine it yourself:

- **Windows:** use the **PowerShell tool** to evaluate `$Host.UI.RawUI.WindowSize.Width`. Use the
  PowerShell tool specifically — running `powershell.exe` from the Bash tool returns the wrong value
  (it gets its own console, not the real one).
- **macOS/Linux:** run `tput cols` (or read `$COLUMNS`).
- If you can't determine it, omit `--width`; the script falls back to the `GHS_WIDTH` line in
  config.env, then to 120.

**Then subtract a gutter margin of 2** and pass the result as `--width <N>`. Claude Code's TUI indents
message/tool output by a couple of columns, so a table exactly as wide as the window has its right
border clipped off-screen — the margin keeps the whole table visible (e.g. a 156-column window →
`--width 154`).

Run `python ~/.claude/skills/github-status/scripts/repos-status.py --width <N>` (`python3` on macOS
and Linux; drop `--width` if undetected). It scans both machines concurrently, so it costs the slower
of the two rather than their sum. Output has three parts:

1. **Machine summary**, one line each: name, OS, projects root, repos discovered, the convention step
   set that machine measured against (`conventions v13 (8f0f4b0)` — its own dotfiles checkout, which
   is what every CONV cell in its column is relative to), and how long ago it was scanned. A machine
   that could not be reached prints `NOT REACHED` with the SSH error instead, and drops out of the
   table entirely — it is named once here rather than under every repo.
2. **The table**, fixed-width. A repo appears if any machine has pending work, the repo has open
   issues, or some clone is behind on conventions; everything else is filtered out. Repos are
   **grouped**: one line per machine under a single PROJECT cell, sorted by AGE ascending (freshest
   pending work first, oldest at the bottom). Repos with no pending work have no age, so that whole
   tail is ordered by the widest convention gap instead, furthest behind first. Columns appear only
   when some cell fills them:
   - **PROJECT** is always present — the clone path relative to the projects root, taken from this
     machine where it has the repo. It doubles as the key you write descriptions against in step 3.
   - **MACHINE** appears only when two machines were reached. The cell carries the machine's state
     when it has no metrics to show: `chrome clean` (present, nothing pending anywhere, conventions
     included) and `chrome absent` (no clone there) are different facts, and a blank cell would say
     both.
   - **BRANCH** shows only for a machine on something other than `main`/`master`.
   - **UNPUSHED** — commits in `@{upstream}..HEAD`.
   - **REMOTE** — commits in `HEAD..@{upstream}`. A trailing `✓` (e.g. `4 ✓`) means the script
     auto-pulled them; the count shown is the pre-pull one. Auto-pull runs on **both** machines, only
     where that clone has no uncommitted changes, and `--ff-only` means a diverged branch fails safe
     and keeps its count without the `✓`.
   - **LOCAL** — `N (+A/-D)`, the porcelain entry count with the line-level diff. Either side of
     `+A/-D` is omitted when 0; a change set with no line diff at all (an untracked dir of binaries)
     shows just `N`.
   - **AGE** — age of the oldest pending work on that machine, as the older of (oldest uncommitted
     file mtime, oldest unpushed commit date), in the compact form `5m` / `3h` / `2d` / `4mo` / `1y`.
     A deletion leaves no mtime behind, so a clone with only deletions falls back to whatever commits
     exist and can show a blank AGE against a filled LOCAL.
   - **CONV** — convention versions that clone has not decided: the same number `/adopt` and the
     session-start notice give, read from `.claude/conventions.tsv` against that machine's step set.
     A `+N` suffix (`3+1`, or `+1` alone) counts machine-scoped steps the repo has decided but that
     machine has not wired. `?` means the record could not be read — the report says why. Blank means
     current, exempt, or someone else's repo. This is per machine, not per repo: the gitignored half
     of the record does not travel, and the two dotfiles checkouts are routinely at different commits.
   - **ISSUES** — open issues (PRs excluded) on the repo's own `origin`, printed once per repo since
     it is a property of the repo rather than of a machine. Whichever machine's `gh` could answer
     supplies it, and a repo the peer alone has but could not answer for is asked again from this
     machine — `gh` needs no clone, so an unauthenticated `gh` over there neither blanks the column
     nor drops a clean-but-ticketed repo out of the report. Blank means zero, issues disabled, or
     neither machine could ask.
   - **DESCRIPTION** — `<analyze below>` on every machine line with pending work, so a repo busy on
     both carries two. It is the one cell that wraps, under its own machine's line. **You fill these
     in** per step 3. On a narrow terminal the column is **dropped entirely** rather than squeezed,
     with a line under the table saying so: eight fixed columns leave it under ~34 characters, a
     one-line summary then wraps to four or five rows, and the table grows past three times the height
     of the report — measured at 122 lines for 18 repos on an 80-column terminal, against 42 without
     it. Nothing is lost; the HTML carries every description in full. Still write them in step 3, and
     still paste the table as it comes.
3. **Detail sections** — `git status --porcelain` and `git log @{upstream}..HEAD` per repo per
   machine, tagged `[machine]` when both were reached. This is raw material for step 3, **not** part
   of the user-facing report: do not paste it back to the user.

The run also writes a state file next to the report. Step 3 reads it rather than re-scanning, so the
descriptions land on exactly the state they were written from.

## 3. Write the descriptions and render the report

**A description belongs to a machine, not to a repo.** The table marks `<analyze below>` once per
machine with pending work, and each one is owed its own **one-line description** of what that
machine's in-flight work accomplishes (≤ ~80 chars; the user-visible change or theme, not file- or
commit-level detail). A repo working on both machines gets two, written from that machine's detail
section alone — one line covering both leaves whichever machine it did not describe unexplained.

**Key each entry by the PROJECT cell — or by whatever that machine calls the folder.** The two differ
when a repo is cloned under different names, and the title comes from whichever machine lists first
even if that one is clean, so the column you are describing can be showing the *other* name. Either
resolves; an alias two repos share is refused rather than guessed.

**Describe the work; leave the bookkeeping to the columns.** Both surfaces already state counts,
branches, issue totals and absence next to the machine they belong to — the HTML in a per-machine
column, the table in its own columns — so repeating any of them in the description says the same
thing twice and pushes out the part only you can write. Keep out:

- commit counts ("4 commits behind", "3 ahead") — REMOTE/UNPUSHED and the HTML metrics carry them;
- a non-default branch — the BRANCH column and the HTML's `on <branch>` carry it;
- open-issue totals — the ISSUES column and the card's issue chip carry them;
- the convention gap — the CONV column and the card's `N conventions behind` carry it, and an
  unadopted step is work nobody has started rather than work in flight, so it is not what a
  description is for;
- "not cloned on chrome" — the MACHINE cell says `chrome absent`, and in the HTML that column is
  simply empty;
- **the machine's own name.** Every description already sits in that machine's column, under its
  header, so naming it repeats the header and costs characters the summary needs. Write "An untracked
  config/ and an .env.example edit.", not "on chrome, an untracked config/ …".

- When a machine has both uncommitted changes and unpushed commits, combine them by theme rather than
  by count: "Mid-flight macOS deploy support, partly committed."
- Repos with no pending work get no description — a row in the report on its open issues or its
  convention gap alone is one of them; leave them out of the map. A machine that is clean or absent
  gets none either — only the ones marked `<analyze below>`.

Then feed the descriptions back as a JSON object keyed by the **PROJECT cell value**, verbatim. A
repo working on one machine takes a plain string, which binds to that machine; a repo working on
several takes an object keyed by machine name:

```
python ~/.claude/skills/github-status/scripts/repos-status.py --report --width <N> <<'JSON'
{"3d/FreeCAD": "<one-line summary>",
 "scheduler": {"air": "<what air is doing>", "chrome": "<what chrome is doing>"}}
JSON
```

A plain string given for a repo working on several machines is refused with a warning rather than
guessed at — it would have to be assigned to one column, asserting something unchecked about the
other. Naming a machine that has no pending work is refused the same way.

- Pass the same `--width <N>` as step 2.
- A key matching no repo is reported on stderr rather than silently dropped — if you see that
  warning, fix the key and re-run; `--report` re-reads the state file, so re-running is free.
- If a description contains a character awkward for a single-quoted heredoc (a literal backslash, or
  the `JSON` end marker), write the object to a file and pass `--descriptions <path>` instead.

This prints the final table and writes the HTML report, then prints its path as a `file:///` link.

## 4. Hand it over

The user sees exactly two things:

1. **The final table**, pasted verbatim from the `--report` output. It is already width-bounded and
   aligned — do not hand-draw it, and do not show the step 2 table with its placeholders.
2. **The report**, as a Markdown link built from the `file:///` URL the script printed, e.g.
   `[Open the report](file:///Users/…/tmp/github-status.html)`. A path is something to read; this file
   is meant to be opened.

Do not paste the machine summary separately (the report carries it in its column headers), and do not
paste the detail sections at all.

## Behavior notes

- **Two machines, one scan.** The peer is scanned by piping this same script file into its
  interpreter over SSH (`ssh <peer> "<python> - --json"`). Nothing is copied to the far side, there is
  no temp file to clean up, and the two ends cannot run different versions of the scan. The peer reads
  its own `config.env` from the conventional install path for its own `PROJECTS_ROOT` and
  `MACHINE_NAME`.
- **Repos merge on their origin slug**, `OWNER/REPO` — the only identity that survives a different
  clone path on each machine. `AnotherSava/jsonl-logs-intellij-plugin` checked out as
  `jsonl-logs-intellij-plugin` on one machine and `intellij-jsonl-extension` on the other is one row,
  and the HTML report shows the differing path on the machine it differs on.
- **Origin-URL filter**: only repos whose `origin` matches `github.com[:/]$GITHUB_USER/` appear, on
  either machine. Third-party clones living under a projects root are skipped automatically.
- **Forks are counted** if the user owns the `origin` — even when they have an `upstream` remote
  pointing at the original author.
- **Hard exclusions**: `notion` and `claude-mermaid-fix`. To change the list, edit the `EXCLUDED` set
  at the top of `scripts/repos-status.py`.
- **Fetches every run, on both machines.** `git fetch --quiet` per repo in parallel (max 16 workers,
  30s timeout each). Failures are swallowed — a dead remote or an offline machine just means the
  displayed counts fall back to whatever the local tracking refs already knew.
- **Auto-pulls clean repos on both machines.** After collecting state, `git pull --ff-only --quiet`
  runs in parallel for every repo that is behind and has no uncommitted changes. `--ff-only`
  guarantees no merge commits — a diverged branch fails safely and stays unpulled.
- **The report is one full-width block per project, machines side by side in a column each.** The
  machine is named once, in a sticky column header that also carries its OS, projects root, repo count
  and scan age — so the page header holds no machine cards and the columns stay labelled as a long
  list scrolls. A column's position is what attributes its contents, which is why nothing inside a
  block repeats a machine name. The column count is written per block from however many machines
  answered, so a single-machine run renders one column rather than a half-empty pair.
- **Descriptions are per machine, and each sits over the column it describes.** A description is about
  work and work belongs to a machine, so the model is `RepoRow.descriptions`, machine name → summary,
  not one string per repo. One string could only ever span both columns — which put prose over a
  column reading "clean" with nothing to say which machine it meant — or be placed over one, leaving
  the other's work unexplained. Descriptions share a grid row above the metrics, so a long one on a
  single side never pushes that side's metrics out of line with its neighbour's. The terminal table
  follows the same model: DESCRIPTION is a per-machine cell wrapping under its own machine's line.
- **In the HTML, a machine with no pending work renders nothing at all** — no text, no rule, an empty
  column. That covers a clean clone and a missing one alike, so the report deliberately stops
  distinguishing them: it exists to show what is outstanding, and neither of those is. **Do not "fix"
  the empty column by putting `clean` or `not cloned here` back** — the ambiguity was chosen knowingly,
  and restoring the labels re-fills every column on a quiet day, which is what the change removed. The
  terminal table still separates the two, because a blank cell there sits between filled neighbours in
  a fixed grid and would read as either fact.
- **An unreachable peer degrades loudly**, never silently: the machine summary and the report header
  both name it with the SSH error, and the table falls back to the single-machine shape. A machine
  that did not answer has no column, so the page header is where its failure is stated. A 300s
  timeout bounds the wait.
- **The table is a snapshot taken before your analysis.** If a repo's state moves while you are
  reading its detail — a sibling Claude session committing mid-run is the usual cause, and the tell is
  a detail section that no longer matches what the table claimed — re-run step 2 and describe from the
  fresh output. Say in the report that you re-ran and why.
- **Artifacts go in the dotfiles repo's gitignored `tmp/`**, as `github-status.html` and
  `github-status-state.json`. The filenames are stable, so an open browser tab reloads onto the new
  report. Override with `--html <path>` / `--state <path>`.
- **The only GitHub API call is the open-issue count** (`gh issue list --repo OWNER/REPO`), pinned to
  the origin slug so a fork reports its own issues and never its `upstream` parent's.
- **The convention gap comes from the `/adopt` engine, not from a second reader of the record.**
  `conventions.py` is imported from the sibling skill by path — the peer runs this script from stdin,
  where there is no `__file__` to import relatively against — and asked for the same numbers the
  session-start notice prints. Two readers of one format drift the day either gains a column, and
  this one would drift silently on the machine nobody is watching. It compares integers and verifies
  nothing; `conventions.py audit <repo>` is what re-derives a recorded line.
- **A machine whose engine could not be read says so**, in its summary line and its report column
  header, instead of leaving an empty CONV column that reads as a fleet with nothing to adopt. The
  same applies per repo: an unparseable record, or one naming a version newer than that machine's
  step set, renders `?` and the reason rather than a number.
- **A repo the conventions do not govern has no cell at all** — a clone of someone else's project, or
  one carrying an `exempt` line. Nothing is asserted about a repo that was never going to hold a
  record.

See `references/findings.md` for background on the depth-4 walk, the ownership filter, and the
explicit-exclusion history.

## Out of scope

- Do NOT push, commit, stash, merge, rebase, or check out anything, on either machine. The only
  mutations are `git fetch` and `git pull --ff-only` on clean repos — both intentional, see above.
- Do NOT scan paths outside each machine's configured `PROJECTS_ROOT`.
- Do NOT run `/adopt`, or any step's `apply`, off the back of this report. The CONV column states a
  gap; closing one is a walk through that repo's own session, with each mutation shown and approved.
- Do NOT call the GitHub API beyond the open-issue count — everything else is local git state.
