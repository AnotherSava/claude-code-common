---
name: registry-prose-audited-against-repos
description: The ports registry's per-claim prose was read against each owning repo on 2026-10-05 — what that settled, and the rows no repo read can reach
metadata:
  type: project
---

On 2026-10-05 every machine-scope claim in `claude/skills/ports/registry.json` whose owner is a repo on
this machine — plus landlord's three, whose repo is here although the ports are on the VPS — was read
against that repo, one agent per repo, with every reported inaccuracy then put to a skeptic instructed to
refute it. 29 claims, seven notes called wrong, five of those confirmed and corrected.

Every error was in the prose rather than in the number: which command binds the port, which file names it,
what the pin rests on. The port numbers held in all 29. Two of the seven were refuted — terse wording a
reader could take two ways, not false statements — which is why the refutation pass is worth repeating if
this is ever done again.

What no repo read can settle, and so remains unverified: the desktop box's third-party rows (8096 Jellyfin,
32400 Plex, 11434 Ollama), which live on the other machine. `check --live` confirmed 5000 and 7000 are
ControlCenter's, wildcard-bound as claimed, and that nothing unrecorded listens here beyond the ephemeral
range; it says nothing about the other box.

Still open: 52631 records a number that does not recur, because rapportd takes a fresh ephemeral port each
boot (it answered on 63790 that day). The note now says so; releasing the row instead was offered and not
decided. See [[port-uniqueness-not-a-rule]] for why this registry's checks live in this repo's gate.
