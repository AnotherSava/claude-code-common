---
name: github-status
description: >-
  List your GitHub-owned local clones under PROJECTS_ROOT that have
  pending work (uncommitted changes, unpushed commits, or inbound
  remote commits), with branch, counts, age of oldest pending work,
  open-issue count, and a per-repo summary. Each run fetches every
  repo's origin in parallel so the counts reflect the current remote.
  TRIGGER when: user asks "/github-status", wants a cross-project overview
  of their repos, "which repos have unpushed commits", "what's new on
  remotes", or "what have I been working on".
  DO NOT TRIGGER when: user is asking about a single specific repo (use
  `git status` / `git log` directly).
allowed-tools: Bash(python3 ~/.claude/skills/github-status/scripts/repos-status.py:*), Bash(test -f ~/.claude/skills/github-status/config/config.env:*), Bash(tput cols:*), PowerShell, AskUserQuestion, Read(~/.claude/skills/github-status/config/config.env), Write(~/.claude/skills/github-status/config/config.env)
---

## Context
- Config file: !`test -f ~/.claude/skills/github-status/config/config.env && echo PRESENT || echo MISSING`
- GitHub user (script default): AnotherSava — override via `GITHUB_USER` env var

## 1. Ensure PROJECTS_ROOT is configured

If **Config file** above is `MISSING`:

1. Ask the user (via `AskUserQuestion`) for the absolute path to the directory that contains all their local git clones. Suggest `$HOME/Projects` as the default if the user is on macOS, or `$HOME/code` on Linux.
2. Write `~/.claude/skills/github-status/config/config.env` with this exact content (substituting `<absolute path>`):

   ```
   # github-status skill config — gitignored, user-specific
   PROJECTS_ROOT="<absolute path>"
   ```

If **Config file** is `PRESENT`, proceed directly to step 2.

## 2. Run the report

**First, detect the terminal width** so the table fills the screen. The script's stdout is piped, which hides the real width from it, so determine it yourself:

- **Windows:** use the **PowerShell tool** to evaluate `$Host.UI.RawUI.WindowSize.Width`. Use the PowerShell tool specifically — running `powershell.exe` from the Bash tool returns the wrong value (it gets its own console, not the real one).
- **macOS/Linux:** run `tput cols` (or read `$COLUMNS`).
- If you can't determine it, omit `--width`; the script falls back to the `GHS_WIDTH` line in config.env, then to 120.

**Then subtract a gutter margin of 2** and pass the result as `--width <N>`. Claude Code's TUI indents message/tool output by a couple of columns, so a table exactly as wide as the window has its right border clipped off-screen — the margin keeps the whole table visible. (e.g. a 156-column window → `--width 154`.)

Then run `python3 ~/.claude/skills/github-status/scripts/repos-status.py --width <N>` (drop `--width` if undetected). The script output has up to three parts:

