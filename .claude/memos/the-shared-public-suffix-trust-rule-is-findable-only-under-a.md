---
created: 2026-10-09 09:43:59
---

# The shared-public-suffix trust rule is findable only under a Next filename

A wildcard allowlist anchored at a shared public suffix trusts every tenant of that suffix, not just you. Measured 2026-10-09 against Next 16.3.1's isCsrfOriginAllowed: the pattern `**.ts.net` returns true for anything.tailxxxx.ts.net and laptop.tailf00d99.ts.net, so a page on a stranger's tailnet can read the dev bundles; `*.<own-tailnet>.ts.net` covers every machine on one tailnet and refuses a foreign one.

The general rule is written down only inside claude/learnings/nextjs16-prisma7-scaffold.md, whose filename advertises Next and Prisma. The learnings directory is indexed by filename alone, so the same mistake in a CORS allowlist, a cookie domain, an image remotePatterns entry, or any *.vercel.app / *.workers.dev / *.herokuapp.com pattern will not find it.

What makes this not a quick fix: a second learnings file restating the measurement is exactly the duplication claude/skills/skill/SKILL.md's 'Don't leave the detail in two places' section now warns against, and the memory frontmatter types (user/feedback/project/reference) fit a cross-cutting technical rule badly. Options worth weighing: a short global memory that states the rule and points at the learning for the evidence; a rename or a second topic-named file that is a pure pointer; or folding it into CLAUDE.md's 'Sharing a Host With Another Project' section, which today covers name collisions in a shared namespace but not trust across one.
