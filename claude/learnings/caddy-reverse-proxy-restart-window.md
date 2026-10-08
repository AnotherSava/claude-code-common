# A Caddy site serves 502 for the whole time its upstream is restarting

Redeploying an app behind `reverse_proxy` answers every request with 502 until the new container is
listening, and nothing in the proxy config suggests it will. Caddy disables retries by default, so the
first dial failure becomes the client's response. A deploy that recreates one container therefore has a
real outage window, measured in seconds, that no health check and no 200 afterwards will reveal.

Found while a neighbouring session happened to be probing the host during a publish: it caught the site
returning 502 with the app container showing `Up 14 seconds`. The publish itself reported success,
because it verifies after a settle delay — by which time the window has closed.

## Turn retries on, and that is the whole fix

```caddyfile
reverse_proxy app-container:3000 {
	lb_try_duration 30s
}
```

- `lb_try_duration` — how long to keep selecting an upstream for one request. **Default: zero, meaning
  retries are off.** This is the setting that decides whether a restart costs latency or errors.
- `lb_try_interval` — how long to wait between attempts. Default `250ms`, which needs no change.

Caddy's own documentation names this exact use: with retries enabled it "can also be used with one or
more upstreams, to hold requests until a healthy upstream can be selected (e.g. to wait and mitigate
errors while rebooting or redeploying an upstream)." A single upstream is a supported case, not a
degenerate one.

A held POST cannot double-submit, and the protection comes from the method rather than from the kind of
failure. Caddy declines to retry a non-safe method once the request has been sent: against an upstream
that accepted the connection, read the whole body and then dropped the socket, a POST took its 502 in
about 20 ms having arrived exactly once, while a GET in that same situation was retried for the whole
window. A status code the upstream itself returned is never retried either — a 502 the app generated is
the app's answer.

**Count the retries a GET can produce before putting this in front of an expensive or side-effecting
handler.** The bound is `lb_try_duration` divided by `lb_try_interval`, so the default 250 ms interval
under a 30-second duration delivers one client request to the application 120 times — measured at exactly
that, which is also what the arithmetic predicts. Raise the interval, shorten the duration, or both.

## What health checking costs, and the one setting that wastes the window

Keep any `fail_duration` well below `lb_try_duration`, and read health checking as a cost in recovery
latency. An unavailable upstream does not short-circuit the retry: an empty pool is retried for the full
duration exactly as a dial failure is, so adding health checking does not reintroduce the error the
duration was set to remove. Measured on v2.11.7 under a 30-second duration and on v2.11.4 under a
5-second one, every configuration consumed its whole window — the duration alone, plus `fail_duration`,
and plus `health_uri` alike — and all three served an upstream that came up mid-window.

What the checking buys back is slower: a `fail_duration` holds the recovered upstream out of the pool
until its own window expires, so a request that could have been served at six seconds was served at ten,
and active checking costs up to one `health_interval`.

**A `fail_duration` at or above `lb_try_duration` is the configuration that throws the window away.** The
exclusion then outlives the retry, so the request fails without ever trying the upstream that came back:
a 60-second fail window against a 30-second duration gave a 502 at 30.05 s while the upstream had been
listening for 24 of those seconds, and the next request waited out the remaining exclusion before being
served.

Active checking answers **503** with `no upstreams available` rather than the 502 a dial failure gives, so
a probe that matches on 502 misses that case entirely. `fail_duration` defaults to `0`, off — an adapted
config carrying the duration alone has no `health_checks` key at all. `health_port` is unmeasured here.

## Size the duration above the real window, and measure the window

A duration shorter than the outage covers the head of it and still 502s the tail — which looks identical
to having no retry at all, so the setting reads as not working rather than as too small.

Measure it from the container timings rather than estimating. On a stack where a one-shot migration
container runs before the app, read both:

```bash
docker inspect <migrate-container> --format 'started={{.State.StartedAt}} finished={{.State.FinishedAt}}'
docker inspect <app-container>     --format 'created={{.Created}} started={{.State.StartedAt}}'
```

The gap that matters runs from the old app container going away — near the new one's `Created` — to the
new one serving. One measured stack: a migration step of under four seconds inside a 14.5-second gap
between the old container leaving and the new one starting.

**Then add headroom for the application's own startup, because `StartedAt` is not when it listens.** A
framework that compiles or warms on boot is still refusing connections after the container is up, and
the container timings cannot see that part at all. The 502 observed above was taken while the container
had been up 14 seconds, which is the evidence that these two are different moments.

Raise it when the migration step grows. A schema change that adds minutes of migration silently pushes
the window back past the duration.

## What the duration costs

A request arriving during a genuine outage — a crash loop, a missing image — hangs for the full duration
before failing, where it used to fail at once. That is the trade being made: a deploy window stops
producing errors, and a real outage takes longer to report one. For a site whose deploys are frequent and
whose outages are rare, holding is the better default, and it is the reason to size the duration to the
measured window rather than padding it generously.

**It covers selecting an upstream, so it does nothing for a response already in flight.** Caddy's own
wording is how long to "try selecting available backends for each request", and selection happens before
any bytes reach the client; once headers and part of a body have gone out they cannot be retracted, and a
status the upstream returned is never retried. A long streaming route — a download that writes a whole
database out, an event stream — therefore gives a truncated body when its upstream restarts mid-response,
and no duration protects it. Reasoned from the documented behaviour and that HTTP constraint rather than
measured: nobody here has killed an upstream part-way through a download.

## Verify the directive took effect, not just that it parsed

A typo fails `caddy adapt` outright, so parsing proves little. Assert the value in the adapted JSON,
which is what the server actually loads:

```bash
caddy adapt --config <file> --adapter caddyfile | python3 -c '
import json,sys
def walk(o):
    if isinstance(o,dict):
        if "load_balancing" in o: print(o["load_balancing"])
        if "health_checks" in o: print("HEALTH CHECKS PRESENT:", o["health_checks"])
        for v in o.values(): walk(v)
    elif isinstance(o,list):
        for v in o: walk(v)
walk(json.load(sys.stdin))'
```

Expect a `try_duration` of `30000000000` — nanoseconds — and read the whole printed line rather than
matching it exactly: the script prints the entire `load_balancing` object, so `lb_policy round_robin` adds
a `selection_policy` key beside the duration. The `HEALTH CHECKS PRESENT` line appears whenever
`health_uri` or `fail_duration` is set, which is how you see which kind of checking a config actually
turned on and what interval or fail window it carries.

Run `caddy adapt` with a local binary of the **same version** as the server. The Caddyfile adapter is
version-specific, so a directive accepted locally by a newer binary can be rejected by an older server,
and the failure then surfaces during the install rather than here.
