---
name: heartbeat
description: >-
  Give a scheduled job a dead-man's switch, so its silence is noticed — derive the grace from the
  job's own cadence, create the check through the healthchecks.io API, put the ping URL where the
  job's other credentials live, wire the exit codes onto the right endpoints, and prove it by
  watching the alarm fire. Also audits which scheduled jobs have no check at all.
  TRIGGER when: a scheduled job (backup, self-check, sync, report) has nothing that would notice it
  stopping; a heartbeat or dead-man's switch is being added, moved or diagnosed; a healthchecks.io
  check must be created or its grace chosen; someone asks how a job's failure would be noticed, or
  which jobs are unmonitored.
  DO NOT TRIGGER when: the task is provisioning the backup itself (that is `backup`, which hands
  over here at its last step); alerting for a web service's uptime rather than a scheduled job; or
  choosing where a secret lives (that is `doppler`).
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

# The dead-man's switch

A scheduled job cannot report its own absence. Every other check runs *inside* the thing being
checked, so when the thing stops, so do they — and a stopped check is indistinguishable from a
passing one. This skill installs the one mechanism that inverts that: an external monitor that
expects to hear from the job, and speaks when it does not.

It is a skill rather than a note because its failure modes are silent by construction. A check that
was never created, a grace copied from a neighbour, a URL pinged by hand before the job existed —
each leaves a green dashboard over an unwatched job, which is worse than an obviously absent one.

## Context
- Project root: !`git rev-parse --show-toplevel 2>/dev/null || pwd`
- Scheduled jobs here: !`find . -maxdepth 4 \( -name '*.timer' -o -name '*.service' -o -name 'backup*.sh' -o -name 'offsite*' -o -name 'crontab*' \) -not -path '*/node_modules/*' -not -path '*/.git/*' | head -20`
- Ping already wired: !`grep -rl -e 'hc-ping' -e 'HEARTBEAT_URL' -e 'healthchecks' . --exclude-dir=node_modules --exclude-dir=.git 2>/dev/null | head -10 || echo NONE`
- Doppler coordinates: !`cat doppler.yaml 2>/dev/null || echo "(no doppler.yaml — ask /doppler for this project's shard and config)"`

## Two channels, two questions

The distinction below is the whole design, and conflating the two is the mistake this skill exists
to prevent.

| Channel | Answers | Fires when |
|---|---|---|
| the verdict (mail, report, log) | did the job **pass**? | the job ran and judged itself |
| the heartbeat (this skill) | did the job **run at all**? | the monitor stops hearing from it |

So **the heartbeat fires on a failed run too.** Conflate them and a failing job looks dead while a
dead job looks failing — and those want opposite responses from whoever is woken.

**A heartbeat is the one check permitted to degrade quietly.** An unset or unreachable ping URL is a
note, never a failure: a heartbeat able to fail the job would turn a monitoring aid into an outage.
The exception is earned rather than convenient, because *the silence is itself the alarm* — an
unsent ping is exactly what the monitor reports. Nothing else gets this exemption.

## The shape

| Piece | Where |
|---|---|
| the check | healthchecks.io, named `<machine>-<job>` |
| the ping URL | the **job's own** Doppler config, beside its other credentials |
| the API key | `HEALTHCHECKS_API_KEY` in Doppler `tools`/`prd` — Claude's cross-project store |
| the ping | in the job, on every **completed** run, success and failure alike |
| the grace | derived from the job's cadence — see `references/grace-derivation.md` |

**The inventory of what is and is not monitored does not belong in this repository, which is
public.** Check names, ping URLs, and which machines are unwatched are a map of where to attack and
where nobody is looking. They live in the private repo that owns the thing being watched. This file
carries the method only.

**A ping URL is a credential.** Anyone holding it can forge a heartbeat, or silence a real alert by
pinging on the job's behalf. Treat it like a token: never in a commit, never printed to a terminal,
never in a transcript. `scripts/hc.py` is built so it never prints one.

## Process

### 1. Establish what needs watching, and what already is

From **Scheduled jobs here** and **Ping already wired**, decide which case this is:

- **Nothing wired** — the normal case; continue.
- **Something wired** — read it first. A job that already pings may have the wrong grace, or ping
  only on success (which quietly converts the heartbeat into a verdict channel — see step 5).

For an audit across a whole account rather than one job:

```bash
python3 ~/.claude/skills/heartbeat/scripts/hc.py list
```

