# Keeping a unit alive, and being told when it isn't

Hardening a systemd service so a transient fault doesn't become a permanent one — and wiring an alert that
actually fires. Four traps here, and **every one of them fails silently**: the unit loads, `daemon-reload`
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
