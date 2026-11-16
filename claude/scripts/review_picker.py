#!/usr/bin/env python3
"""Put a set of decisions in front of the user as a page of rows, each preset to a recommendation, and hand back the answer.

A skill that stops on a list of recommendations — `/review-manual`'s findings, `/wrap-up`'s summary — would otherwise
print it as chat text and read the overrides back as typed ids. This page makes the decision a round of changing what
should not go as recommended. Each row offers its own choices as a group of pills with the recommended one selected,
so Apply on an untouched page is "do what you recommended". A row's ✎ button opens a note under it for "this, but like
this"; the note comes back keyed by the row's id. Read-only blocks (a table, preformatted text) sit between the
sections where the decision needs them, and page-level flags are checkboxes beside Apply.

Shown as a blocking agterm HTML overlay over the calling session, which is what returns the answer. The session has
one overlay slot, so whatever page it holds there, a hidden one included, is closed and discarded first. The page's
Apply calls `session.overlay.submit` with the answer, and `agtermctl ... --block` prints that value. Outside agterm
(agwinterm on Windows, a plain terminal) nothing can carry an answer back from the page, so the same page is published
on the tailnet instead, its Apply becomes "Copy answer", and the user pastes the copied JSON into the chat. The script
then exits at once with the URL rather than blocking, and the caller waits for the paste.

Input is a JSON file:
    {"title": "...",
     "blocks": [
       {"kind": "choices", "heading": "Findings",
        "columns": [{"key": "finding", "label": "Finding"}, {"key": "seen", "label": "Seen", "age": true}, ...],
        "note_choice": "fix", "single": "start",
        "rows": [{"id": "r1-8", "label": "8", "finding": "...", "detail": "...", "choices": ["fix", "leave"], "choice": "fix", "dim": false}, ...]},
       {"kind": "entries", "heading": "Backlog", "columns": [...], "rows": [{"id": "a-slug", "label": "1", "detail": "...", ...}, ...]},
       {"kind": "triage", "heading": "Review", "rows": [<review-auto's triage objects, as the workflow returns them>]},
       {"kind": "table", "heading": "...", "columns": ["#", "Finding", ...], "rows": [["1", "..."], ...]},
       {"kind": "list", "heading": "Commits", "items": [{"text": "feat(x): ...", "note": "..."}, ...]},
       {"kind": "text", "text": "..."},
       {"kind": "prose", "text": "..."}],
     "status": {"label": "Review bookmark:", "text": "moves past everything reviewed", "ok": true, "detail": "3 follow-up ..."},
     "flags": [{"id": "push", "label": "Push after committing", "value": true}]}
    `status` is optional: one line at the right of the title row, an optional `label`, then `text` in green when `ok`
    is true and red when it is false, then an optional `detail` on a line of its own.
    A `list` block shows each item's `text` in monospace and its optional `note` after it in body text; an item that is
    `{"rule": "<label>"}` instead is a green entry, dot and label, marking a place between its neighbours. A `text` block
    is preformatted; a `prose` block is a plain paragraph, its blank lines splitting it into paragraphs.
    `heading`, `columns`, `note_choice`, `dim` and `flags` are optional. `choice` is the recommendation and must be one
    of the row's `choices`; `note_choice`, when set, is selected on a row as soon as a note is written on it; `dim`
    draws the row in lighter grey; ids are unique across the page. A `choices` block's columns are `{"key", "label"}`
    objects, each `key` naming a row field and `label` defaulting to it; a `table` block's columns are plain strings
    and its rows are lists of cells, one per column. A `triage` block reads each object's `id`, `finding`,
    `disposition`, `outcome`, `lens`, `frequency`, `cost` and `file`, any of them absent or null; it numbers the
    rows from 1, puts each id and file in the hover, and shows a disposition whose outcome is `applied` in green.
    An `entries` block is a `choices` block with nothing to choose: the same rows and columns, drawn without pills
    or notes, for items the page only shows. On a row of either kind, `label` is what the first column shows in
    place of the id, which stays the answer's key and moves to the hover; use it where the visible number can shift
    under an answer given later. `detail` is long text kept under the row behind a ▸ button. A column with
    `"age": true` holds epoch seconds and shows them as "3h ago", kept current by the page, with the stamp on hover.
    `single` on a `choices` block names a choice one row at a time can hold: taking it on a second row returns the
    first to its recommendation, so it has to be a choice every row offers and none is preset to.
    A page with no `choices` block and no flags has nothing to apply: in agterm its bar holds only Close, elsewhere
    it has no bar, and closing it is exit 2 as for any page.

Prints one JSON line and exits:
    0  {"outcome": "submitted", "choices": {"r1-8": "fix", ...}, "notes": {"r1-8": "..."}, "flags": {"push": true}}
       (every row has its choice; notes holds only rows whose note is non-empty)
    2  {"outcome": "dismissed"}                         (closed without Apply: nothing was decided)
    3  not inside agterm and the page could not be published; the reason is on stderr
    4  {"outcome": "published", "url": "https://..."}   (not inside agterm: hand over the URL, the answer is pasted)
    1  anything else; the reason is on stderr
"""
from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
from typing import Callable

