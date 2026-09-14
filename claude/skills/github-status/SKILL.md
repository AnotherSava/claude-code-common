---
name: github-status
description: >-
  Cross-machine overview of your GitHub-owned local clones — every repo with
  pending work (uncommitted changes, unpushed commits, inbound remote commits)
  or open issues, merged across this machine and its peer, with branch, counts,
  age of the oldest pending work, and a one-line summary per repo. Prints a box
  table and writes a self-contained HTML report. Each run fetches every repo's
  origin on both machines so the counts reflect the current remote.
  TRIGGER when: user asks "/github-status", wants a cross-project overview of
  their repos, "which repos have unpushed commits", "what's new on remotes",
  "what have I been working on", or "what is uncommitted on the other machine".
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

1. **Machine summary**, one line each: name, OS, projects root, repos discovered, and how long ago it
   was scanned. A machine that could not be reached prints `NOT REACHED` with the SSH error instead,
   and drops out of the table entirely — it is named once here rather than under every repo.
2. **The table**, fixed-width. A repo appears if any machine has pending work or the repo has open
   issues; everything else is filtered out. Repos are **grouped**: one line per machine under a single
   PROJECT cell, sorted by AGE ascending (freshest pending work first, oldest at the bottom), with
   issue-only repos last. Columns appear only when some cell fills them:
   - **PROJECT** is always present — the clone path relative to the projects root, taken from this
     machine where it has the repo. It doubles as the key you write descriptions against in step 3.
   - **MACHINE** appears only when two machines were reached. The cell carries the machine's state
     when it has no metrics to show: `chrome clean` (present, nothing pending) and `chrome absent`
     (no clone there) are different facts, and a blank cell would say both.
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
     file mtime, oldest unpushed commit date). A deletion leaves no mtime behind, so a clone with only
     deletions falls back to whatever commits exist and can show a blank AGE against a filled LOCAL.
   - **ISSUES** — open issues (PRs excluded) on the repo's own `origin`, printed once per repo since
     it is a property of the repo rather than of a machine. Whichever machine's `gh` could answer
     supplies it, and a repo the peer alone has but could not answer for is asked again from this
     machine — `gh` needs no clone, so an unauthenticated `gh` over there neither blanks the column
     nor drops a clean-but-ticketed repo out of the report. Blank means zero, issues disabled, or
     neither machine could ask.
   - **DESCRIPTION** — `<analyze below>` for every repo with pending work. **You fill this in** per
     step 3.
3. **Detail sections** — `git status --porcelain` and `git log @{upstream}..HEAD` per repo per
   machine, tagged `[machine]` when both were reached. This is raw material for step 3, **not** part
   of the user-facing report: do not paste it back to the user.

The run also writes a state file next to the report. Step 3 reads it rather than re-scanning, so the
descriptions land on exactly the state they were written from.

## 3. Write the descriptions and render the report

For every repo the table marks `<analyze below>`, read its detail sections and synthesize a
**one-line description** of what the in-flight work accomplishes (≤ ~80 chars; the user-visible change
or theme, not file- or commit-level detail).

- When a repo has work on **both** machines, say so in the one line — that contrast is the reason the
  report spans two machines. "Memo migration here; on chrome an untracked config/ and 32 commits
  behind" beats describing only the machine you are sitting at.
- When a repo has both uncommitted changes and unpushed commits, combine them: "Mid-flight macOS
  deploy support; 3 commits already, 2 docs files still uncommitted."
- Repos with no pending work (issue-only rows) get no description; leave them out of the map.

Then feed the descriptions back as a JSON object keyed by the **PROJECT cell value**, verbatim:

```
python ~/.claude/skills/github-status/scripts/repos-status.py --report --width <N> <<'JSON'
{"claude": "<one-line summary>",
 "3d/FreeCAD": "<one-line summary>"}
JSON
```

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

Do not paste the machine summary separately (it is in the report's header), and do not paste the
detail sections at all.

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
- **An unreachable peer degrades loudly**, never silently: the machine summary and the report header
  both name it with the SSH error, and the table falls back to the single-machine shape. A 300s
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

See `references/findings.md` for background on the depth-4 walk, the ownership filter, and the
explicit-exclusion history.

## Out of scope

- Do NOT push, commit, stash, merge, rebase, or check out anything, on either machine. The only
  mutations are `git fetch` and `git pull --ff-only` on clean repos — both intentional, see above.
- Do NOT scan paths outside each machine's configured `PROJECTS_ROOT`.
- Do NOT call the GitHub API beyond the open-issue count — everything else is local git state.
