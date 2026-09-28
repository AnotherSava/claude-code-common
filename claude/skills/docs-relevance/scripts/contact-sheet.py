#!/usr/bin/env python3
"""Build the documentation screenshots' contact sheet from the manifest, the images and git.

    python contact-sheet.py [--manifest PATH] [--notes PATH] [--out PATH] [--base REV] [--originals DIR] [--changed ID,...]

Run from anywhere in the repo. The manifest is found by name (screenshots.json, exactly one) unless
given; the page goes to tmp/screenshot-contact-sheet-<date>.html, which must be gitignored along with
the sidecar beside it, and its file:/// URL is printed on a line of its own.

WHAT THE SHEET SHOWS IS DERIVED FROM WHAT THE REPO KEEPS. The frames, what each shows, how it is
captured and the standard it is judged by come from the manifest. Each file's stages come from three
places: its previous version, read out of git at --base (HEAD by default, through git's own filters so
an LFS pointer is read as the image); its unframed capture, raw/<name> beside the frames; and the
working-tree frame. A renamed file is followed through the manifest as the base revision has it: within
one entry id, a name the base entry already had is itself, and each new name pairs, in order, with a
base name of that entry that has left the tree and the manifest. A file that git has under another
path which no longer exists is taken as renamed too. Failing both, the saved originals directory (--originals, by default
the newest tmp/screenshot-originals-*) supplies the previous version of a frame that was never
committed, which is the case the skill keeps those copies for.

What happened to a file is read off those stages. No previous version is new. Identical to it is left
alone. A raw identical to the previous frame, or to the previous raw, is a border: the picture is the
one already published and only its edge moved. Anything else is re-captured. A listed file that is
missing is an orphan, reported with its own dot rather than failing the build; a file an entry dropped
since the base revision is named on that entry, and any page still citing a file that is gone is
called DANGLING, whichever entry it belonged to. An entry's dot takes
the strongest of its files' outcomes, orphan first, then re-captured, new, border, left alone; each
file of a series carries its own outcome on its meta line. Every image the skill's doc-image pathspec
finds that no entry lists is shown as unregistered.

THE ONE THING A PERSON WRITES IS THE NOTES FILE: the verdicts in words, each frame's staleness proof
and what a re-capture would need, the lede, and the coverage gaps. JSON, every key optional, every
unknown key refused:

    {"runLine": "...", "lede": ["<b>...</b> ..."],
     "legend": [{"key": "stale", "label": "stale, awaiting a decision", "colour": "#bf8700"}],
     "frames": {"<id or unregistered path>": {"verdict": "...", "dot": "<kind>", "proof": ["..."], "needs": "...", "standard": "..."}},
     "gaps": [{"page": "...", "section": "...", "shows": "...", "why": "...", "needs": "...", "frame": "<id, once captured>"}]}

A dot is one of the derived kinds (recaptured, new, border, alone, orphan) or a key the notes' legend
adds; a run that shows no change yet, the proposal written before any capture, uses that to tell stale
from current. "standard" replaces the "Judged by" line, and an empty one drops it, as for a frame
reported NOT CHECKED. Proof, lede and needs strings are HTML, so a sheet can carry <code> and <b>;
everything else is escaped. A frame with no proof, and a gap or undecided frame with no re-capture
recipe, says so on the page where it would be.

THE TEMPLATE IS THE SOURCE OF THE PAGE'S FIXED PARTS. Its style, its script, and its nav from the top
through the list heading are copied from references/contact-sheet.html beside this file, and the dot
colours are read off its legend, so a template change reaches every sheet; the build refuses when an
element the script looks up is missing from the page. "Updated this pass" is read off a sidecar of
content hashes beside the page, screenshot-contact-sheet.hashes.json, together with the files it
marked: a write that moves no image keeps the previous marks, and --changed sets them outright (an
empty --changed= marks nothing), which is what the first write needs, when there is no baseline yet. Every image is a base64 data: URI.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import html
import io
import json
import posixpath
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

from PIL import Image

TEMPLATE = Path(__file__).resolve().parent.parent / "references" / "contact-sheet.html"
BOX, ZOOM, GAP = 40, 6, 14
# The template legend's wording, which is how its colours are found.
LEGEND = {"recaptured": "re-captured or keyed", "new": "new this session", "border": "border only", "alone": "left alone"}
ORPHAN = ("orphan", "file missing", "#cf222e")
VERDICTS = {"orphan": "file missing", "recaptured": "re-captured", "new": "new", "border": "border added", "alone": "unchanged"}
RANK = ["orphan", "recaptured", "new", "border", "alone"]
IMAGE_SPEC = [":/docs/*.png", ":/docs/*.jpg", ":/docs/*.jpeg", ":/docs/*.gif", ":/docs/*.webp", ":(top,exclude,glob)docs/**/raw/**"]
EMBED = r"\]\([^)]+\.(png|jpg|jpeg|gif|webp)\)|src=.[^ >]+\.(png|jpg|jpeg|gif|webp)"
TARGET = re.compile(r"""\]\(\s*<?([^)\s>]+)|src=["']?([^"'\s>]+)""")
OPTIONS = ("--manifest", "--notes", "--out", "--base", "--originals", "--changed")
NOTE_KEYS = {"runLine", "lede", "legend", "frames", "gaps"}
FRAME_NOTE_KEYS = {"verdict", "dot", "proof", "needs", "standard"}
GAP_KEYS = {"page", "section", "shows", "why", "needs", "frame"}


class Repo:
    def __init__(self, root: Path, base: str | None) -> None:
        self.root = root
        self.base_name = base or "HEAD"
        run = self.git("rev-parse", "--verify", "--quiet", f"{self.base_name}^{{commit}}")
        self.base = run.stdout.decode().strip() or None
        if self.base is None and base is not None:
            raise SystemExit(f"contact-sheet: --base {base} is not a commit in this repository")
        self._blobs = None

    def git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.root), "-c", "core.quotePath=false", *args], capture_output=True)

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def at_base(self, rel: str) -> bytes | None:
        """The file as the base revision has it, through git's filters, or None."""
        if self.base is None:
            return None
        run = self.git("cat-file", "--filters", f"{self.base}:{rel}")
        return run.stdout if run.returncode == 0 else None

    def ignored(self, path: Path) -> bool:
        return self.git("check-ignore", "-q", self.rel(path)).returncode == 0

    def renamed_from(self, path: Path, listed: set) -> str | None:
        """A base path holding this file's exact content that is gone from the tree and from the manifest."""
        if self.base is None:
            return None
        if self._blobs is None:
            self._blobs = {}
            for rec in filter(None, self.git("ls-tree", "-r", "-z", self.base).stdout.decode("utf-8", "replace").split("\0")):
                meta, name = rec.split("\t", 1)
                self._blobs.setdefault(meta.split()[2], []).append(name)
        oid = self.git("hash-object", str(path)).stdout.decode().strip()
        gone = [p for p in self._blobs.get(oid, []) if not (self.root / p).exists() and p not in listed]
        return gone[0] if gone else None


