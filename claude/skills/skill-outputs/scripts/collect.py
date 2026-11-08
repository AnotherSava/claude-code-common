#!/usr/bin/env python3
"""Collect every /wrap-up summary written since a moment, across all projects' transcripts, into one HTML page.

    collect.py --since 2026-10-31T03:38:29-07:00 [--out <file>]

Only /wrap-up's summary is recognised so far. A second skill's output is a reason to generalise
the "wrap-up" passed to invokes_skill() and _is_wrap_up_summary() against that real case, not before.

The page lists one tab per summary and a toggle per section; a section is a heading at the level of
the summary's Review heading (its first heading where it has none), so the toggles follow whatever
format each summary was written in.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime

# realpath, because ~/.claude/skills is a symlink into the dotfiles repo and the paths below climb out of it.
HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "shared"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "scripts"))

from review_picker import triage_rows  # noqa: E402 — needs the sys.path lines above
from transcripts import PROJECTS, content_blocks, invokes_skill, parse_iso, project_dir_name, records, text_of, timestamp  # noqa: E402 — needs the sys.path lines above

# How the closing prompt of /wrap-up's step 7 opens, in every wording it has had: `go` from commit 063e8e2 on,
# `recommended` before it. It is the one part every summary with something to approve carries, since each section
# above it is left out when it has nothing in it. A new wording in claude/skills/wrap-up/SKILL.md is added here, and
# the old ones kept, so summaries written before the change are still found.
WRAP_UP_PROMPTS = ("Reply `go`", "Reply `recommended`")
# How the one line of an all-empty run opens (step 7 of the same SKILL.md). That run prints no prompt, so it has
# no WRAP_UP_PROMPTS marker; it is kept as the record of the run, and the line is matched by its opening alone.
WRAP_UP_EMPTY_OPENING = "Nothing to commit."
# Where step 7 writes a summary shown as a page, through review_picker.py; that summary never reaches chat as text, so
# it is found by the Write call that created the file, and its JSON is turned back into markdown for the page below.
WRAP_UP_SPEC_FILE = "wrap-up-summary.json"
DEFAULT_OUT = os.path.join(HERE, "..", "..", "..", "..", "tmp", "skill-outputs-wrap-up.html")


def _is_wrap_up_summary(text: str) -> bool:
    return any(prompt in text for prompt in WRAP_UP_PROMPTS) or text.lstrip().startswith(WRAP_UP_EMPTY_OPENING)


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _spec_markdown(spec: dict) -> str:
    """A page summary as the markdown its chat form would have been, so both split into the same section toggles.

    Each row shows its recommended choice in bold among the others; the answer the user gave on the page is not in the
    spec, and the summary is what this page compares. The format is the one `_render` in claude/scripts/review_picker.py
    renders, so a block kind or column field added there is added here too; until it is, the block shows as raw JSON.
    """
    state = spec.get("status")
    parts = [f"{state.get('label', '')} **{state.get('text', '')}**  \n{state.get('detail', '')}".strip()] if isinstance(state, dict) else []
    for block in spec.get("blocks") or []:
        lines = [f"## {block['heading']}"] if block.get("heading") else []
        if block.get("kind") == "table":
            columns = block.get("columns") or [""] * len((block.get("rows") or [[]])[0])
            lines += ["| " + " | ".join(map(_cell, columns)) + " |", "|" + "---|" * len(columns)]
            lines += ["| " + " | ".join(map(_cell, row)) + " |" for row in block.get("rows") or []]
        elif block.get("kind") == "triage":
            keys = ["position", "disposition", "outcome", "finding", "lens", "rating", "id"]
            lines += ["| # | " + " | ".join(keys[1:]) + " |", "|" + "---|" * len(keys)]
            lines += ["| " + " | ".join(_cell(row[k]) for k in keys) + " |" for row in triage_rows({"rows": block.get("rows") or []})]
        elif block.get("kind") == "list":
            lines += [f"- ── {item['rule']} ──" if "rule" in item else f"- `{item.get('text', '')}`" + (f" {item['note']}" if item.get("note") else "") for item in block.get("items") or []]
        elif block.get("kind") == "prose":
            lines += [block.get("text", "")]
        elif block.get("kind") == "text":
            lines += ["```", block.get("text", ""), "```"]
        elif block.get("kind") == "choices":
            keys = [column["key"] for column in block.get("columns") or []]
            labels = [column.get("label", column["key"]) for column in block.get("columns") or []]
            lines += ["| # | " + " | ".join(map(_cell, labels)) + " | Choice |", "|" + "---|" * (len(keys) + 2)]
            for row in block.get("rows") or []:
                choices = " · ".join(f"**{c}**" if c == row.get("choice") else str(c) for c in row.get("choices") or [])
                lines.append(f"| {_cell(row.get('id', ''))} | " + " | ".join(_cell(row.get(key, "")) for key in keys) + f" | {choices} |")
        else:
            lines += [f"Block kind {block.get('kind')!r} is not rendered by collect.py:", "```json", json.dumps(block, indent=2), "```"]
        parts.append("\n".join(lines))
    flags = ", ".join(f"{flag.get('label', flag.get('id'))}: {'on' if flag.get('value') else 'off'}" for flag in spec.get("flags") or [])
    return "\n\n".join(parts + ([flags] if flags else []))


def _page_summary(record: dict) -> str | None:
    """The markdown of a page summary this record wrote, or None when it wrote none."""
    for block in content_blocks(record):
        payload = block.get("input") or {}
        if block.get("type") == "tool_use" and block.get("name") == "Write" and str(payload.get("file_path", "")).endswith(WRAP_UP_SPEC_FILE):
            try:
                return _spec_markdown(json.loads(payload.get("content", "")))
            except (ValueError, TypeError, KeyError, AttributeError):
                return None
    return None


def _project_name(transcript: str) -> str:
    prefix = project_dir_name(os.path.join(os.path.expanduser("~"), "Projects")) + "-"
    name = os.path.basename(os.path.dirname(transcript))
    return name[len(prefix):] if name.startswith(prefix) else name


def _read_rows(transcript: str) -> list[tuple[dict, datetime]]:
    """The transcript's user and assistant records, each paired with its timestamp; a record without one is skipped."""
    rows = []
    for r in records(transcript):
        if r is not None and r.get("type") in ("user", "assistant"):
            stamp = timestamp(r)
            if stamp is not None:
                rows.append((r, stamp))
    return rows


