# Memory index

- [Project memory versioning](project-memory-versioning.md) — project memory is version-controlled via a per-project symlink into the repo; why that won over centralized/sync/global alternatives
- [Telegram notification dismissal gaps](project_telegram_dismissal_gaps.md) — UserPromptSubmit-only dismissal misses approvals, cross-project, and manual argv-path notifications
- [Essential-traffic mode hides gated commands](essential-traffic-hides-gated-commands.md) — the disable-nonessential-traffic flag stays by choice; gated slash commands read as "Unknown command", don't re-offer removing it
- [Memory index is one source, generated](memory-index-single-source.md) — CLAUDE.md's list is rendered from MEMORY.md's `{always}` entries; why `@`-import and a drift checker were rejected
- [Adoption is prose, not scripts](adoption-prose-over-scripts.md) — the three facts that let a source-destroying migration drop its scripted per-item assertion, and the incident that argued against it
- [v1's assertion is directory-blind](v1-assertion-is-directory-blind.md) — it checks a checklist line reached some file, not which of `memos/` and `done/`; an open item filed as addressed passes
- [Untracked checklists block the split](untracked-checklists-block-the-split.md) — two repos hold an uncommitted `.claude/memos.md`; commit it before `/adopt` runs there or v1 destroys every marker
- [Settings writes dirty this repo](settings-writes-dirty-this-repo.md) — any Claude Code settings write lands here through the symlink; the effort keys were removed 2026-10-09 and `ultracode` must not come back
- [Remote session diagnostics](remote-session-diagnostics.md) — "remote session" means the tmux feature, not Remote Control; the four read-only commands for its live state, and why an attach can work while the conversation is new
- [Docs stay text-only](docs-stay-text-only.md) — why there are no images here (2026-09-24); the instruction itself is in `CLAUDE.md`, where `/docs-relevance` reads it
- [v9 stock-take is inventory only](v9-stocktake-inventory-only.md) — nothing runs before the commit-gate question; running candidates was rejected 2026-09-26, don't re-propose it
- [Commit and wrap-up stay separate](commit-wrapup-stay-separate.md) — merging them was rejected 2026-09-30; they are already composed and the assumed overlap is absent
- [Port uniqueness is not a rule](port-uniqueness-not-a-rule.md) — it lives in this repo's gate because three port-claiming repos have no gate at all; v15 does the per-repo replacement instead
- [Registry prose audited against repos](registry-prose-audited-against-repos.md) — 2026-10-05: 29 claims read against their owning repos, numbers all held; a v15 adoption falsifies a note and nothing here reports it
- [Memo surfacing is session start only](memo-surfacing-session-start-only.md) — decided 2026-10-06; a count in place of the list and keeping the task-completion listing were both declined, don't re-propose either
