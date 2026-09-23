---
created: 2026-09-23 02:21:01
---

# The output style's park-it line and its closing ask are two questions a one-word reply cannot both answer

Take this through /tune-output, which owns the response-style file and has the A/B harness and the ledger.

The style prescribes a body line for a parked observation — `Noticed elsewhere: <the thing>. Memo it?` — and separately requires the reply to end with a single closing ask, itself a question. When both are present the reader has two questions in front of them and one place to answer.

Measured 2026-09-23 in the claude dotfiles repo, twice in the same session. Each reply carried `Memo it?` in the body and a different closing question (`Push?`); the user's `y` answered the closing one both times, and the parked item had to be re-raised twice before it was disposed of. Two round trips spent on a collision the style creates by construction.

Two directions, either of which resolves it: the park-it line stops being a question and becomes a statement the user can act on or ignore, or the style forbids it co-occurring with a closing ask and makes it the closing ask when there is nothing else competing.
