# Global Guidelines

Never use absolute paths in committed documentation (README, CLAUDE.md, docs/, comments). Use relative paths for files within the project and generic descriptions for external references (e.g. "the BGA extension repo" not `D:\projects\bga\assistant`). Absolute paths are machine-specific and break for other contributors.

Always ask clarifying questions before implementing if anything is ambiguous or unclear.

Never add "Generated with Claude Code" attribution (or any equivalent self-promotion) to text you author: PR descriptions, issue bodies, comments, commit messages, docs, etc. Leave it out entirely unless the user explicitly asks for it.

## Self-Sufficiency

Before asking the user to do something (run a command, edit a file, check a value), figure out how to do it yourself. If the action is non-destructive, just do it. If it's destructive or irreversible, ask the user for permission — but propose the concrete action, don't ask the user to perform it.

When changes are ready to test, run the project's `deploy` command (or equivalent) yourself via Bash. Do not suggest the user "run `deploy`" or type `! deploy`. The Self-Sufficiency rule applies: invoke the action, don't outsource it.

Exclude `node_modules/` from all file and content search patterns — it clogs results with false positives.

Do not inline Python scripts into Bash commands via `python -c`. Instead, use a heredoc: `python <<'EOF' ... EOF`.

Do not add logic, data structures, classes, or exports to production code that exist only to support tests. Tests should exercise the public API and real behavior — not rely on test-only hooks, flags, exports, or types in production modules.

## Research Before Trial-and-Error

When a problem resists the first attempt or two — especially browser/CSS quirks, framework behavior, tool errors, or library/API limitations — search the web for the root cause and known fixes instead of iterating blindly or concluding it can't be done. A targeted search often surfaces a proven solution, and explains *why* the naive attempts failed, faster than guess-and-check. Lean toward researching early when the territory is unfamiliar or a fix isn't converging; reserve trial-and-error for cases where simply trying it is genuinely cheaper than a search. The repeated-experiment smell (three tweaks, three failures) is the signal to stop and look it up.

## Git Workflow

- Do not create git commits unless explicitly asked
- Do not push to remote unless explicitly requested
- Follow `~/.claude/skills/shared/commit-message-rules.md`
- Prefer `git status --short` over `git diff --stat` for change-set summaries. Changes sit unstaged until `/commit` runs, so untracked files are part of the pending commit — and `git diff --stat` silently omits them, producing an incomplete picture.

## Bash Commands

