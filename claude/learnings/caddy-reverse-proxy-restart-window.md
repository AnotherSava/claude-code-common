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
- `lb_try_interval` — how long to wait between attempts, default `250ms`. Together with the duration it
  sets how many times one request can reach the upstream, which is the reason to raise it in front of a
  handler that is expensive or has side effects.

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
handler — and read the condition, which is an upstream that accepts the connection and then drops it.**
While the port is simply closed nothing reaches the application at all, so the amplification is zero
during a restart window and this paragraph says nothing about that case. Where the upstream does accept,
the arrival count is roughly `lb_try_duration` divided by `lb_try_interval`: a 30-second duration at the
default 250 ms interval delivered one client request 120 times, and a 5-second duration gave 21 then 22
arrivals across two runs at that interval, against 6 then 7 at a one-second one. Approximate, so size
from the ratio rather than from those figures. Raise the interval, shorten the duration, or both.

**Do not read the zero as a reason to leave the interval alone.** A peer took the amplification as
covering the dial-refused publish window, found correctly that a closed port delivers nothing, and
concluded from that incorrectly that `lb_try_interval` buys nothing — then shipped without it. The two
cases are different failures: a closed port cannot amplify, and an upstream that accepts while unable to
answer is exactly what a crashing or half-started app does.

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

The mechanism offered for that, read off Caddy's source by another session rather than measured here:
`max_fails` defaults to 1, so one failed dial marks the single upstream down for the whole
`fail_duration`, and while it is down Caddy stops attempting the dial at all — which is why an app that
binds shortly afterwards goes unnoticed. The same reading has `tryAgain`'s guard excluding
`errNoUpstream` since 2.7.5, which would date the empty-pool retry rather than make it new. Both agree
with what the measurements above show; the version boundary is unverified here, and an adapted config
emits no `max_fails` key, consistent with the default.

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

The application's own log closes that gap wherever it prints a line on becoming ready. Subtracting the
database's start from that line's timestamp measures the whole window, the part `docker inspect` is blind
to included — on a second stack of a database, a one-shot migration and the app, 8.3 seconds, of which the
migration was 1.66. **Take the sample from a publish nobody has touched by hand.** That one had its
database container removed beforehand for an unrelated reason, so it paid for a cold start that a publish
reusing the volume and the image layers does not: it overstates the window, which is the safe direction
for sizing a duration and the wrong one to quote as a figure.

Raise it when the migration step grows. A schema change that adds minutes of migration silently pushes
the window back past the duration.

## What the duration costs

A request arriving during a genuine outage — a crash loop, a missing image — hangs for the full duration
before failing, where it used to fail at once. That is the trade being made: a deploy window stops
producing errors, and a real outage takes longer to report one. For a site whose deploys are frequent and
whose outages are rare, holding is the better default, and it is the reason to size the duration to the
measured window rather than padding it generously.

**A readiness check pointed at the proxy stops answering while the upstream is down.** The hold applies to
it exactly as to real traffic, so a probe that used to take its 502 at once now gets nothing until the
duration expires — and one with a shorter timeout cannot distinguish a proxy that has not started from a
proxy that is up and holding, because both give it the same silence. Probe the listener with a TCP connect
instead, or allow the check more time than the duration. A 3-second HTTP readiness loop against a held
port retried fifty times and hung for 160 seconds.

**It covers selecting an upstream, so it does nothing for a response already in flight.** Caddy's own
wording is how long to "try selecting available backends for each request", and selection happens before
any bytes reach the client; once headers and part of a body have gone out they cannot be retracted, and a
status the upstream returned is never retried. A long streaming route — a download that writes a whole
database out, an event stream — therefore gives a truncated body when its upstream restarts mid-response,
and no duration protects it.

Measured on v2.11.4 against a local upstream that declared a `Content-Length` of 100000 and took ten
seconds to write it. Killed three seconds in, the client got HTTP 200 with 26624 bytes and curl exited 18,
`CURLE_PARTIAL_FILE`; the same kill with no `lb_try_duration` at all gave 200 and 28672 bytes,
indistinguishable from it. **A truncated response carries a success status**, so a probe reading status
codes reports a healthy site through exactly this failure. What notices is the byte count against the
declared length, curl's exit, or a check on the content itself.

**Pick that content check by what it reads to, not by what it parses.** A `.tar.gz` missing gzip's last
eight bytes fails `gzip -t` ("unexpected end of file") and fails bsdtar's `-tzf`, while Python's `tarfile`
in `r:gz` mode iterates every member and reads all of their bytes without raising — a tar's end-of-archive
block precedes the gzip trailer, so a consumer satisfied by its members never reaches the part that would
have told it. Draining the decompressor is what raises, with `EOFError: Compressed file ended before the
end-of-stream marker was reached`, and reading the members is not draining it. Measured on python 3.14.7
against a 257-byte archive, which is small enough to decompress in one buffer and still was not caught.

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

**Ask the running proxy instead, wherever you can reach it.** Adapting a file says what that file means,
and the admin API says what the server is holding, which is the one that answers whether the retry is live
on the host right now — a file installed since the proxy last read it adapts correctly and is serving
nothing. The endpoint sits on `127.0.0.1:2019` inside the container, and the literal address is the part
that matters: these images map `localhost` to `::1` in `/etc/hosts` while Caddy's admin listener is IPv4
only, so the hostname form reports `Connection refused` from an endpoint that is perfectly up — measured
at exit 1 against exit 0 for the address, in the same container.

```bash
ssh <box> "docker exec <proxy-container> wget -qO- http://127.0.0.1:2019/config/" | python3 <filter>
```

**Filter it before it reaches a terminal, and print no more than the keys you came for.** A proxy's running
config carries whatever credentials its own plugins hold, an ACME DNS provider's API token among them. The
walk above, narrowed to each `reverse_proxy` handler's `dial`, `load_balancing` and `health_checks`, prints
one line per upstream — which on a shared proxy doubles as a census of which tenants hold the retry and
which still answer 502 through their own publishes.

## The publish that installs the directive is not protected by it

Check whether the deploy recreates the upstream before it installs the proxy config. In that order the
publish carrying the retry for the first time runs its own outage window under the config the proxy was
already holding, which is the one with no retry in it. A 200 afterwards and a `try_duration` in the
adapted JSON are both true at that point and neither says a request was ever held; the publish after it is
the first that exercises the setting.

The publish path these projects share has that order. Its script — `publish-ssh-compose.sh` in the
`publish` skill — brings the stack up with `docker compose up -d` in one step and reaches the vhost only in
the next, which covers all three of its shapes, since the gated gate call, the ungated co-tenant install
and the proxy-owner recreate all sit in that later step. A proxy-owner repo is no exception for having its
config reset into the checkout earlier: the running proxy keeps reading the old file until that step
recreates the container.

Prove the setting with a `docker restart <app-container>` under a per-second probe instead of waiting for a
publish. It isolates what is being tested, the proxy config staying put throughout, so the retry is the
only thing that can be holding a request: one such run held a request 11.36 s and answered it 200, with
zero 502s across 140 probes.
