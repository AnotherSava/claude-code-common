# Keeping a Mac awake with the lid closed

How to stop macOS sleeping when the laptop lid shuts, why the obvious approaches
all fail, and what the escalation costs. Verified on macOS 26.5.1 / Apple M4 in
July 2026 against Apple's shipping SDK headers, the open-source PowerManagement
and XNU sources, compiled probes, and `pmset -g log` on real hardware.

Much of the advice online about this is wrong, including the README of the
reference project most people copy. The corrections are flagged below.

## The short version

Lid close is **not** idle sleep. It is a separate kernel path ("Clamshell
Sleep"), and no power assertion available to a third-party process affects it.
The only lever is `sudo pmset -a disablesleep 1`, which is a **system-wide sleep
kill switch** — it also disables thermal-emergency and low-battery sleep, and it
**survives reboot**. Any use of it must be bounded and must have recovery paths.

## Why no power assertion works

Apple's own header says so. `IOPMLib.h`, on `kIOPMAssertPreventUserIdleSystemSleep`:

> The display may dim and idle sleep while [this] is enabled, but the system may
> not idle sleep. The system may still sleep for **lid close**, Apple menu, low
> battery, or other sleep reasons.

The other candidates are dead ends too:

- `kIOPMAssertionTypeNoIdleSleep` — deprecated alias for the above, inherits the
  same limitation.
- `kIOPMAssertionTypePreventSystemSleep` — the header calls it "not supported in
  any OS X releases", which is *stale* (it does create, and `caffeinate -s` uses
  it), but `caffeinate(8)` documents it as "valid only when system is running on
  AC power", and it does not affect the lid path regardless.
- `kIOPMAssertionTypeDenySystemSleep` — **not a public constant**; absent from the
  entire SDK. The string is accepted by powerd as an alias for
  `PreventSystemSleep`, but citing it as public API is folklore.

### The gate, in powerd's source

`PMAssertions.c` → `setClamshellSleepState()` disables clamshell sleep only for:

1. `isDesktopMode()` — an external display (see "the free path" below), or
2. an assertion carrying `kAssertionLidStateModifier`.

That modifier bit is settable only via the private property
`kIOPMAssertionAppliesOnLidClose`, and `callerIsEntitledToAssertion()` gates it
behind the Apple-private entitlement `com.apple.private.iokit.assertonlidclose`.
Third parties cannot obtain `com.apple.private.*` entitlements.

Verified empirically: a compiled, unentitled, ad-hoc-signed probe calling
`IOPMAssertionCreateWithProperties` with `AppliesOnLidClose=true` across seven
assertion types returned `0xe00002c1` (`kIOReturnNotPrivileged`) every time.

```bash
# Confirm the entitlement string is in the shipping binary:
strings /System/Library/CoreServices/powerd.bundle/powerd | grep assertonlidclose
# → com.apple.private.iokit.assertonlidclose

# Confirm caffeinate does NOT hold it — so no caffeinate flag can help:
codesign -d --entitlements - /usr/bin/caffeinate 2>/dev/null | grep -i lidclose
# → (no match)
```

### caffeinate flag → assertion mapping

Confirmed by running each flag and reading `pmset -g assertions`:

| Flag | Assertion |
|------|-----------|
| `-d` | `PreventUserIdleDisplaySleep` |
| `-i` | `PreventUserIdleSystemSleep` |
| `-m` | `PreventDiskIdle` |
| `-s` | `PreventSystemSleep` (AC power only) |
| `-u` | `UserIsActive` (defaults to a 5s timeout without `-t`) |

`caffeinate -w <pid>` blocks until that pid exits, then drops the assertion —
a useful poll-free deadman primitive.

Assertions are **per-process** and are reaped by the OS when the owner dies,
including on `SIGKILL`. A crashed app cannot wedge the machine awake. They can
be held indefinitely (timeout is optional). Releasing an already-released id
returns `kIOReturnBadArgument` (`0xe00002c2`) rather than crashing.

## The free path: desktop mode

