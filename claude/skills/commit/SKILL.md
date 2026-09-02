---
name: commit
description: Reflects on the session, then analyzes changes and generates Conventional Commit messages
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git status:*), Bash(git log:*), Bash(git reset HEAD:*), Bash(git ls-files:*), Bash(git rev-list:*), Bash(git rev-parse:*), Bash(git push:*), Bash(gh issue list:*), Bash(bash ~/.claude/scripts/sanitize-project-memory.sh:*), Bash(bash ~/.claude/scripts/link-project-memory.sh:*), Bash(rm:*)
---

# Commit Changes

You are tasked with creating git commits for the changes made during this session.

Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.

## Context
- Repo root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Ignore rules: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && cat "$R/.gitignore" 2>/dev/null || true`
- Wire project memory: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && PID=$(printf '%s' "$R" | sed 's|[^a-zA-Z0-9]|-|g') && MEM="$HOME/.claude/projects/$PID/memory" && if [ -d "$MEM" ] && [ ! -L "$MEM" ] && [ -n "$(ls -A "$MEM"/*.md 2>/dev/null)" ]; then bash ~/.claude/scripts/link-project-memory.sh "$R" 2>&1; else echo "(already version-controlled or no project memory to wire)"; fi || true`
- Sanitize project memory: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && bash ~/.claude/scripts/sanitize-project-memory.sh "$R" 2>/dev/null || true`
- Unstage all (keep: diffing a partially-staged tree once produced a commit message describing edits that were never in the repo): !`git reset HEAD 2>/dev/null || true`
- Remote ahead by: !`git fetch origin --quiet 2>/dev/null || true; git rev-list --count HEAD..@{upstream} 2>/dev/null || echo "n/a"`
- Uncommitted changes: !`git status --short`
- Diff summary: !`git diff --stat $(git rev-parse -q --verify HEAD || echo 4b825dc642cb6eb9a060e54bf8d69288fbee4904)`
- Full diff: !`git diff $(git rev-parse -q --verify HEAD || echo 4b825dc642cb6eb9a060e54bf8d69288fbee4904)`
- Recent commits: !`git log --oneline -10 2>/dev/null || echo "(no commits yet)"`
- Open issues: !`gh issue list --repo "$(git remote get-url origin 2>/dev/null | sed -E 's#^.*github\.com[:/]##; s#\.git$##; s#/$##')" --state open --limit 30 2>/dev/null || echo "n/a"`
- Pending memos: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && cat "$R/.claude/memos.md" 2>/dev/null | grep '^- \[ \]' || echo "(none)"`
- Project commit-checks: !`R=$(git rev-parse --show-toplevel 2>/dev/null || pwd) && test -f "$R/.claude/commit-checks.sh" && echo "PRESENT — step 6 MUST run it" || echo "none"`

## Working directory

