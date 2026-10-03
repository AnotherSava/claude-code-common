# Self-repair in a watermark-driven sync

A receiver that asks its peer for "everything newer than what I already hold" repairs itself for
free, and the repair rests on a precondition that is easy to delete while making the code look
better: the receiver's high-water mark has to be able to go *down*.

## The arrangement this is about

Push notifies, pull moves content. Each side is authoritative for its own records. A push carries
metadata plus a **tip** — the newest timestamp the sender holds. The receiver compares that tip
against its own newest held record and fetches the difference itself. Nothing on either side
records what was delivered, so a dropped fetch costs only a retry: the next push re-advertises the
same tip and the range is asked for again.

Deriving the request from stored state rather than from a tracked watermark is what makes that
work — a number tracked alongside the data is a guess about someone else's contents and goes stale
silently. But it also means the entire repair budget sits in one comparison, `tip > held`. Anything
that leaves `held` where it is removes the receiver's only way to notice it is missing something.

## The trap

Overwriting a record with a **stale** version lowers `held`, and therefore schedules its own
repair. Inserting that stale version beside the current one keeps `held` where it was, and nothing
ever asks again.

Measured 2026-10-03 in the claude-code-dashboard dialog sync. A full catch-up fetch asks for the
whole conversation and takes long enough — megabytes — that an incremental pull issued while it is
in flight can merge first. The catch-up body then delivers an older copy of a reply that is still
streaming at the origin.

The original merge replaced that turn's reply with whatever arrived, older copy included. That
reads as lossy, and for one push cycle the receiver did show stale text — then the sender's tip
exceeded the receiver's lowered mark, the range was re-pulled, and the final text arrived.

Its replacement inserted instead, on the reasoning that an entry identified by `(role, timestamp,
text)` should never be overwritten by a different one. Nothing was lost and nothing read stale, and
the conversation kept two copies of one reply permanently: the origin no longer held the old
version, so no later pull mentioned it, and `held` had not moved, so no later pull was made. An
adversarial review found it; the test suite did not, because every test asserted on one merge call
rather than on two fetches completing out of order.

## What to check before changing a write in this shape

- **Does this write ever lower the receiver's mark, and is that how the next round learns to
  re-ask?** If so, the lowering is the feature.
- **Is there a second signal that would notice the discrepancy?** Here there was none. The catch-up
  is triggered by a person opening a window, not by a clock, so "it will be fixed next time" had no
  next time.
- **Does the new operation preserve the structure the producer guarantees?** The origin writes at
  most one reply per turn. The insert produced two — a shape nothing in the system could create
  deliberately, and therefore nothing could undo.

The last one is the cheapest check and the one that generalizes: ask what shapes the *writer* can
emit, and treat a receiver that can construct a shape the writer cannot as a defect regardless of
how it got there.
