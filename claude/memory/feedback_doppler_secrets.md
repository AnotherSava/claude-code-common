---
name: feedback_doppler_secrets
description: Default to Doppler (not plaintext .env) for secrets/keys/tokens in any project; the /doppler skill owns the commands
metadata:
  type: feedback
---

When a project needs secrets, API keys, or tokens, default to managing them in **Doppler** rather than a plaintext `.env`. Offer it, don't impose it — a project that already has Vault, a cloud secret manager, or encrypted-in-repo secrets keeps what it has.

**Why:** The user wants secrets synced across multiple dev machines without committing them and without manual copy-paste drift. Doppler is the single source of truth; a plaintext `.env` per machine drifts and risks accidental commits. (Established 2026-06-23 while wiring a project's Doppler setup.)

**How to apply:** Invoke the **`/doppler` skill**. It owns every command template, the project/config resolution rules, and the failure modes, and it is the only place they are maintained — this file deliberately holds none of them. Never reconstruct a `doppler` command from memory: each landmine (workplace vs project, `dev` vs `prd`, value quoting, `!`-prefix leakage, unbound directory) silently produces a wrong result instead of an error, which is why the detail was consolidated into the skill on 2026-08-14. Related: [[refs-private]] for the `tools`/`prd` ad-hoc credential store.
