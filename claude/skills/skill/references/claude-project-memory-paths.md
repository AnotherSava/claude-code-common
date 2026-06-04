# Claude project memory paths

Reference for any skill that needs to read or write files under `~/.claude/projects/<project-id>/` — most commonly the project's memory directory.

## Layout

Claude Code stores per-project data at:

```
~/.claude/projects/<project-id>/
├── memory/
│   ├── MEMORY.md           # index of project memories
│   └── <memory-name>.md    # individual memory files
└── ...                     # session logs, subagent history, etc.
```

`<project-id>` is a deterministic mangle of the project's absolute path, so any skill with the CWD can compute the path without enumerating the `projects/` directory.

## Mangling rule

Replace **every non-alphanumeric character** in the absolute path with a single `-`. Only `[a-zA-Z0-9]` survive unchanged (case included); separators, dots, underscores, and spaces all become `-`. Hyphens already in the path map to themselves, so they pass through unchanged.

| Input path                                  | Project ID                                |
| ------------------------------------------- | ----------------------------------------- |
| `D:\projects\my-app`                        | `D--projects-my-app`                      |
| `D:\projects\games\achievement-overlay`     | `D--projects-games-achievement-overlay`   |
| `D:\projects\instagram\ai.answers.daily`    | `D--projects-instagram-ai-answers-daily`  |
| `/home/oleg/projects/claude`                | `-home-oleg-projects-claude`              |

**Dots and underscores collapse to dashes too** — `ai.answers.daily` becomes `ai-answers-daily`, not `ai.answers.daily`. Verified against a real harness-written transcript path; do not assume dots are preserved.

**Common mistake:** do NOT replace path separators with `--` (double dash). Each character becomes exactly one `-`. `D:\` is `D--` only because `:` and `\` are two consecutive non-alphanumeric characters, each getting its own single replacement.

## Cross-platform CWD recipe

On Git Bash / MSYS, plain `pwd` returns Unix-style paths (`/d/projects/claude`), which mangle incorrectly. `pwd -W` returns the Windows-style path (`D:/projects/claude`), which mangles correctly. Linux and macOS use plain `pwd`.

Two-line bash snippet that works on all three:

```bash
cwd="$(pwd -W 2>/dev/null || pwd)"
project_id="$(printf '%s' "$cwd" | sed 's|[^a-zA-Z0-9]|-|g')"
```

The `2>/dev/null || pwd` fallback keeps it portable: `pwd -W` errors silently on POSIX shells and the fallback kicks in.

Full project-memory path:

```bash
project_memory="$HOME/.claude/projects/$project_id/memory"
```

## Gotchas

- **Case is preserved on Windows.** `D:` stays uppercase; do not lowercase the drive letter.
- **No trailing separator.** Mangling is applied to the canonical absolute path without a trailing slash. If your source has one, strip it first.
- **Symlinks resolve to their target.** If CWD is inside a symlinked directory, `pwd -P` (physical) may yield a different project ID than `pwd -L` (logical). Claude Code uses the *logical* path — the one the user invoked from — so prefer plain `pwd`/`pwd -W` over `pwd -P`.
- **Project may have no data yet.** `~/.claude/projects/<project-id>/` and its `memory/` subdirectory are created lazily. Any read should tolerate absence (`cat ... 2>/dev/null || echo "(none)"`); any write should `mkdir -p` first.
- **The `memory/` dir may be a symlink into the repo.** Repos wired with `~/.claude/scripts/link-project-memory.sh` replace the cache `memory/` dir with a symlink to a committed `<repo>/.claude/memory/`, so project memory is version-controlled. Reads follow the link transparently, but the Write/Edit tools refuse to write *through* a symlink — resolve it with `readlink` and write to the real repo path.
