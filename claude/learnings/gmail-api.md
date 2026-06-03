# Gmail API — labels, IDs, and read-vs-write

Practical knowledge for any Gmail integration (extension, script, server). Not derivable from a repo — it's how the API itself behaves.

## Label identity

- **System labels** have fixed, account-independent IDs that are identical across every account and (mostly) equal to the name: `INBOX`, `SENT`, `DRAFT`, `SPAM`, `TRASH`, `UNREAD`, `STARRED`, `IMPORTANT`, `CHAT`, and the category labels `CATEGORY_PERSONAL` / `CATEGORY_SOCIAL` / `CATEGORY_PROMOTIONS` / `CATEGORY_UPDATES` / `CATEGORY_FORUMS`. These you can safely hardcode.
- **User-created labels** get an **opaque, server-assigned ID** at creation time, e.g. `Label_5705790327954958474`. That ID:
  - is **not derivable from the name** — it's an arbitrary token, not a hash or transform;
  - is **stable across renames** — renaming a label changes its `name` but keeps its `id` (the id is the durable identity);
  - **changes on delete + recreate** — a new label with the same name gets a fresh id;
  - is **per-account** — the same label name has a different id in a different account, including `/u/0` vs `/u/1` of the same user.
- Consequence: you **cannot ship hardcoded ids for user labels** in a multi-account / multi-user app. The name↔id mapping lives server-side; discover it via `users.labels.list` and match on `name`.

## Read by name, write by ID

- **Reading / filtering** can use the **name** via the search query syntax: `q=label:remind`, `q=label:"ads/deal"`. No id needed — Gmail resolves the name server-side and tolerates a non-existent label (empty result).
- **Writing** (`users.messages.batchModify` / `messages.modify` with `addLabelIds` / `removeLabelIds`) accepts **only label IDs** — there is no name-based variant. Examples: archive = remove `INBOX`; "remove pending" = remove the resolved `pending` label id; trash = `users.messages.trash` (or add the `TRASH` system id).
- So any feature **configured by label name but performing writes** must resolve name→id at least once (a `labels.list` fetch). You can't avoid fetching the label list somewhere.

## Design implication

- Resolve names→ids **where the label list already lives** (e.g. the background service worker / cache layer that already fetched `labels.list`), not in every UI consumer. Benefits:
  - consumers don't depend on the label list being **pushed** to them (removes a class of "stuck waiting for labels" bugs);
  - resolution stays **always-fresh** against the live list — no persisted id to go stale when a label is deleted+recreated, and no invalidation logic to maintain.
- If the cached value behind the id (e.g. a per-label message-index) is built asynchronously, gate the reply on that value being **ready**, not merely on the id resolving — see the "pull/deferred reply must wait for readiness" note in `chrome-extension.md`.