SHARED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "shared")
PUBLISH = os.path.join(SHARED, "tailnet_publish.py")
sys.path.insert(0, SHARED)

from live_time import LIVE_TIME_SCRIPT, rel_time  # noqa: E402 — needs the sys.path line above


def _e(value: object) -> str:
    # quote=True on every value: the same helper fills attributes (ids, choices) as well as text.
    return html.escape(str(value), quote=True)


def _validate(spec: dict) -> None:
    """Refuse a spec the page would render wrongly, naming the block or row at fault."""
    blocks = spec.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("blocks must be a non-empty list")
    status = spec.get("status")
    if status is not None and not (isinstance(status, dict) and isinstance(status.get("text"), str) and isinstance(status.get("ok"), bool)):
        raise ValueError("status must be an object with a text and a boolean ok")
    seen: set[str] = set()
    for index, block in enumerate(blocks):
        kind = block.get("kind") if isinstance(block, dict) else None
        columns = block.get("columns") if isinstance(block, dict) else None
        if kind == "table":
            if not isinstance(block.get("rows"), list):
                raise ValueError(f"block {index}: a table needs rows")
            if not all(isinstance(row, list) for row in block["rows"]):
                raise ValueError(f"block {index}: a table's rows are lists of cells, one per column")
            if columns is not None and not (isinstance(columns, list) and all(isinstance(column, str) for column in columns)):
                raise ValueError(f"block {index}: a table's columns are a list of strings")
        elif kind == "triage":
            if not isinstance(block.get("rows"), list) or not all(isinstance(row, dict) and "id" in row for row in block["rows"]):
                raise ValueError(f"block {index}: a triage block's rows are review-auto's triage objects, each with an id")
        elif kind == "list":
            if not isinstance(block.get("items"), list) or not all(isinstance(item, dict) and (isinstance(item.get("text"), str) or isinstance(item.get("rule"), str)) for item in block["items"]):
                raise ValueError(f"block {index}: a list's items are objects with a text or a rule")
        elif kind in ("text", "prose"):
            if not isinstance(block.get("text"), str):
                raise ValueError(f"block {index}: a {kind} block needs text")
        elif kind in ("choices", "entries"):
            rows = block.get("rows")
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"block {index}: a {kind} block needs rows")
            if columns is not None and not (isinstance(columns, list) and all(isinstance(column, dict) and "key" in column for column in columns)):
                raise ValueError(f'block {index}: a {kind} block\'s columns are {{"key", "label"}} objects, not {columns!r}')
            ages = [column["key"] for column in columns or [] if column.get("age")]
            for row in rows:
                if not isinstance(row, dict) or "id" not in row:
                    raise ValueError(f"block {index}: every row needs an id")
                rid = str(row["id"])
                if rid in seen:
                    raise ValueError(f"row {rid} appears twice")
                seen.add(rid)
                if not all(isinstance(row.get(key, ""), str) for key in ("label", "detail")):
                    raise ValueError(f"row {rid}: label and detail are text")
                # A bool is an int to Python, and would be drawn as a moment in 1970.
                if not all(row.get(key) in (None, "") or (isinstance(row[key], (int, float)) and not isinstance(row[key], bool)) for key in ages):
                    raise ValueError(f"row {rid}: an age column holds epoch seconds")
                if kind == "choices":
                    choices = row.get("choices")
                    if not isinstance(choices, list) or not choices or row.get("choice") not in choices:
                        raise ValueError(f"row {rid}: choice must be one of a non-empty choices list")
            if kind == "choices":
                note_choice = block.get("note_choice")
                if note_choice is not None and not all(note_choice in row["choices"] for row in rows):
                    raise ValueError(f"block {index}: note_choice {note_choice!r} is not a choice on every row")
                single = block.get("single")
                if single is not None and not all(single in row["choices"] and row["choice"] != single for row in rows):
                    raise ValueError(f"block {index}: single {single!r} must be a choice on every row and the recommendation on none")
        else:
            raise ValueError(f"block {index}: kind must be choices, entries, triage, table, list, text or prose, not {kind!r}")