1. **Table**, fixed-width. A repo appears if it has pending work (uncommitted changes, unpushed commits, or inbound remote commits after the auto-pull pass) **or** at least one open issue on its origin; everything else is filtered out. Rows are sorted by AGE ascending (freshest pending work first; oldest at the bottom). Issue-only repos have no pending-work age, so they sort to the very bottom with blank LOCAL/AGE cells. Columns:
   - **PROJECT** is always present.
   - **BRANCH** appears only if any repo is on a branch other than `main` or `master`.
   - **UNPUSHED** appears only if any repo has unpushed commits (`@{upstream}..HEAD` > 0).
   - **REMOTE** appears only if any repo is behind its upstream (`HEAD..@{upstream}` > 0). Shows the count of commits inbound from the remote. A trailing `✓` (e.g. `4 ✓`) means the script auto-pulled those commits via fast-forward; the displayed count is the pre-pull behind count. Auto-pull happens only when the repo also has no uncommitted changes (`LOCAL` empty); diverged branches (`UNPUSHED > 0`) fail the fast-forward check and show the count without a `✓`.
   - **LOCAL** appears only if any repo has uncommitted entries. Format is `N (+A/-D)` (e.g. `5 (-211)`, `6 (+530/-61)`), where `N` is the porcelain entry count and `(+A/-D)` is the line-level diff in parentheses. Either side of `+A/-D` is omitted when 0; if there's no line diff at all (rare — e.g., untracked dir with only binaries) the cell shows just `N`. Lines come from `git diff HEAD --numstat` for tracked files plus `wc -l` of each untracked text file (untracked counts entirely as additions). Binary files (NUL-byte sniff) and files > 1 MB are skipped.
   - **AGE** appears only if any repo has unpushed commits or uncommitted changes. Shows the age of the oldest pending work in short human form (`"5 hours"`, `"2 weeks"`, `"1 year"`). The age is the older of (oldest uncommitted-file mtime, oldest unpushed-commit committer date) for that repo. Deleted files can't contribute (no mtime survives a delete) — for a repo with only deletions, this falls back to whatever commits exist.
   - **ISSUES** appears only if any shown repo has at least one open issue. Shows the count of open GitHub issues (pull requests excluded) on the repo's **own `origin`** — the query is pinned to the origin slug with `gh issue list --repo OWNER/REPO`, so a fork reports its own issues, never its `upstream` parent's. A blank cell means zero open issues, issues disabled on the fork, or that `gh` was unavailable/unauthenticated for that repo. A repo with open issues but no pending git work still appears (as its own row), with the other columns blank and DESCRIPTION `—`.
   - **DESCRIPTION** appears only if any repo has unpushed commits **or** uncommitted changes — populated with `<analyze below>` for those repos, `—` for the rest. **You fill this in** per step 3.
2. **Uncommitted changes** section — per-repo `git status --porcelain` listing for every dirty repo. Each line starts with a 2-char status: X (staged) Y (unstaged). Spaces are rendered as `·` for column alignment — e.g. `·M file` (unstaged modify), `M· file` (staged modify), `MM file` (both), `??  file` (untracked), `·D file` (unstaged deletion).
3. **Unpushed commits** section — per-repo `git log @{upstream}..HEAD --format="%h %s"` for every repo with unpushed work. This is the raw data you use in step 3.

The script's table contains placeholders by design — you are not meant to paste it verbatim. Read off its columns and cell values, then feed them back through the script's `--render` mode with the DESCRIPTION cells filled in (see step 3).

## 3. Re-render the table with descriptions filled in

Read the "Uncommitted changes" and "Unpushed commits" sections from the script output. For every repo whose row shows `<analyze below>`, synthesize a **one-line description** of what the in-flight / unpushed work accomplishes (≤ ~80 chars; focus on the user-visible change or theme, not file- or commit-level detail).

- If a repo has BOTH uncommitted changes and unpushed commits, combine them into one line — e.g. "Mid-flight macOS deploy support; 3 commits already; 2 docs files still uncommitted."
- If a repo has only one kind, describe just that.
- Repos with `—` in the DESCRIPTION cell stay as `—`.

Then **render the final table with the script's own renderer** — do NOT hand-draw the box table. The DESCRIPTION column stretches to fill the `--width` you pass (the same width detected in step 2), padding short text to the right edge and wrapping long text across lines — fiddly to reproduce by hand. Build a JSON spec with the descriptions filled in and pipe it to `--render`, passing the same `--width <N>`:

```
python3 ~/.claude/skills/github-status/scripts/repos-status.py --render --width <N> <<'JSON'
{"columns": ["project", "branch", "remote", "local", "age", "issues", "description"],
 "rows": [
   {"project": "claude", "branch": "main", "remote": "6", "local": "20 (+669/-52)", "age": "3 days", "issues": "", "description": "<your one-line summary>"}
 ]}
JSON
```

- `columns` lists the column keys (`project`, `branch`, `remote`, `local`, `age`, `issues`, `description`) that appeared in the script's table, **in the same order**. Omit any column the script omitted.
- Each row is a dict keyed by those column keys. Copy every non-description cell value **verbatim** from the script's table (including any `✓` marker and blank cells); set `description` to your one-line summary, or `—` for repos the script marked `—`. Project names use forward slashes (e.g. `bga/assistant`), so no backslash escaping is needed.
- If a description contains a character awkward for a single-quoted heredoc (a literal backslash, or the `JSON` end marker), write the spec to a file instead and pass its path: `repos-status.py --render path/to/spec.json`.
- Paste the renderer's output **verbatim** as the user-facing report — it is already width-bounded and aligned.

