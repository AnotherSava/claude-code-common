---
name: github-pages
description: >-
  Arrange a project's README and GitHub Pages documentation into a consistent
  user-first layout: short README that links out, Jekyll site with a user-facing
  index, one page per user-facing feature, and exactly one developer page.
  TRIGGER when: setting up docs/ for a new project, adding a GitHub Pages site,
  writing or restructuring a README that will link to GH Pages, adding a new
  user-facing feature page, or asked to align docs with this project or
  bga-assistant.
  DO NOT TRIGGER when: editing unrelated docs outside docs/, working on a
  project that already has an incompatible docs framework (Docusaurus, MkDocs,
  VitePress, etc.).
---

# GitHub Pages Documentation Layout

Use this skill when organizing project-level documentation into a README plus a GitHub Pages Jekyll site. The goal is a consistent shape across repos: the README sells the project in under a screen, every user-facing capability has its own page written from the user's perspective, and developers get exactly one entry-point page.

Reference implementations that already follow this layout:

- the chrome-assistant repo (monorepo variant, site-per-subfolder under `docs/pages/`)
- the BGA assistant repo (flat variant, one page per supported game)

Read their `README.md`, `docs/index.md`, `docs/_config.yml`, `docs/pages/development.md`, and a user-facing page (`docs/pages/gmail/index.md`, `docs/pages/innovation.md`) before writing new docs — copy their tone and shape.

## Core principles

1. **Single source of truth lives on GitHub Pages.** The README is an entry point, not a manual. If something takes more than a paragraph, it belongs on a page and the README links to it.
2. **User perspective by default.** Every page except `development.md` is written for someone using the thing, not building it. No build commands, no internal module names, no architecture diagrams — those go under `development`.
3. **Exactly one developer page.** `docs/pages/development.md`. Deeper technical docs (data flow, storage layout, API contracts) are linked *from* development, not elevated to top-level nav.
4. **Consistent navigation on every page.** Same top bar, same order, same horizontal rule below it.
5. **Screenshots live in `docs/screenshots/`** and are referenced from every page that needs them.

## File layout

Flat variant (single product, several user-facing capabilities):

```
README.md
docs/
  _config.yml
  index.md
  pages/
    <feature-a>.md        # user-facing
    <feature-b>.md        # user-facing
    development.md        # the one dev page
    privacy.md            # if the product handles user data
  screenshots/
    *.png
```

Monorepo variant (several products sharing one docs site):

```
README.md
docs/
  _config.yml
  index.md
  pages/
    <product-a>/
      index.md            # user-facing entry for product A
      privacy.md          # optional, product-specific
      <technical-subpage>.md  # linked only from development.md
    <product-b>/
      index.md
    development.md        # the one dev page (covers all products)
  screenshots/
    *.png
```

## README.md shape

Keep it short enough to read on one screen at normal zoom. Structure, in order:

1. H1 project title.
2. One-line italicized tagline *or* a short plain paragraph that names the problem the project solves.
3. Cover screenshot: `![Project](docs/screenshots/<cover>.png)`.
4. One section per user-facing feature / supported site / supported game:
   - Heading is a link to the GH Pages feature page: `## [Feature Name](https://<org>.github.io/<repo>/pages/<feature>)` (flat) or `.../pages/<product>` (monorepo).
   - One paragraph blurb lifted from the feature page's intro.
   - Optional inline screenshot.
5. Install line pointing to the Chrome Web Store / distribution channel.
6. Any beta / access / allowlist notice as a blockquote.
7. Footer pointer to full docs:

   ```markdown
   See full project documentation at **[<org>.github.io/<repo>](https://<org>.github.io/<repo>/)**:

   - [Installation and usage](https://<org>.github.io/<repo>/)
     - [<Feature A>](https://<org>.github.io/<repo>/pages/<feature-a>)
     - [<Feature B>](https://<org>.github.io/<repo>/pages/<feature-b>)
   - [Developer guide](https://<org>.github.io/<repo>/pages/development)
   ```

The README never contains setup, build, architecture, or API content. If you catch yourself writing any of that in the README, move it to `development.md` and leave a link.

## docs/_config.yml

Minimal Jekyll config, same across all projects in this family:

```yaml
title: <Project Name>
description: <same tagline used in README / index.md>
theme: jekyll-theme-hacker
baseurl: /<repo-name>
```

## docs/index.md shape

This is the GH Pages home. It mirrors the README but lives inside the site, so nav links are relative and content can be slightly longer.

```markdown
---
layout: default
title: <Project Name>
---

[Home](.) | [<Feature A>](pages/<feature-a>) | [<Feature B>](pages/<feature-b>) | [Development](pages/development) | [Privacy](pages/privacy)

---

*<Tagline — same as README.>*

<Short problem-framing paragraph, same spirit as README.>

## Install

[Install from Chrome Web Store](<url>)

<Optional beta blockquote.>

## <Feature A or supported site>

<User-facing blurb. Link the heading to `pages/<feature-a>` if the page exists as a separate file.>

![<Alt>](screenshots/<file>.png)

## <Feature B>

...

## Usage

1. <Step one.>
2. <Step two.>
3. <Step three.>

## Acknowledgments

<Only if third-party assets, libraries, or reference implementations need attribution.>
```

The top navigation line is the same on every page in the site — copy it verbatim. Order: Home → user-facing pages in the same order as the README → Development → Privacy. Nothing else goes in the top bar.

## docs/pages/<feature>.md shape (user-facing)

One page per user-facing capability. Always written for the user, never the developer.

