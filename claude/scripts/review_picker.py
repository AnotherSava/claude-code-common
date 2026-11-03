#!/usr/bin/env python3
"""Put a set of decisions in front of the user as a page of rows, each preset to a recommendation, and hand back the answer.

A skill that stops on a list of recommendations — `/review-manual`'s findings, `/wrap-up`'s summary — would otherwise
print it as chat text and read the overrides back as typed ids. This page makes the decision a round of changing what
should not go as recommended. Each row offers its own choices as a group of pills with the recommended one selected,
so Apply on an untouched page is "do what you recommended". A row's ✎ button opens a note under it for "this, but like
this"; the note comes back keyed by the row's id. Read-only blocks (a table, preformatted text) sit between the
sections where the decision needs them, and page-level flags are checkboxes beside Apply.

Shown as a blocking agterm HTML overlay over the calling session, which is what returns the answer: the page's
Apply calls `session.overlay.submit` with the answer, and `agtermctl ... --block` prints that value. Outside agterm
(agwinterm on Windows, a plain terminal) nothing can carry an answer back from the page, so the same page is published
on the tailnet instead, its Apply becomes "Copy answer", and the user pastes the copied JSON into the chat. The script
then exits at once with the URL rather than blocking, and the caller waits for the paste.

Input is a JSON file:
    {"title": "...",
     "blocks": [
       {"kind": "choices", "heading": "Findings",
        "columns": [{"key": "finding", "label": "Finding"}, ...],
        "note_choice": "fix",
        "rows": [{"id": "r1-8", "finding": "...", "choices": ["fix", "leave"], "choice": "fix", "dim": false}, ...]},
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

PUBLISH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "shared", "tailnet_publish.py")


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
        elif kind == "choices":
            rows = block.get("rows")
            if not isinstance(rows, list) or not rows:
                raise ValueError(f"block {index}: a choices block needs rows")
            if columns is not None and not (isinstance(columns, list) and all(isinstance(column, dict) and "key" in column for column in columns)):
                raise ValueError(f'block {index}: a choices block\'s columns are {{"key", "label"}} objects, not {columns!r}')
            for row in rows:
                if not isinstance(row, dict) or "id" not in row:
                    raise ValueError(f"block {index}: every row needs an id")
                rid = str(row["id"])
                if rid in seen:
                    raise ValueError(f"row {rid} appears twice")
                seen.add(rid)
                choices = row.get("choices")
                if not isinstance(choices, list) or not choices or row.get("choice") not in choices:
                    raise ValueError(f"row {rid}: choice must be one of a non-empty choices list")
            note_choice = block.get("note_choice")
            if note_choice is not None and not all(note_choice in row["choices"] for row in rows):
                raise ValueError(f"block {index}: note_choice {note_choice!r} is not a choice on every row")
        else:
            raise ValueError(f"block {index}: kind must be choices, triage, table, list, text or prose, not {kind!r}")


# The spec format has a second reader: `_spec_markdown` in skills/skill-outputs/scripts/collect.py renders the same
# blocks as markdown, so a new block kind or column field is added there too.
def _choices_block(block: dict) -> str:
    columns = block.get("columns") or []
    note_choice = block.get("note_choice")
    note_attr = f' data-note-choice="{_e(note_choice)}"' if note_choice else ""
    head = "".join(f"<th>{_e(column.get('label', column['key']))}</th>" for column in columns)
    rows = []
    for row in block["rows"]:
        rid = _e(row["id"])
        pills = "".join(
            f'<label class="pill{" rec" if choice == row["choice"] else ""}"><input type="radio" name="{rid}" value="{_e(choice)}"'
            f'{" checked" if choice == row["choice"] else ""}><span>{_e(choice)}</span></label>'
            for choice in row["choices"]
        )
        cells = "".join(f"<td>{_e(row.get(column['key'], ''))}</td>" for column in columns)
        rows.append(
            f'<tr class="item{" dim" if row.get("dim") else ""}" data-id="{rid}"><td class="id">{rid}</td>{cells}'
            f'<td class="pills">{pills}</td>'
            f'<td class="note"><button type="button" class="feedback" title="Add a note">✎</button></td></tr>'
            f'<tr class="feedback-row" hidden><td></td><td colspan="{len(columns) + 2}">'
            f'<textarea rows="2" placeholder="Note"{note_attr}></textarea></td></tr>'
        )
    return f'<table><thead><tr><th>#</th>{head}<th></th><th></th></tr></thead><tbody>\n' + "\n".join(rows) + "\n</tbody></table>"


def _triage_block(block: dict) -> str:
    # Rows show their position, which /wrap-up reads back as the n-th triage row (claude/skills/wrap-up/SKILL.md,
    # "The page"); review-auto's own id, such as `r1-6` or `polish-edit-5`, is in the hover with the file.
    text = lambda row, key: "" if row.get(key) is None else str(row[key])
    # One grid for the whole block, so the number, lens and disposition tracks are each as wide as their widest entry
    # and line up across rows. Each row is a subgrid whose second line takes any extra height a long finding brings,
    # so the rating line stays right under the lens and disposition.
    rows = []
    for position, row in enumerate(block["rows"], start=1):
        rid, file = text(row, "id"), text(row, "file")
        rating = " · ".join(text(row, key) for key in ("frequency", "cost") if text(row, key))
        hover = _e(rid + (" · " + file if file else ""))
        rows.append(
            f'<div class="trow"><b class="num" title="{hover}">{position}</b>'
            f'<span class="lens" title="{hover}">{_e(text(row, "lens"))}</span>'
            f'<span title="{hover}"><span class="disp{" applied" if text(row, "outcome") == "applied" else ""}">{_e(text(row, "disposition"))}</span></span>'
            f'<div class="finding">{_e(text(row, "finding"))}</div><span class="meta">{_e(rating)}</span></div>'
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
    render = {"choices": _choices_block, "triage": _triage_block, "table": _table_block, "text": lambda block: f'<pre>{_e(block["text"])}</pre>',
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
    # Styled from the terminal theme agterm injects, with a fallback at each use, so the page reads as part of the
    # session in light and dark alike.
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{_e(title)}</title>
<style>
  html {{ overscroll-behavior-y: none; }}
  body {{ font: 13px/1.45 -apple-system, system-ui, sans-serif; margin: 16px 20px; color: var(--agterm-foreground, #222); background: var(--agterm-background, #fff); }}
  header {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 4px 24px; margin: 0 0 12px; }}
  h1 {{ font-size: 15px; font-weight: 600; margin: 0; }}
  .status {{ text-align: right; }}
  .status .ok {{ color: #2f9e5b; font-weight: 600; }}
  .status .bad {{ color: #d9534f; font-weight: 600; }}
  h2 {{ font-size: 13px; font-weight: 600; margin: 20px 0 6px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; vertical-align: top; padding: 6px 8px; border-bottom: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 15%, transparent); }}
  th {{ font-weight: 600; font-size: 12px; opacity: 0.7; }}
  tr.item.dim {{ color: color-mix(in srgb, var(--agterm-foreground, #222) 55%, transparent); }}
  tr.item.changed td.id {{ box-shadow: inset 3px 0 var(--agterm-color-4, #2563eb); }}
  td.id {{ white-space: nowrap; opacity: 0.8; }}
  td.pills {{ white-space: nowrap; }}
  .pill {{ display: inline-block; cursor: pointer; }}
  .pill input {{ display: none; }}
  .pill span {{ display: inline-block; padding: 1px 9px; margin: 0 2px 2px 0; border-radius: 999px; border: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 25%, transparent); opacity: 0.75; }}
  .pill.rec span {{ border-style: dashed; }}
  .pill input:checked + span {{ background: var(--agterm-color-4, #2563eb); border: 1px solid transparent; color: #fff; opacity: 1; }}
  .triage {{ display: grid; grid-template-columns: max-content max-content max-content minmax(0, 1fr); column-gap: 10px; align-items: baseline; }}
  .triage .finding {{ grid-column: 4; padding-left: 14px; }}
  .triage .trow {{ grid-column: 1 / -1; display: grid; grid-template-columns: subgrid; grid-template-rows: auto 1fr; align-items: baseline; border-top: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 15%, transparent); padding: 6px 0; }}
  .triage .trow:last-child {{ border-bottom: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 15%, transparent); }}
  .triage .num {{ grid-row: 1 / 3; }}
  .triage .finding {{ grid-row: 1 / 3; align-self: start; }}
  .triage .lens {{ font-size: 12px; opacity: 0.75; white-space: nowrap; }}
  .disp {{ display: block; text-align: center; font-size: 12px; padding: 0 8px; border-radius: 999px; border: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 30%, transparent); }}
  .disp.applied {{ background: #1e7a46; border-color: #1e7a46; color: #fff; }}
  .triage .meta {{ grid-column: 2 / 4; grid-row: 2; align-self: start; font-size: 12px; opacity: 0.6; white-space: nowrap; }}
  ul.list {{ margin: 0; padding-left: 18px; }}
  ul.list li {{ margin: 3px 0; }}
  ul.list code {{ font: 12px/1.45 ui-monospace, monospace; }}
  ul.list li.rule {{ color: #2f9e5b; font-size: 12px; font-weight: 600; }}
  ul.list li.rule span::before {{ content: "\\2190\\00a0"; }}
  ul.list .note {{ opacity: 0.65; font-size: 12px; }}
  p.prose {{ margin: 8px 0 0; white-space: pre-line; }}
  pre {{ font: 12px/1.45 ui-monospace, monospace; white-space: pre-wrap; margin: 0; padding: 8px 10px; border-radius: 6px; background: color-mix(in srgb, var(--agterm-foreground, #222) 6%, transparent); }}
  .bar {{ position: sticky; bottom: 0; display: flex; gap: 8px; align-items: center; padding: 12px 0 4px; background: var(--agterm-background, #fff); }}
  .flag {{ margin-left: 8px; cursor: pointer; }}
  button {{ font: inherit; padding: 4px 14px; border-radius: 6px; border: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 30%, transparent); background: transparent; color: inherit; cursor: pointer; }}
  button.apply {{ background: var(--agterm-color-4, #2563eb); border-color: transparent; color: #fff; }}
  #count {{ opacity: 0.7; }}
  td.note {{ width: 2em; }}
  button.feedback {{ padding: 0 6px; border-color: transparent; opacity: 0.6; }}
  button.feedback.on {{ opacity: 1; border-color: color-mix(in srgb, var(--agterm-foreground, #222) 30%, transparent); }}
  tr.feedback-row td {{ border-bottom: none; padding-top: 0; }}
  #answer {{ font: 12px ui-monospace, monospace; flex: 1; }}
  textarea {{ font: inherit; width: 100%; box-sizing: border-box; padding: 4px 6px; border-radius: 4px; color: inherit; background: transparent; border: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 30%, transparent); }}
</style></head>
<body>
<header><h1>{_e(title)}</h1>{status}</header>
{sections}
<div class="bar">
  <button type="button" class="apply" id="apply">{"Apply" if in_agterm else "Copy answer"}</button>
  {'<button type="button" data-agterm="session.overlay.close">Cancel</button>' if in_agterm else '<textarea id="answer" rows="1" readonly hidden></textarea>'}
  {flags}
  <span id="count"></span>
</div>
<script>
  const items = [...document.querySelectorAll('tr.item')];
  const count = document.getElementById('count');
  const picked = (row) => row.querySelector('input[type=radio]:checked').value;
  const recommended = (row) => row.querySelector('.pill.rec input').value;
  const noteOf = (row) => row.nextElementSibling.querySelector('textarea');
  // A tally per choice, and a mark on each row moved off its recommendation, so what Apply will do is visible at once.
  const recount = () => {{
    const tally = new Map();
    for (const row of items) {{ tally.set(picked(row), (tally.get(picked(row)) || 0) + 1); row.classList.toggle('changed', picked(row) !== recommended(row)); }}
    const changed = items.filter((row) => row.classList.contains('changed')).length;
    count.textContent = [...tally].map(([choice, n]) => choice + ' ' + n).join(' · ') + (changed ? ' — ' + changed + ' changed' : '');
  }};
  for (const row of items) {{
    const note = noteOf(row);
    const toggle = row.querySelector('button.feedback');
    row.addEventListener('change', recount);
    toggle.addEventListener('click', () => {{ const panel = note.closest('tr'); panel.hidden = !panel.hidden; if (!panel.hidden) note.focus(); }});
    note.addEventListener('input', () => {{
      toggle.classList.toggle('on', note.value.trim() !== '');
      const choice = note.dataset.noteChoice;
      if (choice && note.value.trim()) {{ row.querySelector(`input[value="${{CSS.escape(choice)}}"]`).checked = true; recount(); }}
    }});
  }}
  recount();
  document.getElementById('apply').addEventListener('click', () => {{
    const choices = Object.fromEntries(items.map((row) => [row.dataset.id, picked(row)]));
    const notes = Object.fromEntries(items.map((row) => [row.dataset.id, noteOf(row).value.trim()]).filter(([, text]) => text));
    const flags = Object.fromEntries([...document.querySelectorAll('input[data-flag]')].map((box) => [box.dataset.flag, box.checked]));
    const value = JSON.stringify({{ choices, notes, flags }});
    {answer}
  }});
</script>
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Show rows of recommended choices as a page and print the user's answer; outside agterm, publish the page and print its URL.")
    parser.add_argument("spec", help="JSON file: {title, blocks: [{kind: choices|table|text, ...}], flags?}")
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