That lists every check the key can see with its cadence, grace and last ping, and flags the two ways
a check can look configured while being incapable of raising an alarm:

- **`last_ping=NEVER`** (status `new`, `n_pings=0`) — the switch is *not armed*. A check that has
  never been pinged has no due time, so it stays in `new` forever and **can never go down**. This is
  the loudest possible audit finding, not a transient state that will resolve itself: nothing is
  watching that job and nothing ever will until something pings it.
- **no integrations** — it can go down, and nobody is told.

The API key is **per-project** on healthchecks.io — there is no account-wide key — so this audits one
project, and a job whose check lives in another project reads as absent. Report which project was
audited rather than "all checks": an audit that cannot see a check must say so rather than counting
it as missing, and one that cannot see a *project* must not imply it covered everything.

Name the job's cadence explicitly before continuing: the trigger, its jitter, and — for anything not
on an always-on machine — how long the machine is typically off. Step 2 cannot be done without it.

### 2. Derive the grace, or establish that it cannot be derived

**The grace does not start at the last ping — it starts when the check is already late.** A check is
late at `last_ping + period` and goes down at `last_ping + period + grace` (for a scheduled check,
down at `scheduled_time + grace`). The period is therefore *already in the deadline*, and a grace
chosen as though it were measured from the last ping double-counts it by a whole period. This is the
single easiest thing to get wrong here, and it fails in the direction that looks fine: a too-large
grace never false-alarms, so nothing ever tells you the switch stopped covering a single miss.

Work with the deadline, not the grace, and the two bounds are:

```
period + grace  >  longest ordinary gap     ->  grace >  jitter
period + grace  <  gap after ONE missed run ->  grace <  period - jitter
```

Worked, for a daily timer with 1h of jitter — ordinary gap up to 25h, the ping after one miss as
early as 47h:

```
grace > 1h  and  grace < 23h      band (1h, 23h)     choose ~12h
```

State the inputs, the inequalities and the chosen value. Sit near the middle of the band, and sanity
check the result by writing down the actual deadline (`24h + 12h = 36h`) and confirming it falls
between 25h and 47h.

**If the machine is not always on, the band is empty** — the governing term is how long a human left
it off, which appears in no config, moves both bounds together, and has no upper limit. Do not pick a
round number and present it as arithmetic. Read `references/grace-derivation.md`: it covers why the
empirical rescue is not one, and the predicate to use instead (*hours the machine has been up since
the last success*, which is derivable from inputs the system reads).

Do not copy a grace from a neighbouring job because the cadences look similar, and do not align it
with any other threshold for tidiness — the reference explains what that silently changes.

### 3. Create the check

Show the exact request first and **wait for the user** — this writes to their account.

```bash
python3 ~/.claude/skills/heartbeat/scripts/hc.py upsert \
  --name '<machine>-<job>' --grace-seconds <N> \
  --schedule '<cron or OnCalendar>' --tz '<IANA zone>' --channels '*' \
  --tags '<machine> <kind>' --desc '<what silence here means>' --dry-run
```

Re-run without `--dry-run` on approval. Notes that matter:

- **`--channels` is not optional in practice.** The API assigns **no** integrations by default —
  unlike the web UI — so a check created without it goes red on the dashboard and mails nobody. That
  is this skill's own nightmare produced by its happy path, and it surfaces only at step 6 after you
  have deliberately broken the job and waited out a grace period for an alert that could never
  arrive. `hc.py` defaults it to `*` for that reason; pass `--channels ''` only to assign none
  deliberately.

- **Name it `<machine>-<job>`.** A bare `backup` is a claim on a namespace shared with every other
  machine's backup; the second one to arrive either collides or, worse, quietly reuses the first.
- **Give a schedule, not a period, wherever the job runs on a calendar** (weekdays only, a fixed
  clock time). A flat period counts an expected weekend of quiet as silence. `--schedule` accepts a
  cron expression or a systemd `OnCalendar` expression, so a timer's cadence can be transcribed
  rather than translated.
- **Never send both.** The API keeps the schedule and silently discards the period. `hc.py` refuses
  to send both for that reason.
- The upsert is keyed on the name: re-running updates rather than duplicating (HTTP 201 created,
  200 updated). Read which one you got — an unexpected 200 means the name was already taken.

### 4. Put the ping URL where the job's other credentials live

```bash
python3 ~/.claude/skills/heartbeat/scripts/hc.py store-url \
  --name '<machine>-<job>' --doppler-project '<shard>' --doppler-config 'prd_<app>'
```

