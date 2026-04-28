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

- `utilization` is a **0–100 percentage**. Always divide by 100, then clamp to `[0, 1]`. (Older guidance suggested an "if > 1.5 divide, else treat as fraction" heuristic, but that misinterprets real low percentages — `1.0` means 1%, not 100%. Verified across many real responses on a Max account that the API returns percentages exclusively.)
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

## Refreshing the OAuth token directly

You don't have to spawn the Claude Code CLI to refresh an expired access token — the same OAuth endpoint Claude Code uses is callable directly with the stored `refreshToken`.

- **Endpoint:** `POST https://console.anthropic.com/v1/oauth/token`
- **Headers:** `Content-Type: application/json`
- **Body:**
  ```json
  {
    "grant_type": "refresh_token",
    "refresh_token": "<refreshToken from .credentials.json>",
    "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
  }
  ```
  The `client_id` is Claude Code's public OAuth client (hardcoded in the CLI, also visible in the `claude.ai/login` redirect URL).
- **Response:**
  ```json
  { "access_token": "...", "refresh_token": "...", "expires_in": 3600 }
  ```
  Both tokens rotate — the new `refresh_token` replaces the old one. Compute `expiresAt = now_ms + expires_in * 1000` and write `accessToken` / `refreshToken` / `expiresAt` back to `.credentials.json` atomically (temp file + rename) while preserving unrelated fields like `scopes`/`subscriptionType`/`rateLimitTier`.

**Race with Claude Code's own refresh:** refresh tokens are single-use. If both your tool and Claude Code attempt a refresh with the same token simultaneously, whichever calls second gets a 4xx and the new token written by the first caller. Mitigation: defer the first expired sighting one poll cycle to give Claude Code a chance to refresh on its own; only refresh yourself if the token is still expired on the next poll. The losing-side 4xx is recoverable — next poll re-reads `.credentials.json`, picks up the rotated token, proceeds normally.

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
