# Global Guidelines

Never prepend `cd` to commands — the working directory is already the project root.
Use relative paths for files inside the project. Absolute paths are acceptable for files outside the project root.

Never use absolute paths in committed documentation (README, CLAUDE.md, docs/, comments). Use relative paths for files within the project and generic descriptions for external references (e.g. "the BGA extension repo" not `D:\projects\bga\assistant`). Absolute paths are machine-specific and break for other contributors.

Always ask clarifying questions before implementing if anything is ambiguous or unclear.

## Self-Sufficiency

Before asking the user to do something (run a command, edit a file, check a value), figure out how to do it yourself. If the action is non-destructive, just do it. If it's destructive or irreversible, ask the user for permission — but propose the concrete action, don't ask the user to perform it.

When changes are ready to test, run the project's `deploy` command (or equivalent) yourself via Bash. Do not suggest the user "run `deploy`" or type `! deploy`. The Self-Sufficiency rule applies: invoke the action, don't outsource it.

Exclude `node_modules/` from all file and content search patterns — it clogs results with false positives.

Do not inline Python scripts into Bash commands via `python -c`. Instead, use a heredoc: `python <<'EOF' ... EOF`.

Do not add logic, data structures, classes, or exports to production code that exist only to support tests. Tests should exercise the public API and real behavior — not rely on test-only hooks, flags, exports, or types in production modules.

## Git Workflow

- Do not create git commits unless explicitly asked
- Do not push to remote unless explicitly requested
- Follow `~/.claude/skills/shared/commit-message-rules.md`
- Prefer `git status --short` over `git diff --stat` for change-set summaries. Changes sit unstaged until `/commit` runs, so untracked files are part of the pending commit — and `git diff --stat` silently omits them, producing an incomplete picture.

## Windows Bash Commands

When running commands via Bash on Windows, always use forward slashes (`/`) in paths, not backslashes (`\`). Backslashes are interpreted as escape characters by bash and get stripped.

When asking the user to run a command manually (e.g. launching an app, system config), provide PowerShell syntax — not bash or cmd.

## Code Style

### Formatting

- Leave an empty line at the end of every file
- Prefer single-line expressions over multi-line formatting, even if they're long. **Exception**: multi-line is acceptable when calling functions/constructors with all named parameters.

### UI Text Casing

Default to sentence case for user-facing UI strings (menu items, buttons, dialog titles, tooltips, notifications). Capitalize only the first word and proper nouns/acronyms. Examples: "Open config file", "Hide with Esc", "Start with Windows". See `~/.claude/memory/feedback_sentence_case_ui.md` for rationale and edge cases.

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

## Gitignore

When adding entries to `.gitignore`, choose the right scope:
- **Global gitignore** (`~/.gitignore_global`): OS-specific or user-specific files — IDE folders, OS thumbnail caches, tool outputs for tools the user happens to use (e.g. `.idea/`, `Thumbs.db`, `.ralphex/`).
- **Project gitignore** (`.gitignore`): files that everyone who checks out the project should ignore — build outputs, `.env` files, `node_modules/`, `__pycache__/`.

## Symlinks

- **Windows:** Never create symlinks from Bash (`ln -s`) — it silently creates copies instead. Use PowerShell `New-Item -ItemType SymbolicLink` from an Administrator prompt. Use `$PWD` to build absolute target paths.
- **Linux / macOS:** Use `ln -s` with an absolute target path (`"$(pwd)/..."`).

## Global Memory

Cross-project preferences and feedback. Memory files live in `~/.claude/memory/`. When saving a memory that applies across all projects (not just the current one), write the file there and add an index entry below. Same frontmatter format as project-specific memories.

- [Follow skill instructions exactly](~/.claude/memory/feedback_follow_skill_instructions.md) — never abbreviate or skip steps in skills, even when output feels verbose
- [Fix failing skills](~/.claude/memory/feedback_fix_skills.md) — fix the skill definition instead of working around failures manually
- [Glob safety for numeric filenames](~/.claude/memory/feedback_glob_safety_windows.md) — `hex_4*.png` matches hex_40, hex_400, AND hex_441; use explicit ranges
- [Post-iteration cleanup audit](~/.claude/memory/feedback_post_iteration_cleanup.md) — before committing after a debug/optimize session, remove changes from disproven theories; don't leave cruft

## Skills

Skills live in `.claude/skills/<skill-name>/` (project-local) or `~/.claude/skills/<skill-name>/` (global). The entry point for each skill is `SKILL.md`.
