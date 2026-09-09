#!/usr/bin/env sh
# Report the current output-shaping configuration. Read-only, never fails: any
# problem is printed as a finding rather than raised, so the skill's Context
# section always renders.
#
# The important check is the last one. An unknown or unreachable output style is
# a silent no-op in Claude Code — exit 0, no warning — so a session with a
# missing symlink looks identical to a working one. Only naming the selection
# and the file separately can tell those apart.

CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SKILL_DIR="$CLAUDE_DIR/skills/tune-output"

PY=python3
command -v python3 >/dev/null 2>&1 || PY=python
command -v "$PY" >/dev/null 2>&1 || PY=""

selected=""
if [ -f "$CLAUDE_DIR/settings.json" ] && [ -n "$PY" ]; then
  selected=$("$PY" -c 'import json,sys
try: print(json.load(open(sys.argv[1],encoding="utf-8")).get("outputStyle","") or "")
except Exception: print("")' "$CLAUDE_DIR/settings.json" 2>/dev/null)
fi

if [ -z "$selected" ]; then
  echo "output style selected: NONE (settings.json has no outputStyle key -> harness default)"
else
  echo "output style selected: $selected"
  found=""
  for d in "$CLAUDE_DIR/output-styles" ./.claude/output-styles; do
    [ -f "$d/$selected.md" ] && found="$d/$selected.md" && break
  done
  if [ -n "$found" ]; then
    echo "  style file: $found"
    if grep -qi '^keep-coding-instructions:[[:space:]]*true' "$found"; then
      echo "  keep-coding-instructions: true"
    else
      echo "  keep-coding-instructions: MISSING -- built-in engineering instructions are being dropped"
    fi
  else
    echo "  style file: NOT FOUND -- the selection is a silent no-op, nothing is being applied"
  fi
fi

if [ -e "$CLAUDE_DIR/output-styles" ]; then
  if [ -L "$CLAUDE_DIR/output-styles" ]; then
    echo "output-styles dir: symlinked (ok)"
  else
    echo "output-styles dir: present but NOT a symlink -- edits here are not in the dotfiles repo"
  fi
else
  echo "output-styles dir: ABSENT at $CLAUDE_DIR/output-styles"
fi

if [ -f "$SKILL_DIR/ledger.md" ]; then
  # `; true` not `|| echo 0`: grep -c prints its count AND exits 1 when that count
  # is zero, so the fallback branch fires on a legitimate 0 and n gets both values.
  n=$(grep -c '^## [0-9]' "$SKILL_DIR/ledger.md" 2>/dev/null; true)
  echo "ledger: $n pass(es) recorded; most recent:"
  grep '^## [0-9]' "$SKILL_DIR/ledger.md" 2>/dev/null | tail -3 | sed 's/^## /  - /'
else
  echo "ledger: MISSING at $SKILL_DIR/ledger.md"
fi

exit 0
