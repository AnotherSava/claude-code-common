#!/usr/bin/env python3
"""Digest the current Claude Code session transcript down to its prose.

A transcript is mostly tool traffic. Across real sessions, assistant and user text
account for 11-82 KB inside files running 0.8-3.5 MB, so discarding tool results and
keeping every word either side actually said costs little and loses nothing a wrap-up
review needs. That is the point: no keyword heuristic decides which questions or
concerns survive into the digest, because the reader does all of the judging.

The window is one section of work: it begins at the last /clear in the file, which is
normally the first record anyway, because clearing mints a fresh transcript.

Always exits 0. The wrap-up skill runs this as a preprocessed context command, where a
non-zero exit is fatal, so every failure is reported inside the output instead.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import traceback
from datetime import datetime
from typing import Any

SYSTEM_REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
COMMAND_NAME_RE = re.compile(r"<command-name>([^<]*)</command-name>")
COMMAND_ARGS_RE = re.compile(r"<command-args>([^<]*)</command-args>")
INJECTED_MARKERS = ("<local-command-stdout>", "<local-command-caveat>")

# Checked in order: the first one present names what a tool call was aimed at.
TOOL_ARG_KEYS = ("command", "file_path", "notebook_path", "path", "pattern", "skill", "description", "url", "query", "prompt")

# Tools whose result is conversation rather than tool output. Their results are the one
# kind worth rescuing from the discarded tool traffic: an AskUserQuestion answer is the
# user speaking, and skipping it drops direction that was never repeated in a message.
DECISION_TOOLS = ("AskUserQuestion", "ExitPlanMode")

TOOL_ARG_CHARS = 54
MAX_TOOLS_SHOWN = 8
MIN_PER_MESSAGE_CHARS = 800


def _collapse(text: str, limit: int) -> str:
    """Squeeze whitespace to single spaces and cap the result at limit characters."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


def _elide_middle(text: str, limit: int) -> tuple[str, bool]:
    """Keep the head and tail of an overlong message, naming how much was removed.

    The middle goes rather than the tail because a question is usually the last thing
    said before a turn ends, and the tail is what a reviewer needs most.
    """
    if len(text) <= limit:
        return text, False
    head = int(limit * 0.6)
    tail = limit - head
    removed = len(text) - limit
    return f"{text[:head]}\n[... {removed} characters elided ...]\n{text[-tail:]}", True


def _local_time(stamp: str) -> datetime | None:
    """Parse a transcript's UTC ISO timestamp into local time."""
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone() if parsed.tzinfo else parsed