def rows_table(block: dict, moment: Callable[[float], str], text: Callable[[object], str]) -> dict:
    """A `choices` or an `entries` block as the parts every rendering of it shows, read one way for all of them.

    Returns `decides` (the block offers choices), `headings` (each column's label), `width` (the columns a row spans:
    the number, the data columns and, where the block decides, the choices) and `rows`. Each row holds `id`; `first`,
    its label or else its id, with `labelled` saying which; `cells`, an age column through `moment` and every other
    column through `text`; `choices` as (choice, recommended) pairs; `detail`; and `dim`. Every field but the cells is
    the raw value, for the caller to escape. The skill-outputs comparison page reads rows through here too
    (`_spec_markdown` in claude/skills/skill-outputs/scripts/collect.py), so a field a row gains reaches both or
    neither.
    """
    columns = block.get("columns") or []
    decides = block["kind"] == "choices"
    rows = [{"id": str(row.get("id", "")), "first": str(row.get("label", row.get("id", ""))), "labelled": "label" in row,
             "cells": [moment(row.get(column["key"]) or 0) if column.get("age") else text(row.get(column["key"], "")) for column in columns],
             "choices": [(str(choice), choice == row.get("choice")) for choice in row.get("choices") or []] if decides else [],
             "detail": str(row.get("detail") or ""), "dim": bool(row.get("dim"))}
            for row in block.get("rows") or []]
    return {"decides": decides, "headings": [str(column.get("label", column["key"])) for column in columns], "width": len(columns) + (2 if decides else 1), "rows": rows}


