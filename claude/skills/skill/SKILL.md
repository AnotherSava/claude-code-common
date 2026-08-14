---
name: skill
description: >-
  Guidelines for creating and updating Claude Code skills.
  TRIGGER when: writing a new SKILL.md, modifying an existing skill, or the user asks about skill conventions.
---

# Skill Authoring Guidelines

Read this before creating or modifying any skill. These conventions ensure skills are consistent, minimal, and fast to invoke.

## Skill structure

```
skills/<skill-name>/
├── SKILL.md          # Entry point (required)
├── scripts/          # Helper scripts (optional)
└── references/       # Reference docs cited from SKILL.md (optional)
```

- Entry point is always `SKILL.md`
- Place in `~/.claude/skills/` for global skills, `.claude/skills/` for project-local
- Shared resources go in `~/.claude/skills/shared/`

## Addressing Claude project data (per-project memory, sessions, etc.)

If your skill needs to read or write anything under `~/.claude/projects/<project-id>/` — most commonly a project's memory directory — see `~/.claude/skills/skill/references/claude-project-memory-paths.md`. It documents the path mangling rule, the cross-platform CWD recipe, and the common gotchas. Cite that file from your skill rather than re-deriving the algorithm.

## Frontmatter

Every SKILL.md starts with YAML frontmatter:

```yaml
---
name: <skill-name>           # kebab-case, matches directory name
description: >-              # one-line summary for the skill list + trigger rules
  What the skill does.
  TRIGGER when: <conditions>.
allowed-tools: <tool-list>   # optional — restricts which tools the skill can use
---
```

### Description

The `description` field serves double duty: it appears in the skill list shown to the model, and it controls when the model auto-invokes the skill. Write it so that:

1. The **first sentence** summarizes what the skill does (shown in the skill list)
2. A **TRIGGER when:** clause lists the conditions for auto-invocation (if applicable)
3. Optionally, a **DO NOT TRIGGER when:** clause prevents false positives

### allowed-tools

Whitelist the minimum set of tools the skill needs. Use glob patterns for Bash:
```yaml
allowed-tools: Bash(git diff:*), Bash(git add:*), Read, Glob
```
Omit `allowed-tools` only if the skill genuinely needs unrestricted access.

## Writing the skill body

### Be prescriptive, not conversational

Skills are instructions, not documentation. Write them as numbered steps with exact commands. The model follows them literally — vague guidance produces inconsistent results.

### Reference shared rules

Don't duplicate conventions that exist in shared files. Reference them:
```
Read `~/.claude/skills/shared/bash-rules.md` for bash command constraints.
Read `~/.claude/skills/shared/commit-message-rules.md` for commit message formatting.
```

### Don't leave the detail in two places

When a new skill covers ground an existing memory or learning already documents, the skill takes the operational detail and the older file slims to a pointer — never both in full. Two full copies drift the moment one is updated, and which one gets read depends on whichever trigger fired first.

Update the pointer sites in the same change: the `CLAUDE.md` index line, and any hook whose injected reminder cites the old file. Keep in the memory only what the skill can't carry — the preference itself and the *why* — since a memory is always loaded while a skill is invoked on demand.

### Extract optional depth into `references/`

SKILL.md should carry only what every invocation needs. Deep, situational, or rarely-touched knowledge belongs in `references/<topic>.md` with a short pointer from SKILL.md describing *when* to consult it. The model reads the reference on demand, so the entry point stays lean and the detail loads only when relevant.

