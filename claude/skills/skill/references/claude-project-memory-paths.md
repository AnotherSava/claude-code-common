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

Replace each `:`, `/`, and `\` in the absolute path with a single `-`. Everything else (case, dots, hyphens already in the path) is preserved.

| Input path                                  | Project ID                                |
| ------------------------------------------- | ----------------------------------------- |
| `D:\projects\my-app`                        | `D--projects-my-app`                      |
| `D:\projects\games\achievement-overlay`     | `D--projects-games-achievement-overlay`   |
| `/home/oleg/projects/claude`                | `-home-oleg-projects-claude`              |

**Common mistake:** do NOT replace path separators with `--` (double dash). Each `:`, `\`, `/` becomes exactly one `-`. `D:\` is `D--` only because `:` and `\` are two consecutive characters, each getting its own single replacement.

## Cross-platform CWD recipe

On Git Bash / MSYS, plain `pwd` returns Unix-style paths (`/d/projects/claude`), which mangle incorrectly. `pwd -W` returns the Windows-style path (`D:/projects/claude`), which mangles correctly. Linux and macOS use plain `pwd`.

Two-line bash snippet that works on all three:

```bash
cwd="$(pwd -W 2>/dev/null || pwd)"
project_id="$(printf '%s' "$cwd" | sed 's|[:/\\]|-|g')"
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
