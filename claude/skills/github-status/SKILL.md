---
name: github-status
description: >-
  List your GitHub-owned local clones under PROJECTS_ROOT with branch,
  last-pushed date, unpushed commits, behind-upstream count, and
  uncommitted file counts. Each run fetches every repo's origin in
  parallel so the counts reflect the current remote.
  TRIGGER when: user asks "/github-status", wants a cross-project overview
  of their repos, "which repos have unpushed commits", "what's new on
  remotes", or "what have I been working on".
  DO NOT TRIGGER when: user is asking about a single specific repo (use
  `git status` / `git log` directly).
allowed-tools: Bash(python3 ~/.claude/skills/github-status/scripts/repos-status.py), Bash(test -f ~/.claude/skills/github-status/config/config.env:*), AskUserQuestion, Read(~/.claude/skills/github-status/config/config.env), Write(~/.claude/skills/github-status/config/config.env)
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

Run `python3 ~/.claude/skills/github-status/scripts/repos-status.py`. The script output has up to three parts:

1. **Table**, fixed-width and sorted by upstream commit date (newest first). Columns:
   - **PROJECT** is always present.
   - **BRANCH** appears only if any repo is on a branch other than `main` or `master`.
   - **UNPUSHED** appears only if any repo has unpushed commits (`@{upstream}..HEAD` > 0).
   - **IN** appears only if any repo is behind its upstream (`HEAD..@{upstream}` > 0). Shows the count of commits inbound from the remote.
   - **OUT** appears only if any repo has uncommitted entries. Format is `N (+A/-D)` (e.g. `5 (-211)`, `6 (+530/-61)`), where `N` is the porcelain entry count and `(+A/-D)` is the line-level diff in parentheses. Either side of `+A/-D` is omitted when 0; if there's no line diff at all (rare — e.g., untracked dir with only binaries) the cell shows just `N`. Lines come from `git diff HEAD --numstat` for tracked files plus `wc -l` of each untracked text file (untracked counts entirely as additions). Binary files (NUL-byte sniff) and files > 1 MB are skipped.
   - **AGE** appears only if any repo has unpushed commits or uncommitted changes. Shows the age of the oldest pending work in short human form (`"5 hours"`, `"2 weeks"`, `"1 year"`). The age is the older of (oldest uncommitted-file mtime, oldest unpushed-commit committer date) for that repo. Deleted files can't contribute (no mtime survives a delete) — for a repo with only deletions, this falls back to whatever commits exist.
   - **DESCRIPTION** appears only if any repo has unpushed commits **or** uncommitted changes — populated with `<analyze below>` for those repos, `—` for the rest. **You fill this in** per step 3.
2. **Uncommitted changes** section — per-repo `git status --porcelain` listing for every dirty repo. Each line starts with a 2-char status: X (staged) Y (unstaged). Spaces are rendered as `·` for column alignment — e.g. `·M file` (unstaged modify), `M· file` (staged modify), `MM file` (both), `??  file` (untracked), `·D file` (unstaged deletion).
3. **Unpushed commits** section — per-repo `git log @{upstream}..HEAD --format="%h %s"` for every repo with unpushed work. This is the raw data you use in step 3.

The script's table contains placeholders by design — you are not meant to paste it verbatim. Use its column layout as the template and produce one final filled-in table in your response (see step 3).

## 3. Re-render the table with descriptions filled in

Read the "Uncommitted changes" and "Unpushed commits" sections from the script output. For every repo whose row shows `<analyze below>`, synthesize a **one-line description** of what the in-flight / unpushed work accomplishes (≤ ~80 chars; focus on the user-visible change or theme, not file- or commit-level detail).

- If a repo has BOTH uncommitted changes and unpushed commits, combine them into one line — e.g. "Mid-flight macOS deploy support; 3 commits already; 2 docs files still uncommitted."
- If a repo has only one kind, describe just that.
- Repos with `—` in the DESCRIPTION cell stay as `—`.

Then **emit a single table to the user** with the same columns the script chose, in the same order, with the DESCRIPTION cells filled in. Match the script's box-drawing style: Unicode `┌─┬─┐` top, `│` cell separators, `├─┼─┤` header divider, `└─┴─┘` bottom.

**Column widths**: per column, width = max(header length, longest cell value). The `│ cell │` rendering gives one space of padding on each side automatically.

**Alignment**:
- Values: all left-aligned.
- Headers: UNPUSHED, IN, OUT, AGE are centered; PROJECT, BRANCH, DESCRIPTION are left-aligned.

Do NOT paste the "Uncommitted changes" or "Unpushed commits" sections to the user — those are raw data for your analysis, not part of the user-facing report. The DESCRIPTION cell already summarizes them.

Do not show the script's original placeholder table either; your filled table replaces it. The user sees: just the filled table.

## Behavior notes

- **Origin-URL filter**: only repos whose `origin` matches `github.com[:/]$GITHUB_USER/` appear. Third-party clones living under PROJECTS_ROOT (e.g. forks of upstream tools) are skipped automatically.
- **Forks are counted** if AnotherSava owns the `origin` — even when they have an `upstream` remote pointing at the original author.
- **Hard exclusions**: `notion` and `claude-mermaid-fix`. To change the list, edit the `EXCLUDED` set at the top of `scripts/repos-status.py`.
- **Fetches every run.** Before reading state, the script runs `git fetch --quiet` per repo in parallel (max 16 workers, 30s timeout each). Failures are swallowed — a dead remote or offline machine just means the displayed counts fall back to whatever the local tracking refs already knew.
- **`unpushed`** = commits in `@{upstream}..HEAD` (local-only commits the remote doesn't have).
- **`IN`** = commits in `HEAD..@{upstream}` (remote commits you haven't pulled).
- **`OUT`** = `git status --porcelain | wc -l` (entry count) combined with line-level diff totals for both tracked and untracked text content.
- The per-file detail section reproduces `git status --porcelain` output for each dirty repo, with the leading XY status code's spaces replaced by `·` so the columns line up.
- Branches with no upstream show empty UNPUSHED / IN cells and sort to the bottom.

See `references/findings.md` for background on the depth-4 walk, ownership filter rationale, and the explicit-exclusion history.

## Out of scope

- Do NOT push, commit, stash, merge, rebase, or check out anything. The only mutation the skill performs is `git fetch` (intentional, to refresh tracking refs).
- Do NOT scan paths outside PROJECTS_ROOT.
- Do NOT call the GitHub API — local git state only.
