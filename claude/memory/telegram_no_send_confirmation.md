---
name: telegram_no_send_confirmation
description: Telegram bots can't read their own sent messages → no send confirmation/idempotency; duplicate-on-timeout is unavoidable, only mitigable
metadata:
  type: project
---

The Telegram Bot API gives no way to confirm or dedupe a message the bot sent:
`sendMessage` has no idempotency key, and a bot **cannot read its own outgoing
messages** (`getUpdates` returns only *incoming* updates, never the bot's sends).
So there is no confirmation channel — a `getUpdates`-based reconciliation of "did
my send land?" is impossible; don't re-propose it.

Consequence for the notification path (`telegram.rs` / `notifications.rs`
`reconcile`): sends are **at-least-once** (the loop retries on any `Err` by not
recording an `outstanding` handle). A reqwest **read timeout is ambiguous** —
Telegram may have delivered the message and only the ACK was lost — so a retry
can duplicate (this caused a real double-notification). It can only be
*mitigated*, not eliminated. Two mitigations are in place:

1. **Timeout split** (a15ab77): a short `connect_timeout` (unreachable → clean
   "not delivered" retry) plus a generous overall `timeout` (a slow-but-successful
   send acks instead of false-timing-out). Closes the *single slow-ACK* case.
2. **Retry backoff on maybe-delivered failures** (`reconcile`): `TelegramCallError::maybe_delivered`
   (a post-connect read timeout, mirrored into `SendError`) sets a per-session
   `RetryHold` (`UNCERTAIN_RETRY_BACKOFF_MS`, 5min) so a *sustained* outage doesn't
   resend the same ping every ~30s. Closes the multi-minute-outage case: a real
   ~4-min outage once produced **six** identical `printlab` pings (5 delivered-but-
   unacked retries + 1 confirmed) — backoff collapses that to ~1 retry. A
   `not_delivered` (connect/API) failure clears the hold and retries promptly; the
   hold is scoped by `for_status` so a new actionable state pings without waiting.

At-least-once is kept deliberately so a real outage never silently drops an
actionable `blocked`/`error` ping — the rare residual duplicate is the accepted
trade. Related: [[context_alert_outstanding_not_persisted]].