An external display plus an input device puts the Mac in desktop/clamshell mode,
which disables clamshell sleep with **no root and no code at all**. On Apple
Silicon this works on battery too (`gDesktopModeOnBattery`), unlike the Intel-era
rule that demanded the power adapter. If a docked external display is available,
this is strictly better than anything below.

## The only real lever: `pmset disablesleep`

`sudo pmset -a disablesleep 1` sets the kernel's `userDisabledAllSleep`. In XNU's
`IOPMrootDomain.cpp`, `checkSystemSleepAllowed()` tests that flag in the block
commented "Conditions that prevent idle **and demand** system sleep" — *before*
and independent of `sleepReason`. Clamshell sleep is a demand sleep, and there
are only two callers of `checkSystemSleepAllowed`, so nothing routes around it.

Note it is **undocumented**: `disablesleep` appears nowhere in `man pmset` and is
absent from `pmset -g cap`. The string is present in the binary and the property
is live in `IOPMrootDomain`.

### Three things that make it dangerous

1. **It is a kill switch, not a lid switch.** `userDisabledAllSleep` blocks
   *every* sleep request, including thermal-emergency and low-battery sleep
   (`privateSleepSystem` → `checkSystemSleepEnabled` → `kIOReturnNotPermitted`).
   A closed laptop in a bag with this set will neither sleep nor protect itself.
   Bound every hold with a timer and a battery floor.

2. **It survives reboot.** ← *This is the correction that matters most.*
   `pmset.m` comments "We write the settings to disk here";
   `IOPMSetSystemPowerSetting` persists to
   `/Library/Preferences/com.apple.PowerManagement.plist`; and powerd's
   `PMSettings_prime()` re-applies it into the kernel at every boot. Widely
   repeated guidance that "a reboot clears it" — including the Sleepless
   project's README, the most-copied reference implementation — is **false**.
   Ship a boot-time reset job; do not rely on restart as the recovery path.

3. **Root is enforced by uid, not entitlement.** `IOPMEnergyPrefs.c`:
   ```c
   if ((getuid() != 0) && (geteuid() != 0)) { return kIOReturnNotPrivileged; }
   ```
   No code-signing identity, entitlement, or paid Developer ID changes this.
   Don't go buying a certificate hoping to avoid the escalation.

## Reading the truth from IORegistry (no root needed)

```bash
ioreg -c IOPMrootDomain -r -d 1 | grep -E "SleepDisabled|AppleClamshellState"
ioreg -c AppleSmartBattery -r -d 1 | grep -E '"(CurrentCapacity|MaxCapacity|ExternalConnected)"'
```

| Property | Service | Trustworthy? |
|---|---|---|
| `SleepDisabled` | `IOPMrootDomain` | **Yes** — the exact property `pmset` writes and `checkSystemSleepAllowed` reads. Verify arms against this. |
| `AppleClamshellState` | `IOPMrootDomain` | **Yes** — `Yes` when the lid is shut. Corroborated by `Wake ... due to ... lid` in `pmset -g log`. |
| `AppleClamshellCausesSleep` | `IOPMrootDomain` | **No — do not trust.** Observed reading `No` while `pmset -g log` went on recording `Entering Sleep state due to 'Clamshell Sleep'` on the same machine. It reflects powerd's derived policy state, not a live guarantee. |
| `ExternalConnected` / `CurrentCapacity` | `AppleSmartBattery` | Yes. Absent entirely on a desktop Mac — treat a missing service as "no battery", not as an error. |

`AppleClamshellCausesSleep` looks like the obvious oracle for "would a lid close
sleep me right now?" It is not. Verifying a veto against it will happily vouch
for a hold that never took.

### Ground truth for did-it-work

```bash
pmset -g log | grep "Clamshell Sleep"
```
Every unprotected lid close writes one line. Their **absence** across a lid-close
window is the proof the veto held. Note the event is edge-triggered at the moment
the lid shuts: suppress that edge and the machine later falls to ordinary *idle*
sleep rather than snapping shut when the hold ends.

## Escalating without nagging the user: the sudoers pattern

