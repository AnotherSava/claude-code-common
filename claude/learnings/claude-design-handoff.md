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

## Post-adoption consistency audit

A bulk port lands as one big commit and *always* leaves drift behind — the "prune dead rules" and "`nav()`→`Link`" steps are never applied exhaustively. After the dust settles, sweep these categories (a read-only fan-out finds them; fix in one pass, then `tsc`/lint/test/build):

- **Orphan CSS** — selectors in the ported stylesheet that no `className` references. The inverse also bites: a class used in markup with no rule, i.e. a silently-unstyled element.
- **Duplicated literal constants** — a fallback colour / magic value declared in several files (and inlined raw in others); hoist to one shared export.
- **Internal-link mechanism split** — the hash-router→`next/link` conversion gets applied to nav but missed on in-prose body links, leaving a mix of `<a href="/…">` (full reload) and `<Link>`. Standardize; keep `<a>` only for external / `mailto:` / `tel:`.
- **Inline SVGs duplicating the icon kit** — copy-pasted glyph paths (e.g. the same chevron in two files) instead of the shared `Icon`. Add the glyph once and reuse; preserve any class the CSS animates (e.g. a rotation hook), and note the icon component's `viewBox` may differ from the inline SVG's (rewrite the path to its grid).
- **Hand-styled elements bypassing the kit** — a raw `<button className="btn btn--…">` instead of `<Button>`; the generated class is identical, so the swap is safe.
- **Inline styles bypassing tokens** — repeated magic font-sizes/colours in `style={{}}`; promote shared ones to a design-system class (a BEM modifier like `card--msg`, or a text utility like `fineprint`) and keep only genuinely positional one-offs inline.
- **Missing aria on custom controls** — `aria-current="page"` on active nav, `aria-expanded` on disclosure toggles; the port styles the active/open *state* (a class) but forgets the semantics.

Deliberate non-drift — verify before "fixing": an unused-but-typed component variant (e.g. `btn--quiet` backing `variant="quiet"`) is API surface, not dead code; a stylistically-distinct bespoke SVG (a filled map-marker vs the stroked icon) is intentional, not a duplicate.

## Reconciling against the prototype later (when a user flags a mismatch)

When a user comes back with "this differs from the design," the **handoff bundle's CSS/code is the source of truth — not a screenshot**, even one the user provides:

- A **screenshot captures only the resting state.** Interaction-dependent states are invisible in it: a field's *dimmed-while-default* look, a *reset-to-default* affordance that appears only once detached, a *paler active-fill* on inheriting controls. Inferring "what the design does" from a static image will miss these and cost extra correction rounds — open the bundle and read the rules.
- **Orphaned CSS classes are positive fingerprints of dropped details.** A selector the port never references (e.g. a `.seg--dim` opacity rule with no `className` using it) usually means a real design state got pruned during the bulk port. Grep the ported stylesheet for unused classes and ask whether each was intentional.
- **Your own "I changed X" code comments are the other fingerprint.** A note like `/* darkened from the design's medium blue to the accent token for WCAG AA */` records exactly where the port diverged from the prototype — when the user later wants prototype parity, those comments point straight at what to revert (and why it was changed, so you can restore fidelity *and* keep AA, e.g. a paler-but-still-≥4.5:1 token rather than reusing the primary accent).
- **Distinguish "displays differently" from "behaves differently."** A divergence can be visual (a missing badge), behavioural (explicit apply-to-all vs silent per-field inheritance), or both — name which, and confirm the direction with the user before rewriting interaction, since the original divergence may have been a documented deliberate adaptation.
