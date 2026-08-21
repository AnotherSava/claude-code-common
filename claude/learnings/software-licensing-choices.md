# Choosing (and changing) a licence for your own project

Verified 2026-08-19 against the licence texts and publisher pages cited. Not legal advice — this is a map of the
options, not a substitute for a lawyer once money depends on the answer.

## The licence does nothing while the repo is private

A licence is a grant *to other people*. If nobody has a copy, copyright's default — all rights reserved — already
governs, and the `LICENSE` file binds no one. Changing it on a private repo is a **pre-commitment**, not an act
with present effect. Useful consequence: there is no urgency, and no cost either, so the option-preserving move
is cheap whenever you notice.

## Relicensing: what you can and cannot do

- **A sole copyright holder can relicense freely.** No permission needed. What changes is the terms on which
  *future* copies are offered; what does not change is anything already accepted by someone holding a copy.
- **Verify sole authorship before relying on this** — `git log --format='%an <%ae>' | sort -u`, plus a grep for
  `Co-authored-by` / `Signed-off-by` trailers. One outside commit without a CLA and the assumption collapses.
- **MIT's irrevocability is widely asserted and not actually settled.** Its text contains neither "perpetual" nor
  "irrevocable" (Apache-2.0 does). The counter-theories are consideration (*Jacobsen v. Katzer*, Fed. Cir. 2008)
  and reliance. Treat distributed copies as permanently granted — but know the confident version of this claim,
  in both directions, is folklore.
- **Old commits still contain the old LICENSE.** If you later grant someone repo access, say the terms explicitly
  in the access grant rather than letting a historical tree speak for you. Rewriting history to strip old licence
  files buys nothing against copies already taken.
- Record the change honestly: keep the previous licence text under a dated note ("versions through YYYY-MM-DD
  were released under X"). Cheap, and it prevents an argument about which terms applied when.

## MIT does not restrict the author

The common misreading is that a permissive licence blocks monetisation. It does not — you can sell hosting on your
own MIT code, because you need no licence from yourself. What MIT does is let **anyone else** do the same, at zero
R&D cost, with no obligation to share improvements back. That asymmetry, not any restriction on you, is the reason
to think twice before publishing something you might commercialise.

## AGPL is an anti-fork tool, not an anti-reselling tool

§13 requires that **if you modify the Program**, users interacting with it over a network be offered the
Corresponding Source. The trigger is *modification*: a competitor hosting an **unmodified** copy and charging for
it owes nothing beyond the notice. That gap is exactly why MongoDB wrote SSPL.

Costs: Google states plainly that AGPL is not allowed at Google, and many corporate allowlists mirror that — so it
deters future acquirers and integrators. A sole copyright holder can dual-license (AGPL publicly, proprietary for
payment), which makes AGPL cheaper for a solo project than for a multi-contributor one.

## Source-available options

| | BUSL-1.1 | PolyForm |
|---|---|---|
| Publisher | MariaDB plc | PolyForm Project |
| Mechanism | Non-production use by default, with an optional Additional Use Grant; converts to the **Change License** on the **Change Date** | Fixed-purpose forms — Noncommercial, Internal-Use, Small-Business, Shield, … |
| Constraints | Change License must be GPL-2.0-or-later compatible; Change Date ≤ 4 years. Carries MariaDB trademark/attribution terms | **Shield** is the closest to "read it, host it, but don't compete with me" |
| OSI-approved | No | No — both fail OSD #6 (no restriction on field of endeavour) |

Both are less well recognised by scanners and registries than MIT/AGPL. BUSL suits "commercial head start, open
eventually"; PolyForm Shield suits "visible source, no clone SaaS".

## Decision table

| What you want | Licence |
|---|---|
| Undecided, repo private | All rights reserved — keeps every path open |
| Personal, happy for anyone to use it | MIT, or Apache-2.0 for the patent grant |
| Open source, no proprietary fork | AGPL-3.0 |
| Open source **and** sell hosting | AGPL + commercial dual-license |
| Visible source, competing SaaS forbidden | PolyForm Shield |
| Head start now, open later | BUSL-1.1 |

You can always **add** a licence; you can never **subtract** one. When undecided, granting nothing is the position
that preserves the most.

## The thing that actually forecloses your options is a contributor, not a file

Dual-licensing requires controlling 100% of the copyright.

- **DCO** (`git commit -s`) certifies provenance. It grants you **no** right to relicense — inbound licence equals
  outbound licence.
- **CLA** (Apache ICLA, Project Harmony) leaves copyright with the contributor but grants you a perpetual,
  irrevocable, **sublicensable** licence plus a patent grant. That sublicensing right is what permits
  dual-licensing or closing the source later.

Adopt the CLA **before** the first outside PR. Retrofitting means chasing every past contributor, and one who
declines (or is unreachable) permanently blocks the commercial path.

## Housekeeping when you change it

`LICENSE` is not the only declaration. Also update the package manifest — npm's documented value for "no rights
granted" is `"license": "UNLICENSED"` (pair with `"private": true`). A manifest still claiming MIT contradicts the
LICENSE file and is what dependency scanners actually read. In a JS project the lockfile's root entry mirrors the
manifest; `npm install --package-lock-only` refreshes it.

"No LICENSE file at all" and "All rights reserved" are legally equivalent in substance — with no licence, the work
is under exclusive copyright by default. The explicit notice is worth writing anyway, because it forecloses the
reading that you merely forgot.
