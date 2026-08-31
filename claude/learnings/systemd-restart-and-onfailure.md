# Keeping a unit alive, and being told when it isn't

Hardening a systemd service so a transient fault doesn't become a permanent one — and wiring an alert that
actually fires. Six traps here, and **every one of them fails silently**: the unit loads, `daemon-reload`
succeeds, and the file reads as though it took effect.

## StartLimit* are `[Unit]` options, not `[Service]`

They moved in systemd 229. Put them in `[Service]` and systemd logs a warning nobody reads, ignores them,
and leaves the default budget in place — so the drop-in you wrote to change the budget changes nothing.

```ini
[Unit]
StartLimitIntervalSec=3600
StartLimitBurst=60
OnFailure=alert@%n.service

[Service]
Restart=always
RestartSec=10s
```

`Restart=` and `RestartSec=` are `[Service]`. `OnFailure=`, `StartLimitIntervalSec=`, `StartLimitBurst=`
and `OnSuccess=` are `[Unit]`. Two independent agents drafting the same file both got this wrong, which
suggests the split is genuinely counter-intuitive — the restart *budget* is a unit property, the restart
*behaviour* is a service property.

## `StartLimitIntervalSec=0` silently disables `OnFailure=`

The tempting "just never give up" setting, and it breaks the half that tells you something is wrong.

- **CHANGES WITH 239:** "When `OnFailure=` is used in combination with `Restart=` on a service unit, then
  the specified units will no longer be triggered on failures that result in restarting."
- **CHANGES WITH 254:** "…dependent units are not notified until the service converges to a final
  (successful or failed) state."

Disabling the rate limiter means the unit *never* converges to `failed`, so `OnFailure=` never fires. You
end up believing you have an alert. Use a generous but **finite** budget instead — 60 starts an hour is far
beyond any real fault and still converges when the daemon is genuinely dead.

Note the reports conflict across versions (upstream #33710 describes the opposite on v255 — firing on
*every* restart, i.e. an email every 10s from a box you can't reach to stop it). Read `NEWS` on the machine
you're actually configuring, and test the alert rather than assuming either behaviour.

## The default budget kills a fast crash-loop permanently

The default is `StartLimitBurst=5` over `StartLimitIntervalSec=10s`. A unit with `RestartSec=100ms` that
fails *immediately* burns all five in about half a second, and systemd then marks it `failed` with
`start-limit-hit` and stops trying — until a human runs `systemctl reset-failed`. A unit that crashes
*slowly* (after >10s) never trips the limit and self-heals forever. So the exposure is narrow and real: only
the fast failure strands you, and that's the one a bad binary or a corrupt state file produces.

This matters most when the unit is what gives you access. Check `ExecStopPost=` too — a cleanup that tears
down a network interface turns "the daemon is down" into "the daemon is down and the route to the box is
gone."

## `Type=oneshot` disables the start timeout, so a hung job hangs forever

The default that reverses itself for the one type where it matters most. `systemd.service(5)` on
`TimeoutStartSec=`:

> Defaults to `DefaultTimeoutStartSec` set in the manager, except when `Type=oneshot` is used, in which case
> the timeout is disabled by default.

A timer-driven `oneshot` — a backup, a sync, a report — is exactly the shape that talks to a third party over
the network, and a half-open socket is exactly what produces an indefinite hang. Without an explicit
`TimeoutStartSec=` the unit sits in `activating` until someone notices, holds whatever exclusive lock the job
took, and never fires `OnFailure=` because it never converges to a final state. The next two nights then fail
on the *lock* rather than on the cause, so the failure has erased its own origin.

```ini
[Service]
Type=oneshot
TimeoutStartSec=3600      # generous, and finite; the point is that it terminates
```

Bound the individual calls inside the job as well. The unit timeout turns a hang into a killed unit with
nothing recorded; a per-call timeout turns it into a named failure of the step that hung.

## A templated `OnFailure=` handler must not speak for units it knows nothing about

`OnFailure=alert@%n.service` is a good pattern precisely because any unit can adopt it — which is also how it
goes wrong. Two traps, both from the handler having been written when only one unit used it:

- **Its wording ossifies around the first caller.** A handler whose message says "the self-check did not run,
  so nothing was asserted about this box" is simply false once a backup unit routes through it: that check
  ran fine and something else died. Derive the subject from `%i`, and keep any caller-specific claim behind
  an explicit test for that caller's unit name.
- **Shared alerting state is the sharper one.** If the handler touches a rate-limiting clock belonging to
  some *other* message — the box's health verdict, say — then a unit that fails nightly re-stamps that clock
  nightly, and the reminder it belongs to never comes due again. A backup job can silence every alert about
  everything else, permanently, with nothing anywhere reporting a fault. Give a unit-failure notification its
  own per-unit clock, keyed by unit name, and never let it write a clock it does not own.

A local workaround exists and is worth recognising as one: `SuccessExitStatus=` on the *first* unit stops its
ordinary non-zero exit reaching the handler at all, which protects that unit and leaves every later adopter
walking straight back into the defect. Fix the handler.

Note the exit-code contract differs per unit and the two are easy to copy wrongly between them. A command
whose exit 1 means "I ran and the answer is bad" needs `SuccessExitStatus=1`, or systemd calls a successful
run a failure. A command whose exit 1 means "I did not do my job" must **not** have it, or systemd calls a
failure a success. Same directive, opposite correct answers, and no test catches the wrong one.

## `WatchdogSec=` requires the daemon to implement it

A daemon must call `sd_notify(WATCHDOG=1)` on a timer. If it doesn't, systemd `SIGABRT`s a perfectly healthy
process at every interval — the hardening manufactures the outage. Readiness and watchdog are separate
protocols and implementing one implies nothing about the other. Check the binary before assuming:

```
grep -c 'WATCHDOG=1' /usr/sbin/<daemon>   # 0 → do NOT set WatchdogSec
grep -c 'READY=1'    /usr/sbin/<daemon>   # readiness only, unrelated
```

If you need liveness coverage for a daemon that can't be watchdogged, use an external timer that probes it
and restarts on a bad reading — not `WatchdogSec=`.

## Applying and verifying

A drop-in goes in `/etc/systemd/system/<unit>.service.d/*.conf` — there is no flat form, systemd reads only
that directory shape. **`daemon-reload` does not restart running units**, so adding one is genuinely zero
downtime; it applies at the unit's next start, which is exactly when it matters.

Verify against systemd's own view, never against the file or the exit status of the reload:

```
systemctl show <unit> -p Restart -p RestartSec -p StartLimitBurst -p StartLimitIntervalUSec -p OnFailure
systemctl cat <unit>          # shows the base unit plus every drop-in, in order
```

A drop-in with keys in the wrong section reloads perfectly happily. `systemctl show` is what proves systemd
agreed with you, and it reports the *effective* values — which is the only claim worth making.

## Test the notifier before you rely on it

`journalctl -u 'alert@*'` returning "No data available" means the alert template has never run, and an
untested notifier is exactly as unproven as whatever it is meant to be covering. Fire it once by hand
(`systemctl start alert@test.service`) and confirm the message arrives.

Check the alert path doesn't depend on the thing it reports: if the unit being watched is the network, the
notifier must reach the outside without it. Egress HTTPS to a third-party API usually survives; anything
routed through the failed interface does not.
