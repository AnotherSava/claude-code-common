"""Reading Claude Code session transcripts: which directory holds a project's, and what each record says.

Every script that opens a transcript reads it through here, so a malformed line, a byte that is not UTF-8 or a
record shaped unlike the rest is skipped in one place rather than crashing whichever copy forgot the guard.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Iterator

PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")

# The harness's rule, also spelled where this module cannot be imported: `MANGLE_RE` in
# claude/conventions/universal/memory-cache-linked.py, the `project_id` sed in claude/scripts/link-project-memory.sh
# and claude/skills/reflect/gather-context.sh, and the reference claude/skills/skill/references/claude-project-memory-paths.md.
# Change every one of them together; `grep -rnF 'a-zA-Z0-9]' claude` finds them.
_MANGLE_RE = re.compile(r"[^a-zA-Z0-9]")


def project_dir_name(path: str) -> str:
    """The `~/.claude/projects` directory name the harness derives from a cwd: each non-ASCII-alphanumeric character becomes a dash."""
    return _MANGLE_RE.sub("-", path)


def records(path: str) -> Iterator[dict[str, Any] | None]:
    """Each line of a transcript as a record, or None for a line that is not a JSON object, so a caller can count them."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                yield None
                continue
            yield record if isinstance(record, dict) else None


def parse_iso(raw: str) -> datetime:
    """An ISO 8601 string as a datetime, a trailing `Z` read as UTC; raises ValueError when it is not one."""
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def timestamp(record: dict[str, Any]) -> datetime | None:
    """A record's `timestamp` as an aware datetime, or None when it is missing or not an ISO 8601 string."""
    raw = record.get("timestamp")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return parse_iso(raw)
    except ValueError:
        return None


def content_blocks(record: dict[str, Any]) -> list[dict[str, Any]]:
    """A record's message content as a list of blocks, whether it was stored as a string or a list."""
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def text_of(record: dict[str, Any]) -> str:
    """The text blocks of a record's message, joined."""
    return "\n".join(b.get("text") or "" for b in content_blocks(record) if b.get("type") == "text")


def calls_skill(block: dict[str, Any], name: str) -> bool:
    """Whether a content block is Claude invoking skill `name` through the Skill tool, a leading slash or surrounding spaces ignored."""
    if block.get("type") != "tool_use" or block.get("name") != "Skill":
        return False
    skill = (block.get("input") or {}).get("skill")
    return isinstance(skill, str) and skill.strip().lstrip("/") == name


def invokes_skill(record: dict[str, Any], name: str) -> bool:
    """Whether a record starts a run of skill `name`: the user typing it, or Claude invoking it through the Skill tool."""
    if record.get("type") == "user" and f"<command-name>/{name}</command-name>" in text_of(record):
        return True
    return any(calls_skill(block, name) for block in content_blocks(record))
