# Screenshot manifest

`docs/screenshots/screenshots.json` records what each documentation screenshot shows, and whether this
skill may replace it. One entry covers **one screenshot or a series** taken together from the same
screen; the policy and the capture recipe apply to every file in the entry.

It exists to remember a decision the pixels cannot carry: whether the user wants this image kept up to
date automatically, on approval, or never. Without it that question is re-asked every run.

## Schema

```json
{
  "screenshots": [
    {
      "id": "settings-window",
      "files": ["settings.png"],
      "shows": "Settings window, Notifications page",
      "policy": "confirm",
      "capture": {
        "command": "bash docs/screenshots/capture/settings-window.sh",
        "steps": [
          "Deploy the current build so the shot matches the working tree, not the installed release",
          "Tray icon > Settings... > Notifications page",
          "Capture the window rect, then crop away the title bar"
        ]
      }
    }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Stable kebab-case key, and the name of the capture script. Never reuse it for a different screen — the history of a decision is keyed to it. |
| `files` | yes | Paths **relative to the manifest's own directory**. More than one means a series captured together. |
| `shows` | yes | One line naming what is in the frame, specific enough to tell two shots of the same app apart. |
| `policy` | no | `auto`, `confirm` or `never`. **Absent means the user has not decided yet** — see below. |
| `precision` | no | `impressionistic` when the frame argues breadth rather than fact — a hero collage, a marquee. Absent means literal, the default. **The user's to give, like `policy`** — it lowers what future runs catch. See below. |
| `verifiedAt` | no | The commit this shot was last actually examined against. **Absent means never examined** — see below. |
| `capture` | only for `auto` / `confirm` | `command` is the reproducible way to produce the image; `steps` are the ordered instructions used to write that command the first time. A `never` entry needs neither. |

Keep it to these fields. When a run needs a fact the schema cannot hold, add the field then — with the
step that reads it — rather than reserving one in advance. Fields that were considered and left out,
so the same ground is not re-argued: `sources` (which files back the shot) and `thirdPartyUi` (whether
absent text proves anything), both of which the staleness check currently derives for itself and would
only be worth storing once that derivation proves slow or wrong; `dimensions`, which `file <path>`
already reports from the image itself and which a stored copy can only drift from; a free-text
`notes`, which would absorb exactly the facts that ought to become fields; and a `policySetBy`
companion recording whether a human chose the value, whose only job would have been to say which of
two meanings `policy` was carrying — the reason `policy` is optional instead.

## What each policy permits

- **absent** — the user has not decided. Behaves as `confirm`, and the run asks them to settle it.
- **`never`** — put the staleness on the contact sheet and stop. The user takes the picture; this skill only files it.
- **`confirm`** — propose on the contact sheet, saying what changed and what a replacement would show. On approval, capture and replace.
- **`auto`** — capture and replace without asking, then show the swap on the contact sheet and say why.

Absence is the whole record of "not yet answered" — there is no fourth enum value and no companion
flag saying whether a human chose the value. A present `policy` is a decision; an absent one is the
lack of one, which is a null check rather than a sentinel hiding inside the enum. It is also why
undecided is safe to leave lying around: `confirm` cannot act without approval, so an unanswered entry
never captures anything on its own.

`policy` governs replacement only. Detection — proving a shot stale — runs for every entry regardless,
including `never`.

## What `precision` is for

Literal matching — every visible string still in source, every enumerated set shown in full — is the
right standard for a frame documenting a screen. It is the wrong one for a frame documenting *scope*.
A hero collage exists to say "this covers a lot, across several products"; it is angled, overlapping
and partly occluded on purpose, and nobody reads a toggle out of it. Held to literal matching it goes
stale on almost every release, and a verdict that fires every time is one the reader learns to skip —
which costs the frames where staleness actually matters.

`"precision": "impressionistic"` changes the standard, not the coverage. The frame is still opened,
still swept, still given a `verifiedAt`. What changes is what counts as stale: the claim it makes, not
the literals inside it. A collage advertising four games goes stale when one is dropped, or when a
whole surface it ought to show is missing — not when a control in one of its panels gains an option.
Say on the contact sheet which standard a frame was judged by, so a reader can disagree with the
standard rather than only with the verdict.

Like `policy`, this key is the user's to give and absent by default. It widens what a future run will
let through, so it is not a judgement to make on their behalf — a frame that merely *looks* decorative
may still be one they read for detail.

## What `verifiedAt` is for

Staleness detection is normally scoped to shots the current diff implicates, which bounds the work but
has one hole: a shot that went stale in an *earlier* commit is never revisited, because its backing
source is not in today's diff. It stays wrong indefinitely, and the prose beside it keeps reading true.

So the scoping applies only to shots that have been examined at least once. An entry with **no
`verifiedAt`** is opened and checked whatever the diff says; one that has it falls back under the
normal rule. Write the current commit's short sha after examining a shot — whether or not it turned
out stale, since "checked and fine" is exactly the fact worth not re-deriving.

Only its presence is read today. The value is there for a human reading the file, and because a later
version that also records which sources back a shot could ask the sharper question — *have those
files changed since this sha* — without another schema change.

`auto` skips the question, not the evidence: a replacement made under it is still shown before and
after on the contact sheet, still reversible from the copy taken before overwriting, and still settled
by the user one screenshot at a time. The difference between `auto` and `confirm` is when they are
asked, not whether.

## Keeping it current

The manifest is written by this skill, not only read by it:

- A screenshot with no entry, or an entry with no `policy`, is **undecided**: ask the user which policy
  it should have and write their answer into `policy`. When the question cannot be asked, write the
  entry without a `policy` and say so in the report, so the next interactive run asks.
- An entry whose files have all vanished is **orphaned metadata**: report it, and remove it only after
  the user confirms the image was deliberately dropped.
- A renamed image is a `files` fix on the existing entry, not a new registration — the policy decision
  survives the rename.
- Entries are ordered as the images appear in the documentation, so a reviewer can follow both in one
  pass.

## The contact sheet

The sheet is how this check talks to the user about pictures. Any run with something visual to settle
writes a single HTML page and links it — a stale frame, a proposed replacement, a verdict that wants a
second pair of eyes. Images scattered through a transcript are not a substitute: they arrive in
whatever order they were read, separated by tool output, and for a run touching three shots the reader
is left flipping between six pictures trying to remember which pair was which.

**It usually comes before the change, not after.** Under `confirm`, `never`, and an absent policy the
sheet *is* the proposal, so it is written before any capture — "what changed and what the replacement
would show" is a claim about pictures, and prose cannot put a picture in front of the person deciding.
Only `auto` writes it afterwards, as evidence of a swap already made. Skip it when the run turned up
nothing to settle — no stale frame, no orphan, no undecided policy, nothing replaced — and say that
you skipped it. It is named for the photographer's contact sheet, every frame laid out together so the
person who has to choose can see them side by side; calling it a *report* invited writing it only once
the work was already done.

Write it outside the repo — `$TEMP/screenshot-contact-sheet-<date>.html` — so it never joins the change
set, and reference every image by an absolute `file:///` URL so the committed file, a saved original
and a new capture all resolve. Give the user the page itself as a `file:///` URL too, on its own line
and nothing else on it: a Windows path with backslashes is not clickable, and the point of the page is
that it opens.

