---
name: feedback_check_the_limit_is_real
description: An accurate report of a limitation is not the end of the work — check whether the system already holds the evidence you said it lacked, whether the general rule you are applying even has its premise here, and whether a later step already owns the work you are offering to do
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


## A second shape: a general limit whose premise does not hold here

**A rule that is true in general can be absent in your specific case, and reporting it as a blocker
makes it true.** Seen 2026-09-02. Twice in one session I declared documentation work blocked on
something external — "these three screenshots need a re-capture on a live game table", and "you need
two captures over known backdrops to separate a subject from its background" — and both were correct
general statements, misapplied. The two-backdrop solve exists because colour *and* coverage are
unknown at a boundary pixel; those subjects were rounded rectangles, so their **geometry** supplied
the coverage and a single existing capture was enough. Nothing was blocked. By then the blocker had
been written into a memo and a screenshot manifest as fact, and the proposed unblocking involved the
user setting up a table and editing site CSS — for work that needed neither.

The tell differs from the case above. There the question is *what already decided this upstream*;
here it is **does this general rule's premise actually hold for my subject?** A method's precondition
is a property of the method, not of the world, so check the subject against it before reporting the
subject as the obstacle. Both times the correction was the user asking nothing more than "why do you
need that?" — which is the question to ask yourself before writing a limitation down, because once
it is in a memo it stops being re-examined.

## A third shape: already owned by a later step

**Check whether something you are about to hand the user is already owned by a step that runs
later.** Seen 2026-09-03. Closing out a session I reported the remote being three commits ahead
as an open decision and offered to work out the safe stash/fast-forward sequence, when `/commit`
step 1 already does exactly that, cites the learning for it, and had been read in that same
session an hour earlier.

The tell is offering to *do* something rather than reporting a limit, and the cost differs from
the two shapes above: not a false blocker, but redundant triage handed to the user, plus a second
and worse implementation of a procedure that already exists. Before flagging anything at a
handover point, ask which step owns it; if a later one does, say nothing and let it run. The
correction was "sync should be part of commit skill, isn't it there already?", which is the same
one-line question as in both cases above.
