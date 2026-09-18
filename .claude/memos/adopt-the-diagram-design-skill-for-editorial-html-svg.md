---
created: 2026-09-18 15:02:00
---

# Adopt the diagram-design skill for editorial HTML/SVG diagrams

Repo: https://github.com/cathrynlavery/diagram-design

What it is: a Claude Code skill that produces editorial-quality diagrams as self-contained HTML + SVG — no build step, no JavaScript, no external images. Ships architecture, flow, pyramid, Sankey, fishbone, Wardley map, kanban, user journey, deployment, dependency graph, UML class, story map and database schema layouts, each in minimal light, minimal dark and full-editorial variants. It can also redraw existing draw.io, Mermaid or Excalidraw sources at a chosen format, size and detail level, and it matches a brand by reading a website.

Why it is worth a look here: diagrams currently come from the claude-mermaid plugin, whose output is Mermaid. This produces static HTML and SVG instead, which is what the GitHub Pages docs sites in these projects actually want to embed.

Decisions to make when picking this up:
1. Vendor it as a global skill under claude/skills/diagram-design/, or install it as a plugin. Vendoring means it has to be added to the whitelist in .gitignore, to BOTH install blocks in README.md, and to LINKS in claude/hooks/check-install.py — the install-links test fails the commit gate when those disagree.
2. Decide what happens to claude-mermaid. Two diagram skills that overlap will be picked between at random unless one of them is retired or their triggers are made disjoint.
3. Check its license before vendoring.
