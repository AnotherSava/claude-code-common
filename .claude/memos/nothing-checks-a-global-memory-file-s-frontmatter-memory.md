---
created: 2026-10-04 22:49:42
---

# Nothing checks a global memory file's frontmatter — memory-file-shape covers only .claude/memory/

Decide whether the global memory payload under `claude/memory/` should get a shape check, and if so whether it is a versioned rule or a universal one.

The gap, measured 2026-10-04: `claude/conventions/rules/memory-file-shape.py` sets `REL = ".claude/memory"` and walks `<root>/.claude/memory/`, so it governs a repo's *project* memory only. The 244-file global payload at `claude/memory/` is outside it. `claude/scripts/render-memory-index.py` is the only other thing that reads the area, and it opens `MEMORY.md` and writes `CLAUDE.md` without ever opening the files it links — so a global memory with missing or malformed frontmatter passes every check this repo runs.

The baseline, measured 2026-10-04: all 244 files open with `---`, so a check turned on now starts clean and has no existing violations to triage or scope out.

One false positive comes with it, and it is already known. The two transcrypt memories — `refs-private.secret.md` and `machines-private.secret.md` — pass that count only because this clone is unlocked; in a locked one they read as base64 and surface as a missing frontmatter line. The docstring of `memory-file-shape.py` names exactly that case for project memory, so any global equivalent inherits it and has to say so in its finding rather than leave a reader guessing.

How it surfaced: during /commit of `feedback_reject_what_was_proposed.md` the gate was reported as having validated that file's frontmatter. It had not — the forked /docs-relevance caught the claim, and reading the rule confirmed the scope. The file was fine, but only because a human read it.

The design question this needs: a versioned rule means every repo adopts a check for a directory only the dotfiles repo has, which is the wrong shape; a universal rule reaches every repo with no adoption, and the bar there is a property no migration could settle whose violation nothing else reports. Global memory shape arguably fails the universal test too, since it is one fact about one repo rather than about this machine's relationship to a repo. A third option is a plain suite under `claude/tests/` wired into `.claude/commit-checks.sh`, which is where this repo's own non-convention checks already live — that is probably the right home, and it needs no convention version at all.
