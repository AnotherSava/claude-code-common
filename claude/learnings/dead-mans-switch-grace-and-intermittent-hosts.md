# Choosing a dead-man's-switch grace period, and why an intermittent host has none

A dead-man's switch — a job that pings an external monitor, which alerts when the pings stop — is the
standard answer to "how do we learn that a scheduled job died". The grace period is the only number in it,
and on an always-on host it is derivable rather than chosen:

```
grace > period + jitter      else it cries wolf on an ordinary late run
grace < 2 x period           else a single missed run is invisible
```

For a daily timer with an hour of jitter that is the open interval (25h, 48h), and any value inside it is
defensible. Worth asserting in a test that parses the *installed* timer and recomputes the band, so the
constant cannot drift away from the schedule it was derived from.

## On a machine that is legitimately switched off, the interval is empty

Substitute a desktop or laptop and the derivation collapses, in two stages.

First, `period` stops being a duration. If the machine is off overnight, a daily 03:30 trigger essentially
never fires; catch-up-on-next-boot means the real cadence is *one run per logon*, and "one logon" is not a
number of hours. The `period` term the band is built from does not exist.

Second, even a generous fixed value is a **risk budget wearing a derivation's clothes**. Pick 96h and an
ordinary Friday-to-Monday absence has already burned 78 of it; a Friday-to-Tuesday return is ~102h and
alerts falsely while the owner is away and least able to act. Meanwhile a job that breaks on Monday is not
reported until Friday. A monitor that cries wolf gets muted, which is strictly worse than no monitor —
you now believe you are covered.

## The predicate that *is* derivable

Alert on **"the machine was up and did not succeed"**, not on "no recent success". That is false while the
owner is away and true when something is actually broken.

Compute it on the machine itself, from its own uptime: accumulate hours the host has been powered **since
the last successful run**, and fail once that exceeds the trigger's own arithmetic (at-logon delay, plus one
run's duration, plus margin). Every input is something the system already reports, so a test can recompute
it and will fail if the schedule moves.

Resist resolving it with a *second machine* as the observer — "an always-on box watches for the data
arriving" is the tempting design and it is usually worse:

- The observer holds no independent evidence. It has only the reporter's own word arriving by a different
  transport, which is not a second opinion.
- Its "I could not check" outcome is typically a note rather than a failure, so a revoked credential makes
  the monitor stop monitoring while still reporting healthy.
- It puts a network call to a third party inside whatever run owns the observer's own liveness. A hung
  socket there takes down the thing that was supposed to be watching.

The external monitor still earns its place, but only as a backstop for "the machine never came back at
all" — where a false alarm costs one email. Use a cron-style schedule with a timezone rather than a flat
period, so predictable idle windows are not counted as silence.

## Two channels, two questions

The alert that says a job **failed** and the heartbeat that says a job **ran** answer different questions,
and they must not be merged. The ping therefore fires on failure too — otherwise a job that runs and fails
every night pings green forever.

Conflate them and a broken job looks dead while a dead machine looks broken, and those want opposite
responses from whoever is woken.

**The heartbeat is the one check permitted to degrade quietly.** An unset or unreachable ping URL is a note,
never a failure — a heartbeat able to fail the job it monitors converts a monitoring aid into an outage.
The exception is earned rather than convenient: the silence *is* the alarm, so an unsent ping is exactly
what the monitor reports.

Where the monitor supports it, ping `$URL/$exit_code` rather than a bare `/fail`, so the success/failure
rule lives in the monitor instead of being re-derived locally, and a partial failure stays distinguishable
from a hard one in the event log.

## It is not trusted until it has been seen firing

Stop the job, wait out the grace, confirm the alert actually arrives, start it again, confirm the recovery
notice. A switch nobody has watched fire is an assertion, which is the thing it was built to replace.
