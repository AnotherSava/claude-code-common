# Working out what held a Mac awake

Asking "why didn't this Mac sleep?" looks like a question about power settings and is
almost always a question about who was holding an assertion. `pmset -g log` answers it
completely, and its format has one trap that produces confident, wrong answers — a
subagent investigating this hit it and built a headline finding on top of it, and the
reconstruction below is what caught that.

The *lid* path is a separate kernel route no assertion reaches, and its companion file is
`~/.claude/learnings/macos-lid-close-sleep.md`. This file is about idle sleep.

## The live picture

```bash
pmset -g assertions      # who holds what right now, with how long each has been held
pmset -g                 # settings, plus a "sleep prevented by <procs>" attribution line
pmset -g log             # the history: Created / Released / ClientDied / TimedOut / Summary
```

The `sleep` and `displaysleep` lines of `pmset -g` name the processes responsible in
parentheses, which is the fastest route to a culprit and needs no log parsing at all:

```
 sleep                1 (sleep prevented by coreaudiod, coreaudiod, caffeinate, powerd)
 displaysleep         5 (display sleep prevented by parsecd)
```

## The trap: a duration is the span *ending* at its timestamp

Every `Created` / `Released` / `ClientDied` / `TimedOut` / `Summary` line carries an
elapsed time, and that time is **how long the assertion had been held when the line was
written** — so the interval is `[timestamp - duration, timestamp]`, not
`[timestamp, timestamp + duration]`.

This matters because a process that renews an assertion on a cycle writes one line per
renewal, and each line's duration covers the gap back to the previous one. Consecutive
renewals are therefore **contiguous**:

```
06:07:45 ... ClientDied ... 00:03:59   → covers 06:03:46–06:07:45
06:11:45 ... ClientDied ... 00:03:59   → covers 06:07:46–06:11:45
06:15:45 ... ClientDied ... 00:03:59   → covers 06:11:46–06:15:45
```

Read forward instead — treating each timestamp as a gap *opening* — and that unbroken
chain reads as a 3.9-minute lapse every four minutes. Measured 2026-09-26: exactly that
misreading produced a fabricated coverage gap, presented with a timestamp and a duration,
which survived into a structured report as the single piece of evidence for a conclusion.

Reconstruct properly, then merge:

```python
import subprocess, re, datetime as dt
log = subprocess.run(["pmset", "-g", "log"], capture_output=True, text=True).stdout
pat = re.compile(
    r'^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) [-+]\d{4}\s+Assertions\s+'
    r'PID (\d+)\(([\w-]+)\)\s+(\w+)\s+PreventUserIdleSystemSleep.*?'
    r'(\d{2}):(\d{2}):(\d{2})\s+id:(\S+)')

def intervals(proc, cap_minutes=None):
    iv = []
    for ln in log.splitlines():
        m = pat.match(ln)
        if not m:
            continue
        d, t, pid, name, act, hh, mm, ss, aid = m.groups()
        if name != proc:
            continue
        end = dt.datetime.fromisoformat(f"{d}T{t}")
        dur = dt.timedelta(hours=int(hh), minutes=int(mm), seconds=int(ss))
        if cap_minutes and dur > dt.timedelta(minutes=cap_minutes):
            continue                      # assertion-id reuse artifact
        iv.append([end - dur, end])
    iv.sort()
    out = []
    for s, e in iv:
        if out and s <= out[-1][1] + dt.timedelta(seconds=5):
            out[-1][1] = max(out[-1][1], e)   # merge; 5s absorbs respawn jitter
        else:
            out.append([s, e])
    return out
```

Two details that are not optional. **Key on `(assertion id, pid)` and cap implausible
durations** — ids are reused, and a reused id yields one interval spanning hours that
swallows every real gap. And **merge with a few seconds of slack**, because a
kill-and-respawn renewal leaves a sub-second hole that a coverage chart should not draw as a
gap — though on battery that hole is where the mid-turn deaths under "Claude Code's own
inhibitor" happen.