`docs/plans/**` paths and any file paths in this skill are relative to **Repo root** from Context. The cwd may be a subdirectory — prefix Repo root when calling Read/Edit/Write/Grep/Glob, and pass paths from `git status --short` to `git add` verbatim (they're already repo-root-relative; git resolves them from cwd up to the repo root automatically).

## CRITICAL CONSTRAINT

**The ONLY direct file changes this skill may make are through `/reflect`, `/clean-code`, and `/documentation`.** Never move, rename, or delete source files. Never restructure code beyond what those skills do. (Exception: untracked junk artifacts like `*.stackdump` may be discarded — see step 1.)

## Process:

**Pacing:** Steps 1–7 are preparation. Sub-skills may legitimately pause when they find substantive changes needing approval (e.g. reflect proposing items to save, clean-code proposing dead-code removal, documentation proposing edits). Honor those gates. But when a sub-skill finishes with nothing to report, continue immediately to the next step — do not insert an extra confirmation gate. The only gates the commit skill itself owns are step 1 (related-issue check, only if an open issue matches the change set), step 6 (project commit-checks, if `.claude/commit-checks.sh` exists and its run fails), step 7 (plan-filename warning, if triggered), step 8 (commit-plan approval), and step 9 (push).

1. **Assess the current state of the repository** (use Context above):
   - **Remote sync check (do this first):** If **Remote ahead by** is > 0, the remote has commits you don't have locally and `git push` will be rejected at the end. Surface this to the user immediately and propose syncing before proceeding; wait for their confirmation, since it could conflict with the pending changes. **The tree is dirty at this point — that is this skill's whole premise — so `git pull --rebase` refuses to run**, and its `--autostash` pops without `--index`, flattening any staged/unstaged split. Read `~/.claude/learnings/git-stash-pull-safety.md` and follow it: check `git log @{upstream}..HEAD` first, because a branch that is purely behind wants `git stash push` → `git merge --ff-only` → `git stash pop` rather than a rebase at all. After syncing, re-check `git status --short` since the working tree may differ.
   - Use **Uncommitted changes**, **Diff summary**, and **Full diff** to understand the total change set against HEAD
   - **Scope guard:** Only commit files that belong to this repository. If earlier work in the conversation touched files in other projects, do not include those changes — each project's commits are handled separately.
   - **Discard junk artifacts:** delete untracked crash-dump / junk files that should never be committed — e.g. `*.stackdump` (Git Bash crash dumps on Windows), `core` dumps. Remove them with `rm` so they don't clutter the change set or get staged. Only delete clearly-disposable, never-source artifacts; if an untracked file's purpose is at all unclear, leave it and mention it rather than deleting.
   - **Orphaned-data check:** Look for data that has outlived the logic that produced or consumed it — a file/directory left stranded after the code operating on it was removed. Two signals: (a) the current change set **deletes** a module/tool/script, yet its data file or directory (the cache, export, generated output, or config it managed) is still present in the tree; (b) an untracked or tracked data file/directory sits under a tool/module path whose source code is no longer present (removed in a recent commit — check `git log --oneline -10` and `git ls-files <dir>`). The motivating case: a tool's code was removed in a prior commit but a lone `data/<tool>.csv` survived, silently resurrecting the deleted tool's directory. When you spot orphaned data, surface it (the data path + the logic that's gone) and **ask the user whether the data should be removed too** — do not auto-delete, as data is sometimes preserved deliberately. On confirmation, remove it with `rm` so it doesn't get committed or left behind; otherwise leave it and note that the data is being kept.
   - **Executable-mode check:** For any file in the change set meant to be run directly — a git hook under `git/hooks/`, or a script carrying a `#!` shebang on its first line — verify git tracks it as mode `755`, not `644` (`git ls-files -s <path>`). Git records the execute bit and silently **ignores a non-executable hook** (and won't run a non-executable script), so one committed `644` is born inert on every checkout. When you find one, restore the bit with `chmod +x <path> && git update-index --chmod=+x <path>` and fold the mode change into the commit; surface it rather than fixing silently.

     **On an untracked file `git ls-files -s` prints nothing at all**, so on a repo with no commits this check finds no problem on the one run where it matters most — a first commit introduces every script's mode at once, into the root commit. For an untracked path read the filesystem instead (`stat -f '%OLp' <path>` on macOS, `stat -c '%a' <path>` on Linux/Git Bash); that is the mode `git add` will record — **but only where `core.filemode` is true.** On Windows it defaults to **false**, and git then ignores the filesystem execute bit and records `644` whatever the file system says, so `stat` measures a number git will not use and confirms a mode that will not be committed. Verified 2026-09-02: a Windows clone reported `create mode 100644` for two scripts that were 755 on disk, following this instruction as written. Read `git config core.filemode` first; where it is false the only honest instrument is `git ls-files -s <path>` **after staging** — stage, check, then fix with `git update-index --chmod=+x <path>`, since nothing in the working tree can carry the bit for you. This is also why a script first committed from a filemode-true machine stays 755 for everyone: the index remembers, and the trap only fires when a *new* executable is first committed from Windows. Watch the opposite error too: a shebang'd file that is deliberately **not** executable is a library, not a defect — check its docstring before `chmod +x`, and take an odd mode that disagrees with its neighbours as a question rather than an answer.
   - **Untracked-skill check:** Run `bash ~/.claude/scripts/audit-skill-tracking.sh` (it prints nothing and exits 0 when there is nothing to report, and in a repo with no skills directory). Prefix it with `timeout 20` only where that command exists — macOS ships neither `timeout` nor `gtimeout` unless coreutils is installed, and an unconditional prefix fails the step outright with `command not found`. Deliberately a step rather than a Context probe: the `!` probes above are evaluated together, several of them git commands contending with `git reset HEAD` for `index.lock`, and adding more there has stalled skill loading past its two-minute budget. For each path it lists, that skill exists on disk but is excluded by a wildcard rule, so this commit will silently leave it behind — and because an ignored path never appears in `git status`, nothing else in this flow will mention it. Surface the list and ask which of two things each one is. **Keep it:** add `!<path>` to `.gitignore` beside its siblings so it commits. **Deliberately local:** append its directory name to `claude/untracked-skills.local.txt` (or `.claude/…` for a project's own skills) with a short reason — that file is gitignored and per-machine, and recording the decision there is what stops the skill being raised on every future commit. Do not decide either way yourself. Never carry the decision only in conversation: it dies at the next `/clear`, and the same skill gets re-raised forever. Symlinked skills and already-declared ones are filtered out, so anything listed is genuinely undecided.
   - If there are no uncommitted changes in this repository, still run step 2 — reflection may produce files worth committing. If the tree is still clean after reflection, stop — there is nothing to commit.
   - Review the conversation history (if any) to understand what was accomplished — but do not assume all changes come from this session; the repo state is the source of truth
   - **Open-issue triage:** Using **Open issues** from Context, judge whether any open issue relates to the current change set (match issue titles/labels against the changed files and the work done this session).
     - For each issue that **is related** — the change set fixes, touches, or directly bears on what the issue describes — surface it (number + title) and ask the user whether it should be addressed before committing. Wait for their answer. Do not auto-close issues or add `Fixes #N` / `Closes #N` trailers to commit messages unless the user confirms. If they ask to address it, the resulting code changes flow through the remaining steps normally.
     - Issues that are **not related** are NOT raised now — hold them and report them after the push (step 9).
     - If **Open issues** is `n/a` (no `gh`, no GitHub remote, or none open), skip this triage entirely.

2. **Reflect:** Run `/reflect` to extract and persist conversation learnings before they are lost. Skip this step only if `/reflect` already ran in this conversation with no substantive work since — re-running it would just re-scan the same ground. Honor its save-approval gate. **If `/reflect` finds nothing worth saving, immediately proceed to step 3 in the same response — do not stop, do not ask for confirmation.** If any files were saved, re-run `git status --short` and `git diff HEAD` afterwards — the Context snapshot above predates reflection, so the change set may have grown. Files reflect saves outside this repository (e.g. global memory or learnings living in another repo) are excluded by the scope guard — they get committed in their own repo, not here.

3. **Clean code:** Run `/clean-code` to remove debug prints, dead code, duplication, and optimize imports. **If `/clean-code` reports nothing to clean up, immediately proceed to step 4 in the same response — do not stop, do not ask for confirmation.** Only pause if `/clean-code` proposes substantive changes that need user approval.

4. **Update stale documentation — do this BEFORE planning commits:**
   Run `/documentation` to scan and fix stale references in README, docs, CLAUDE.md, and source comments. All documentation fixes become part of the commit(s) — do not commit code with outdated docs. **If `/documentation` reports nothing to fix, immediately proceed to step 5 in the same response — do not stop, do not ask for confirmation.** Only pause if `/documentation` proposes edits that need user approval.

5. **Confidentiality check:**
   - Scan the diff for content that should not be committed to a public repository: API keys, tokens, passwords, private URLs, internal hostnames, personal data (emails, phone numbers, real names in test data), or proprietary business logic
   - Pay extra attention to learning files (`claude/learnings/`): these are domain knowledge docs meant to be generic and reusable — flag any project-specific details, internal URLs, proprietary names, or customer data that leaked in from the source project
   - **Absolute / machine-specific paths:** scan every file headed for the commit for absolute filesystem paths — `C:\Users\...`, `D:\projects\...`, `/Users/<name>/...`, `/home/<name>/...`, and the like. The global rule forbids them in committed content (README, docs, comments, **and committed memory and learnings**): they're machine-specific and break both for other contributors and for the user, who works from a Windows and a macOS machine. This applies even though such a path isn't secret — it's the confidentiality step's job because this is the catch-all for "content that shouldn't go into the repo as-is." What must go is a pointer into a *specific machine's* tree — a personal projects root, a home directory with a real username, a custom install dir. Exempt, and not worth re-flagging every run: standard OS install locations (`C:\Program Files\...`, `/Applications/...`), documented defaults and placeholders (`C:/Programs/your-app`, `{{path-to-app}}`), paths already elided (`C:\Users\...\`), this rule's own counter-examples, and archived plans under `docs/plans/completed/`. When found, propose genericizing: a path relative to the repo for files inside the project, a generic description for external references (e.g. "a local Evernote backup" instead of `D:\backup\Evernote\md\`). Don't silently rewrite wording — surface the findings and let the user decide.
   - **Encryption is NOT an exemption — scan transcrypt-encrypted files too.** A file marked `filter=crypt` changes *who can read it*, never *whether its contents belong in git*. transcrypt smudges to plaintext in the working tree, so these files read normally here; the only mistake available is skipping them because they look handled. Classify by what the content **does**:
     - **It authenticates something** — API key, token, password, passphrase, private key, a connection string with credentials in it. **Never commit, encrypted or not.** It belongs in the secret manager (`/doppler`). Committing it encrypted looks safe and is not: history is permanent, so rotating the credential does not remove the old value; one shared passphrase makes its blast radius *every secret ever committed under it*, including for anyone who held the key once and no longer should; and it bypasses the rotation, per-environment separation and revocation the secret manager exists to give you.
     - **It describes something** — hostnames, filesystem paths on a server, container names, tailnet addresses, project or config names. Committable. Encrypt it when the repo is public or might become public; leave it plain when the repo is private and expected to stay so.
   - **The `.secret.md` suffix invites exactly the wrong reading.** It means *private*, not *authenticating* — someone will eventually treat the filename as permission to put a credential there. The existing encrypted files are on the right side of that line and should stay there: one holds *coordinates for* credentials rather than the values, the other holds machine names and a login. Flag any drift toward real credential values in them.
   - If anything looks sensitive — or any absolute path turned up — list the findings and ask the user before proceeding; do not silently include them in the commit plan

6. **Plan your commit(s):**
   - **Project commit-checks (run first):** Read **Project commit-checks** from Context — never assert from memory whether the script exists. If it says `PRESENT`, run it (`bash .claude/commit-checks.sh`) before drafting the plan; only `none` permits skipping, and then silently. This lets a project gate its own commits on tests or linters too slow to run on every edit. It is a Context probe rather than a step precisely because "check whether it exists" is the part that gets forgotten: claiming the file was absent without looking once let three commits through ungated. On a non-zero exit, surface the output and STOP — do not present a commit plan for code that fails its own checks; hand the failures back to be fixed first. When the failure is clearly environmental rather than a defect in the change set (missing dependencies, a stale generated client, the wrong runtime version), say so, name the change set's actual reach, and let the user decide whether to fix the environment or override the gate — do not override it yourself.
   - Read `~/.claude/skills/shared/commit-message-rules.md` for commit message formatting and validation rules
   - Group into atomic commits by feature/fix/refactor — no file belongs to more than one group, and each group can be committed independently
   - Identify which files belong together
   - If a single file contains changes that belong to different commits, do NOT attempt to split it with `git add -p` or partial staging — assign the file to the commit where it fits best and note the mixed content in the plan
   - Put tests and documentation changes in the same commit as the feature they cover, unless there is a significant reason to separate
   - **Implemented memos**: if a pending memo (Context **Pending memos** / `<repo>/.claude/memos.md`) is clearly implemented by this change set, flip its `- [ ]` to `- [x]` **now** and fold `.claude/memos.md` into the commit that implements it — check it off *with the changes*, not as a follow-up after the push. (Only memos this change set actually delivers; still-open ones stay untouched until step 10.)
   - **Plan files (`docs/plans/**`)**: bundle each plan file into the SAME commit as the implementation it describes. Match by filename slug / content keywords against the changed source paths. Only emit a separate `docs(plans):` commit if the plan file is the ONLY change (e.g. editing a plan mid-design without implementing yet, or archiving unrelated historical plans).
   - **Project memory (`.claude/memory/**`)**: the *Wire project memory* context step version-controls it — the first time it runs in a project it migrates the machine-local memory cache into `<repo>/.claude/memory/` and junctions the cache to it (idempotent; it skips already-wired or memory-less repos, so most runs are a no-op). When it *did* migrate files, they show up as untracked in **Uncommitted changes** — fold them into a commit (their own `chore: version-control project memory`, or alongside the session's docs). The Sanitize step already stripped `originSessionId` telemetry, but these are running work-logs that often carry machine-specific absolute paths and ids — the confidentiality check (step 5) MUST still pass over them and genericize/redact before they land.
   - Draft and validate commit messages following the shared rules

7. **Validate plan filenames:**
   For every plan file under `docs/plans/` that's part of this change set (new, modified, or renamed — check both `docs/plans/*.md` and `docs/plans/completed/*.md`):
   - Read the file and check whether it contains a top-level `# H1` heading (on any line, outside fenced code blocks).
   - If no H1 is found, warn the user explicitly: the `plan-archive.py` hook derives the filename slug from the plan's H1 and falls back to the original random codename (e.g. `zesty-coalescing-crystal`) when no H1 is present. Suggest a descriptive slug based on the plan's content, offer to rename the file and add an H1, and wait for user confirmation before proceeding. Do not silently include a codename-slug plan file in a commit.
   - If the file starts with the `<!-- plan-archive: no ...` fallback marker comment, treat it the same as a missing H1 — the hook explicitly flagged it. If the user fixes the title, offer to remove the now-stale marker comment in the same edit.

8. **Present your plan to the user:**
   - Separate each commit with a unicode line: `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`
   - For each commit show:
     1. **Commit N**
     2. Commit message with only the type prefix in **bold** (e.g. **refactor**: description), no code block
     3. Number of files and lines changed, then without an empty line in between, the file list — produced by `scripts/format_files.py`, not by hand:

        ```bash
        printf '%s\n' \
          $'path/one.ts\tBrief description' \
          $'path/two.css\tBrief description' \
          | python3 ~/.claude/skills/commit/scripts/format_files.py
        ```

        Paste its output verbatim. It emits a fenced code block with the paths padded to a common width, which is the only way the columns survive — rendered markdown collapses runs of spaces, so hand-padding (or `&nbsp;` entities, which render literally in a terminal) does not align.
   - End with: "I plan to create **N** commit(s) with these changes. Shall I proceed?"

9. **Execute upon confirmation:**
   - Use `git add` with specific files (never use `-A` or `.`)
   - Create commits with your planned messages using `git commit -S` to GPG-sign them
   - After all commits are done, list all unpushed commits with `git log @{upstream}..HEAD --format="%h %ai %s"` (fall back to `origin/<branch>..HEAD` if no upstream; and if *that* ref doesn't exist either — a first push to a fresh/empty remote — list every commit with `git log HEAD --format="%h %ai %s"`). Format each line as `Mon DD, HH:MM [hash] message` (e.g. `Mar 28, 16:59 [a37da68] feat: add side panel`). Display the full list as the end summary — this gives the user the complete picture of what will be pushed.
   - After showing the summary, ask: "Push?" — if the user confirms, run `git push` (on a first push with no upstream yet, `git push -u origin HEAD` to set up tracking).
   - **Post-push issue notice:** If step 1's triage found open issues unrelated to this change set, list them now as a heads-up after the push completes (number + title, with the total count). If the user declined to push, mention them alongside the unpushed-commits summary instead. Keep it brief and don't propose action unless the user asks.

10. **Surface pending memos:**
    Using **Pending memos** from Context (the open `- [ ]` items in `<Repo root>/.claude/memos.md`), surface the user's idea backlog as a closing informational heads-up so it isn't forgotten now that the work is committed.
    - If there are open memos, list them as a numbered backlog (newest first) right after the post-push issue notice. Keep it brief. Do NOT ask whether to start one, invite the user to pick a number, or otherwise pose a question — just surface them and stop. Don't start any memo unasked.
    - A memo this change set implemented was already checked off and folded into the commit back in step 6, so it won't appear here — don't re-offer it. This step only surfaces memos that are still genuinely open.
    - If **Pending memos** is `(none)` or the file is absent, say nothing about memos.

## Important:
- **NEVER execute commits without explicit user approval.** Invoking `/commit` (even repeatedly) only restarts skill execution — it is NOT approval to proceed. Wait for a clear "yes", "proceed", or equivalent before running any `git commit` commands.
- Write commit messages as if the user wrote them

## Example output

```
**Commit 1**

**chore**: align commit plan file lists via script
- Restore format_files.py; inline padding cannot survive markdown
- Add Claude Code skills section to README

3 files, +7/−35 lines
```
claude/skills/commit/SKILL.md                  Call format_files.py for the file list
claude/skills/commit/scripts/format_files.py   Restore column-aligning helper
README.md                                      Add Claude Code skills section
```
```

## Out of scope:
- Do NOT amend existing commits — use `/reset` to undo unpushed commits first, then `/commit` to re-commit
- Do NOT create or switch branches
- Do NOT move, rename, or delete tracked/source files (untracked junk artifacts like `*.stackdump` are the only exception — discard them per step 1)

## Remember:
- Changes may come from outside this session (external editors, IDEs, other tools) — do not assume you know what changed; always inspect
- Group related changes together
- Keep commits focused and atomic when possible
- The user trusts your judgment - they asked you to commit