Apple's TN2065 recommends exactly this, and it is what Amphetamine's "Power
Protect" does (`/private/etc/sudoers.d/amphetamine_powerProtect`). A per-toggle
`osascript … with administrator privileges` is *not* viable as a steady-state
path: auth caches for only five minutes and is keyed to the exact script text,
so the on- and off-scripts each prompt separately.

```
someuser ALL=(root) NOPASSWD: /usr/bin/pmset -a disablesleep 0, /usr/bin/pmset -a disablesleep 1
```

Rules learned the hard way:

- **No dot in the filename.** `sudo` skips files in an include directory whose
  names contain `.` or end in `~`. Naming the drop-in after a bundle id
  (`com.example.app`) leaves the grant permanently, silently inert.
- **Pin the argv.** sudo matches arguments literally when they are specified, so
  the rule above permits exactly two commands and cannot be widened into a root
  shell. The rule and every call site must then agree character-for-character —
  build both from one constant.
- **No `Digest_Spec`.** `/usr/bin/pmset` lives on the sealed, read-only system
  volume under SIP, so binary substitution isn't a threat, and a hash would break
  the grant on every OS update.
- **Validate before installing**: write to a temp file, `visudo -cf "$T"`, then
  `chown root:wheel`, `chmod 0440`, and `mv` into place.
- **The privileged script must be a single line.** AppleScript string literals
  cannot contain raw newlines, so a heredoc is impossible inside
  `do shell script "…"`. Emit multi-line files with `printf '%s\n' 'a' 'b' > file`.
- Escape for AppleScript by doubling backslashes then escaping `"`. Verify the
  whole pipeline unprivileged against scratch paths before ever handing it to
  root — `osascript` + `visudo -c` + `plutil -lint` will catch quoting bugs
  without a password prompt.

Alternatives, all ruled out: `SMAppService.daemon` (macOS 13+) requires a
Developer ID **and** notarization; `SMJobBless` is deprecated *and* needs matching
Developer ID designated requirements. A hand-installed plist in
`/Library/LaunchDaemons` **does** work for an ad-hoc-signed app — launchd does
not signature-verify legacy daemons — which is what makes the boot-reset job
below viable.

## Recovery layers

Because the flag is persistent, global, and safety-suppressing, one recovery path
is not enough:

1. **A bounded lease** — the primary control.
2. **A battery floor** — never arm below it; release if crossed. The low-battery
   emergency sleep is suppressed while armed.
3. **A detached deadman** — `sh -c 'while kill -0 <pid>; do sleep 2; done; <clear>'`,
   spawned detached so it reparents to launchd. Survives `SIGKILL`, Force Quit,
   and `std::process::exit()`, which bypasses language-level destructors.
4. **A boot-reset LaunchDaemon** — `RunAtLoad`, running `pmset -a disablesleep 0`.
   Mandatory, because of the reboot persistence above. Its `Program` is an Apple
   platform binary, so the installing app's own signature is irrelevant.
5. **Clear-on-start** — always release at app startup before anything can arm.

Manual teardown:

```bash
sudo launchctl bootout system /Library/LaunchDaemons/<label>.plist
sudo rm /Library/LaunchDaemons/<label>.plist
sudo rm /etc/sudoers.d/<name-with-no-dot>
sudo pmset -a disablesleep 0
```

## Design note: the veto must be pre-armed

A lid close sleeps the machine essentially instantly, so there is no window in
which to react to `AppleClamshellState` changing. Anything that wants to survive
a lid close must already be armed before it happens.

The countdown, however, *can* be timed against the lid, because once armed the
machine stays up to observe it. Anchoring a lease to the lid-close edge rather
than to when the work started is what makes "15 minutes" mean fifteen minutes of
carrying the machine shut, instead of expiring two minutes after someone closes
the lid thirteen minutes into a task.

## Aside: Claude Code holds its own caffeinate

Claude Code spawns `caffeinate -i -t 300`, renewed while a session is active. So
plain *idle* sleep during an agent run is already largely covered, and adding a
`PreventUserIdleSystemSleep` assertion alongside it is mostly redundant. The lid
case is the real gap — and the only one that needs root.