# The spec format has a second reader: `_spec_markdown` in skills/skill-outputs/scripts/collect.py renders the same
# blocks as markdown. A row of a `choices` or `entries` block reaches both through `rows_table`; a new block kind is
# added there too.
def _rows_block(block: dict) -> str:
    """A `choices` or an `entries` block: one row per item, with pills and a note only where the block offers choices."""
    table = rows_table(block, rel_time, _e)
    decides = table["decides"]
    span = table["width"]
    note_choice = block.get("note_choice")
    note_attr = f' data-note-choice="{_e(note_choice)}"' if note_choice else ""
    single = f' data-single="{_e(block["single"])}"' if decides and block.get("single") is not None else ""
    head = "".join(f"<th>{_e(heading)}</th>" for heading in table["headings"])
    rows = []
    for row in table["rows"]:
        rid = _e(row["id"])
        dim = " dim" if row["dim"] else ""
        hover = f' title="{rid}"' if row["labelled"] else ""
        first = f'<td class="id"{hover}>{_e(row["first"])}</td>'
        cells = "".join(f"<td>{cell}</td>" for cell in row["cells"])
        more = '<button type="button" class="more" title="Show the rest" aria-expanded="false">▸</button>' if row["detail"] else ""
        if decides:
            pills = "".join(
                f'<label class="pill{" rec" if recommended else ""}"><input type="radio" name="{rid}" value="{_e(choice)}"'
                f'{" checked" if recommended else ""}><span>{_e(choice)}</span></label>'
                for choice, recommended in row["choices"]
            )
            rows.append(
                f'<tr class="item{dim}" data-id="{rid}">{first}{cells}<td class="pills">{pills}</td>'
                f'<td class="note">{more}<button type="button" class="feedback" title="Add a note">✎</button></td></tr>'
            )
        else:
            rows.append(f'<tr class="entry{dim}" data-id="{rid}">{first}{cells}<td class="note">{more}</td></tr>')
        if row["detail"]:
            rows.append(f'<tr class="detail-row" data-for="{rid}" hidden><td></td><td colspan="{span}"><div class="detail">{_e(row["detail"])}</div></td></tr>')
        if decides:
            rows.append(f'<tr class="feedback-row" data-for="{rid}" hidden><td></td><td colspan="{span}"><textarea rows="2" placeholder="Note"{note_attr}></textarea></td></tr>')
    return f'<table{single}><thead><tr><th>#</th>{head}{"<th></th><th></th>" if decides else "<th></th>"}</tr></thead><tbody>\n' + "\n".join(rows) + "\n</tbody></table>"


def triage_rows(block: dict) -> list[dict[str, str]]:
    """A triage block's rows as the fields every rendering of it shows, each a string, absent or null ones empty.

    Rows are named by their position, which /wrap-up reads back as the n-th triage row (claude/skills/wrap-up/SKILL.md,
    "The page"); review-auto's own id, such as `r1-6` or `polish-edit-5`, is secondary. The skill-outputs comparison
    page (claude/skills/skill-outputs/scripts/collect.py) renders the same rows from here, so both name a row alike.
    """
    text = lambda row, key: "" if row.get(key) is None else str(row[key])
    return [{"position": str(position), "id": text(row, "id"), "file": text(row, "file"), "lens": text(row, "lens"), "disposition": text(row, "disposition"),
             "outcome": text(row, "outcome"), "finding": text(row, "finding"), "rating": " · ".join(text(row, key) for key in ("frequency", "cost") if text(row, key))}
            for position, row in enumerate(block["rows"], start=1)]


def _triage_block(block: dict) -> str:
    # One grid for the whole block, so the number, lens and disposition tracks are each as wide as their widest entry
    # and line up across rows. Each row is a subgrid whose second line takes any extra height a long finding brings,
    # so the rating line stays right under the lens and disposition.
    rows = []
    for row in triage_rows(block):
        hover = _e(row["id"] + (" · " + row["file"] if row["file"] else ""))
        rows.append(
            f'<div class="trow"><b class="num" title="{hover}">{row["position"]}</b>'
            f'<span class="lens" title="{hover}">{_e(row["lens"])}</span>'
            f'<span title="{hover}"><span class="disp{" applied" if row["outcome"] == "applied" else ""}">{_e(row["disposition"])}</span></span>'
            f'<div class="finding">{_e(row["finding"])}</div><span class="meta">{_e(row["rating"])}</span></div>'
        )
    return '<div class="triage">\n' + "\n".join(rows) + "\n</div>"


