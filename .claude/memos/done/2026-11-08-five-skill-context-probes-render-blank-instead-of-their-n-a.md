---
created: 2026-10-01 19:08:57
---

# Five skill context probes render blank instead of their n/a fallback

The `!` context probes in `release/SKILL.md` and `publish/SKILL.md` cannot reach their documented fallback, so an absent file renders as an empty value rather than `n/a`/`none` — the agent reading the context block cannot tell "not present" from "probe broke".

Two independent defects stack in the same lines.

1. `head` exits 0 on empty input, so `… | head -1 || echo n/a` never runs the fallback. Reproduced 2026-10-01:

       printf '' | head -1 ; echo $?                      # 0
       ls /nonexistent 2>/dev/null | head -1 || echo none  # prints nothing, exit 0

2. The globs in those lines are unquoted, so under zsh (what the Bash tool runs on macOS) `nomatch` aborts the whole command substitution before the pipeline runs at all. Platform-independent on the `head` half, macOS-only on this half.

The affected lines:

- `claude/skills/release/SKILL.md` — AssemblyName (`"$R"/src/*.csproj`), Tauri Cargo version
- `claude/skills/publish/SKILL.md` — Compose file, Vhost file, CI publish workflow

The fix shape, which is why this was not folded into the 2026-10-01 wrap-up commit: quote each glob, and replace `| head -1 || echo X` with capture-then-test. The signing-policy probe in `release/SKILL.md` already does it right and is the pattern to copy:

       F=$(… | head -3 | tr '\n' ' '); [ -n "$F" ] && echo "$F" || echo none

One trap when picking this up: `tmp/docs-relevance-2026-10-01.patch` holds a one-line change to that signing probe — the single line in the set whose fallback was already sound. Applying it fixes nothing and leaves the five broken lines untouched. Fix the whole enumerated set or none of it.

Background on the shell half is in `claude/learnings/bash-portability.md`, under the bracket-glob section (commit 787e931).
