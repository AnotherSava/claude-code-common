# Global Guidelines

Never prepend `cd` to commands — the working directory is already the project root.
Use relative paths for files inside the project. Absolute paths are acceptable for files outside the project root.

Never use absolute paths in committed documentation (README, CLAUDE.md, docs/, comments). Use relative paths for files within the project and generic descriptions for external references (e.g. "the BGA extension repo" not `D:\projects\bga\assistant`). Absolute paths are machine-specific and break for other contributors.

Always ask clarifying questions before implementing if anything is ambiguous or unclear.

## Self-Sufficiency

Before asking the user to do something (run a command, edit a file, check a value), figure out how to do it yourself. If the action is non-destructive, just do it. If it's destructive or irreversible, ask the user for permission — but propose the concrete action, don't ask the user to perform it.

Exclude `node_modules/` from all file and content search patterns — it clogs results with false positives.

Do not inline Python scripts into Bash commands via `python -c`. Instead, use a heredoc: `python <<'EOF' ... EOF`.

Do not add logic, data structures, classes, or exports to production code that exist only to support tests. Tests should exercise the public API and real behavior — not rely on test-only hooks, flags, exports, or types in production modules.

## Git Workflow

- Do not create git commits unless explicitly asked
- Do not push to remote unless explicitly requested
- Follow `~/.claude/skills/shared/commit-message-rules.md`

## Windows Bash Commands

When running commands via Bash on Windows, always use forward slashes (`/`) in paths, not backslashes (`\`). Backslashes are interpreted as escape characters by bash and get stripped.

When asking the user to run a command manually (e.g. launching an app, system config), provide PowerShell syntax — not bash or cmd.

## Code Style

### Formatting

- Leave an empty line at the end of every file
- Prefer single-line expressions over multi-line formatting, even if they're long. **Exception**: multi-line is acceptable when calling functions/constructors with all named parameters.

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

## Skills

Skills live in `.claude/skills/<skill-name>/` (project-local) or `~/.claude/skills/<skill-name>/` (global). The entry point for each skill is `SKILL.md`.
