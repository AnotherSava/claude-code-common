#!/usr/bin/env python3
"""Put a review's findings in front of the user as a table to tick, and hand back the ticked ids.

`/review-manual` ends a read-only `review-auto` run by letting the user choose what gets fixed. A chat table makes
that a round of typing ids back; this page makes it a round of unticking what should stay. Each row carries the
finding, its rating and the session's own view, with the box pre-ticked where the session recommends a fix, so Apply
on an untouched page is "do what you recommended". A row's feedback button opens a note under it for "fix, but like
this"; writing one ticks the row, and the note comes back keyed by its id.

Shown as a blocking agterm HTML overlay over the calling session, which is what returns the answer: the page's
Apply calls `session.overlay.submit` with the ticked ids, and `agtermctl ... --block` prints that value. Outside agterm
there is no such return path, so the script refuses with exit 3 and the caller presents the table in chat instead.

Input is a JSON file:
    {"title": "...", "rows": [{"id": "r1-8", "finding": "...", "rating": "plausible, recoverable",
                               "view": "Fix: keep stored extras ...", "fix": true}, ...]}

Prints one JSON line and exits:
    0  {"outcome": "submitted", "fix": ["r1-8", ...], "feedback": {"r1-8": "..."}}
       (an empty list is a real answer: fix nothing; feedback holds only rows whose note is non-empty)
    2  {"outcome": "dismissed"}                         (closed without Apply: nothing was decided)
    3  not inside agterm; the reason is on stderr
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


def _render(title: str, rows: list[dict]) -> str:
    """The page. Every value is escaped: findings quote code and email text, and the page can run agterm commands."""
    body = "\n".join(
        f'<tr><td class="pick"><input type="checkbox" value="{html.escape(str(row["id"]), quote=True)}"'
        f'{" checked" if row.get("fix") else ""}></td>'
        f'<td class="id">{html.escape(str(row["id"]))}</td>'
        f'<td>{html.escape(str(row.get("finding", "")))}</td>'
        f'<td class="rating">{html.escape(str(row.get("rating", "")))}</td>'
        f'<td>{html.escape(str(row.get("view", "")))}</td>'
        f'<td class="note"><button type="button" class="feedback" title="Fix, with feedback">✎</button></td></tr>'
        f'<tr class="feedback-row" hidden><td></td><td colspan="5"><textarea rows="2" placeholder="How to fix it"></textarea></td></tr>'
        for row in rows
    )
    # Styled from the terminal theme agterm injects, with a fallback at each use, so the page reads as part of the
    # session in light and dark alike. A row is ticked by clicking anywhere on it, not only on the box.
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
  body {{ font: 13px/1.45 -apple-system, system-ui, sans-serif; margin: 16px 20px; color: var(--agterm-foreground, #222); background: var(--agterm-background, #fff); }}
  h1 {{ font-size: 15px; font-weight: 600; margin: 0 0 12px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; vertical-align: top; padding: 6px 8px; border-bottom: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 15%, transparent); }}
  th {{ font-weight: 600; font-size: 12px; opacity: 0.7; }}
  tr.row {{ cursor: pointer; }}
  tr.row:hover {{ background: color-mix(in srgb, var(--agterm-foreground, #222) 6%, transparent); }}
  td.pick {{ width: 1.5em; }}
  td.id, td.rating {{ white-space: nowrap; opacity: 0.8; }}
  .bar {{ position: sticky; bottom: 0; display: flex; gap: 8px; align-items: center; padding: 12px 0 4px; background: var(--agterm-background, #fff); }}
  button {{ font: inherit; padding: 4px 14px; border-radius: 6px; border: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 30%, transparent); background: transparent; color: inherit; cursor: pointer; }}
  button.apply {{ background: var(--agterm-color-4, #2563eb); border-color: transparent; color: #fff; }}
  #count {{ opacity: 0.7; }}
  td.note {{ width: 2em; }}
  button.feedback {{ padding: 0 6px; border-color: transparent; opacity: 0.6; }}
  button.feedback.on {{ opacity: 1; border-color: color-mix(in srgb, var(--agterm-foreground, #222) 30%, transparent); }}
  tr.feedback-row td {{ border-bottom: none; padding-top: 0; }}
  textarea {{ font: inherit; width: 100%; box-sizing: border-box; padding: 4px 6px; border-radius: 4px; color: inherit; background: transparent; border: 1px solid color-mix(in srgb, var(--agterm-foreground, #222) 30%, transparent); }}
</style></head>
<body>
<h1>{html.escape(title)}</h1>
<table>
<thead><tr><th></th><th>#</th><th>Finding</th><th>Rating</th><th>View</th><th></th></tr></thead>
<tbody>
{body}
</tbody>
</table>
<div class="bar">
  <button type="button" class="apply" id="apply">Apply</button>
  <button type="button" data-agterm="session.overlay.close">Cancel</button>
  <span id="count"></span>
</div>
<script>
  const boxes = [...document.querySelectorAll('td.pick input')];
  const count = document.getElementById('count');
  const recount = () => {{ const n = boxes.filter((b) => b.checked).length; count.textContent = n === 1 ? '1 to fix' : n + ' to fix'; }};
  const noteOf = (box) => box.closest('tr').nextElementSibling.querySelector('textarea');
  for (const box of boxes) {{
    const row = box.closest('tr');
    const note = noteOf(box);
    const toggle = row.querySelector('button.feedback');
    row.classList.add('row');
    row.addEventListener('click', (event) => {{ if (event.target !== box && event.target !== toggle) box.checked = !box.checked; recount(); }});
    box.addEventListener('change', recount);
    // Feedback means "fix it, like this", so writing any ticks the row.
    toggle.addEventListener('click', () => {{ const panel = note.closest('tr'); panel.hidden = !panel.hidden; if (!panel.hidden) note.focus(); }});
    note.addEventListener('input', () => {{ toggle.classList.toggle('on', note.value.trim() !== ''); if (note.value.trim()) {{ box.checked = true; recount(); }} }});
  }}
  recount();
  document.getElementById('apply').addEventListener('click', () => {{
    const picked = boxes.filter((b) => b.checked);
    const feedback = Object.fromEntries(picked.map((b) => [b.value, noteOf(b).value.trim()]).filter(([, text]) => text));
    const value = JSON.stringify({{ fix: picked.map((b) => b.value), feedback }});
    agterm.request('session.overlay.submit', {{ args: {{ value }} }}).catch((error) => {{ count.textContent = 'Could not submit: ' + error; }});
  }});
</script>
</body></html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Show review findings as a table of checkboxes and print the ids the user leaves ticked.")
    parser.add_argument("rows", help="JSON file: {title, rows: [{id, finding, rating, view, fix}]}")
    parser.add_argument("--out", help="where to write the page; default: beside the rows file, as review-picker.html")
    parser.add_argument("--render-only", action="store_true", help="write the page and print its path without showing it")
    options = parser.parse_args()

    try:
        with open(options.rows, encoding="utf-8") as handle:
            spec = json.load(handle)
        rows = spec["rows"]
        if not isinstance(rows, list) or not all(isinstance(row, dict) and "id" in row for row in rows):
            raise ValueError("rows must be a list of objects with an id")
    except (OSError, ValueError, KeyError) as error:
        print(f"review_picker: cannot read {options.rows}: {error}", file=sys.stderr)
        return 1

    out = os.path.abspath(options.out or os.path.join(os.path.dirname(os.path.abspath(options.rows)), "review-picker.html"))
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(_render(str(spec.get("title") or "Review findings"), rows))
    if options.render_only:
        print(out)
        return 0

    session = os.environ.get("AGTERM_SESSION_ID")
    if not session or not shutil.which("agtermctl"):
        print("review_picker: not inside agterm, so the page has no way to answer; present the table in chat", file=sys.stderr)
        return 3

    shown = subprocess.run(["agtermctl", "session", "overlay", "open", "--html", out, "--js", "--block", "--target", session],
                           capture_output=True, text=True)
    if shown.returncode == 2:
        print(json.dumps({"outcome": "dismissed"}))
        return 2
    if shown.returncode != 0:
        print(f"review_picker: agtermctl exited {shown.returncode}: {(shown.stderr or shown.stdout).strip()}", file=sys.stderr)
        return 1
    try:
        answer = json.loads(shown.stdout)
        picked = json.loads(answer["value"])
        fix, feedback = picked["fix"], picked["feedback"]
    except (ValueError, KeyError, TypeError) as error:
        print(f"review_picker: unreadable answer {shown.stdout.strip()!r}: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"outcome": "submitted", "fix": fix, "feedback": feedback}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
