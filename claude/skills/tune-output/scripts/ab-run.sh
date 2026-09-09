#!/usr/bin/env bash
# Generate both arms of a response-style A/B.
#
#   ab-run.sh <candidate-rule.md> <prompts.json> <out-dir>
#
# Arm A is today's behaviour. Arm B adds the candidate, selected through the same
# `outputStyle` settings key production would use, so the test exercises the real
# mechanism rather than an approximation of it.
#
# Both arms load the user's real global CLAUDE.md. Do not "isolate" that away: a
# config-less baseline measures the candidate against a bare Claude and flatters
# it. The question is what the candidate adds to the rules already in force.
#
# The cwd is a scratch dir outside every repo, so no project CLAUDE.md and no git
# status reach either arm.
#
# ISOLATION is the flag combination below, and it is not obvious. `--tools ""` does
# NOT disable anything — it is silently ignored, and a run using it reaches every
# MCP server the user has configured. That failure is invisible in the output
# unless a response happens to cite something it could only have fetched. What
# works, verified behaviourally:
#   --strict-mcp-config                     drops every MCP server
#   --disallowed-tools WebSearch WebFetch Bash   drops the remaining live-state tools
# `--restricted` also drops MCP, but it ignores user settings files and takes the
# global CLAUDE.md with them, which defeats the point of the baseline. File tools
# stay enabled and are harmless: the scratch cwd is empty.

set -euo pipefail

RULE="${1:?usage: ab-run.sh <candidate-rule.md> <prompts.json> <out-dir>}"
PROMPTS="${2:?usage: ab-run.sh <candidate-rule.md> <prompts.json> <out-dir>}"
OUT="${3:?usage: ab-run.sh <candidate-rule.md> <prompts.json> <out-dir>}"
MODEL="${AB_MODEL:-claude-opus-5}"
STYLE=ab-candidate
ISOLATION="--strict-mcp-config --disallowed-tools WebSearch WebFetch Bash"

# Flag-level isolation is not sufficient on its own -- see references/ab-harness.md.
# This preamble goes on BOTH arms, identically, so it cannot bias the comparison. It
# constrains where the answer comes FROM, and says nothing about how it is shaped.
PREAMBLE='Answer directly, from what you already know. Do not use any tools, do not read or search any files, do not search the web, and do not spawn subagents. Treat this as a question to answer in one reply, not a task to execute.

'

PY=python3
command -v python3 >/dev/null 2>&1 || PY=python

[ -f "$RULE" ] || { echo "no such rule file: $RULE" >&2; exit 1; }
[ -f "$PROMPTS" ] || { echo "no such prompts file: $PROMPTS" >&2; exit 1; }

mkdir -p "$OUT"
cp "$PROMPTS" "$OUT/prompts.json"
cp "$RULE" "$OUT/rule.md"

SCRATCH=$(mktemp -d)
cleanup() { rm -rf "$SCRATCH"; }
trap cleanup EXIT INT TERM

mkdir -p "$SCRATCH/.claude/output-styles"
{
  printf -- '---\nname: %s\ndescription: A/B candidate\nkeep-coding-instructions: true\n---\n\n' "$STYLE"
  cat "$RULE"
} > "$SCRATCH/.claude/output-styles/$STYLE.md"

n=$("$PY" -c 'import json,sys; print(len(json.load(open(sys.argv[1],encoding="utf-8"))))' "$PROMPTS")
echo "model: $MODEL"
echo "pairs: $n  ->  $OUT"

for i in $(seq 0 $((n - 1))); do
  id=$("$PY" -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8"))[int(sys.argv[2])]["id"])' "$PROMPTS" "$i")
  "$PY" -c 'import json,io,sys
c=json.load(open(sys.argv[1],encoding="utf-8"))[int(sys.argv[2])]["prompt"]
io.open(sys.argv[3],"w",encoding="utf-8").write(sys.argv[4]+c)' "$PROMPTS" "$i" "$SCRATCH/p.txt" "$PREAMBLE"

  for arm in A B; do
    echo "  [$((i + 1))/$n] $id  arm $arm"
    if [ "$arm" = A ]; then
      ( cd "$SCRATCH" && claude -p --model "$MODEL" $ISOLATION < p.txt ) > "$OUT/$i.$arm.md" 2>&1 \
        || echo "ARM $arm FAILED" >> "$OUT/$i.$arm.md"
    else
      ( cd "$SCRATCH" && claude -p --model "$MODEL" $ISOLATION \
          --settings "{\"outputStyle\":\"$STYLE\"}" < p.txt ) > "$OUT/$i.$arm.md" 2>&1 \
        || echo "ARM $arm FAILED" >> "$OUT/$i.$arm.md"
    fi
    # An empty file is a failed call that exited 0. It reads as a legitimately
    # terse answer in the sheet, so flag it here rather than letting it be judged.
    [ -s "$OUT/$i.$arm.md" ] || echo "ARM $arm RETURNED NOTHING -- re-run this pair" > "$OUT/$i.$arm.md"
  done
done

echo
echo "arms written. Re-run any pair reporting FAILED or RETURNED NOTHING before building the sheet."
echo "next: $PY ~/.claude/skills/tune-output/scripts/ab-sheet.py $OUT"