```markdown
---
layout: default
title: <Feature Name>
---

[Home](..) | [<Feature A>](<feature-a>) | [<Feature B>](<feature-b>) | [Development](development) | [Privacy](privacy)

---

<One-paragraph intro linking to any external context (e.g. the game on BGG, the site being extended).>

### <Sub-capability 1>

<Explain what the user sees and can do. Screenshot below the paragraph.>

![<Alt>](../screenshots/<file>.png)

### <Sub-capability 2>

...

### Features

- **<Feature bullet>**: <one-line user-visible description>
- ...

### Standard features

<Bullet list of features shared across all pages in the project — live updates, keyboard shortcuts, persisted settings, per-page zoom, etc. Keep this identical across pages in the same project so users can tell which are product-wide vs. feature-specific.>
```

Rules for user-facing pages:

- Lead with visible behaviour, not internals. Never mention filenames, module names, or message protocols here.
- Every sub-capability gets a short paragraph and ideally a screenshot.
- Large screenshots use the clickable pattern: `<a href="../screenshots/foo.png"><img src="../screenshots/foo.png" alt="..." width="1000"></a>`.
- The bottom **Features** list is a feature-scoped enumeration; **Standard features** is the project-wide list and should be copy-identical across sibling pages.

## docs/pages/development.md shape (the one developer page)

Exactly one developer page per project. It's the entry point to all technical content. Structure:

```markdown
---
layout: default
title: Development
---

[Home](..) | [<Feature A>](<feature-a>) | [<Feature B>](<feature-b>) | [Development](development) | [Privacy](privacy)

---

## Setup

### Prerequisites

- <runtime versions>

### Install

<install commands in a code fence>

### Load from source / Install from source

<numbered steps for loading the extension / running the app from source>

## Commands

- `<cmd>` — <description>
- ...

## Architecture

<Short rationale — why the project is shaped the way it is. One or two paragraphs. No code.>

## Project structure

<Code fence with an annotated tree. Each leaf file gets a short comment describing its responsibility.>

### Path aliases / Tooling notes

<Anything non-obvious a contributor needs to know before editing.>

## Architecture reference

<Bulleted links to deeper technical sub-pages — data-flow, storage-layout, etc. These live under docs/pages/<product>/ in the monorepo variant, or as siblings in the flat variant.>

## Testing

<How to run tests and coverage.>
```

Rules for the developer page:

- Links to technical sub-pages go here, not in the top nav.
- If a sub-page is only interesting to developers (data flow, storage layout, internal APIs), it does **not** get a top-bar entry — it is reached only via "Architecture reference".
- Keep prose short. Bulleted lists and code fences beat paragraphs for setup / commands / structure.

## docs/pages/privacy.md (if applicable)

Required when the product reads, stores, or transmits user data. Follow the BGA Assistant shape: what is / isn't collected, how the extension works, a permissions table, contact. Link it from the top nav.

## Navigation conventions

- Top-bar format: `[Home](<up>) | [<Page A>](<a>) | [<Page B>](<b>) | [Development](<dev>) | [Privacy](<priv>)` followed by a blank line, `---`, blank line, then content.
- `Home` link target by depth:
  - From `docs/index.md` → `.`
  - From `docs/pages/<page>.md` → `..`
  - From `docs/pages/<product>/<page>.md` → `../..`
- Sibling page links are bare names (no `.md`, no leading `./`): `[Gmail](gmail)`, `[Development](development)`.
- Every page in a project has the **same** top bar — copy it verbatim when adding a page. If you add a new user-facing page, update the bar on every existing page in the same batch.

## Writing process

Follow these steps whenever creating or restructuring docs for a project that should follow this layout.

1. **Inventory.** List the user-facing capabilities. Each one becomes a `docs/pages/<feature>.md` (flat) or a `docs/pages/<product>/index.md` (monorepo). Confirm the list with the user before writing files — page count drives the whole nav bar.
2. **Fix the nav bar.** Write the exact top-bar string once and paste it into every page. Order: Home → inventory pages in user-priority order → Development → Privacy (if applicable).
3. **Write `_config.yml`.** Use the four-field template above. `baseurl` must match the GitHub repo name.
4. **Write `docs/index.md`.** Start from the tagline, add one subsection per inventory item, end with Usage. Keep it scannable.
5. **Write user-facing pages.** One sub-capability heading + paragraph + screenshot, repeat. End with the Features / Standard features bullet lists. Never mention code.
6. **Write `development.md`.** Setup → Commands → Architecture rationale → Project structure tree → Architecture reference → Testing. Link any technical sub-pages from "Architecture reference".
7. **Write `README.md` last.** Lift the tagline and per-feature blurbs from `index.md` and the user-facing pages. End with the links-to-docs block. Never paste setup or architecture into the README.
8. **Verify every link.** Walk every top-bar and README link and confirm the target file exists at the relative path you wrote. Broken links here are the most common failure.
9. **Verify cross-consistency.** Tagline in README, `index.md`, and `_config.yml description` should match. Top-bar string should be byte-identical across all pages. **Standard features** list should be copy-identical across sibling user-facing pages.

## Out of scope

- Do NOT add more than one developer-perspective page to the top nav — technical deep-dives go under "Architecture reference" on `development.md`.
- Do NOT invent new top-bar entries per page (Home / user-pages / Development / Privacy only).
- Do NOT write setup, build, or architecture content in `README.md` or user-facing pages.
- Do NOT migrate a project that already uses Docusaurus, MkDocs, VitePress, Astro Starlight, or similar — this skill is for the `jekyll-theme-hacker` + `docs/` on GH Pages setup only.
- Do NOT create CONTRIBUTING.md, CHANGELOG.md, or other root-level docs unless the user asks — they are not part of this layout.