**Show every screenshot, not only the ones in question** — anything replaced as a before/after pair,
and every other one as the picture that is currently committed. A verdict of "unchanged" or "not
implicated" is a claim about an image, and a page that argues it in prose while showing the picture
only for the ones that changed asks the reader to take the quiet ones on trust. It is also where a
wrong verdict gets caught: this check reads text, so it cannot see layout, a cropped edge or a control
that moved, and putting the picture in front of the one person who can recognise those is most of what
the page is for.

**Number every frame, and put them one click apart.** Numbers follow manifest order and are used in the
chat write-up as well, so a reply can say "re-shoot 2 and 6" instead of describing two pictures in
prose. Coverage gaps — features documented with no screenshot at all — are numbered too, in their own
`G1, G2, …` series, so "do G1, drop G4" cannot be mistaken for a frame number. The numbered entries sit in a fixed list down the left, outside the content column, and clicking
one switches to that frame — showing a dozen screenshots on a page the reader can only scroll means
being told about number 6 and then hunting for it. **All frames** stays available for reading straight
down, because the argument for showing every frame is that they get compared. Colour each list entry by
its verdict so the shape of the run is legible before anything is clicked.

Every frame awaiting a decision carries **what a re-capture would need** — the session, the app state,
the preconditions — beside the case for making it. The user is being asked to spend effort, not merely
to agree, so the cost and the reason belong in the same place. Where several frames need the same
setup, group them: "one four-player table with a void detected" covers two shots and is one errand,
not two.