Good candidates for extraction:
- Recipes used by only a minority of invocations (e.g. a complex error-recovery flow, an uncommon platform variation)
- Long tables, example matrices, or edge-case catalogs
- Background rationale that helps when something goes wrong but isn't needed on the happy path
- Cross-skill knowledge where SKILL.md-level duplication would drift (the "Addressing Claude project data" section below is an example — most skills don't need path mangling, so it lives in `references/claude-project-memory-paths.md`)

Pointer style — cite with enough context that the model knows when to follow the link:
```
If <condition>, see `references/<topic>.md` for <what it covers>.
```

Keep it a one-liner in SKILL.md; the reference carries the depth.

### Always confirm before destructive actions

If the skill performs irreversible operations (commits, pushes, deletes, moves), require explicit user confirmation before executing. Show the plan first, then ask.

### Scope guard

State explicitly what the skill does NOT do. An "Out of scope" section prevents scope creep:
```
## Out of scope
- Do NOT amend existing commits
- Do NOT create or switch branches
```

## Injecting dynamic context with `!` commands

The `!`\`command\`` syntax in SKILL.md runs shell commands **automatically as preprocessing** before the skill content reaches the model. The command output replaces the placeholder inline — the model never sees the command, only the results. This eliminates the reconnaissance phase entirely.

See `~/.claude/learnings/skill-context-evaluator.md` for known limitations, workarounds, and which commands work reliably in context.

### How to write a Context section

When creating or updating a skill, identify every piece of data the skill needs before it can start its real work. For each one, add a labeled `!` line. Place the **Context** section at the top of the skill body (before the first process step).

Format — each line is a labeled command (backticks are escaped in these examples so invoking THIS skill doesn't execute them — preprocessing runs `!` lines even inside fenced code blocks; write them unescaped in your skill):
```markdown
## Context
- Uncommitted changes: !\`git status --short\`
- Diff summary: !\`git diff HEAD --stat\`
- Recent history: !\`git log --oneline -10\`
- Build errors: !\`npm run build 2>&1 | tail -n 50\`
```

For commands too complex for a single line, use a script:
```markdown
- Precondition checks: !\`bash ~/.claude/skills/<skill-name>/scripts/preflight.sh\`
```

### What qualifies as a context command

- **Read-only** — avoid mutations. Exception: idempotent setup commands (e.g. `git reset HEAD` to unstage) are allowed if they must run before the data-collection commands that follow.
- **No command substitution** — `$()` inside `!` commands is blocked by the permission checker. Use simple commands or fallback chains with `||` (e.g. `git log @{upstream}..HEAD 2>/dev/null`).
- **Deterministic** — runs the same way on every invocation, not conditional on prior results. Commands that can legitimately fail (e.g. `gh pr view` when no PR exists) must go in the skill body, not in context — the context evaluator treats any non-zero exit as a fatal error.
- **Labeled** — the label describes what data the command provides
- **Output-scoped** — limit output to what the skill actually needs. Use flags (`--short`, `--oneline`, `--stat`, `--format`), line limits (`-n`, `--limit`, `head -n`), field selectors (`--json ... --jq`), or filters (`grep`, `tail`) to trim noise. Unbounded output wastes context.
- **Complete** — if a process step needs data on every invocation, that data must be in the Context section. Process steps should never need to re-run a command that Context could have provided. When reviewing a skill, scan every command in the process steps — if it runs unconditionally, it belongs in Context. Since `!` commands are replaced by their output during preprocessing, the model never sees the command text — only the label and the output. Process steps must reference context data by its **label** (e.g. "use **Diff summary**"), never by the command that produced it (e.g. not "run `git diff --stat`").
- **CWD-portable** — global skills can be invoked from any project's working directory. Context commands that read files OUTSIDE that CWD (e.g. the skill's own config at `~/.claude/skills/<name>/...`) can be denied by Claude Code's auto-mode classifier as "scope escalation". The credential-heuristic is especially trigger-happy on `.env` filenames. See "Cross-CWD safety" below.

### Process steps should use context output directly

Since `!` commands are preprocessed, the data is always present when the model reads the skill. Process steps should reference the context output directly — no need to re-run commands or check whether data is available. When referring to context data in process steps, use the **same label** from the Context section (e.g. "**Ignore rules** from Context above"), not the underlying filename or command — the model sees labels, not filenames.

### Prune unused context items

Every context item must be referenced by at least one process step (by its label). When reviewing or updating a skill, scan the Context section and remove any items that no process step uses — unused context wastes the preprocessing budget and pollutes the model's input with irrelevant data.

### Cross-CWD safety

A user can invoke any global skill from any project. The skill's own config / reference files live in `~/.claude/skills/<name>/`, which is *outside* the user's CWD whenever the CWD isn't `~/.claude/`. Claude Code's auto-mode classifier runs heuristics on every Bash command — when a `!` Context command reads outside the CWD, especially from `.env`-suffixed files, it may deny with: `"scope escalation beyond the <repo> repo and may expose credentials"`.

Mitigations, in order of preference:

1. **Existence-check, not content-read.** Use `!` + `test -f ~/.claude/skills/<name>/config/<file> && echo PRESENT || echo MISSING` and branch on the literal `PRESENT`/`MISSING` in process steps. No file content is read; the credential heuristic doesn't fire.
2. **Avoid `.env` filenames** for skill-local config. Use `.conf`, `.ini`, `.txt`, or no extension. The classifier treats `.env` as credential-bearing regardless of actual contents.
3. **Whitelist with `:*` wildcard** in `allowed-tools` when the compound form `cmd && X || Y` is needed:
   `Bash(test -f ~/.claude/skills/<name>/config/<file>:*)`. The `:*` allows arguments and shell continuations after the prefix.
4. **Read content via the `Read` tool**, not Bash, when content really is required. `Read(~/.claude/skills/<name>/config/<file>)` declared in `allowed-tools` doesn't go through the Bash classifier.

If the skill's own script (`Bash(python3 ~/.claude/skills/<name>/scripts/<script>)`) is also denied when invoked from outside CWD, the user can add a project-local or global permission rule in `settings.json` allowing scripts under `~/.claude/skills/`.

## Full-width terminal output

When a skill renders output meant to fill the terminal — a table, an aligned/wrapped listing — it must detect the terminal width, because the rendering script can't.

**Why the script can't self-detect.** A skill's helper runs with its stdout **piped** (the `!` context capture, or the Bash tool), so `shutil.get_terminal_size()` / `tput cols` *inside the script* return a fallback, not the real window. For the same reason, **width-dependent rendering must not live in a Context `!` line** — that always renders at the fallback width. Render it in a process step instead, after detecting the width.

**The pattern** (reuse the `github-status` skill's implementation):

1. Detect the width yourself, in a process step:
   - **Windows:** the **PowerShell tool** evaluating `$Host.UI.RawUI.WindowSize.Width` — the PowerShell tool specifically; `powershell.exe` from Bash gets its own console and reports the wrong value.
   - **macOS/Linux:** `tput cols` (or `$COLUMNS`).
2. Subtract a small gutter (≈2 columns) — Claude Code's TUI indents tool/message output, so content exactly as wide as the window gets its right edge clipped.
3. Pass the result to the helper as `--width <N>`; the helper honors `--width`, else falls back to `get_terminal_size()` then a fixed default. If detection fails, omit `--width` and accept the fallback.

Add `PowerShell` and `Bash(tput cols:*)` to `allowed-tools` for the detection step. Working examples: `~/.claude/skills/github-status` (a bordered table) and `~/.claude/skills/memo` (a wrapped, aligned listing).

## Gitignore

A skills directory is usually covered by an ignore-everything-then-allowlist rule, so a new skill can end up untracked with no signal at all: it never appears in `git status`, and the only copy lives on the machine that created it. Verify tracking as the final step of creating a skill — don't skip it because the skill obviously sits inside a tracked repo.

Ask git instead of reading an ignore file by hand:

1. Resolve the symlink — `readlink ~/.claude/skills` gives the real directory inside the dotfiles repo.
2. From that repo, check the new skill by its **repo-relative** path: `git check-ignore -v claude/skills/<skill-name>/`

Interpret the result:

| Result | Meaning | Action |
|---|---|---|
| exit 1, no output | not ignored | tracked — done |
| exit 0 + a `<file>:<line>:<pattern>` citation | ignored | add `!claude/skills/<skill-name>/` to the cited file, beside its siblings, and re-run until it exits 1 |
| exit 128, `is outside repository` | the `~/.claude/...` symlink path was passed | retry with the resolved path from step 1 |

Two traps this avoids:

- **Checking a file that can't hold the pattern.** The allowlist normally lives in the dotfiles repo's own `.gitignore`, not the global one (`git config --global core.excludesfile`). Inspecting only the global file reports "nothing excludes it" while the skill stays untracked. Only `check-ignore` names the file and line that actually decides.
- **Reading exit 128 as success.** It is non-zero, so a bare `if git check-ignore …; then` classifies the skill as tracked when the path was merely unresolvable.

To catch skills that are already missing an entry, audit them all from the repo root:

```bash
ls claude/skills | sed 's|^|claude/skills/|; s|$|/|' | git check-ignore -v --stdin
```

Every line of output is an untracked skill; no output means all are tracked. A skill that should also be *published* needs its `### <Title>` section in the repo README — being tracked is necessary, not sufficient.

## Shell environment

Skills that configure bash functions (like `build` and `deploy`) should reference `~/.claude/learnings/shell-environment.md` for the canonical list of expected functions and the verification checklist. When adding a new bash function to a skill, update that file too.

## Cross-platform scripts (Windows + macOS)

Skills run on both Windows (Git Bash) and macOS (zsh/bash), so every script and `!` context command a skill emits must work on both — never assume one OS.

- **Shell rc file** — don't hardcode `~/.bashrc`. Detect the target per-OS (zsh on macOS, bash on Windows Git Bash / Linux) and grep across all candidates when checking whether a function is installed. Reuse the probe the `deploy` / `build` skills already use:
  ```bash
  case "$(uname -s)" in Darwin) echo "~/.zshrc" ;; MINGW*|MSYS*|CYGWIN*) echo "~/.bashrc" ;; *) [ -n "$ZSH_VERSION" ] || [ "${SHELL##*/}" = "zsh" ] && echo "~/.zshrc" || echo "~/.bashrc" ;; esac
  ```
- **OS-specific commands** — branch on `uname -s` and give both arms (as the Full-width terminal section does: `tput cols` on macOS/Linux vs the PowerShell tool on Windows). Never emit a command that exists on only one OS without a fallback.
- **Stay POSIX** — a snippet appended to the rc may run under bash *or* zsh. Use constructs both accept (`[ … ]`, `case`, `$( )`); avoid bash-only `[[ … ]]`/arrays where a POSIX form works, and avoid zsh-only syntax.
- **Beware tool flag drift** — macOS ships BSD `sed`/`grep`/`date` whose flags differ from GNU (e.g. `sed -i` needs an arg on BSD). Prefer portable invocations, or cross-platform tools the skill can already rely on (`git`, `node`, `python`).
- **Paths** — forward slashes everywhere (see Conventions); `~`/`$HOME` resolve on both; never assume drive letters.
- **Verify on the OS you're on, and reason explicitly about the other** before shipping — a Windows-only `!` command silently breaks a macOS user's skill run, and vice versa.

## Conventions

- **One command per Bash call** in skills that use `allowed-tools` with Bash patterns (see `~/.claude/skills/shared/bash-rules.md`)
- **Imperative mood** in instructions ("Run", "Check", "Ask the user")
- **No `cd`** — the working directory is the project root
- **Forward slashes** in all paths (Windows bash compatibility)
- **Heredocs** for multi-line content passed to commands
