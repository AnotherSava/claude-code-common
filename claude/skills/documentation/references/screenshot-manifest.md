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
- **`never`** — report staleness and stop. The user takes the picture; this skill only files it.
- **`confirm`** — propose a replacement and say what changed. On approval, capture and replace.
- **`auto`** — capture and replace without asking, then report what was replaced and why.

Absence is the whole record of "not yet answered" — there is no fourth enum value and no companion
flag saying whether a human chose the value. A present `policy` is a decision; an absent one is the
lack of one, which is a null check rather than a sentinel hiding inside the enum. It is also why
undecided is safe to leave lying around: `confirm` cannot act without approval, so an unanswered entry
never captures anything on its own.

`policy` governs replacement only. Detection — proving a shot stale — runs for every entry regardless,
including `never`.

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
after, still reversible from the copy taken before overwriting, and still settled by the user one
screenshot at a time. The difference between `auto` and `confirm` is when they are asked, not whether.

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

## The run report

Any run that replaced at least one image writes a single HTML page and links it. Images scattered
through a transcript are not a report: they arrive in whatever order they were read, separated by tool
output, and for a run that replaced three shots the reader is left flipping between six pictures
trying to remember which pair was which.

Write it outside the repo — `$TEMP/screenshot-report-<date>.html` — so it never joins the change set,
and reference every image by an absolute `file:///` URL so both the saved original and the new file
resolve. Give the user the page itself as a `file:///` URL too, on its own line and nothing else on
it: a Windows path with backslashes is not clickable, and the point of the page is that it opens.

**Show every screenshot, not only the replaced ones** — replaced ones as a before/after pair, and
every other one as the picture that is currently committed. A verdict of "unchanged" or "not
implicated" is a claim about an image, and a report that argues it in prose while showing the picture
only for the ones that changed asks the reader to take the quiet ones on trust. It is also where a
wrong verdict gets caught: this check reads text, so it cannot see layout, a cropped edge or a control
that moved, and putting the picture in front of the one person who can recognise those is most of what
the page is for.

The page is **read-only**. It states what happened; it does not collect the decision. After linking
it, ask the user per screenshot whether to keep, revert or re-capture — one question covering all of
them, in the same shape as the policy question.

```html
<!doctype html>
<meta charset="utf-8">
<title>Documentation screenshots — DATE</title>
<style>
 body{font:14px/1.5 system-ui,sans-serif;margin:2rem auto;max-width:1400px;color:#1a1a1a}
 h2{margin:2.5rem 0 .25rem;font-size:1.15rem}
 .badge{font:600 11px/1 system-ui;padding:.3em .6em;border-radius:3px;vertical-align:middle;margin-left:.5rem}
 .replaced{background:#0b6bcb;color:#fff} .unchanged{background:#e6e6e6;color:#444}
 .skipped{background:#f4f4f4;color:#777;border:1px solid #ddd}
 .proof{color:#555;margin:.35rem 0 1rem}
 .pair{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}
 .pair figure{margin:0} .pair figcaption{font:600 12px system-ui;color:#666;margin-bottom:.4rem}
 .pair img{max-width:100%;border:1px solid #ddd}
</style>
<h1>Documentation screenshots — DATE</h1>
<p>REACH SENTENCE — which directories were scanned, which images were opened.</p>

<h2>ID <span class="badge replaced">replaced (POLICY)</span></h2>
<p class="proof">PROOF — the literal that vanished and the commit, or the set shown only in part.</p>
<div class="pair">
  <figure><figcaption>Before — WxH</figcaption><img src="file:///ABS/PATH/original.png"></figure>
  <figure><figcaption>After — WxH</figcaption><img src="file:///ABS/PATH/new.png"></figure>
</div>

<h2>ID <span class="badge unchanged">unchanged</span></h2>
<p class="proof">Why nothing was disproven.</p>
<figure class="solo"><figcaption>Current — WxH</figcaption><img src="file:///ABS/PATH/current.png"></figure>

<h2>ID <span class="badge skipped">not implicated</span></h2>
<p class="proof">Which backing sources are absent from the diff.</p>
<figure class="solo"><figcaption>Current — WxH</figcaption><img src="file:///ABS/PATH/current.png"></figure>
```

A solo figure is shown at the same scale as one half of a pair, so the eye compares like with like
down the page — `.solo{max-width:calc(50% - .75rem)}` against the pair's two-column grid.

## Where the file goes when there is no `docs/screenshots/`

If the project keeps its images somewhere else, the manifest sits in the directory that holds them,
still named `screenshots.json`. Do not create a second one; a repo has exactly one manifest.
