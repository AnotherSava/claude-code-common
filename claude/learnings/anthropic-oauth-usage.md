# Anthropic OAuth usage endpoint (`/api/oauth/usage`)

Undocumented beta endpoint that returns rolling 5-hour and 7-day rate-limit utilization for a Claude Code OAuth token. Used by Claude Code's own statusline and by community monitors.

## Request

- **Endpoint:** `GET https://api.anthropic.com/api/oauth/usage`
- **Required headers:**
  - `Authorization: Bearer <accessToken>` — from `~/.claude/.credentials.json` → `claudeAiOauth.accessToken`
  - `anthropic-beta: oauth-2025-04-20`

## Response shape

```json
{
  "five_hour": { "utilization": 0.37, "resets_at": "2026-04-21T03:00:00.000+00:00" },
  "seven_day": { "utilization": 0.67, "resets_at": "2026-04-25T00:00:00Z" }
}
```

- `utilization` is *usually* a `0.0..1.0` fraction, but some deployments return `0..100` percent. **Normalize defensively:** if the raw value is > 1.5, divide by 100, then clamp to `[0, 1]`.
- `resets_at` is ISO-8601 UTC. Use `chrono::DateTime<Utc>` in Rust or `new Date(resets_at).toLocaleString(undefined, ...)` in JS — drop the `timeZone: 'UTC'` option if you want local-time display.

## Credentials

`~/.claude/.credentials.json` structure:

```json
{
  "claudeAiOauth": {
    "accessToken": "sk-ant-oat01-...",
    "refreshToken": "...",
    "expiresAt": 1776752345678,
    "subscriptionType": "max",
    "rateLimitTier": "default_claude_max_5x"
  }
}
```

`expiresAt` is ms-epoch. When expired, running any `claude` CLI command (e.g. `claude -p .`) triggers an OAuth refresh and rewrites the file.

## Rate limiting (important)

Tracked in [claude-code#31637](https://github.com/anthropics/claude-code/issues/31637) and [claude-code#31021](https://github.com/anthropics/claude-code/issues/31021).

- Short-interval polling triggers `HTTP 429 rate_limit_error`. Rapid dev-loop restarts are a common trigger.
- **No `Retry-After` header** — no hint when the bucket clears.
- Rate-limit quota is **pooled per organizationUuid**, not per-account ([claude-code#41886](https://github.com/anthropics/claude-code/issues/41886)).
- **Polling every 10 minutes is stable in practice** (verified on a Max subscription). Still retain last-good values on 429 since community reports indicate recovery isn't always immediate.

## Messages-API fallback

The same utilization/reset data is exposed on every `POST /v1/messages` response as headers — useful when the OAuth endpoint is 429'd:

| Header | Meaning |
|---|---|
| `anthropic-ratelimit-unified-5h-utilization` | 0.0–1.0 fraction |
| `anthropic-ratelimit-unified-5h-reset` | unix seconds |
| `anthropic-ratelimit-unified-7d-utilization` | 0.0–1.0 |
| `anthropic-ratelimit-unified-7d-reset` | unix seconds |
| `anthropic-ratelimit-unified-status` | `rejected` → force 100% |
| `anthropic-ratelimit-unified-reset` | overall, used when per-bucket reset missing |

Upstream monitor sends a 1-token ping to `claude-haiku-4-5-*` and reads the headers off the response when the primary endpoint fails.

## Reference implementations

- [CodeZeno/Claude-Code-Usage-Monitor](https://github.com/CodeZeno/Claude-Code-Usage-Monitor) — Rust, `ureq`, native-tls, hand-rolled ISO-8601 parser, WSL multi-distro credential-hunt, auto-refresh via `claude -p .`. Minimal deps, ~200 LOC core.
- This repo's `src-tauri/src/usage_limits.rs` — reqwest+chrono, simpler (no fallback, no token refresh, configurable poll interval via config.json).
