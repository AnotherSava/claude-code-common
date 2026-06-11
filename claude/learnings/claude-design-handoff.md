# Claude Design handoff bundles → Claude Code implementation

Claude Design (claude.ai/design, an Anthropic Labs product, launched 2026-04-17, powered by Opus 4.7) is a collaborative visual-design tool: a user mocks up a site/app in HTML/CSS/JS, then exports a **handoff bundle** for a coding agent to implement for real. This is the workflow for consuming one.

## Fetching the bundle

The design export URL (e.g. `https://api.anthropic.com/v1/design/h/<id>?open_file=<file>`) returns a **gzip tarball**, not a web page. `WebFetch` can't parse it — it reports the content as binary — but it **saves the raw bytes to a `.bin` file** and prints the path. Extract:

```bash
cp <saved>.bin bundle.bin && tar xzf bundle.bin   # → <project>/ dir
```

On **Windows / Git Bash**, `tar` extracts under the bash `/tmp`, which the Read tool can't open by that path. Convert to a Windows path first:

```bash
cd <project> && cygpath -w "$(pwd)"   # → C:\Users\...\Temp\...  — pass THIS to Read
```

## Bundle structure

- `<project>/README.md` — **"CODING AGENTS: READ THIS FIRST."** Its instructions: read the chat transcripts first; read the user's open file in full and follow its imports; recreate the design **pixel-perfect in the target tech** (don't copy the prototype's internal structure); **do NOT render/screenshot** (read the source directly — everything is in the HTML/CSS); ask if anything is ambiguous.
- `<project>/chats/*.md` — the full design conversation. **Read these.** The *intent and the final decisions* live here, not just in the output files — e.g. a payment-model pivot, a "make it 5 steps not 4" change, a spelling rule, deliberately-abandoned alternates. The transcript explicitly flags decisions that "override the brief."
- `<project>/project/` — the prototype: an HTML entry that loads **React via Babel-in-browser** (plain function components hung on `window`, NOT a build/JSX-compile), **semantic BEM-ish CSS classes (NOT Tailwind)**, often a `CLAUDE.md` with project rules (spelling, tone, business model), plus `screenshots/` and `uploads/`.

## Port strategy that works

The prototype is plain React + semantic CSS. The fastest *and* most faithful port into a Next + Tailwind app:

1. **Bring the design's CSS in largely verbatim** as one or two global stylesheets, scoped under a single wrapper class (e.g. `.vpl`). Adapt only what must change — the font (→ a `next/font` CSS variable) — and prune clearly-dead rules (unused alt themes, candidate fonts, dropped features). Do **NOT** translate hundreds of lines of careful CSS into Tailwind utilities; it's error-prone and lossy.
2. **Recreate the JSX components as TSX** using the **same class names**. The prototype's `window`-global components become normal imports; `React.useState` etc. become hook imports; `Ico`→your `Icon`, hash-router `nav()`→`next/link` + `usePathname`.
3. **Wire live data and preserve existing behaviour.** The prototype's numbers (rates, catalogue) and any client-side "simulation" (e.g. a fake slicer/cost calc) are stand-ins — wire the real backend; never ship the invented figures. Where the design reskins a *working* feature, reskin it (swap presentation onto the existing state/handlers) — don't rewrite the logic.
4. **Keep the scoped wrapper** so the design system never bleeds into other parts of the app (e.g. an existing admin panel in a different style). A Next.js **route group** (`(site)/`) with its own layout is a clean home: it carries the wrapper + shared chrome and leaves sibling routes untouched.

## Gotchas

- Honour the bundle's `CLAUDE.md` rules across **all** ported copy (e.g. Canadian English spelling — `colour`, `analysing`), even where the user's own messages used other spellings.
- Run the design's accent through a **WCAG-AA contrast check**. Design tools happily ship muted-text tokens and "medium-fill" selected states below 4.5:1; fix interactive-text contrast, and flag pervasive muted-body-text contrast to the user rather than unilaterally restyling their approved palette.
- The design may introduce UI for features the backend lacks (a notes field, advanced options). Add the small real backing where it's the documented path; **omit non-functional controls** rather than ship fake UI.
- A multi-agent flow fits well: one **understand** pass (map the design source *and* the existing code's must-preserve contract in parallel), parallel **content-page builds** on a shared kit, then an **adversarial review** (behaviour-preservation, fidelity, backend correctness, a11y) before committing.
