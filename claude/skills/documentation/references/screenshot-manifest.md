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
| `capture` | `command` only for `auto` / `confirm` | `command` is the reproducible way to produce the image; `steps` are the ordered instructions used to write that command the first time. A `never` entry has no `command` — nothing here may run one — but `steps` are worth keeping there, since on a `never` entry they are the setup handed to the person who takes the picture. |

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

Write it outside the repo — `$TEMP/screenshot-contact-sheet-<repo>-<date>.html` — so it never joins the
change set, and reference every image by an absolute `file:///` URL so the committed file, a saved
original and a new capture all resolve. **The repo name is not decoration:** `$TEMP` is shared by every
project on the machine, so a date-only name is a generic name in someone else's namespace. Two repos
running this skill on the same day silently overwrite each other's sheet, and the link handed over in
chat then opens another project's run — which has happened. Put the saved originals under a
correspondingly scoped directory for the same reason. Give the user the page itself as a `file:///` URL too, on its own line
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

`contact-sheet.html` beside this file is the working template — copy it, fill the marked slots, and
open it in a browser before handing it over. Four of its parts are not decoration:

**A theme toggle in the nav, always visible.** Screenshots are judged against a page, and a
documentation site can be light or dark. A per-image border claims to hold on both; a sheet rendered
in one of them tests nothing, and neither can the reader. Put the button at the top of the sticky
column so it stays reachable while stepping through frames, and persist the choice in `localStorage`
so a reload does not silently revert what was being examined.

**Four corner crops at 6× nearest-neighbour, before and after.** A one-pixel change — a hairline
added, a stray line cropped away — is invisible at page scale, so a sheet showing only full images
asserts a difference the reader cannot see. Crop all four corners, not one: a bad crop can sit on any
edge, and sampling the top-left and generalising is how one survives review. Lay them out as they sit
in the frame, separated by a **transparent** gutter, so the page shows through and the separator
follows the theme instead of needing a colour invented for it.

```python
BOX, ZOOM, GAP = 40, 6, 14
im = Image.open(src).convert("RGB"); w, h = im.size
b = min(BOX, w // 2, h // 2); side = b * ZOOM
crops = [im.crop((0,0,b,b)), im.crop((w-b,0,w,b)), im.crop((0,h-b,b,h)), im.crop((w-b,h-b,w,h))]
sheet = Image.new("RGBA", (side*2+GAP, side*2+GAP), (0,0,0,0))
for k, c in enumerate(crops):
    sheet.paste(c.resize((side,side), Image.NEAREST).convert("RGBA"),
                ((k%2)*(side+GAP), (k//2)*(side+GAP)))
```

**Panel switching over scrolling**, with a numbered spine and a verdict-coloured dot per entry, so the
shape of the run reads before anything is clicked and "re-shoot 2 and 6" lands somewhere. Keep an
**All frames** view for reading straight down, and bind ← / → to step the list.

**Carry two time scales, and keep them distinct.** The spine's dot says what happened to a frame
across the whole session — added, re-captured, or touched only in passing; the last-pass marking says
what moved since the reader last looked. They answer different questions ("what is the shape of this
work" against "what do I need to re-check now"), and collapsing them into one signal loses whichever
the reader needed. Give the dot a legend. **Watch for it going uniform:** a dot whose every frame ends
up the same colour has stopped carrying information — in one run it meant "bordered" and every frame
became bordered, at which point it was decoration — and should be repurposed to whatever distinction
is now live.

**Mark what changed since the reader last looked.** A sheet is regenerated repeatedly inside one
session — a crop here, a colour fixed there — and by the third pass the reader cannot tell which
frames moved, so they either re-examine all of them or trust that the summary named them all. Keep a
sidecar of per-image content hashes beside the sheet, diff against it on each write, and mark the
differing frames in the spine and with a badge. Hashes rather than mtimes: an mtime is the checkout
time and identical across the tree, which is the same reason it proves nothing about staleness. Allow
an explicit override (`--changed=a,b`) for the first run, when the sidecar has no baseline yet.

**Make the marks sticky.** A sheet is regenerated for its own reasons too — a CSS fix, a caption reworded, a view corrected — and on those writes no image has moved, so a naive diff clears every mark before the reader has looked. Store the marked set alongside the hashes and carry it forward on any write where nothing moved; only a write that actually changes an image replaces it.

**Scoped badge classes.** `.on` is already the section-visible and nav-active class, so a badge
written as a bare `.on { background: … }` paints every visible *section* that colour. This shipped
through several revisions of a real sheet before anyone saw it, because the sheet was being validated
by grepping the HTML for dangling image paths and never opened. Write `.badge.on` / `.badge.off`, and
open the finished page in a browser — the one check that would have caught it.

## Where the file goes when there is no `docs/screenshots/`

If the project keeps its images somewhere else, the manifest sits in the directory that holds them,
still named `screenshots.json`. Do not create a second one; a repo has exactly one manifest.
