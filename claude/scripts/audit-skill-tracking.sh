#!/usr/bin/env bash
# Report skills that git is ignoring because nobody added their allowlist line.
#
# A skills directory is normally ignore-everything-then-allowlist
# (`claude/skills/*` plus one `!claude/skills/<name>/` per skill). Miss the line
# and the skill is invisible: it never shows in `git status`, so nothing signals
# the omission and the only copy stays on the machine that made it.
#
# The skill-tracked.py hook catches the common case at creation time, but only
# for a SKILL.md written through the Write tool. A directory that was copied,
# moved, renamed, unpacked by a plugin, or created from a shell heredoc slips
# past it — as does a skill that was already unregistered. This is the sweep
# that does not care how the directory got there.
#
# Everything it prints is meant to be acted on, so three kinds of noise are
# filtered out:
#
#   * Symlinked skills — externally installed (a plugin, ~/.agents/skills).
#     Their content lives elsewhere and was never this repo's to commit.
#   * Skills named in `<skills-parent>/untracked-skills.local.txt` — the
#     decisions file, holding skills confirmed as machine-local on purpose. A
#     decision recorded there survives /clear and a new session, so it is never
#     asked twice. The file is itself gitignored and per-machine, because the
#     set of locally-installed skills differs between machines; a fresh clone
#     has none, and every skill is decided again there.
#   * Skills ignored by an EXPLICIT per-skill rule rather than a wildcard. An
#     exact path in .gitignore is already an unambiguous "keep this one out".
#
# Usage: audit-skill-tracking.sh [repo-root]      (default: cwd's repo)
# Exit:  0 always — a reporting tool, safe in a skill's `!` context probe.

set -u

root=$(git -C "${1:-.}" rev-parse --show-toplevel 2>/dev/null) || exit 0

# Load the decisions files once: one skill-directory name per line, `#` comments
# and blank lines ignored. They sit beside `skills/` rather than inside it, so
# the blanket `skills/*` rule cannot swallow the file recording these decisions.
#
# Trimming uses parameter expansion only. An earlier version shelled out per
# line (`$(printf … | tr …)`); at Windows process-spawn cost that turned a
# 28-line comment header into a ~30s stall, which would hang the `!` context
# probe that calls this. Keep this loop free of subshells.
declared=$'\n'
for list in "$root"/claude/untracked-skills.local.txt "$root"/.claude/untracked-skills.local.txt; do
    [ -f "$list" ] || continue
    while IFS= read -r line || [ -n "$line" ]; do
        line=${line%%#*}
        line=${line#"${line%%[![:space:]]*}"}   # ltrim
        line=${line%"${line##*[![:space:]]}"}   # rtrim
        [ -n "$line" ] && declared="$declared$line"$'\n'
    done < "$list"
done

# Both layouts: a dotfiles-style checkout (claude/skills/) and a project's own
# .claude/skills/. A literal glob (no match) is filtered by the -d test.
candidates=()
for dir in "$root"/claude/skills/*/ "$root"/.claude/skills/*/; do
    [ -d "$dir" ] || continue
    stripped=${dir%/}
    [ -L "$stripped" ] && continue          # externally installed, not ours to commit
    name=${stripped##*/}
    case $declared in *$'\n'"$name"$'\n'*) continue ;; esac
    candidates+=("${dir#"$root"/}")
done
[ ${#candidates[@]} -eq 0 ] && exit 0

printf '%s\n' "${candidates[@]}" \
    | git -C "$root" check-ignore -v --stdin 2>/dev/null \
    | while IFS=$'\t' read -r rule path; do
        # rule is <source>:<line>:<pattern>; the pattern is everything after the
        # second colon, so a Windows path like C:/... in the source cannot split it.
        pattern=${rule#*:}
        pattern=${pattern#*:}
        # No wildcard => an exact, deliberate rule. Only a blanket glob is a miss.
        case $pattern in
            *[*?[]*) printf '%s\tignored by %s\n' "$path" "$rule" ;;
        esac
    done

exit 0
