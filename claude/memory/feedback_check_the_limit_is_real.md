---
name: feedback_check_the_limit_is_real
description: An accurate report of a limitation is not the end of the work — check whether the limit is removable, especially when the system already holds the evidence you said it lacked
metadata:
  type: feedback
---

**An accurate report of a limitation is not the end of the work.** Before settling
for describing a limit honestly — a ladder of weaker/stronger options, a "claim vs.
verified" distinction, a hedged label — check whether the limit is actually
removable. Ask specifically: **does the system ALREADY contain the evidence I said
it lacks?**

**Why:** seen 2026-08-30. Asked to design cross-machine sender identity, I correctly
established that a fleet-wide shared bearer token proves "a token-holder", not "which
machine", proposed an honest three-level attestation ladder, and stopped. Oleg asked
whether I had considered addressing it. I had not — and the answer was sitting
unused: the listener is tailnet-scoped, so WireGuard had **already** authenticated
the node, and the code was discarding that result to read a self-declared string. One
`tailscale whois` call turned a claim into a checked fact, with no new secret and no
rotation burden. The honest ladder was accurate and premature. Note the near miss on
the other side too: the first fix I reached for was per-device tokens — more
machinery, weaker result — because I was thinking about what to *add* rather than
what was already there and unread.

**How to apply:** the tell is proposing a *vocabulary* for a limitation (levels,
hedged labels, "unverified") instead of a fix. That is the moment to ask what already
authenticated, already validated, or already decided this upstream — a transport, a
kernel, a daemon, a prior gate. Distinguish a limit that is **inherent** (a raw
socket writer cannot observe delivery; no amount of design changes that) from one
that is **incidental** (we simply never asked the daemon). Say which kind it is, and
for an incidental one say what would remove it. See [[feedback_indicator_certainty]]
for the other half — once a limit genuinely is inherent, never dress it up as
certainty — and [[feedback_ship_the_ladder]], which is about decomposition rather
than about whether the ceiling is real.
