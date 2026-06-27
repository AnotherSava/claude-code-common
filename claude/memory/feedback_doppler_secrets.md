---
name: feedback_doppler_secrets
description: Default to Doppler (not plaintext .env) for managing secrets/keys/tokens in any project
metadata:
  type: feedback
---

When a project needs secrets, API keys, or tokens, default to managing them in **Doppler** rather than a plaintext `.env`. The user has the Doppler CLI installed (`winget install Doppler.doppler`) and an account in workplace `sava`.

**Why:** The user wants secrets synced across multiple dev machines without committing them and without manual copy-paste drift. Doppler is the single source of truth; a plaintext `.env` per machine drifts and risks accidental commits. (Established 2026-06-23 while wiring a project's Doppler setup.)

**How to apply:**
- Per project: create a Doppler project + `dev` config, import any existing `.env` (`doppler secrets upload .env -p <proj> -c dev`), add a committable `doppler.yaml` (`setup:\n  project: <proj>\n  config: dev`) — it holds no secrets — and wrap the env-dependent dev scripts with `doppler run -- …` (e.g. `dev`, `db:migrate`). Leave `build`/`start`/`test`/`lint` bare so CI and prod aren't forced onto Doppler.
- Add/change a secret with `doppler secrets set KEY=value -p <proj> -c dev` — never by editing `.env`.
- Second-machine onboarding: `winget install Doppler.doppler` → `doppler login` (interactive — needs a real TTY; fails under Claude Code's `!` prefix with "Incorrect function") → `doppler setup` (auto-reads `doppler.yaml`).
- Offer, don't impose: if a project already has its own secret-management (Vault, cloud secret manager, encrypted-in-repo), respect it rather than swapping to Doppler.