def _blocks_of(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize a record's message content into a list of content blocks."""
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def _summarize_tool(name: str, tool_input: dict[str, Any]) -> str:
    """Render one tool call as `Name(what it was pointed at)`."""
    for key in TOOL_ARG_KEYS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return f"{name}({_collapse(value, TOOL_ARG_CHARS)})"
    return name


def _resolve_transcript(session_id: str | None) -> tuple[str | None, str, list[str]]:
    """Locate the transcript file, reporting how it was found and what was assumed."""
    notes: list[str] = []
    projects = os.path.join(os.path.expanduser("~"), ".claude", "projects")
    if session_id:
        matches = glob.glob(os.path.join(projects, "*", f"{session_id}.jsonl"))
        if len(matches) == 1:
            return matches[0], "session-id", notes
        if len(matches) > 1:
            notes.append(f"session id matched {len(matches)} files; used the newest")
            return max(matches, key=os.path.getmtime), "session-id", notes
        notes.append(f"no transcript named {session_id}.jsonl under ~/.claude/projects")
    else:
        notes.append("CLAUDE_CODE_SESSION_ID was not set in the environment")
    mangled = re.sub(r"[^a-zA-Z0-9]", "-", os.getcwd())
    candidates = glob.glob(os.path.join(projects, mangled, "*.jsonl"))
    if not candidates:
        notes.append(f"no transcripts under the directory for this cwd ({mangled})")
        return None, "UNRESOLVED", notes
    notes.append("fell back to the most recently written transcript for this cwd, which may be another session")
    return max(candidates, key=os.path.getmtime), "newest-in-cwd-dir", notes


def _result_text(block: dict[str, Any]) -> str:
    """Flatten a tool_result's content, which is a string in some records and blocks in others."""
    content = block.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text") or "" for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _read_items(path: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Turn a transcript into an ordered list of prose, command, decision and tool events."""
    items: list[dict[str, Any]] = []
    decision_ids: set[str] = set()
    stats = {"records": 0, "unparsed": 0, "sidechain": 0}
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                stats["unparsed"] += 1
                continue
            stats["records"] += 1
            stamp = _local_time(record.get("timestamp") or "")
            if record.get("isSidechain"):
                stats["sidechain"] += 1
                continue
            kind = record.get("type")
            if kind not in ("user", "assistant"):
                continue
            for block in _blocks_of(record):
                block_type = block.get("type")
                if kind == "assistant":
                    if block_type == "text":
                        text = (block.get("text") or "").strip()
                        if text:
                            items.append({"kind": "assistant", "ts": stamp, "text": text})
                    elif block_type == "tool_use":
                        name = block.get("name") or "?"
                        if name in DECISION_TOOLS:
                            decision_ids.add(block.get("id") or "")
                            continue  # rendered from its result, which holds both the question and the answer
                        items.append({"kind": "tool", "ts": stamp, "text": _summarize_tool(name, block.get("input") or {})})
                    continue
                if block_type == "tool_result":
                    if block.get("tool_use_id") in decision_ids:
                        answer = _result_text(block).strip()
                        if answer:
                            items.append({"kind": "decision", "ts": stamp, "text": answer})
                    continue  # every other tool_result is tool output, not the user talking
                if block_type != "text":
                    continue
                raw = block.get("text") or ""
                named = COMMAND_NAME_RE.search(raw)
                if named:
                    args = COMMAND_ARGS_RE.search(raw)
                    items.append({"kind": "command", "ts": stamp, "text": named.group(1).strip().lstrip("/"), "args": _collapse(args.group(1), 120) if args else ""})
                    continue
                if any(marker in raw for marker in INJECTED_MARKERS) or record.get("isMeta"):
                    continue  # command output, or skill and system text injected as if from the user
                text = SYSTEM_REMINDER_RE.sub("", raw).strip()
                if text:
                    items.append({"kind": "user", "ts": stamp, "text": text})
    return items, stats


def _clip_to_last_clear(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Start the window at the last /clear, which is where the current section began.

    Clearing normally starts a fresh transcript, so on almost every run this drops nothing.
    It is an observation about how sessions behave rather than a guarantee, though, and a
    resumed or continued session can carry earlier work in the same file. Reviewing that
    would widen the window past the one section being wrapped up, so bound it here instead
    of trusting the file to begin in the right place.
    """
    last = -1
    for index, item in enumerate(items):
        if item["kind"] == "command" and item["text"] == "clear":
            last = index
    if last <= 0:
        return items, 0
    return items[last:], last


def _render(items: list[dict[str, Any]], per_message_chars: int, tool_detail: bool) -> tuple[str, int]:
    """Render the ordered items as a numbered conversation, newest last."""
    lines: list[str] = []
    elided = 0
    index = 0
    last_date = ""
    pending_text: list[str] = []
    pending_tools: list[str] = []
    open_block = False

    def stamp_of(item: dict[str, Any]) -> str:
        nonlocal last_date
        when = item.get("ts")
        if not when:
            return "--:--"
        label = when.strftime("%H:%M")
        date = when.strftime("%Y-%m-%d")
        if date != last_date:
            last_date = date
            return f"{date} {label}"
        return label

    def flush_tools() -> None:
        if not pending_tools:
            return
        if tool_detail:
            shown = pending_tools[:MAX_TOOLS_SHOWN]
            extra = len(pending_tools) - len(shown)
            suffix = f" (+{extra} more)" if extra else ""
            pending_text.append("  . " + " . ".join(shown) + suffix)
        else:
            pending_text.append(f"  . {len(pending_tools)} tool calls")
        pending_tools.clear()

    def flush_block() -> None:
        nonlocal open_block
        flush_tools()
        if pending_text:
            lines.extend(pending_text)
            lines.append("")
        pending_text.clear()
        open_block = False

    def open_claude_block(item: dict[str, Any]) -> None:
        nonlocal index, open_block
        if open_block:
            return
        index += 1
        lines.append(f"[{index}] {stamp_of(item)} CLAUDE")
        open_block = True

    def elided_body(text: str) -> str:
        """Elide an overlong message, counting it so the header can report the truncation."""
        nonlocal elided
        body, was_elided = _elide_middle(text, per_message_chars)
        elided += 1 if was_elided else 0
        return body

    for item in items:
        kind = item["kind"]
        if kind == "tool":
            open_claude_block(item)
            pending_tools.append(item["text"])
            continue
        if kind == "assistant":
            open_claude_block(item)
            flush_tools()
            pending_text.append(elided_body(item["text"]))
            continue
        flush_block()
        index += 1
        if kind == "command":
            args = f" {item['args']}" if item.get("args") else ""
            lines.append(f"[{index}] {stamp_of(item)} USER ran /{item['text']}{args}")
            lines.append("")
            continue
        if kind == "decision":
            lines.append(f"[{index}] {stamp_of(item)} USER decided")
            lines.append(elided_body(item["text"]))
            lines.append("")
            continue
        lines.append(f"[{index}] {stamp_of(item)} USER")
        lines.append(elided_body(item["text"]))
        lines.append("")
    flush_block()
    return "\n".join(lines).strip(), elided


def main() -> int:
    parser = argparse.ArgumentParser(description="Digest the current session transcript down to its prose.")
    parser.add_argument("--session-id", default=os.environ.get("CLAUDE_CODE_SESSION_ID"), help="session to digest; defaults to CLAUDE_CODE_SESSION_ID")
    parser.add_argument("--max-chars", type=int, default=120000, help="budget for the conversation body")
    parser.add_argument("--per-message-chars", type=int, default=4000, help="cap on a single message before its middle is elided")
    options = parser.parse_args()

    path, how, notes = _resolve_transcript(options.session_id)
    if path is None:
        print("=== session ===")
        print("resolved-via: UNRESOLVED")
        for note in notes:
            print(f"note: {note}")
        print("\n=== conversation ===\n(no transcript to read)")
        return 0

    items, stats = _read_items(path)
    items, dropped = _clip_to_last_clear(items)
    body, elided = _render(items, options.per_message_chars, tool_detail=True)
    reductions: list[str] = []
    if len(body) > options.max_chars:
        body, elided = _render(items, options.per_message_chars, tool_detail=False)
        reductions.append("tool calls collapsed to per-turn counts")
    per_message = options.per_message_chars
    while len(body) > options.max_chars and per_message > MIN_PER_MESSAGE_CHARS:
        per_message = max(MIN_PER_MESSAGE_CHARS, per_message // 2)
        body, elided = _render(items, per_message, tool_detail=False)
        reductions.append(f"per-message cap lowered to {per_message}")
    if len(body) > options.max_chars:
        reductions.append(f"STILL OVER the {options.max_chars}-char budget, but no message was dropped")

    stamps = [item["ts"] for item in items if item.get("ts")]
    opened_with_clear = bool(items) and items[0]["kind"] == "command" and items[0]["text"] == "clear"
    window = f"clipped to the last /clear, dropping {dropped} earlier items" if dropped else "whole transcript"
    print("=== session ===")  # emitted only once every fallible step above has succeeded
    print(f"file: {path}")
    print(f"resolved-via: {how}")
    for note in notes:
        print(f"note: {note}")
    print(f"window: {window}")
    print(f"started: {stamps[0].strftime('%Y-%m-%d %H:%M %Z') if stamps else 'unknown'} (local)")
    print(f"last-activity: {stamps[-1].strftime('%Y-%m-%d %H:%M %Z') if stamps else 'unknown'} (local)")
    print(f"opened-with-clear: {'yes' if opened_with_clear else 'no'}")
    print(f"user-messages: {sum(1 for item in items if item['kind'] == 'user')}")
    print(f"user-decisions: {sum(1 for item in items if item['kind'] == 'decision')}")
    print(f"assistant-messages: {sum(1 for item in items if item['kind'] == 'assistant')}")
    print(f"tool-calls: {sum(1 for item in items if item['kind'] == 'tool')}")
    print(f"records: {stats['records']} (sidechain skipped: {stats['sidechain']}, unparsed: {stats['unparsed']})")
    print(f"body-chars: {len(body)}")
    print(f"messages-elided: {elided}" if elided else "messages-elided: 0")
    print(f"reductions: {'; '.join(reductions) if reductions else 'none'}")
    print()
    print("=== conversation ===")
    print(body if body else "(no prose in this transcript)")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        sys.exit(main())
    except Exception:  # a context command must never exit non-zero: report and carry on
        print("=== session ===")
        print("resolved-via: UNRESOLVED")
        print("note: session_scan.py raised, traceback below")
        print(_collapse(traceback.format_exc(), 2000))
        print("\n=== conversation ===\n(no transcript to read)")
        sys.exit(0)
