# Memory index

- [Project memory versioning](project-memory-versioning.md) — project memory is version-controlled via a per-project symlink into the repo; why that won over centralized/sync/global alternatives
- [Telegram notification dismissal gaps](project_telegram_dismissal_gaps.md) — UserPromptSubmit-only dismissal misses approvals, cross-project, and manual argv-path notifications
- [Essential-traffic mode hides gated commands](essential-traffic-hides-gated-commands.md) — the disable-nonessential-traffic flag stays by choice; gated slash commands read as "Unknown command", don't re-offer removing it
- [Memory index is one source, generated](memory-index-single-source.md) — CLAUDE.md's list is rendered from MEMORY.md's `{always}` entries; why `@`-import and a drift checker were rejected
- [Adoption is prose, not scripts](adoption-prose-over-scripts.md) — the three facts that let a source-destroying migration drop its scripted per-item assertion, and the incident that argued against it
- [v1's assertion is directory-blind](v1-assertion-is-directory-blind.md) — it checks a checklist line reached some file, not which of `memos/` and `done/`; an open item filed as addressed passes
- [Untracked checklists block the split](untracked-checklists-block-the-split.md) — two repos hold an uncommitted `.claude/memos.md`; commit it before `/adopt` runs there or v1 destroys every marker
- [Effort changes dirty this repo](effort-changes-dirty-this-repo.md) — `/effort` writes through the settings.json symlink into the tree; press `s` for session-only, and two effort keys can disagree
