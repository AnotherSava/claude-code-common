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
kill-and-respawn renewal leaves a sub-second hole that is not a lapse.

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

Claude Code holds `caffeinate -i -t 300`, respawned on a 240s interval so the 300s timeout
never expires while it is wanted. It is **refcount-driven, not a timer**, and the refcount
follows the session status. From the 2.1.251 binary:

```
status:S.isLoading||S.delegatedActive?"busy":"idle"
if(this.refCount>0||this.pendingKillTimeout!==null)n("Restarting sleep inhibitor to maintain prevention")
```

Three consequences worth knowing before building anything that tries to cover for it:

- **`delegatedActive` means background/subagent work holds it too**, so a long delegated
  run is covered for its whole duration with no silence bound anywhere in the mechanism.
- **The renewal loop stops when the refcount drops**, so the chain is evidence of a live
  turn rather than of a running process — gaps in it line up with stretches where nothing
  was executing.
- **Release is deferred by a ~30s `pendingKillTimeout`**, which is why coverage runs a
  little past the end of a turn and why sub-minute gaps at turn boundaries are expected
  rather than lapses.

A lapse into sleep does look exactly like you would expect when it happens — the release
line carries `[System: No Assertions]` and the sleep follows within seconds:

```
10:04:15 ... ClientDied PreventUserIdleSystemSleep "caffeinate command-line tool" 00:04:00 ... [System: No Assertions]
10:04:20 Sleep    Entering Sleep state due to 'Idle Sleep':TCPKeepAlive=active Using Batt
```

That bracket at the end of each line is the *system aggregate* after the event, so
`[System: No Assertions]` on a release is the one to grep for when hunting a sleep that
killed something mid-run.

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