The `pmset -g log` history reaches back about **7 days**. Say so when reporting a rate: "none in the
log's reach" is a different claim from "never".

## Assertions that are derived, not requested

The system's `powerd` holds `PreventUserIdleSystemSleep "Powerd - Prevent sleep while display is on"`.
It is a *consequence* of the display being awake, not a request by anything — across a
full log it appears only as `Released` and `Summary`, **never once as `Created`**. So
chasing it leads nowhere; find whoever holds a `PreventUserIdleDisplaySleep` instead, and
`pmset -g`'s `displaysleep` line names them outright.

The same indirection shows up in audio: `coreaudiod` takes an assertion per open stream
and the line says whose, as `Created for PID: <pid>` plus a `Resources: audio-in` /
`audio-out` tag. A remote-desktop client with an open audio stream therefore holds the
machine awake three ways at once — its own display assertion, powerd's derived one, and
coreaudiod's on its behalf — while only the first is its own.

Other holders that turn up and mean nothing: `storagekitd` runs ~20-minute
`com.apple.diskmanagementd` holds under a fresh pid each time, and `sharingd` takes short
`Handoff` ones.

## Claude Code's own inhibitor

Claude Code holds `caffeinate -i -t 300` per session and respawns it on a 240s interval so
the 300s timeout never expires while it is wanted. In `pmset -g assertions` it shows as a
`PreventUserIdleSystemSleep` owned by a `caffeinate` child of the `claude` process. It is
**refcount-driven, not a timer**, and the refcount follows the session status. From the
2.1.251 binary:

```
status:S.isLoading||S.delegatedActive?"busy":"idle"
setInterval(()=>{if(this.refCount>0||this.pendingKillTimeout!==null)n("Restarting sleep inhibitor to maintain prevention"),this.killInhibitor(),this.spawnInhibitor()},Ptt)
```

The renewal kills before it spawns: `killInhibitor` sends the running `caffeinate` a
`SIGKILL`, and only then does `spawnInhibitor` start its replacement.

Three consequences worth knowing before building anything that tries to cover for it:

- **`delegatedActive` means background/subagent work holds it too**, so the refcount stays
  up for the whole of a long delegated run, with no silence bound anywhere in the
  mechanism.
- **The renewal loop stops when the refcount drops**, so an unbroken chain is evidence of a
  live turn rather than of a running process. The converse does not hold: every renewal
  leaves a hole, mid-turn included, and the lapse below fell into one.
- **Release is deferred by a ~30s `pendingKillTimeout`**, which is why coverage runs a
  little past the end of a turn and why sub-minute gaps at turn boundaries are expected
  rather than lapses.

### A mid-turn lapse sleeps the Mac on battery

A turn can die mid-stream with `API Error: Your computer went to sleep mid-response`.
Recounted on the Mac on 2026-09-26: nine sleeps did it between 2026-08-21 and 2026-09-24,
in six projects, and five of the nine killed only a subagent. Claude Code deletes
transcripts after 30 days by default, so the count is a floor. Read the battery and AC
idle-sleep timeouts with `pmset -g custom`: on the Mac these came from, idle sleep is one
minute on battery and disabled on AC, so on the charger none of this can happen. Plugging
in avoids it.

The 2026-09-24 death has its last assistant text stamped `17:04:20.522Z`, which is
10:04:20 at the Mac's -0700 offset. That day's `pmset -g log`, audio lines left out:

```
10:00:15 PID 4205(caffeinate) ClientDied PreventUserIdleSystemSleep ... 00:03:59 [System: PrevIdle DeclUser kDisp]
10:04:15 PID 8653(caffeinate) ClientDied PreventUserIdleSystemSleep ... 00:04:00 [System: No Assertions]
10:04:15 PID 527(powerd) Created InternalPreventSleep "com.apple.powermanagement.darkwakelinger" [System: SRPrevSleep kCPU]
10:04:16 Summary- [System: PrevIdle SRPrevSleep kCPU] Using Batt(Charge: 57)
10:04:20 PID 527(powerd) TimedOut InternalPreventSleep "com.apple.powermanagement.darkwakelinger" 00:00:05
10:04:20 Summary- [System: PrevIdle] Using Batt(Charge: 57)
10:04:20 Sleep    Entering Sleep state due to 'Idle Sleep':TCPKeepAlive=active Using Batt
```

The bracket at the end of each line is the *system aggregate* after the event. Both
`ClientDied` lines are renewals, four minutes apart. At 10:00:15 something else still held
idle sleep and the user was active, so the hole was covered. At 10:04:15 nothing was, the
aggregate hit `No Assertions`, and powerd started idle sleep at once: the
`darkwakelinger` is its five-second linger. Something held idle sleep again by 10:04:16
(`PrevIdle`; the log does not name the holder), and the machine slept at 10:04:20 anyway:
**an assertion arriving after idle sleep had begun did not cancel it.** So a renewal is
fatal when three things coincide: battery power, a user idle past the one-minute timeout,
and no other process holding idle sleep at that instant.

To find the incidents, grep the transcripts for the error, then read the sleep line and the
release just before it in the log. Search recursively, since subagent transcripts hold
most of the deaths, and anchor on the JSON field, or every transcript that merely discusses
the error counts too:

```bash
grep -rlE '"(text|content)":"API Error: Your computer went to sleep' ~/.claude/projects
pmset -g log | grep -E "Entering Sleep state|Wake from"
```

The error entry is stamped when the process next runs, not when the machine slept — the
2026-09-24 one reads `17:21:27Z`, the second of a two-second maintenance `DarkWake`
seventeen minutes later — so take the sleep time from the log.

### Bounding a replacement on silence

Anything that holds the assertion in its place needs a bound, because a session that hangs
with its process alive emits nothing and never leaves its working state — so an assertion
held while "any agent is busy" would never be released. **Bound it on silence rather than
on elapsed time.** Over 12,512 in-turn gaps sampled from 40 sessions (an assistant row to
the next assistant row or tool result), the median is 1.4s, p99 is 81s, and 17 exceed ten
minutes; the longest continuously-working stretch among the nine deaths above was 23.5
minutes. A cap on total hold therefore has to choose between bounding a hang and cutting a
genuinely long turn. A silence threshold bounds the first, touches the second only when a
live turn stays quiet for the whole window — one long tool call, or subagent work written
to a transcript nobody reads — and re-arms by itself when a merely slow session emits again.

Hold the replacement continuously, one assertion for the whole stretch, and never renew it
by respawning a process: that hole is what ended the 2026-09-24 turn.

The dashboard project's `idle_awake.rs` does this. It holds a plain
`PreventUserIdleSystemSleep` assertion while any session is `Status::is_live_work` — true
for one that is working or holding background work, **false** for one blocked on the user,
since an agent parked on a question has nothing to lose to a sleep — and releases it once
every busy session has been silent past `idle_awake_silence_ms`. It ships **on** because,
unlike the `pmset disablesleep` lever its lid-close sibling drives, the assertion is
neither privileged nor system-wide. That sibling, and the C calls for holding the assertion
yourself, are in `macos-lid-close-sleep.md`.

## Did it sleep at all?

Before attributing anything, establish whether a sleep happened. The event types are worth
counting rather than eyeballed, because the log is overwhelmingly `Assertions` lines:

```bash
pmset -g log | awk '{print $4}' | sort | uniq -c | sort -rn | head
pmset -g log | grep -E "Entering Sleep state|^.{25}Wake|DarkWake"
```

A long stretch with no `Sleep` line and assertion durations increasing monotonically with
no reset is a machine that never slept — and the monotonic durations are the independent
confirmation, since they would restart across a sleep.