- **Windows (Git Bash):** always use forward slashes (`/`) in paths, not backslashes (`\`). Backslashes are interpreted as escape characters by bash and get stripped.
- **macOS / Linux:** paths are already Unix-style; no special handling needed.

When asking the user to run a command manually (e.g. launching an app, system config):
- **on Windows:** provide PowerShell syntax — not bash or cmd.
- **on macOS / Linux:** provide bash/zsh syntax.

### Background processes I spawn

When I launch a process that outlives the command and that I'll kill later myself (a headless browser, a dev server, a daemon):
- **Redirect its output.** Detach stdout/stderr to a log file or the null device (PowerShell: `Start-Process … -RedirectStandardError <file>` or wrap in `cmd /c "… >nul 2>&1"`; bash: `… >/tmp/x.log 2>&1 &`). Otherwise the process's async messages — GPU/SwiftShader warnings, crash/shutdown lines — leak into the user's terminal, often after my turn ends. This has happened repeatedly with headless Chrome.
- **Kill the whole tree, not just the parent.** Such processes fork children (headless Chrome spawns GPU/renderer subprocesses that keep emitting after the parent dies). Match every related PID by a distinguishing flag/profile/temp-dir I chose (e.g. `--headless` or my `--user-data-dir`), not the parent PID alone — and never by a pattern that could match the user's own running instances (their normal browser, their dev server).
- **Clean up before reporting done.** Remove temp profile dirs, scratch files, and any served generator pages, and confirm zero leftover matching processes.

## Tooling Defaults

- **Node.js**: default to the current active LTS (Node **24** as of May 2026) for new projects, CI workflows, and `.nvmrc` files — unless the project already pins an older version, a dependency demands otherwise, or there's a specific reason to use something else. Always prefer an existing `.nvmrc` / `engines.node` over this default.
- **Package-manager pin**: any project with a `package.json` should pin its toolchain via the `packageManager` field (e.g. `"npm@11.17.0"`) with Corepack enabled, so every machine and CI run uses an identical manager version — an unpinned npm drifts the lockfile across machines (`peer: true` markers, `devOptional`→`dev` churn). Offer to add it when missing rather than pinning silently; bump it deliberately like a dependency (typically alongside a Node upgrade), not on every release. Resolve the current stable with `npm view npm version` and avoid prerelease majors. See `~/.claude/learnings/corepack-packagemanager-pin.md`.

## Best-Practice Adoption

When a project lacks a practice that is standard for its type — a linter for a Python project, ESLint/strict tsconfig for TypeScript, CI for a released library, a lockfile, a test runner — point out the gap and offer to adopt it. Offer, don't adopt silently; and don't nag: one offer per project, and if declined, record the decision in project memory so it isn't re-raised.

When the offer is accepted:
- **Measure before proposing rules**: run the candidate tool against the codebase and triage the real baseline per rule; adopt with a clean baseline (fix or explicitly scope every existing violation).
- **Fit the tool to the project's documented style**, never the reverse — skip or configure rules that fight an established preference, and document every deliberately disabled rule and its reason inside the tool's config file.
- **Prefer enforcement at generation time** (e.g. a PostToolUse lint hook) over conventions that rely on remembering to run something.

## Code Style

### Formatting

- Leave an empty line at the end of every file
- Prefer single-line expressions over multi-line formatting, even if they're long. **Exception**: multi-line is acceptable when calling functions/constructors with all named parameters.

### UI Text Casing

Default to sentence case for user-facing UI strings (menu items, buttons, dialog titles, tooltips, notifications). Capitalize only the first word and proper nouns/acronyms. Examples: "Open config file", "Hide with Esc", "Start with Windows". See `~/.claude/memory/feedback_sentence_case_ui.md` for rationale and edge cases.

### Prose Style

In prose (docs, READMEs, comments), don't open a sentence or line with code-formatted (backtick-wrapped) text when regular text follows — lead with a real word and fold the code reference in after it ("The `notifications` block controls…" not "`notifications` controls…"). Term-definition list items where the code identifier is the subject are the standard exception. See `~/.claude/memory/feedback_no_code_at_sentence_start.md`.

Parallel enumerations should share grammatical form — list-item blurbs are all imperative verbs or all noun phrases, not a mix ("download …" / "explore …" / "build …", not "download …" alongside "a tour of …").

### Explicit State

Use a dedicated field or variable for object state rather than overloading another field's values (e.g., using `internalDate === 0` as a "deleted" sentinel). A simple null/non-null check is fine, but anything beyond that should be an explicit status field.

### Early Returns

Avoid adding early return guards like `if not items: return` when the function would behave identically without them (e.g., a `for` loop over an empty collection naturally does nothing). Only add early returns when they actually change behavior or prevent errors.

### Type Hints (Python)

Always specify parameter and return types.

### Import Organization

Place imports at the top of the file. Order (with blank lines between groups):
1. Standard library
2. Third-party
3. Local

Inline imports only for circular import resolution (add comment: `# inline to avoid circular import`) or `TYPE_CHECKING` blocks.

### Dependencies (Python)

When adding or removing a third-party import, update `requirements.txt` in the same change to keep it in sync.

### Refactoring Safety

When changing field/function names, search all usages (including tests) and update accordingly before making breaking changes. Run all tests after refactoring.

### Single Source of Logic

When the same non-trivial computation or step-sequence is needed in two or more places, extract it into one function every call site calls — do not copy-paste it. Copies drift: a later fix or refinement lands in one and silently misses the others (real case: one path scaled a value by the DPI factor, its copy-pasted sibling forgot to, so the two positioned the same element differently). This matters most for **parallel code paths that must stay behaviorally/visually consistent** (two ways of placing or rendering the same thing) — give them a shared helper so they *cannot* diverge. When you touch code near a pre-existing duplicate, consolidate rather than adding a third copy. Balance against premature abstraction (`~/.claude/memory/feedback_no_premature_abstraction.md`): extract once 2–3 real call sites exist, not speculatively — but once they do, share, don't duplicate. Watch for the divergence smell during review: near-identical blocks whose only differences are *unintended* (a missing `* scale`, a different fallback constant).

## Gitignore

When adding entries to `.gitignore`, choose the right scope:
- **Global gitignore** (`~/.gitignore_global`): OS-specific or user-specific files — IDE folders, OS thumbnail caches, tool outputs for tools the user happens to use (e.g. `.idea/`, `Thumbs.db`, `.ralphex/`).
- **Project gitignore** (`.gitignore`): files that everyone who checks out the project should ignore — build outputs, `.env` files, `node_modules/`, `__pycache__/`.

## Symlinks

Everything under `~/.claude/` is symlinked from the dotfiles repo (`CLAUDE.md`, `settings.json`, `skills/`, `hooks/`, `learnings/`, `memory/`, `scripts/`). The Write and Edit tools **refuse to write through symlinks**. Before editing any file under `~/.claude/`, resolve the symlink with `readlink <path>` and pass the real target path to Write/Edit.

For first-time global installation, use the platform-appropriate command block from `README.md`'s Global Installation section. For ad-hoc symlinks during a session:

- **macOS / Linux:** `ln -s` with an absolute target path (`"$(pwd)/..."`).
- **Windows:** Never create symlinks from Bash (`ln -s`) — it silently creates copies instead. Use PowerShell `New-Item -ItemType SymbolicLink` from an Administrator prompt. Use `$PWD` to build absolute target paths.

## Global Memory

Cross-project preferences and feedback. Memory files live in `~/.claude/memory/`. When saving a memory that applies across all projects (not just the current one), write the file there and add an index entry below. Same frontmatter format as project-specific memories.

**Project memory is version-controlled too.** Repos wired with `~/.claude/scripts/link-project-memory.sh` redirect their machine-local memory cache (`~/.claude/projects/<hash>/memory/`, a symlink) into a committed `<repo>/.claude/memory/`. So when saving *project-specific* memory: resolve the symlink and write to `<repo>/.claude/memory/`, then commit it with the rest of the work. On a fresh clone, re-run the script to re-establish the symlink. If a repo's cache is still a plain directory (not yet wired), run the script first.

- [User GitHub account](~/.claude/memory/user_github_account.md) — handle is `AnotherSava`; use to filter "my repos" vs third-party clones
- [Follow skill instructions exactly](~/.claude/memory/feedback_follow_skill_instructions.md) — never abbreviate or skip steps in skills, even when output feels verbose
- [Fix failing skills](~/.claude/memory/feedback_fix_skills.md) — fix the skill definition instead of working around failures manually
- [Glob safety for numeric filenames](~/.claude/memory/feedback_glob_safety_windows.md) — `hex_4*.png` matches hex_40, hex_400, AND hex_441; use explicit ranges
- [Post-iteration cleanup audit](~/.claude/memory/feedback_post_iteration_cleanup.md) — before committing after a debug/optimize session, remove changes from disproven theories; don't leave cruft
- [Verify before justifying legacy behavior](~/.claude/memory/feedback_verify_before_justifying.md) — if explaining why old code/docs exist (especially defending keeping it), check the source before speculating; defensive guesses preserve cruft
- [Captured the lesson, drop the code](~/.claude/memory/feedback_research_to_production_cleanup.md) — when research code transitions to production, delete helpers whose rationale lives in docs
- [No permanent surface for one-time tasks](~/.claude/memory/feedback_no_permanent_logic_for_one_time.md) — do one-offs (backfills, migrations, seeding) as throwaways and delete; don't add a flag/helper/export to production for a single run, and don't justify it with "single source"/"future use"
- [Stay silent on user `!` commands](~/.claude/memory/feedback_silent_on_bash_input.md) — a bare `!`/bash-input result is the user's own action; return control immediately, no analysis or "looks good" filler, unless they ask
- [Fix bugs at the source, not in callers](~/.claude/memory/feedback_fix_at_source.md) — if a bug lives in code I can modify (including vendored copies), fix it at the source instead of working around or suppressing it (gitignore, filtering, silencing)
- [Generalize global skills, don't fork project-local](~/.claude/memory/feedback_generalize_global_skills.md) — name collisions silently load the wrong SKILL body; use the deploy skill's Context-probe-and-dispatch pattern instead
- [No unsolicited past-data fixes](~/.claude/memory/feedback_no_unsolicited_data_fixes.md) — fix the going-forward code only; don't proactively migrate/correct stale stored data unless asked or after asking
- [Native dialogs render plain text — no clickable links](~/.claude/memory/feedback_native_dialogs_no_links.md) — `tauri-plugin-dialog`/MessageBox/NSAlert can't embed `<a>`; build a custom Tauri webview window for About-style content with links
- [About dialogs describe WHAT, not HOW](~/.claude/memory/feedback_about_what_not_how.md) — About copy stays declarative ("Each session keeps a history"), not action-prescriptive ("Double-click to open")
- [Deploy via the script, not the deploy skill](~/.claude/memory/feedback_deploy_script_not_skill.md) — once a project is configured, run `bash scripts/deploy.sh` directly; reserve the deploy Skill for first-time setup
- [Use Doppler for secrets](~/.claude/memory/feedback_doppler_secrets.md) — default to Doppler (workplace `sava`) over plaintext .env for keys/secrets/tokens; `doppler run` wraps dev scripts, `doppler secrets set` to add; offer don't impose
- [Private references](~/.claude/memory/refs-private.secret.md) — encrypted (transcrypt); coordinates for ad-hoc third-party credentials Claude uses — read it when a task needs one (decrypted locally; opaque without the key)

## Memos

While working on one task the user often surfaces ideas for *other* work — "we should also debounce that search box", "remind me to cache these responses". They want these parked, not acted on, and they want Claude to hold them rather than carrying them in their own head. Memos are the backlog for exactly that: lighter than a GitHub issue (a half-formed thought, not a tracked unit of work), kept in a single committed file, `<repo>/.claude/memos.md`, as a dated `- [ ]` checklist. The `/memo` skill owns the file format and the read/write mechanics.

**Capture — offer, don't impose, and don't act.** When the user drops an idea that isn't part of the current task, offer to memo it ("Want me to memo that?") and append it only on a yes. Never silently record, and never start on the idea — capturing it is the whole point of *not* doing it now. For deliberate captures the user runs `/memo <text>` themselves. Either way the entry lands in `.claude/memos.md` in the format the `/memo` skill defines. Don't confuse a memo with an instruction: if it's plausibly "do this now", ask which they meant.

**Surface at three moments.** The backlog comes back on its own so the user never has to remember it:
- **Session start / `/clear`** — the `memos-surface.py` hook surfaces the open items in the **status bar** only (a transient "what's next" reminder), numbered newest-first to match `/memo`. It injects **nothing** into chat — so you never greet with or push the backlog — and the matching `UserPromptSubmit` hook clears the bar the moment the user sends anything. When that first message is a bare number (or "memo N" / "start N"), the hook injects, bound to that message, which memo it maps to; act on it — start that memo as a fresh task and check it off when done. Any other first message just proceeds normally, with memos unmentioned.
- **Task completion** — when you finish a task during which one or more memos were captured, end the wrap-up with those memos as a numbered list and offer to start one. Don't begin any unasked.
- **Commit** — `/commit` lists the open backlog after the push, alongside its issue notice.

At task completion and commit, the offer is the same: present a numbered list, let the user pick one or leave them. Picking one begins a fresh task; mark its entry `- [x]` once genuinely done.

## Reference Material

Before reinventing a plugin or skill, and whenever you feel under-informed about the technology or domain at hand, consult the official Anthropic repositories:
- Plugins: https://github.com/anthropics/claude-plugins-official
- Skills: https://github.com/anthropics/skills

Browse them for existing implementations to reuse, adapt, or learn from rather than building from scratch.

## Skills

Skills live in `.claude/skills/<skill-name>/` (project-local) or `~/.claude/skills/<skill-name>/` (global). The entry point for each skill is `SKILL.md`.