def _table_block(block: dict) -> str:
    head = "".join(f"<th>{_e(column)}</th>" for column in block.get("columns") or [])
    body = "\n".join("<tr>" + "".join(f"<td>{_e(cell)}</td>" for cell in row) + "</tr>" for row in block["rows"])
    return f"<table class=\"plain\">{f'<thead><tr>{head}</tr></thead>' if head else ''}<tbody>\n{body}\n</tbody></table>"


def _render(spec: dict, in_agterm: bool) -> str:
    """The page. Every value is escaped: rows quote code, transcripts and email text, and the page can run agterm commands.

    In agterm Apply submits the overlay; anywhere else it copies the answer for the user to paste, and Cancel is
    dropped, since closing a browser tab needs no button and reports nothing.
    """
    title = str(spec.get("title") or "Decisions")
    state = spec.get("status")
    status = (f'<div class="status">' + (f'{_e(state["label"])} ' if state.get("label") else "") + f'<span class="{"ok" if state["ok"] else "bad"}">{_e(state["text"])}</span>'
              + (f'<div>{_e(state["detail"])}</div>' if state.get("detail") else "") + "</div>") if state else ""
    render = {"choices": _rows_block, "entries": _rows_block, "triage": _triage_block, "table": _table_block, "text": lambda block: f'<pre>{_e(block["text"])}</pre>',
              "list": lambda block: '<ul class="list">' + "".join(f'<li class="rule"><span>{_e(item["rule"])}</span></li>' if "rule" in item else f'<li><code>{_e(item["text"])}</code>' + (f' <span class="note">{_e(item["note"])}</span>' if item.get("note") else "") + "</li>" for item in block["items"]) + "</ul>",
              "prose": lambda block: "".join(f'<p class="prose">{_e(part.strip())}</p>' for part in block["text"].split("\n\n") if part.strip())}
    sections = "\n".join(
        (f"<h2>{_e(block['heading'])}</h2>\n" if block.get("heading") else "") + render[block["kind"]](block)
        for block in spec["blocks"]
    )
    flags = "".join(
        f'<label class="flag"><input type="checkbox" data-flag="{_e(flag["id"])}"{" checked" if flag.get("value") else ""}> {_e(flag.get("label", flag["id"]))}</label>'
        for flag in spec.get("flags") or []
    )
    if in_agterm:
        answer = "agterm.request('session.overlay.submit', { args: { value } }).catch((error) => { count.textContent = 'Could not submit: ' + error; });"
    else:
        # The answer is shown, selected, only when the browser refuses clipboard access.
        answer = ("navigator.clipboard.writeText(value).then(() => { count.textContent = 'Copied: paste it into the chat'; }, () => {\n"
                  "      const answer = document.getElementById('answer'); answer.value = value; answer.hidden = false; answer.select(); count.textContent = 'Copy the selected text into the chat'; });")
    # A page that only shows things has nothing to apply, so it gets no Apply to press by mistake: a way to close it
    # in agterm, and no bar at all in a browser, where the tab is closed.
    if flags or any(block["kind"] == "choices" for block in spec["blocks"]):
        bar = (f'<div class="bar">\n  <button type="button" class="apply" id="apply">{"Apply" if in_agterm else "Copy answer"}</button>\n  '
               + ('<button type="button" data-agterm="session.overlay.close">Cancel</button>' if in_agterm else '<textarea id="answer" rows="1" readonly hidden></textarea>')
               + f'\n  {flags}\n  <span id="count"></span>\n</div>')
    else:
        bar = '<div class="bar">\n  <button type="button" data-agterm="session.overlay.close">Close</button>\n</div>' if in_agterm else ""
    live = LIVE_TIME_SCRIPT if any(column.get("age") for block in spec["blocks"] if block["kind"] in ("choices", "entries") for column in block.get("columns") or []) else ""
    # Styled from the terminal theme agterm injects, with a fallback at each use, so the page reads as part of the
    # session in light and dark alike.
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{_e(title)}</title>
<style>
  html {{ overscroll-behavior-y: none; }}
  body {{ --rule: color-mix(in srgb, var(--agterm-foreground, #222) 15%, transparent); --ok: #2f9e5b; font: 13px/1.45 -apple-system, system-ui, sans-serif; margin: 16px 20px; color: var(--agterm-foreground, #222); background: var(--agterm-background, #fff); }}
  header {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 4px 24px; margin: 0 0 12px; }}
  h1 {{ font-size: 15px; font-weight: 600; margin: 0; }}
  .status {{ text-align: right; }}
  .status .ok {{ color: var(--ok); font-weight: 600; }}
  .status .bad {{ color: #d9534f; font-weight: 600; }}
  h2 {{ font-size: 13px; font-weight: 600; margin: 20px 0 6px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; vertical-align: top; padding: 6px 8px; border-bottom: 1px solid var(--rule); }}
  th {{ font-weight: 600; font-size: 12px; opacity: 0.7; }}
  tr.item.dim {{ color: color-mix(in srgb, var(--agterm-foreground, #222) 55%, transparent); }}
  tr.item.changed td.id {{ box-shadow: inset 3px 0 var(--agterm-color-4, #2563eb); }}
  td.id {{ white-space: nowrap; opacity: 0.8; }}
  td.pills {{ white-space: nowrap; }}
  .pill {{ display: inline-block; cursor: pointer; }}
  .pill input {{ display: none; }}
  .pill span {{ display: inline-block; padding: 1px 9px; margin: 0 2px 2px 0; border-radius: 999px; border: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 25%, transparent); opacity: 0.75; }}
  .pill.rec span {{ border-style: dashed; }}
  .pill input:not(:checked):not(:disabled) + span:hover {{ background: color-mix(in srgb, var(--agterm-color-4, #2563eb) 18%, transparent); color: var(--agterm-color-4, #2563eb); opacity: 1; }}
  .pill input:checked + span {{ background: var(--agterm-color-4, #2563eb); border: 1px solid transparent; color: #fff; opacity: 1; }}
  .triage {{ display: grid; grid-template-columns: max-content max-content max-content minmax(0, 1fr); column-gap: 10px; align-items: baseline; }}
  .triage .trow {{ grid-column: 1 / -1; display: grid; grid-template-columns: subgrid; grid-template-rows: auto 1fr; align-items: baseline; border-top: 1px solid var(--rule); padding: 6px 0; }}
  .triage .trow:last-child {{ border-bottom: 1px solid var(--rule); }}
  .triage .num {{ grid-row: 1 / 3; }}
  .triage .finding {{ grid-column: 4; grid-row: 1 / 3; align-self: start; padding-left: 14px; }}
  .triage .lens {{ font-size: 12px; opacity: 0.75; white-space: nowrap; }}
  .disp {{ display: block; text-align: center; font-size: 12px; padding: 0 8px; border-radius: 999px; border: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 30%, transparent); }}
  .disp.applied {{ background: #1e7a46; border-color: #1e7a46; color: #fff; }}
  .triage .meta {{ grid-column: 2 / 4; grid-row: 2; align-self: start; font-size: 12px; opacity: 0.6; white-space: nowrap; }}
  ul.list {{ margin: 0; padding-left: 18px; }}
  ul.list li {{ margin: 3px 0; }}
  ul.list code {{ font: 12px/1.45 ui-monospace, monospace; }}
  ul.list li.rule {{ color: var(--ok); font-size: 12px; font-weight: 600; }}
  ul.list li.rule span::before {{ content: "\\2190\\00a0"; }}
  ul.list .note {{ opacity: 0.65; font-size: 12px; }}
  p.prose {{ margin: 8px 0 0; white-space: pre-line; }}
  pre {{ font: 12px/1.45 ui-monospace, monospace; white-space: pre-wrap; margin: 0; padding: 8px 10px; border-radius: 6px; background: color-mix(in srgb, var(--agterm-foreground, #222) 6%, transparent); }}
  .bar {{ position: sticky; bottom: 0; display: flex; gap: 8px; align-items: center; padding: 12px 0 4px; background: var(--agterm-background, #fff); }}
  .flag {{ margin-left: 8px; cursor: pointer; }}
  button {{ font: inherit; padding: 4px 14px; border-radius: 6px; border: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 30%, transparent); background: transparent; color: inherit; cursor: pointer; }}
  button.apply {{ background: var(--agterm-color-4, #2563eb); border-color: transparent; color: #fff; }}
  #count {{ opacity: 0.7; }}
  td.note {{ width: 2em; white-space: nowrap; }}
  button.feedback, button.more {{ padding: 0 6px; border-color: transparent; opacity: 0.6; }}
  button.feedback.on {{ opacity: 1; border-color: color-mix(in srgb, var(--agterm-foreground, #222) 30%, transparent); }}
  button.more[aria-expanded="true"] {{ opacity: 1; }}
  tr.feedback-row td {{ border-bottom: none; padding-top: 0; }}
  tr.detail-row td {{ padding-top: 0; }}
  tr:has(+ tr.detail-row:not([hidden])) td {{ border-bottom-color: transparent; }}
  .detail {{ white-space: pre-wrap; overflow-wrap: anywhere; font-size: 12px; opacity: 0.85; padding-bottom: 4px; }}
  #answer {{ font: 12px ui-monospace, monospace; flex: 1; }}
  textarea {{ font: inherit; width: 100%; box-sizing: border-box; padding: 4px 6px; border-radius: 4px; color: inherit; background: transparent; border: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 30%, transparent); }}
</style></head>
<body>
<header><h1>{_e(title)}</h1>{status}</header>
{sections}
{bar}
<script>
  const items = [...document.querySelectorAll('tr.item')];
  const count = document.getElementById('count');
  const apply = document.getElementById('apply');
  const picked = (row) => row.querySelector('input[type=radio]:checked').value;
  const recommended = (row) => row.querySelector('.pill.rec input').value;
  // A row's note and its detail sit in rows of their own under it, each naming the row it belongs to.
  const under = (kind) => new Map([...document.querySelectorAll('tr.' + kind)].map((panel) => [panel.dataset.for, panel]));
  const noteRows = under('feedback-row');
  const detailRows = under('detail-row');
  const noteOf = (row) => noteRows.get(row.dataset.id).querySelector('textarea');
  // A tally per choice, and a mark on each row moved off its recommendation, so what Apply will do is visible at once.
  const recount = () => {{
    if (!count) return;
    const tally = new Map();
    for (const row of items) {{ tally.set(picked(row), (tally.get(picked(row)) || 0) + 1); row.classList.toggle('changed', picked(row) !== recommended(row)); }}
    const changed = items.filter((row) => row.classList.contains('changed')).length;
    count.textContent = [...tally].map(([choice, n]) => choice + ' ' + n).join(' · ') + (changed ? ' — ' + changed + ' changed' : '');
  }};
  for (const button of document.querySelectorAll('button.more')) {{
    button.addEventListener('click', () => {{
      const panel = detailRows.get(button.closest('tr').dataset.id);
      panel.hidden = !panel.hidden;
      button.textContent = panel.hidden ? '▸' : '▾';
      button.setAttribute('aria-expanded', String(!panel.hidden));
    }});
  }}
  for (const row of items) {{
    const note = noteOf(row);
    const toggle = row.querySelector('button.feedback');
    const table = row.closest('table');
    row.addEventListener('change', (event) => {{
      // The table's single choice is held by one row at a time: taking it here hands the others back their recommendation.
      if (table.dataset.single !== undefined && event.target.value === table.dataset.single) {{
        for (const other of items) if (other !== row && other.closest('table') === table && picked(other) === table.dataset.single) other.querySelector('.pill.rec input').checked = true;
      }}
      recount();
    }});
    toggle.addEventListener('click', () => {{ const panel = note.closest('tr'); panel.hidden = !panel.hidden; if (!panel.hidden) note.focus(); }});
    note.addEventListener('input', () => {{
      toggle.classList.toggle('on', note.value.trim() !== '');
      const choice = note.dataset.noteChoice;
      if (choice && note.value.trim()) {{ row.querySelector(`input[value="${{CSS.escape(choice)}}"]`).checked = true; recount(); }}
    }});
  }}
  recount();
  if (apply) apply.addEventListener('click', () => {{
    const choices = Object.fromEntries(items.map((row) => [row.dataset.id, picked(row)]));
    const notes = Object.fromEntries(items.map((row) => [row.dataset.id, noteOf(row).value.trim()]).filter(([, text]) => text));
    const flags = Object.fromEntries([...document.querySelectorAll('input[data-flag]')].map((box) => [box.dataset.flag, box.checked]));
    const value = JSON.stringify({{ choices, notes, flags }});
    {answer}
  }});
</script>
{live}
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Show rows of recommended choices as a page and print the user's answer; outside agterm, publish the page and print its URL.")
    parser.add_argument("spec", help="JSON file: {title, blocks: [{kind: choices|entries|triage|table|list|text|prose, ...}], status?, flags?}; the module docstring has each kind's fields")
    parser.add_argument("--out", help="where to write the page; default: beside the spec file, with its name and .html")
    parser.add_argument("--render-only", action="store_true", help="write the page and print its path without showing it")
    options = parser.parse_args()

    try:
        with open(options.spec, encoding="utf-8") as handle:
            spec = json.load(handle)
        if not isinstance(spec, dict):
            raise ValueError("the spec must be an object")
        _validate(spec)
    except (OSError, ValueError) as error:
        print(f"review_picker: cannot read {options.spec}: {error}", file=sys.stderr)
        return 1

    session = os.environ.get("AGTERM_SESSION_ID")
    in_agterm = bool(session and shutil.which("agtermctl"))
    out = os.path.abspath(options.out or os.path.splitext(os.path.abspath(options.spec))[0] + ".html")
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(_render(spec, in_agterm))
    if options.render_only:
        print(out)
        return 0

    if not in_agterm:
        published = subprocess.run([sys.executable, PUBLISH, "publish", out], capture_output=True, text=True)
        url = published.stdout.strip()
        if published.returncode != 0 or not url:
            print(f"review_picker: not inside agterm, and publishing the page failed: {published.stderr.strip()}", file=sys.stderr)
            return 3
        print(json.dumps({"outcome": "published", "url": url}))
        return 4

    # agterm refuses an open while the session's overlay slot is taken, a hidden page included (`overlay hidden`),
    # so whatever the session holds is closed first. Its answer is ignored: an empty slot answers `no overlay`.
    subprocess.run(["agtermctl", "session", "overlay", "close", "--target", session], capture_output=True, text=True)
    shown = subprocess.run(["agtermctl", "session", "overlay", "open", "--html", out, "--js", "--block", "--target", session],
                           capture_output=True, text=True)
    if shown.returncode == 2:
        print(json.dumps({"outcome": "dismissed"}))
        return 2
    if shown.returncode != 0:
        print(f"review_picker: agtermctl exited {shown.returncode}: {(shown.stderr or shown.stdout).strip()}", file=sys.stderr)
        return 1
    try:
        answer = json.loads(json.loads(shown.stdout)["value"])
        choices, notes, flags = answer["choices"], answer["notes"], answer["flags"]
        if not all(isinstance(part, dict) for part in (choices, notes, flags)):
            raise TypeError("choices, notes and flags must be objects")
    except (ValueError, KeyError, TypeError) as error:
        print(f"review_picker: unreadable answer {shown.stdout.strip()!r}: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"outcome": "submitted", "choices": choices, "notes": notes, "flags": flags}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