def b64(im: Image.Image) -> str:
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def corners(im: Image.Image) -> str:
    """The four corners at 6x nearest-neighbour, laid out as they sit in the frame, on a transparent gutter."""
    im = im.convert("RGBA")
    w, h = im.size
    b = min(BOX, w // 2, h // 2)
    side = b * ZOOM
    sheet = Image.new("RGBA", (side * 2 + GAP, side * 2 + GAP), (0, 0, 0, 0))
    for k, (x, y) in enumerate([(0, 0), (w - b, 0), (0, h - b), (w - b, h - b)]):
        sheet.paste(im.crop((x, y, x + b, y + b)).resize((side, side), Image.NEAREST), ((k % 2) * (side + GAP), (k // 2) * (side + GAP)))
    return b64(sheet)


def ring(im: Image.Image) -> str:
    """The colour of the frame's outermost row at its middle: the ring the frame step drew."""
    r, g, b, a = im.convert("RGBA").getpixel((im.width // 2, 0))
    return f"<code>#{r:02x}{g:02x}{b:02x}</code>" if a == 255 else "transparent at the edge"


def open_image(data: bytes) -> Image.Image:
    im = Image.open(io.BytesIO(data))
    im.load()
    return im


def file_stages(repo: Repo, shots: Path, originals: Path | None, name: str, old_name: str | None, listed: set) -> dict:
    """One file's outcome and its stages, oldest first, as (label, css class, image)."""
    path, raw_path = shots / name, shots / "raw" / name
    old_path = shots / (old_name or name)
    if not path.exists():
        before = repo.at_base(repo.rel(old_path))
        return {"name": name, "kind": "orphan", "stages": [("Last committed", "", open_image(before))] if before else [], "source": None, "framing": None}
    frame = path.read_bytes()
    before, label, source = repo.at_base(repo.rel(old_path)), "Before (committed)", "git"
    if before is not None and old_path != path:
        label = f"Before (committed as {repo.rel(old_path)})"
    if before is None and (moved := repo.renamed_from(path, listed)):
        old_path, before, label = repo.root / moved, repo.at_base(moved), f"Before (committed as {moved})"
    if before is None and originals is not None and (originals / name).exists():
        before, label, source = (originals / name).read_bytes(), "Before (saved original)", "originals"
    raw = raw_path.read_bytes() if raw_path.exists() else None
    base_raw = repo.at_base(repo.rel(old_path.parent / "raw" / old_path.name))
    if before is None:
        kind = "new"
    elif before == frame:
        kind = "alone"
    elif raw is not None and raw in (before, base_raw):
        kind = "border"
    else:
        kind = "recaptured"
    stages = []
    if before is not None and before != frame:
        stages.append((label, "before", open_image(before)))
    if raw is not None and raw != frame:
        stages.append(("Before framing", "unframed", open_image(raw)))
    stages.append(("Current" if kind == "alone" else "After", "", open_image(frame)))
    framing = None if raw is None else ("the frame step changed nothing: no ring" if raw == frame else "ring " + ring(stages[-1][2]))
    return {"name": name, "kind": kind, "stages": stages, "framing": framing, "source": source if kind not in ("new", "alone") else None}


def file_hash(shots: Path, name: str) -> str:
    h = hashlib.sha256()
    for p in (shots / name, shots / "raw" / name):
        h.update(p.read_bytes() if p.exists() else b"missing")
    return h.hexdigest()


def embeds(repo: Repo) -> dict:
    """Every image the published pages reference, as repo-relative path -> the pages citing it."""
    out = repo.git("grep", "--untracked", "--full-name", "-z", "-InoE", EMBED, "--", ":/docs", ":/README.md", ":!/docs/plans").stdout.decode("utf-8", "replace")
    found = {}
    for rec in filter(None, out.split("\n")):
        parts = rec.split("\0")
        if len(parts) < 3:
            continue
        page, m = parts[0], TARGET.search(parts[-1])
        if not m:
            continue
        target = urllib.parse.unquote((m.group(1) or m.group(2)).split("#")[0].split("?")[0])
        if target.startswith(("http:", "https:", "data:", "//")):
            continue
        resolved = posixpath.normpath(target.lstrip("/") if target.startswith("/") else posixpath.join(posixpath.dirname(page), target))
        found.setdefault(resolved, set()).add(page)
    return found


def check_notes(notes: dict, ids: set, taken: dict) -> list:
    """Every way the notes disagree with the sheet. `taken` is the built-in legend, label -> colour."""
    strings = lambda v: isinstance(v, list) and all(isinstance(p, str) for p in v)
    problems = [f"unknown notes key {k!r}; known: {', '.join(sorted(NOTE_KEYS))}" for k in notes if k not in NOTE_KEYS]
    if "lede" in notes and not strings(notes["lede"]):
        problems.append("notes lede must be a list of strings")
    if "runLine" in notes and not isinstance(notes["runLine"], str):
        problems.append("notes runLine must be a string")
    kinds, labels, colours = set(RANK), set(taken), {c.lower() for c in taken.values()}
    for x in notes.get("legend", []):
        if not (isinstance(x, dict) and set(x) == {"key", "label", "colour"} and all(isinstance(v, str) and v for v in x.values())):
            problems.append(f"notes legend entry {x!r} needs exactly key, label and colour")
        elif x["key"] in kinds:
            problems.append(f"notes legend key {x['key']!r} is already a kind; pick another name")
        elif x["label"] in labels:
            problems.append(f"notes legend label {x['label']!r} is already in the legend")
        elif not re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", x["colour"]):
            problems.append(f"notes legend colour {x['colour']!r} for {x['key']!r} must be #rgb or #rrggbb")
        elif x["colour"].lower() in colours:
            problems.append(f"notes legend colour {x['colour']!r} for {x['key']!r} is already used by another kind")
        else:
            kinds.add(x["key"])
            labels.add(x["label"])
            colours.add(x["colour"].lower())
    for fid, note in notes.get("frames", {}).items():
        if fid not in ids:
            problems.append(f"notes name frame {fid!r}, which is neither a manifest id nor an unregistered image; known: {', '.join(sorted(ids))}")
        problems += [f"notes frame {fid!r} has unknown key {k!r}; known: {', '.join(sorted(FRAME_NOTE_KEYS))}" for k in note if k not in FRAME_NOTE_KEYS]
        if "dot" in note and note["dot"] not in kinds:
            problems.append(f"notes frame {fid!r} has dot {note['dot']!r}; use one of {', '.join(sorted(kinds))}")
        if "proof" in note and not strings(note["proof"]):
            problems.append(f"notes frame {fid!r}: proof must be a list of strings")
        problems += [f"notes frame {fid!r}: {k} must be a string" for k in ("verdict", "needs", "standard") if k in note and not isinstance(note[k], str)]
    for i, gap in enumerate(notes.get("gaps", []), 1):
        problems += [f"notes gap G{i} has unknown key {k!r}; known: {', '.join(sorted(GAP_KEYS))}" for k in gap if k not in GAP_KEYS]
        if not gap.get("page"):
            problems.append(f"notes gap G{i} has no page")
        if gap.get("frame") and gap["frame"] not in ids:
            problems.append(f"notes gap G{i} names frame {gap['frame']!r}, which is not on the sheet")
    return problems


def find_manifest(repo: Repo) -> Path:
    listed = repo.git("ls-files", "-co", "--exclude-standard", "-z", "--", ":/*screenshots.json").stdout.decode().split("\0")
    listed = [p for p in listed if p and Path(p).name == "screenshots.json"]
    if len(listed) != 1:
        raise SystemExit(f"contact-sheet: found {len(listed)} screenshots.json files ({', '.join(listed) or 'none'}); pass --manifest")
    return (repo.root / listed[0]).resolve()


def parse(argv: list[str]) -> dict:
    usage = next(l.strip() for l in __doc__.splitlines() if l.strip().startswith("python contact-sheet.py"))
    opts, args = {}, list(argv)
    while args:
        key, eq, value = args.pop(0).partition("=")
        if key in ("-h", "--help"):
            print(usage)
            raise SystemExit(0)
        if key not in OPTIONS:
            raise SystemExit(f"contact-sheet: unknown option {key!r}\n{usage}")
        if not eq:
            if not args or args[0].startswith("--"):
                raise SystemExit(f"contact-sheet: {key} needs a value\n{usage}")
            value = args.pop(0)
        if not value and key != "--changed":
            raise SystemExit(f"contact-sheet: {key} needs a value\n{usage}")
        opts[key] = value
    return opts


def main(argv: list[str]) -> int:
    opts = parse(argv)
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode != 0:
        raise SystemExit("contact-sheet: run it inside the repository whose screenshots it shows")
    repo = Repo(Path(top.stdout.strip()).resolve(), opts.get("--base"))
    manifest = Path(opts["--manifest"]).resolve() if "--manifest" in opts else find_manifest(repo)
    shots = manifest.parent
    date = datetime.date.today().isoformat()
    out = Path(opts["--out"]).resolve() if "--out" in opts else repo.root / "tmp" / f"screenshot-contact-sheet-{date}.html"
    sidecar = out.parent / "screenshot-contact-sheet.hashes.json"
    for p in (out, sidecar):
        if p.is_relative_to(repo.root) and not repo.ignored(p):
            raise SystemExit(f"contact-sheet: {repo.rel(p)} is not gitignored, so it would land in the next commit; add /tmp/ to .gitignore")
    if "--originals" in opts:
        originals = Path(opts["--originals"]).resolve()
    else:
        saved = sorted((repo.root / "tmp").glob("screenshot-originals-*"))
        originals = saved[-1] if saved else None

    entries = json.loads(manifest.read_text(encoding="utf-8"))["screenshots"]
    problems = [f"manifest entry {e.get('id', i)} lacks {k}" for i, e in enumerate(entries, 1) for k in ("id", "files", "shows") if not e.get(k)]
    if problems:
        raise SystemExit("contact-sheet: " + "; ".join(problems))
    # A rename is a files fix on the same entry, so the base revision's manifest says what each file was called.
    base_manifest = repo.at_base(repo.rel(manifest))
    base_files = {e.get("id"): e.get("files", []) for e in json.loads(base_manifest).get("screenshots", [])} if base_manifest else {}
    listed = {repo.rel(shots / n) for e in entries for n in e["files"]}
    images = [p for p in repo.git("ls-files", "--full-name", "-co", "--exclude-standard", "-z", "--", *IMAGE_SPEC).stdout.decode().split("\0") if p and (repo.root / p).exists()]
    unregistered = [p for p in images if p not in listed]
    for p in unregistered:
        entries.append({"id": p, "files": [posixpath.relpath(p, repo.rel(shots))], "unregistered": True})
    tpl = TEMPLATE.read_text(encoding="utf-8")
    style = tpl[tpl.index("<!doctype html>"):tpl.index("<nav>")].replace("REPO", html.escape(repo.root.name)).replace("DATE", date)
    script = tpl[tpl.index("<script>"):]
    nav_head = tpl[tpl.index("<nav>"):tpl.index('<div class="hd">')]
    dots, labels = {}, dict(LEGEND)
    for kind, label in LEGEND.items():
        m = re.search(r'<i style="background:([^"]+)"></i>' + re.escape(label) + "</span>", nav_head)
        if not m:
            raise SystemExit(f"contact-sheet: the template's legend no longer has {label!r}; update LEGEND to its wording")
        dots[kind] = m.group(1)
    # Kinds the template's legend lacks go in just before its last-pass row, or before its end.
    anchor = re.search(r'\n[ \t]*<span>\s*<i[^>]*class="fresh-key"', nav_head)
    if anchor is None and 'class="legend"' in nav_head:
        anchor = re.compile(r'\n[ \t]*</div>').search(nav_head, nav_head.index('class="legend"'))
    if anchor is None:
        raise SystemExit("contact-sheet: the template's legend has neither a last-pass row nor a closing tag to add kinds before")

    notes = json.loads(Path(opts["--notes"]).read_text(encoding="utf-8")) if "--notes" in opts else {}
    ids = {e["id"] for e in entries}
    changed = [x for x in opts.get("--changed", "").split(",") if x]
    taken = {labels[k]: dots[k] for k in LEGEND} | {ORPHAN[1]: ORPHAN[2]}
    problems = check_notes(notes, ids, taken) + [f"--changed names {x!r}, which is not on the sheet" for x in changed if x not in ids]
    if problems:
        raise SystemExit("contact-sheet: " + "\n  ".join(["notes or flags do not match the sheet:"] + problems))
    extra = [ORPHAN] + [(x["key"], x["label"], x["colour"]) for x in notes.get("legend", [])]
    for key, label, colour in extra:
        dots[key], labels[key] = colour, label

    embedded = embeds(repo)
    last = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else None
    if last is not None and "hashes" not in last:
        last = {"hashes": last, "marked": []}
    frames, hashes = [], {}
    for e in entries:
        was = base_files.get(e["id"], [])
        gone = iter([n for n in was if n not in e["files"] and not (shots / n).exists() and repo.rel(shots / n) not in listed])
        old = {n: (n if n in was else next(gone, None)) for n in e["files"]}
        files = [file_stages(repo, shots, originals, n, old[n], listed) for n in e["files"]]
        dropped = [n for n in was if n not in e["files"] and n not in old.values()]
        for f in files:
            hashes[f["name"]] = file_hash(shots, f["name"])
        derived = next(k for k in RANK if k in [f["kind"] for f in files])
        note = notes.get("frames", {}).get(e["id"], {})
        if dropped and derived in ("border", "alone"):
            derived = "recaptured"
        frames.append({"entry": e, "note": note, "files": files, "dot": note.get("dot", derived), "orphan": derived == "orphan", "dropped": dropped,
                       "pages": sorted({p for n in e["files"] for p in embedded.get(repo.rel(shots / n), ())})})

    # One decision marks files; an entry is marked when any of its files is.
    if "--changed" in opts:
        marked_files = {x["name"] for f in frames if f["entry"]["id"] in changed for x in f["files"]}
    elif last is None:
        marked_files = set()
        print("contact-sheet: no baseline yet, so nothing is marked as updated; pass --changed=<id,...> to mark this run's frames", file=sys.stderr)
    else:
        moved = {n for n, h in hashes.items() if last["hashes"].get(n) != h}
        marked_files = moved or set(last.get("marked", [])) & set(hashes)
    marked = {f["entry"]["id"] for f in frames if any(x["name"] in marked_files for x in f["files"])}
    used = {f["dot"] for f in frames}
    if len(frames) > 1 and len(used) == 1:
        print(f"contact-sheet: every frame's dot reads {labels[next(iter(used))]!r}, so it tells the reader nothing; add a legend to the notes and set each frame's dot from it, or say in the lede why uniform is right", file=sys.stderr)

    def verdict(f: dict) -> str:
        if "verdict" in f["note"]:
            return f["note"]["verdict"]
        if f["entry"].get("unregistered"):
            return "unregistered, policy undecided"
        kinds = [x["kind"] for x in f["files"]]
        if f["orphan"]:
            return "orphaned: " + ", ".join(x["name"] for x in f["files"] if x["kind"] == "orphan") + " missing"
        said = VERDICTS[kinds[0]] if len(set(kinds)) == 1 else ", ".join(f"{kinds.count(k)} {VERDICTS[k]}" for k in RANK if k in kinds)
        return said + (f", {len(f['dropped'])} dropped" if f["dropped"] else "")

    def summary(x: dict) -> str:
        if x["kind"] == "orphan":
            return "missing"
        now = next(im for _, c, im in x["stages"] if c == "")
        before = next((im for _, c, im in x["stages"] if c == "before"), None)
        if before is None:
            return f"{'new' if x['kind'] == 'new' else 'unchanged'} · {now.width} × {now.height}"
        return f"{before.width} × {before.height} → {now.width} × {now.height}"

    def table_sizes(f: dict) -> str:
        return summary(f["files"][0]) if len(f["files"]) == 1 else "; ".join(f"{x['name']}: {summary(x)}" for x in f["files"])

    gaps = notes.get("gaps", [])
    number = {f["entry"]["id"]: i for i, f in enumerate(frames, 1)}
    gap_status = lambda g: f'captured as frame {number[g["frame"]]}' if g.get("frame") else "no shot yet"
    gap_label = lambda g: g["page"] + (f' · {g["section"]}' if g.get("section") else "")
    legend_extra = "".join(f'\n    <span><i style="background:{dots[k]}"></i>{html.escape(labels[k])}</span>' for k, _, _ in extra if k in used)
    head = nav_head[:anchor.start()] + legend_extra + nav_head[anchor.start():]
    nav = [head + f'<div class="hd">ALL {len(frames)} FRAMES</div>']
    for i, f in enumerate(frames, 1):
        fresh, tag = (' class="fresh"', '<span class="tag">new</span>') if f["entry"]["id"] in marked else ("", "")
        nav.append(f'  <a href="#s{i}"{fresh}><span class="n">{i}</span><span class="dot" style="background:{dots[f["dot"]]}"></span>{html.escape(f["entry"]["id"])}{tag}</a>')
    if gaps:
        nav.append(f'  <hr><div class="hd">{len(gaps)} COVERAGE GAPS</div>')
        nav += [f'  <a href="#g{i}"><span class="n">G{i}</span>{html.escape(gap_label(g))}</a>' for i, g in enumerate(gaps, 1)]
    nav.append('</nav>')

    rows = "".join(f'<tr><td>{i}</td><td>{html.escape(f["entry"]["id"])}</td><td>{html.escape(table_sizes(f))}</td><td>{html.escape(verdict(f))}</td></tr>' for i, f in enumerate(frames, 1))
    rows += "".join(f'<tr><td>G{i}</td><td>{html.escape(gap_label(g))}</td><td>' + (html.escape(table_sizes(frames[number[g["frame"]] - 1])) if g.get("frame") else "—") + f'</td><td>{gap_status(g)}</td></tr>' for i, g in enumerate(gaps, 1))
    changed_count = sum(bool(f["dropped"]) or any(x["kind"] != "alone" for x in f["files"]) for f in frames)
    # A citation of a file that is gone, whether or not any entry still lists it: a broken image on the site.
    gone = {path: pages for path, pages in embedded.items() if not (repo.root / path).exists()}
    against = f"against {repo.base_name}" if repo.base else "(no commits yet)"
    run_line = notes.get("runLine", f"{changed_count} of {len(frames)} frames changed {against}")
    base_label = f"{repo.base_name} {repo.base[:7]}" if repo.base else "no commits yet"
    sources = {x["source"] for f in frames for x in f["files"]}
    undo = []
    if "git" in sources:
        undo.append(f"Every committed version is in git at {html.escape(repo.base_name)}; " + ("a tracked file reverts with <code>git checkout -- &lt;path&gt;</code>" if repo.base_name == "HEAD" else f"one comes back with <code>git checkout {html.escape(repo.base_name)} -- &lt;path&gt;</code>"))
    if "originals" in sources:
        undo.append(f"The saved originals of files git never had are in <code>{html.escape(repo.rel(originals))}/</code>")
    default_lede = ["<b>What this check can and cannot prove.</b> It reads text, so it can prove a shot stale and never prove one current, which is why every frame is shown."]
    if undo:
        default_lede.append("<b>Reversible.</b> " + ". ".join(undo) + ".")
    lede = "".join(f"<p>{p}</p>" for p in notes.get("lede", default_lede))
    dangling_note = "".join(f'<p class="proof"><b>DANGLING.</b> {html.escape(", ".join(sorted(pages)))} cite{"s" if len(pages) == 1 else ""} <code>{html.escape(path)}</code>, which is missing: a broken image on the published site.</p>\n  ' for path, pages in sorted(gone.items()))
    sections = [f'''<section id="intro" class="on">
  <h1>Documentation screenshots — {html.escape(repo.root.name)}</h1>
  <p class="meta">{date} · {html.escape(base_label)} · {html.escape(run_line)}</p>
  <div class="lede">{lede}</div>
  {dangling_note}<table><tr><th>#</th><th>Frame</th><th>Before → after</th><th>Verdict</th></tr>{rows}</table>
  <p class="meta">← / → step through · "All frames" reads straight down · the theme button tests the borders</p>
</section>''']
    for i, f in enumerate(frames, 1):
        e, fid, note = f["entry"], f["entry"]["id"], f["note"]
        badge = "on" if f["dot"] in ("recaptured", "new", "border") else "off"
        fresh = ' <span class="badge fresh">updated this pass</span>' if fid in marked else ""
        body = [f'<h2>{i}. {html.escape(fid)} <span class="badge {badge}">{html.escape(verdict(f))}</span>{fresh}</h2>']
        if e.get("shows"):
            body.append(f'<p class="proof"><b>Shows.</b> {html.escape(e["shows"])}</p>')
        missing = {repo.rel(shots / x["name"]) for x in f["files"] if x["kind"] == "orphan"} | {repo.rel(shots / n) for n in f["dropped"]}
        dangling = sorted({p for m in missing if m in gone for p in gone[m]})
        body.append(f'<p class="proof"><b>Embedded in.</b> {html.escape(", ".join(f["pages"]) or "no page")}'
                    + (f' — <b>DANGLING</b> in {html.escape(", ".join(dangling))}: the page cites a file that is missing' if dangling else "") + '</p>')
        if "standard" in note:
            standard = note["standard"]
        elif f["orphan"] or e.get("unregistered") or "NOT CHECKED" in verdict(f):
            standard = ""
        else:
            standard = "its claim, not its literals (impressionistic)" if e.get("precision") == "impressionistic" else "its literals"
        if standard:
            body.append(f'<p class="proof"><b>Judged by.</b> {html.escape(standard)}</p>')
        if note.get("proof"):
            body += [f'<p class="proof">{p}</p>' for p in note["proof"]]
        else:
            what = ("File missing; whether it was dropped on purpose is not recorded." if f["orphan"]
                    else "Left alone; the reason is not recorded." if f["dot"] == "alone" else "No staleness proof recorded.")
            body.append(f'<p class="proof"><b>{what}</b></p>')
            print(f"contact-sheet: frame {i} ({fid}) has no proof in the notes", file=sys.stderr)
        capture = e.get("capture", {})
        if capture.get("command") or capture.get("steps"):
            body.append('<p class="proof"><b>How it is captured.</b>' + (f' <code>{html.escape(capture["command"])}</code>' if capture.get("command") else "") + '</p>')
            if capture.get("steps"):
                body.append('<ol class="proof">' + "".join(f"<li>{html.escape(s)}</li>" for s in capture["steps"]) + '</ol>')
        if note.get("needs"):
            body.append(f'<p class="proof"><b>What a re-capture needs.</b> {note["needs"]}</p>')
        elif not (capture.get("command") or capture.get("steps")):
            body.append('<p class="proof"><b>What a re-capture would need is not recorded.</b></p>')
            print(f"contact-sheet: frame {i} ({fid}) records no way to re-capture it", file=sys.stderr)
        for n in f["dropped"]:
            body.append(f'<p class="meta">{html.escape(n)} · dropped from this entry since {html.escape(repo.base_name)}' + (" · still on disk" if (shots / n).exists() else " · deleted") + '</p>')
        for x in f["files"]:
            parts = [html.escape(x["name"]), html.escape(summary(x))]
            if len(x["stages"]) > 1:
                parts.append(" → ".join(f"{html.escape(l)} {im.width} × {im.height}" for l, _, im in x["stages"]))
            if len(f["files"]) > 1 and x["kind"] in ("recaptured", "border"):
                parts.append(html.escape(VERDICTS[x["kind"]]))
            if x["framing"]:
                parts.append(x["framing"])
            if len(f["files"]) > 1 and x["name"] in marked_files:
                parts.append("updated this pass")
            body.append('<p class="meta">' + " · ".join(parts) + '</p>')
            if not x["stages"]:
                continue
            cls = lambda c: f' class="{c}"' if c else ""
            body.append('<p class="proof">All four corners at 6× nearest-neighbour, laid out as they sit in the frame.</p>')
            body.append('<div class="pair">' + "".join(f'<figure{cls(c)}><figcaption>{html.escape(l)}, four corners at 6×</figcaption><img class="px" src="data:image/png;base64,{corners(im)}"></figure>' for l, c, im in x["stages"]) + '</div>')
            body += [f'<figure{cls(c)}><figcaption>{html.escape(l)}</figcaption><img src="data:image/png;base64,{b64(im)}"></figure>' for l, c, im in x["stages"]]
        sections.append(f'<section id="s{i}">\n  ' + "\n  ".join(body) + '\n</section>')
    for i, g in enumerate(gaps, 1):
        body = [f'<h2>G{i}. {html.escape(gap_label(g))} <span class="badge off">{gap_status(g)}</span></h2>']
        body += [f'<p class="proof"><b>{label}.</b> {html.escape(g[k])}</p>' for k, label in (("shows", "Would show"), ("why", "Why the prose is not enough")) if g.get(k)]
        if g.get("needs"):
            body.append(f'<p class="proof"><b>What a capture needs.</b> {g["needs"]}</p>')
        elif not g.get("frame"):
            body.append('<p class="proof"><b>What a capture would need is not recorded.</b></p>')
            print(f"contact-sheet: gap G{i} records no way to capture it", file=sys.stderr)
        sections.append(f'<section id="g{i}">\n  ' + "\n  ".join(body) + '\n</section>')

    page = style + "\n".join(nav) + "\n\n<main>\n\n" + "\n\n".join(sections) + "\n\n</main>\n\n" + script
    missing_ids = [x for x in re.findall(r"getElementById\('([^']+)'\)", script) if f'id="{x}"' not in page]
    if missing_ids:
        raise SystemExit(f"contact-sheet: the template's script looks up {', '.join(missing_ids)}, which the page lacks; nothing was written")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8", newline="\n")
    sidecar.write_text(json.dumps({"hashes": hashes, "marked": sorted(marked_files)}, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(out.as_uri())
    print(f"{len(frames)} frames ({len(unregistered)} unregistered), {changed_count} changed {against}, {len(marked)} marked as updated, {len(gaps)} gaps", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
