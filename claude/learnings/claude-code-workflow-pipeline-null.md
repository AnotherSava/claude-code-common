# Claude Code workflows: a null stage result ends the item's pipeline

In a Workflow script, `pipeline(items, stage1, stage2, …)` runs no later stage for an item whose stage returned `null`. The authoring reference says only that a stage which *throws* drops the item to `null` and skips the rest. It does not say a returned `null` does the same.

That matters because `agent()` reports a dead subagent with a returned `null`, not a throw: a terminal API error after its retries ("Connection lost while your computer was asleep"), and a call the user skipped. So this shape never sees the failure it checks for:

```js
await pipeline(
  lenses,
  lens => agent(reviewPrompt(lens), { schema: FINDINGS }),
  (review, lens) => {
    if (!review) { silent.push(lens.key); return [] }   // never reached for a dead reviewer
    return parallel(review.findings.map(verify))
  },
)
```

The item comes back `null`, `.flat().filter(Boolean)` removes it, and the round reads as a lens that found nothing.

## Evidence

A `review-auto` run in another repo, on 2026-10-28, had two of three reviewers fail with the connection-lost error. The run journal recorded both as `{"type":"failed"}`. The workflow's result still listed no silent lens, and it went on to polish and record its review bookmark. If stage 2 had run for those two items, both lenses would have been listed silent. The runtime's source was not read, so this behaviour is inferred from that result.

## Handling it

- Decide what a `null` means inside the same stage that made the call, and return a non-null value that carries the decision (for example `{ findings: [] }` after recording the silent lens).
- A test harness that stubs `pipeline` must also stop an item on a returned `null`. A stub that passes `null` on to the next stage keeps the buggy shape above green. In this repo, `claude/tests/review-auto.mjs` models it.
- Retrying a `null` once is safe only for read-only calls. An agent that edits files may have finished its edits before the response was lost, so a second run applies them twice.
