# Deriving the grace period

A grace period is the only number in a dead-man's switch, and it is the one people pick by taste.
This file is the arithmetic, and — more useful — the case where the arithmetic has no answer and
picking a number anyway is the mistake.

## The standard: a number a test can recompute

A threshold is not "arithmetic written in a comment". It is a value something re-derives from an
input the system actually reads, and fails on when that input moves. A justifying paragraph beside
a constant is not the same thing: the paragraph cannot notice when the timer changes underneath it.

So the bar is: **name the input, state the inequality, and put the check where it runs.**

## First: the grace is not measured from the last ping

Get this wrong and every number after it is wrong by a whole period. On healthchecks.io a check is
**late** at `last_ping + period`, and goes **down** at `last_ping + period + grace`. The vendor's own
worked example: period 1 hour, grace 5 minutes, last ping at 12:00 — late at 13:00, down at 13:05.
For a cron/`OnCalendar` schedule the period is replaced by the schedule itself: late at the scheduled
time, down at `scheduled_time + grace`.

So the period is **already in the deadline**. A grace picked as though it were the total tolerated
silence double-counts it, and the resulting check is far more permissive than intended. The error is
invisible in operation: a too-large grace never false-alarms, so nothing ever reports that the switch
quietly stopped covering a single missed run. Reason about the **deadline**, then subtract.

## The band, for a job on a fixed cadence

Two bounds, from the job's own timer, written against the deadline:

```
period + grace  >  longest ordinary gap        ->  grace >  jitter
period + grace  <  gap after ONE missed run    ->  grace <  period - jitter
```

The lower bound is the longest the job can legitimately be quiet while nothing is wrong. The upper
bound is when the *next* ping arrives after exactly one skip — set the grace at or above it and that
recovering ping resets the check before the alert is due, so the switch can only ever see two
consecutive failures. That is a different and much weaker promise than the one usually claimed for it.

Worked, for a `daily` systemd timer with `RandomizedDelaySec=1h` — ordinary gap up to 25h, and the
ping after one missed run arriving as early as 47h:

```
grace >  1h        (jitter)
grace <  23h       (period - jitter)
band  =  (1h, 23h)          choose 12h   ->  deadline 24h + 12h = 36h
```

Check the answer by writing the deadline down and confirming it lands between the two gaps:
`25h < 36h < 47h`. Do this every time. It is the step that catches the double-count, and it takes one
line.

The band is usually wide. Sitting near its middle rather than either edge costs nothing and absorbs a
timer that drifts slightly.

## Do not align two thresholds because they look alike

A system accumulates several durations that are all "a bit more than a day" and mean different
things — a heartbeat grace, a staleness floor for an off-box copy, a window after which a stored
verdict is refused. They come from different timers and have different consequences when wrong.
Aligning them into one constant "for tidiness" silently halves or doubles a coverage window whose
reasoning lived only beside the old value.

The test is the consequence of a false positive:

| Threshold guards | A false positive costs | So it can be |
|---|---|---|
| a heartbeat | one email, and nothing else is watching | tight |
| a gate that blocks a deploy | an operator learning to reach for `--force` | loose |

A `--force` reached for by habit is worse than no check at all. Different consequence, different
number, even when the two are within hours of each other.

## When the band is empty: intermittently-powered machines

A desktop or laptop that is switched off overnight, at weekends, and for holidays breaks the
derivation at its root. Substitute it into the inequalities and there is no value that satisfies
both, because the governing term is **how long a human left the machine off** — and that term:

- appears in no configuration anything reads, so nothing can recompute it;
- moves *both* bounds together, so widening the grace does not recover the lower bound;
- is drawn from a distribution with a long tail, and the long trip *is* the tail.

It gets worse than "wide". A job scheduled daily at 03:30 on a machine that is off overnight
essentially never fires on that trigger; the real cadence becomes one run per logon. "One logon" is
not a duration, so the `period` term the formula needs does not exist at all.

**The empirical rescue is not one.** Taking a year of power history and using the 99th-percentile
off-period bounds the *past* distribution and changes the kind of guarantee: from "never false,
always catches one miss" to "false p% of the time". On a roughly daily cadence that is several false
alarms a year — which is the exact mechanism that produces a muted monitor, and a muted monitor is
worse than none because you then believe you are covered. It also drifts silently: it goes wrong
when the person's life changes, with no commit, no config edit, and nothing to fail.

### What to do instead: change the predicate

The question "has it been too long since a backup?" is unanswerable here. The question
**"was the machine UP, and did it not back up?"** is answerable, and derivable.

Have the job itself compute *hours the machine has been up since the last success* — from the OS's
own uptime plus the last recorded success — and signal failure once that exceeds the trigger's own
arithmetic (for a logon trigger: the trigger's delay, plus one run's typical duration). Every term
is an input the system reads, so a test can recompute it and will fail when the trigger changes.

Then the monitor's grace only has to backstop the residual case, *"the machine never came back at
all"*, where a false alarm costs one email. Set it generously and say plainly that it is a risk
budget rather than a derivation.

Two numbers, for two questions. Only one of them claims to be derived, and that honesty is the
point: a number presented as arithmetic when it is taste is worse than an admitted guess, because
the next person will not re-examine it.

### Why not put the judging on a always-on machine instead

The tempting alternative is to have some always-on server check the artifact's freshness and alarm.
Weigh three things before choosing it, because they are what make it worse than it looks:

- **Whose word is it?** A judge that only reads what the subject uploaded holds the subject's own
  claim, transported. That is not a second opinion. A judge worth having holds *independent*
  evidence — it counts something itself and compares.
- **Can the judge's own failure be silent?** If an unreadable input (a revoked key, a 403, an
  expired credential) is recorded as a note rather than a failure, and the always-on machine mails
  nothing when it is otherwise healthy, then the monitor stops monitoring while everything prints
  OK. Adopting a monitor whose own death is silent, to fix a monitor whose death is silent, is not
  progress.
- **What else shares that process?** Adding a network call to a vendor inside a scheduled run that
  owns something more important — a deploy gate, another heartbeat — couples them. A hung TLS
  handshake with no timeout then takes out the thing it was added beside.

None of these forbids the approach. They are the questions that decide it, and on a shared or
production machine the answers usually point the other way.

## Scheduled rather than periodic

Where a job runs on a calendar rather than an interval — weekdays only, or on a fixed clock time —
express it as a schedule with a timezone rather than a flat period. A flat period counts an expected
weekend of quiet as silence, which reintroduces the false alarm the band was chosen to avoid.
