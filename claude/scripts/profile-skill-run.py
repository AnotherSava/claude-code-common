#!/usr/bin/env python3
"""Profile the wall-clock cost of a skill invocation from a session transcript.

Reads `~/.claude/projects/<slug>/*.jsonl`, finds an invocation of the named skill,
and reports where its seconds went: model time against tool time, a phase per
nested sub-skill, and optionally the turn-by-turn timeline.

    profile-skill-run.py commit                     # this project, newest run
    profile-skill-run.py commit --project tripit    # another project
    profile-skill-run.py commit --timeline          # every turn
"""

from __future__ import annotations

import argparse
import datetime
import glob
import json
import os
import sys

PROJECTS = os.path.expanduser("~/.claude/projects")


def slug_for(path: str) -> str:
    """Claude Code's project directory name: the absolute path with separators as dashes."""
    return os.path.abspath(path).replace("/", "-").replace(".", "-")


def resolve_project(name: str | None) -> str:
    """Return the transcript directory for a project named by slug, path, or basename."""
    if name is None:
        return os.path.join(PROJECTS, slug_for(os.getcwd()))
    if os.path.isdir(name):
        return os.path.join(PROJECTS, slug_for(name))
    direct = os.path.join(PROJECTS, name)
    if os.path.isdir(direct):
        return direct
    candidates = [d for d in glob.glob(os.path.join(PROJECTS, "*")) if name in os.path.basename(d)]
    exact = [d for d in candidates if os.path.basename(d).endswith(f"-{name}")]
    matches = exact or candidates
    if len(matches) != 1:
        listing = ", ".join(sorted(os.path.basename(d) for d in matches)) or "none"
        raise SystemExit(f"{len(matches)} project dirs match {name!r}: {listing}")
    return matches[0]


def stamp(row: dict) -> datetime.datetime | None:
    raw = row.get("timestamp")
    return datetime.datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None


def load(path: str) -> list[dict]:
    rows = []
    with open(path) as handle:
        for line in handle:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def find_invocation(rows: list[dict], skill: str) -> int | None:
    """Index of the last turn that invoked `skill`, whether typed or called by the model."""
    typed = f"<command-name>/{skill}</command-name>"
    found = None
    for i, row in enumerate(rows):
        blob = json.dumps(row.get("message", {}))
        if typed in blob or f'"skill":"{skill}"' in blob or f'"skill": "{skill}"' in blob:
            found = i
    return found


def tool_uses(row: dict) -> list[tuple[str, dict]]:
    content = (row.get("message") or {}).get("content") or []
    return [(c["name"], c.get("input", {})) for c in content if isinstance(c, dict) and c.get("type") == "tool_use"]


def has_tool_result(row: dict) -> bool:
    content = (row.get("message") or {}).get("content")
    return any(isinstance(c, dict) and c.get("type") == "tool_result" for c in content or [])


APPROVALS = {"y", "n", "yes", "no", "ok", "okay", "go", "go ahead", "continue", "proceed", "do it", "sure"}


def user_text(row: dict) -> str | None:
    """The text a user typed in this row, or None when it carries only tool results."""
    if row.get("type") != "user":
        return None
    content = (row.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    parts = [c.get("text", "") for c in content or [] if isinstance(c, dict) and c.get("type") == "text"]
    return "\n".join(parts) if parts else None


def find_end(rows: list[dict], start: int) -> int:
    """Index one past the run: the next typed instruction, past approvals and the harness's own notes."""
    for i in range(start + 1, len(rows)):
        text = user_text(rows[i])
        if text is None:
            continue
        stripped = text.strip()
        if stripped.lower().rstrip(".!") in APPROVALS:
            continue
        if stripped.startswith(("Base directory for this skill:", "<", "[")) or "system-reminder" in stripped:
            continue
        return i
    return len(rows)


def profile(rows: list[dict], start: int, end: int, timeline: bool) -> None:
    begin = stamp(rows[start])
    previous = begin
    model_seconds = tool_seconds = 0.0
    turns = 0
    tool_counts: dict[str, int] = {}
    marks: list[tuple[str, float]] = [("own steps", 0.0)]
    slowest: list[tuple[float, str]] = []
    pending = "?"
    cache_read = cache_write = output = 0

    for i in range(start + 1, end):
        now = stamp(rows[i])
        if now is None:
            continue
        delta = (now - previous).total_seconds()
        previous = now
        offset = (now - begin).total_seconds()
        row_kind = rows[i].get("type") or "?"
        label = ""

        if row_kind == "assistant":
            model_seconds += delta
            turns += 1
            usage = (rows[i].get("message") or {}).get("usage") or {}
            cache_read += usage.get("cache_read_input_tokens", 0)
            cache_write += usage.get("cache_creation_input_tokens", 0)
            output += usage.get("output_tokens", 0)
            for name, args in tool_uses(rows[i]):
                tool_counts[name] = tool_counts.get(name, 0) + 1
                label += f" {name}"
                detail = args.get("command") or args.get("file_path") or args.get("skill") or ""
                pending = f"{name}({str(detail)[:60]})"
                if name == "Skill":
                    marks.append((f"from /{args.get('skill')}", offset))
        else:
            tool_seconds += delta
            if has_tool_result(rows[i]):
                slowest.append((delta, pending))

        if timeline:
            print(f"  {offset:7.1f}s  +{delta:5.1f}s  {row_kind:9s}{label}")

    total = (previous - begin).total_seconds()
    marks.append(("(end)", total))

    print(f"\ntotal {total:.0f}s   model {model_seconds:.0f}s ({model_seconds / total:.0%})"
          f"   tool+idle {tool_seconds:.0f}s   turns {turns}")
    print(f"context re-read {cache_read / 1e6:.1f}M tok over {turns} turns"
          f" (~{cache_read // max(turns, 1) // 1000}k per turn)"
          f"   bodies loaded {cache_write // 1000}k   output {output // 1000}k")

    print("\nsegment                   seconds   share")
    for (name, at), (_, nxt) in zip(marks, marks[1:]):
        span = nxt - at
        print(f"  {name:23s} {span:7.1f}   {span / total:5.0%}")
    print("  a sub-skill has no return marker, so a segment runs to the next sub-skill or the end —")
    print("  the last one also carries whatever the parent did after that sub-skill returned")

    print("\ntool calls: " + ", ".join(f"{n}×{c}" for n, c in sorted(tool_counts.items(), key=lambda kv: -kv[1])))

    print("\nslowest waits (a `sleep` here is the skill choosing to wait, not latency)")
    for delta, what in sorted(slowest, reverse=True)[:5]:
        print(f"  {delta:6.1f}s  {what}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("skill", help="skill name as invoked, without the slash")
    parser.add_argument("--project", help="project slug, path, or a unique fragment of either")
    parser.add_argument("--timeline", action="store_true", help="print every turn")
    args = parser.parse_args()

    directory = resolve_project(args.project)
    transcripts = sorted(glob.glob(os.path.join(directory, "*.jsonl")), key=os.path.getmtime, reverse=True)
    if not transcripts:
        raise SystemExit(f"no transcripts in {directory}")

    for path in transcripts:
        rows = load(path)
        start = find_invocation(rows, args.skill)
        if start is not None:
            end = find_end(rows, start)
            bound = "end of transcript" if end == len(rows) else "the next typed instruction"
            print(f"{os.path.basename(path)}  /{args.skill} at {stamp(rows[start])}, measured to {bound}")
            profile(rows, start, end, args.timeline)
            return

    print(f"/{args.skill} never invoked in {os.path.basename(directory)}", file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
