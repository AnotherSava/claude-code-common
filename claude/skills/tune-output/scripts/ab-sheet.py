"""Render an A/B run as a blind side-by-side page.

    ab-sheet.py <out-dir>

Reads <out-dir>/prompts.json and the N.A.md / N.B.md arm files written by
ab-run.sh, shuffles each pair's arms into Left/Right independently, and writes
compare.html plus key.json.

The shuffle is seeded from os.urandom and recorded only in key.json, which this
script never prints. So whoever runs it does not learn the mapping by running it
and can judge the pairs honestly before opening the key.
"""

import html
import json
import os
import random
import sys

FAIL_MARKERS = ("ARM A FAILED", "ARM B FAILED", "RETURNED NOTHING")


def _read_arm(out_dir: str, index: int, arm: str) -> str:
    path = os.path.join(out_dir, f"{index}.{arm}.md")
    if not os.path.exists(path):
        return "_(missing)_"
    text = open(path, encoding="utf-8", errors="replace").read().strip()
    # The CLI appends a per-invocation environment marker. It is identical in both
    # arms and only distracts, so drop a trailing one.
    head, sep, tail = text.rpartition("\n")
    if sep and tail.strip().startswith("·") and tail.strip().endswith("·"):
        text = head
    return text


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Response style A/B &mdash; {n} pairs</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  :root {{ color-scheme: light dark; --bg:#fbfbfa; --fg:#22201d; --mut:#6b6660; --line:#e3e0da; --card:#fff; --accent:#7a5c3e; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#191817; --fg:#e6e3de; --mut:#98938c; --line:#333029; --card:#211f1d; --accent:#c8a678; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif; }}
  header.top {{ position:sticky; top:0; z-index:5; background:var(--bg); border-bottom:1px solid var(--line); padding:14px 24px; }}
  header.top h1 {{ font-size:15px; margin:0 0 4px; font-weight:600; }}
  header.top p {{ margin:0; color:var(--mut); font-size:13px; max-width:80ch; }}
  nav {{ margin-top:8px; }}
  nav a {{ display:inline-block; min-width:24px; text-align:center; padding:2px 6px; margin-right:4px;
           border:1px solid var(--line); border-radius:5px; color:var(--fg); text-decoration:none; font-size:12px; }}
  nav a:hover {{ border-color:var(--accent); }}
  main {{ padding:0 24px 64px; }}
  section {{ margin-top:36px; }}
  h2 {{ font-size:14px; font-weight:600; color:var(--mut); letter-spacing:.02em;
        margin:0 0 10px; display:flex; align-items:center; gap:10px; }}
  .num {{ display:inline-grid; place-items:center; width:22px; height:22px; border-radius:50%;
          background:var(--accent); color:var(--bg); font-size:12px; font-weight:700; }}
  .flag {{ color:#c0392b; font-weight:600; }}
  details.prompt {{ margin-bottom:14px; border:1px solid var(--line); border-radius:8px; background:var(--card); }}
  details.prompt summary {{ cursor:pointer; padding:8px 12px; font-size:12px; color:var(--mut); }}
  details.prompt pre {{ margin:0; padding:0 12px 4px; white-space:pre-wrap; font-size:13px; line-height:1.5; }}
  .watch {{ margin:0; padding:0 12px 12px; font-size:12px; color:var(--mut); font-style:italic; }}
  .pair {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; align-items:start; }}
  article {{ border:1px solid var(--line); border-radius:8px; background:var(--card); overflow:hidden; }}
  article > header {{ padding:6px 14px; font-size:12px; font-weight:600; color:var(--mut); border-bottom:1px solid var(--line); }}
  .md {{ padding:4px 16px 14px; font-size:14px; }}
  .md :first-child {{ margin-top:10px; }}
  .md pre {{ background:rgba(127,127,127,.10); padding:10px 12px; border-radius:6px; overflow-x:auto; font-size:12.5px; }}
  .md code {{ background:rgba(127,127,127,.13); padding:1px 4px; border-radius:3px; font-size:12.5px; }}
  .md pre code {{ background:none; padding:0; }}
  .md h1,.md h2,.md h3 {{ font-size:14px; margin:16px 0 6px; }}
  .md ol,.md ul {{ padding-left:22px; }}
  .md li {{ margin:3px 0; }}
  .md table {{ border-collapse:collapse; font-size:13px; }}
  .md th,.md td {{ border:1px solid var(--line); padding:4px 8px; text-align:left; }}
</style>
<header class="top">
  <h1>Response style A/B &mdash; {n} pairs</h1>
  <p>Sides are shuffled independently per pair, so a side that wins here says nothing about the next pair.
     One arm is today's behaviour, the other adds the candidate rules. Both load your real global CLAUDE.md;
     tools are disabled in both, so this shows how a reply reads, not how the rules behave while work is
     executing. If any answer cites something outside its own prompt, the isolation failed and the run is void.</p>
  <nav>{nav}</nav>
</header>
<main>{body}</main>
<script>
  const render = () => document.querySelectorAll('.md').forEach(el => {{
    const src = JSON.parse(el.dataset.md);
    el.innerHTML = window.marked ? marked.parse(src)
      : '<pre>' + src.replace(/[&<>]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c])) + '</pre>';
  }});
  window.marked ? render() : window.addEventListener('load', render);
</script>
"""


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: ab-sheet.py <out-dir>", file=sys.stderr)
        raise SystemExit(2)
    out_dir = os.path.abspath(sys.argv[1])
    prompts = json.load(open(os.path.join(out_dir, "prompts.json"), encoding="utf-8"))

    rng = random.Random(os.urandom(16))
    key, sections, flagged = {}, [], []

    for i, case in enumerate(prompts):
        left_arm, right_arm = ("A", "B") if rng.random() < 0.5 else ("B", "A")
        key[case["id"]] = {"left": left_arm, "right": right_arm}
        left, right = _read_arm(out_dir, i, left_arm), _read_arm(out_dir, i, right_arm)
        bad = any(m in left or m in right for m in FAIL_MARKERS)
        if bad:
            flagged.append(case["id"])
        sections.append({
            "n": i + 1, "id": case["id"], "prompt": case["prompt"],
            "watch": case.get("what_to_watch", ""), "left": left, "right": right, "bad": bad,
        })

    json.dump(key, open(os.path.join(out_dir, "key.json"), "w", encoding="utf-8"), indent=1)

    body = "".join(
        f"""
<section id="p{s['n']}">
  <h2><span class="num">{s['n']}</span>{html.escape(s['id'])}
      {'<span class="flag">&mdash; a run failed, re-run this pair</span>' if s['bad'] else ''}</h2>
  <details class="prompt"><summary>prompt</summary><pre>{html.escape(s['prompt'])}</pre>
    <p class="watch">{html.escape(s['watch'])}</p></details>
  <div class="pair">
    <article><header>Left</header><div class="md" data-md="{html.escape(json.dumps(s['left']))}"></div></article>
    <article><header>Right</header><div class="md" data-md="{html.escape(json.dumps(s['right']))}"></div></article>
  </div>
</section>""" for s in sections)

    nav = " ".join(f'<a href="#p{s["n"]}">{s["n"]}</a>' for s in sections)
    path = os.path.join(out_dir, "compare.html")
    open(path, "w", encoding="utf-8").write(PAGE.format(n=len(sections), nav=nav, body=body))

    print(f"wrote {path} ({len(sections)} pairs)")
    print(f"link:  file:///{path.replace(os.sep, '/').lstrip('/')}")
    if flagged:
        print(f"WARNING: failed runs in pair(s): {', '.join(flagged)} -- re-run before judging")


if __name__ == "__main__":
    main()