It fetches the URL and pipes it into Doppler without printing it, under the key **`HEARTBEAT_URL`**
(override with `--key`). Use that name in the job unless the project already has its own.

**The job's own config, never a shared monitoring one.** A rebuild that restores the job restores its
monitoring in the same step. And an alert channel belonging to one system must not carry another
system's failures: whoever learns that a subject line sometimes means something else is the person
who ignores the real one. Ask `/doppler` for the coordinates rather than deriving them.

**Then deliver it to the machine, and make its absence refuse.** Doppler is where the value lives, not
where the job reads it, and this is the step that silently does not happen — every symptom of skipping
it looks like success. Three things, in order:

1. Re-render the job's credential file or container environment from Doppler so `HEARTBEAT_URL`
   actually reaches the machine. If this skill was entered from `backup`, that file was written at
   *its* step 5, before this key existed — so it must be rendered again, not assumed current.
2. Add the key to whatever list makes a deploy refuse without it, if the project has one. A heartbeat
   that degrades quietly (as it must) cannot report its own absence, so the *deploy* has to.
3. Confirm the job can see it — one run, and the ping arrives. Until a first ping exists the check
   sits in `new` and can never alert, which is indistinguishable from healthy on the dashboard.

### 5. Wire the ping

On every **completed** run, success and failure alike. Map the job's outcomes onto endpoints:

| Outcome | Endpoint | Why |
|---|---|---|
| success | `$HEARTBEAT_URL` | the plain endpoint means "ran and passed" |
| any failure | `$HEARTBEAT_URL/$exit_code` | the monitor applies 0-success / non-zero-failure itself, so the rule is not re-derived in the script, and the code stays visible in the events log |
| ran, produced something degraded | `$HEARTBEAT_URL/$exit_code` — the failure side | see below |
| a note worth recording that changes nothing | `$HEARTBEAT_URL/log` | records an event without changing state |

**A partial result goes on the failure side.** The tempting third option is to treat "it ran and
produced something incomplete" as success, and it is wrong in the direction that costs most: under
"did it run" semantics, a job stuck in a permanently-degraded state pings green forever while its
output silently rots. The dividing line is whether the degradation touches the thing the job exists
to produce. If it does, it is a failure with a label, not a note.

**POST the evidence as the ping body.** The monitor stores the first 100 kB (10 kB on a self-hosted
instance) and shows it on the event, so exit code, artifact id, counts and any drill result belong
there. Without it, every failure ping looks alike. This is also usually the first thing that ever
*reads* a status file the job was already writing.

Ping *last*, after the job has judged itself — a heartbeat sent before the work is done reports on
work that has not happened.

### 6. Watch it fire — and do not ping it by hand first

**Do not ping the URL from a workstation to "check that it works".** A new check sits silent until
its first ping, and that ping starts the clock. Ping it while nothing is yet feeding it on a
schedule and it goes down one period-plus-grace later, mailing about a job that was never being
watched — a false alarm in the one channel whose entire value is that it only speaks when something
is wrong. Let the job send the first one.

Then break it deliberately, because a dead-man's switch nobody has watched fire is exactly the
assertion it replaces. Stop the job, wait past the deadline, then start it again.

**Budget the real wait: `period + grace` from the last ping**, not the grace alone (for a scheduled
check, grace after the next scheduled time). Expecting the alert a grace period after stopping the
job means giving up early and concluding the switch is broken when it is merely not due yet.

**You must see** three things, and the third is the one usually skipped:

1. the alert arrive after the grace;
2. the check return to *up* once the job runs again;
3. a **recovery** notice.

A switch that alerts but never says it recovered leaves you unable to tell *fixed* from *still
broken, and the mail is broken too*.

### 7. Record it

In the project's own deploy or runbook doc, one line: what silence on this check means, what the
grace is and which inputs it was derived from, and where the ping URL lives. If the grace could not
be derived, say so there in those words — an admitted risk budget stays re-examinable, while a
number presented as arithmetic does not.

Where the project has a private inventory of what is monitored, update it there, not here.

## Out of scope

- Do NOT put a check name, ping URL, or a list of unmonitored machines in this repository
- Do NOT ping a check by hand before its job is running on a schedule
- Do NOT create, pause or delete a check without showing the request and getting a yes
- Do NOT reuse one check for two jobs or two machines, or one project's alert channel for another's
- Do NOT make the heartbeat able to fail the job it watches
- Do NOT provision the backup itself — that is `backup`