def _when(stamp: datetime) -> str:
    # `%-d` is glibc and BSD only; Windows' C runtime rejects it, so the day is formatted by hand.
    return f"{stamp:%b} {stamp.day}, {stamp:%H:%M}"


def _collect(since: datetime) -> list[dict[str, str]]:
    entries = []
    for transcript in glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")):
        rows = _read_rows(transcript)
        for i, (row, row_stamp) in enumerate(rows):
            if not invokes_skill(row, "wrap-up") or row_stamp < since:
                continue
            for later, later_stamp in rows[i + 1:]:
                if invokes_skill(later, "wrap-up"):
                    break
                if later["type"] != "assistant":
                    continue
                md = _page_summary(later) or (text_of(later) if _is_wrap_up_summary(text_of(later)) else None)
                if md:
                    stamp = later_stamp.astimezone()
                    entries.append({"project": _project_name(transcript), "when": _when(stamp), "sort": stamp.isoformat(), "session": os.path.basename(transcript)[:8], "md": md})
                    break
    return sorted(entries, key=lambda e: e["sort"], reverse=True)


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
:root{color-scheme:light dark;--bg:#fff;--fg:#1d1d1f;--mute:#6e6e73;--line:#e5e5ea;--sel:#eef3ff;--acc:#2f6fed}
@media(prefers-color-scheme:dark){:root{--bg:#1c1c1e;--fg:#f2f2f7;--mute:#98989d;--line:#38383a;--sel:#26324a;--acc:#6e9bff}}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 -apple-system,system-ui,sans-serif;background:var(--bg);color:var(--fg);display:flex;flex-direction:column;height:100vh}
#wrap{flex:1;display:flex;min-height:0}
header{display:flex;gap:8px;align-items:center;padding:10px 16px;border-bottom:1px solid var(--line);flex-wrap:wrap}
header .l{color:var(--mute);font-size:13px;font-weight:600;margin-right:8px}
header button{font:inherit;font-size:13px;border:1px solid var(--line);background:none;color:var(--mute);border-radius:999px;padding:3px 12px;cursor:pointer}
header button.on{background:var(--acc);border-color:var(--acc);color:#fff}
.sec.off{display:none}
nav{width:260px;flex:none;border-right:1px solid var(--line);overflow-y:auto}
nav button{display:block;width:100%;text-align:left;border:0;background:none;color:inherit;padding:10px 16px;border-bottom:1px solid var(--line);cursor:pointer;font:inherit}
nav button:hover{background:var(--sel)}nav button.on{background:var(--sel);box-shadow:inset 3px 0 var(--acc)}
nav .p{font-weight:600}nav .w{color:var(--mute);font-size:12px}
main{flex:1;overflow-y:auto;padding:24px 40px;max-width:1100px}
main h2,main h3{font-size:18px;border-bottom:1px solid var(--line);padding-bottom:4px;margin-top:28px}
main .meta{color:var(--mute);font-size:12px;margin-bottom:8px}
table{border-collapse:collapse;margin:10px 0;font-size:13px}td,th{border:1px solid var(--line);padding:4px 8px;vertical-align:top;text-align:left}
code{font:12px ui-monospace,Menlo,monospace;background:var(--sel);padding:1px 4px;border-radius:3px}pre{background:var(--sel);padding:10px;overflow-x:auto;border-radius:6px}pre code{background:none;padding:0}
</style></head><body><header><span class="l">__TITLE__</span><span id="toggles"></span></header><div id="wrap"><nav id="tabs"></nav><main id="body"></main></div>
<script>
const E = __DATA__;
const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g, '-');
const heading = line => { const m = line.match(/^(#{1,3}) (.+?)\s*$/) || line.match(/^(\*\*)([^*]+)\*\*\s*$/); return m && {mark: m[1], name: m[2]}; };
function split(md){
  const lines = md.split('\n'); let mark = null, fence = false;
  // A summary may open with a title above its sections, so the Review heading sets the level where there is one.
  for (const l of lines) { if (/^```/.test(l)) fence = !fence; const h = !fence && heading(l); if (h && (!mark || h.name === 'Review')) { mark = h.mark; if (h.name === 'Review') break; } }
  const out = [{name: null, lines: []}]; fence = false;
  for (const l of lines) { if (/^```/.test(l)) fence = !fence; const h = !fence && heading(l);
    if (h && h.mark === mark) out.push({name: h.name, lines: [l]}); else out[out.length - 1].lines.push(l); }
  return out;
}
const SECS = [];
E.forEach(e => { e.parts = split(e.md); e.parts.forEach(p => { if (p.name && !SECS.includes(p.name)) SECS.push(p.name); }); });
const hidden = new Set(JSON.parse(localStorage.getItem('hidden') || '[]'));
function apply(){ document.querySelectorAll('.sec').forEach(d => d.classList.toggle('off', hidden.has(d.dataset.sec))); }
const tg = document.getElementById('toggles');
SECS.forEach(s => { const b = document.createElement('button'); b.textContent = s; const k = slug(s); b.classList.toggle('on', !hidden.has(k));
  b.onclick = () => { hidden.has(k) ? hidden.delete(k) : hidden.add(k); b.classList.toggle('on', !hidden.has(k)); localStorage.setItem('hidden', JSON.stringify([...hidden])); apply(); };
  tg.appendChild(b); });
const tabs = document.getElementById('tabs'), body = document.getElementById('body');
function show(i){ [...tabs.children].forEach((b, j) => b.classList.toggle('on', i === j)); const e = E[i];
  const meta = document.createElement('div'); meta.className = 'meta'; meta.textContent = e.project + ' · ' + e.when + ' · session ' + e.session;
  body.innerHTML = e.parts.map(p => '<div class="sec" data-sec="' + (p.name ? slug(p.name) : '') + '">' + marked.parse(p.lines.join('\n')) + '</div>').join('');
  body.prepend(meta); body.scrollTop = 0; apply(); }
E.forEach((e, i) => { const b = document.createElement('button'); b.innerHTML = '<div class="p"></div><div class="w"></div>';
  b.querySelector('.p').textContent = e.project; b.querySelector('.w').textContent = e.when; b.onclick = () => show(i); tabs.appendChild(b); });
if (E.length) show(0);
</script></body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", required=True, help="ISO 8601 moment with its offset; summaries written before it are left out")
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()
    try:
        since = parse_iso(args.since)
    except ValueError:
        sys.exit(f"collect.py: --since is not an ISO 8601 time: {args.since}")
    if since.tzinfo is None:
        sys.exit("collect.py: --since needs an offset, such as 2026-10-31T03:38:29-07:00")
    entries = _collect(since)
    title = "/wrap-up summaries since " + _when(since.astimezone())
    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(PAGE.replace("__TITLE__", title).replace("__DATA__", json.dumps(entries).replace("</", "<\\/")))
    for e in entries:
        print(f"{e['when']}  {e['project']}  {e['session']}")
    print(f"{len(entries)} summaries -> {out}")


if __name__ == "__main__":
    main()