Do NOT paste the "Uncommitted changes" or "Unpushed commits" sections to the user — those are raw data for your analysis, not part of the user-facing report. The DESCRIPTION cell already summarizes them.

Do not show the script's original placeholder table either; your filled table replaces it. The user sees: just the filled table.

## Behavior notes

- **Origin-URL filter**: only repos whose `origin` matches `github.com[:/]$GITHUB_USER/` appear. Third-party clones living under PROJECTS_ROOT (e.g. forks of upstream tools) are skipped automatically.
- **Forks are counted** if AnotherSava owns the `origin` — even when they have an `upstream` remote pointing at the original author.
- **Hard exclusions**: `notion` and `claude-mermaid-fix`. To change the list, edit the `EXCLUDED` set at the top of `scripts/repos-status.py`.
- **Fetches every run.** Before reading state, the script runs `git fetch --quiet` per repo in parallel (max 16 workers, 30s timeout each). Failures are swallowed — a dead remote or offline machine just means the displayed counts fall back to whatever the local tracking refs already knew.
- **Auto-pulls clean repos.** After collecting state, the script runs `git pull --ff-only --quiet` in parallel for every repo where `REMOTE > 0` AND `LOCAL` is empty (no uncommitted changes). `--ff-only` guarantees no merge commits — diverged branches fail safely and stay unpulled. Successful pulls add a trailing `✓` to the REMOTE column value.
- **Counts open issues via `gh`.** For every owned repo (not just the pending-work set — a repo can earn a row on open issues alone), the script runs `gh issue list --repo OWNER/REPO --state open` (in parallel, PRs excluded) to populate the ISSUES column. The `OWNER/REPO` slug is parsed from the repo's `origin` URL and passed explicitly — without `--repo`, gh would auto-resolve a fork to its `upstream` parent and report the wrong project's issues. This is the only GitHub API call the skill makes; if `gh` is missing, unauthenticated, the fork has issues disabled, or it times out, the cell falls back to blank rather than failing the run.
- **Full-width, elastic DESCRIPTION.** The table fills the target width and the DESCRIPTION column is elastic — it takes whatever the fixed columns leave, padding short text out to the right edge and wrapping long text across lines. Target width resolves as: `--width N` (or `GHS_WIDTH` env) → the `GHS_WIDTH` line in config.env → the detected terminal width → 120. A piped stdout can't see the real terminal, which is why step 2 detects the width and passes `--width` — minus a 2-column gutter margin, because Claude Code indents message/tool output and a table as wide as the window gets its right border clipped. DESCRIPTION won't shrink below ~18 chars — past that the table overflows rather than producing unreadable one-word ribbons.
- **Forward-slash project names.** Project names are rendered with `/` separators on every platform (not Windows `\`), so they round-trip cleanly through the `--render` JSON.
- **`UNPUSHED`** = commits in `@{upstream}..HEAD` (local-only commits the remote doesn't have).
- **`REMOTE`** = commits in `HEAD..@{upstream}` (remote commits you haven't pulled).
- **`LOCAL`** = `git status --porcelain | wc -l` (entry count) combined with line-level diff totals for both tracked and untracked text content.
- The per-file detail section reproduces `git status --porcelain` output for each dirty repo, with the leading XY status code's spaces replaced by `·` so the columns line up.
- Branches with no upstream show empty UNPUSHED / REMOTE cells; they appear only if they have local uncommitted changes, sorted alongside everything else by AGE.

See `references/findings.md` for background on the depth-4 walk, ownership filter rationale, and the explicit-exclusion history.

## Out of scope

- Do NOT push, commit, stash, merge, rebase, or check out anything. The only mutations the skill performs are `git fetch` and `git pull --ff-only` on clean repos (both intentional, see Behavior notes).
- Do NOT scan paths outside PROJECTS_ROOT.
- Do NOT call the GitHub API beyond the open-issue count (`gh issue list`) — everything else is local git state only.