The page is **read-only**. It states the case; it does not collect the decision. After linking it, ask
per screenshot — before a capture, which frames to shoot; after one, keep, revert or re-capture — one
question covering all of them, in the same shape as the policy question.

```html
<!doctype html>
<meta charset="utf-8">
<title>Documentation screenshots — DATE</title>
<style>
 body{font:14px/1.5 system-ui,sans-serif;margin:0;color:#1a1a1a;display:flex;align-items:flex-start}
 nav{position:sticky;top:0;flex:0 0 240px;height:100vh;overflow:auto;box-sizing:border-box;
     background:#f7f7f8;border-right:1px solid #e0e0e0;padding:1.1rem .6rem}
 nav a{display:flex;gap:.5rem;align-items:baseline;padding:.4rem .55rem;border-radius:4px;
       color:#333;text-decoration:none;font-size:13px}
 nav a:hover{background:#ececf0} nav a.on{background:#dde7f5;font-weight:600}
 nav .n{color:#999;font-variant-numeric:tabular-nums;min-width:1.3em;text-align:right}
 nav a.on .n{color:#555}
 nav .dot{width:8px;height:8px;border-radius:50%;flex:0 0 8px;align-self:center}
 nav hr{border:0;border-top:1px solid #e0e0e0;margin:.55rem .4rem}
 main{flex:1;min-width:0;padding:1.8rem 2.4rem;max-width:1200px}
 section{display:none} section.on{display:block} body.all section{display:block}
 h1{font-size:1.5rem;margin:0 0 .3rem}
 h2{margin:0 0 .25rem;font-size:1.15rem} body.all h2{margin-top:2.6rem}
 .badge{font:600 11px/1 system-ui;padding:.3em .6em;border-radius:3px;vertical-align:middle;margin-left:.5rem}
 .stale{background:#b42318;color:#fff} .replaced{background:#0b6bcb;color:#fff}
 .unchanged{background:#e6e6e6;color:#444}
 .skipped{background:#f4f4f4;color:#777;border:1px solid #ddd}
 .meta{color:#777;font-size:12px;font-family:ui-monospace,Consolas,monospace;margin:.1rem 0 .7rem}
 .proof{color:#555;margin:.35rem 0 .5rem}
 .pre{background:#fbfaf7;border-left:3px solid #d9a441;padding:.6rem .9rem;margin:.6rem 0 1rem;color:#4a4a4a}
 .pair{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}
 .pair figure{margin:0}
 figcaption{font:600 12px system-ui;color:#666;margin-bottom:.4rem}
 figure{margin:0 0 1rem} img{max-width:100%;border:1px solid #ddd;background:#fff}
</style>

<nav>
  <a href="#all"><span class="n"></span>All frames</a>
  <hr>
  <a href="#s1"><span class="n">1</span><span class="dot" style="background:#b42318"></span>ID</a>
  <a href="#s2"><span class="n">2</span><span class="dot" style="background:#0b6bcb"></span>ID</a>
  <a href="#s3"><span class="n">3</span><span class="dot" style="background:#c9c9c9"></span>ID</a>
</nav>

<main>
<section id="intro" class="on">
  <h1>Documentation screenshots — DATE</h1>
  <p>REACH SENTENCE — which directories were scanned, which images were opened, and that this
  check reads text so it can prove a shot stale and never prove one current.</p>
</section>

<section id="s1">
  <h2>1. ID <span class="badge stale">stale — awaiting your call (POLICY)</span></h2>
  <p class="meta">file.png · WxH · where it is embedded</p>
  <p class="proof">PROOF — the literal that vanished and the commit, or the set shown only in part.
  For an <code>impressionistic</code> frame, say so and judge the claim instead.</p>
  <p class="pre">TO RE-CAPTURE — the session, app state and preconditions this shot needs.</p>
  <figure><figcaption>Current — WxH</figcaption><img src="file:///ABS/PATH/current.png"></figure>
</section>

<section id="s2">
  <h2>2. ID <span class="badge replaced">replaced (POLICY)</span></h2>
  <p class="meta">file.png · WxH · where it is embedded</p>
  <p class="proof">PROOF — what changed and why this replacement was made.</p>
  <div class="pair">
    <figure><figcaption>Before — WxH</figcaption><img src="file:///ABS/PATH/original.png"></figure>
    <figure><figcaption>After — WxH</figcaption><img src="file:///ABS/PATH/new.png"></figure>
  </div>
</section>

<section id="s3">
  <h2>3. ID <span class="badge unchanged">not disproven</span></h2>
  <p class="meta">file.png · WxH · where it is embedded</p>
  <p class="proof">Why nothing was disproven — or, for a skipped frame, which backing sources are
  absent from the diff.</p>
  <figure><figcaption>Current — WxH</figcaption><img src="file:///ABS/PATH/current.png"></figure>
</section>
</main>

<script>
function show(hash){
  var id = (hash || '').replace(/^#/, '') || 'intro';
  var all = id === 'all';
  document.body.classList.toggle('all', all);
  document.querySelectorAll('section').forEach(function(s){
    s.classList.toggle('on', !all && s.id === id);
  });
  document.querySelectorAll('nav a').forEach(function(a){
    a.classList.toggle('on', a.getAttribute('href') === '#' + id);
  });
  if (!all) scrollTo(0, 0);
}
addEventListener('hashchange', function(){ show(location.hash) });
addEventListener('keydown', function(e){          // left/right only — up/down stay as scroll
  if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
  var links = [].slice.call(document.querySelectorAll('nav a'));
  var i = links.findIndex(function(a){ return a.classList.contains('on') });
  if (i < 0) return;
  e.preventDefault();
  location.hash = links[(i + (e.key === 'ArrowRight' ? 1 : -1) + links.length) % links.length]
    .getAttribute('href');
});
show(location.hash);
</script>
```

One frame at a time is the default, so a figure gets the full content column and is sized for reading.
In **All frames** the pairs fall into their two-column grid and solo figures sit beside them at the
same scale, so the eye compares like with like down the page. Do not reintroduce a global
half-width rule for solo figures: a sheet written *before* any capture usually carries no pairs at
all, and then there is no grid to match — every frame would shrink to half width for nothing.

The list is the only navigation, so it must be complete: one entry per manifest entry, in the same
order, plus **All frames** at the top. A frame reachable only by scrolling in the All view is a frame
the user was told about by number and then has to hunt for.

## Where the file goes when there is no `docs/screenshots/`

If the project keeps its images somewhere else, the manifest sits in the directory that holds them,
still named `screenshots.json`. Do not create a second one; a repo has exactly one manifest.
