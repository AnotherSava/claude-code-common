# Hardening sshd on a remote box without locking yourself out

Tightening ssh on a machine you can only reach *by* ssh. The changes are small; the failure mode is
total and needs out-of-band recovery. This is the order and the verification that make it safe.

## Measure before deciding, and bound the claim to what you measured

```
journalctl -u ssh --since "7 days ago" | grep -c "Failed password"
journalctl -u ssh --no-pager | grep "Accepted password"     # WHOLE retained journal, not a window
journalctl -u ssh --no-pager | grep -c "Accepted publickey"
journalctl -u ssh --no-pager -o short-iso | head -1          # how far back the journal actually goes
```

"No password logins in 7 days" and "no password logins ever" are different claims and the second is the
one that decides whether disabling password auth removes a fallback. Check how far the journal reaches
before generalising — a box can be older than its journal, and that gap supports no claim at all.

**The decisive comparison is not the count, it's the ordering.** One accepted password login looks like a
fallback someone relies on. Check what came next: if the first `Accepted publickey` is from the *same
source address* seconds later, that password login was the bootstrap that installed the key replacing it,
and nothing has used password auth since. Same number, opposite conclusion.

## Check for a drop-in before editing the main file

```
grep -n "^Include" /etc/ssh/sshd_config
ls -la /etc/ssh/sshd_config.d/
```

Cloud images routinely ship `/etc/ssh/sshd_config.d/50-cloud-init.conf` setting `PasswordAuthentication
yes`. Because `Include` sits near the top and sshd takes the **first** value obtained for a keyword, that
drop-in beats anything further down the main file. Edit the wrong one and the change appears applied and
does nothing. `sshd -T` is the arbiter — it prints the effective config, not the file's intent.

Where no drop-in exists, prefer editing the main file over adding one: a drop-in silently overriding a
line that still reads `yes` leaves two places disagreeing, and the next reader believes the file.

## Order the steps by blast radius

1. **`PasswordAuthentication no`** — safe when the measurement above shows key-only use. Cannot lock out a
   key holder.
2. **Narrow the firewall to the private network** — this is the dangerous one, and the only one needing a
   recovery plan.
3. **`PermitRootLogin prohibit-password`** — do it last. Use `prohibit-password`, **not `no`**, when every
   login is root-by-key and no non-root admin account exists; `no` locks out everyone.

Validate and reload rather than restart, every time:

```
sshd -t && systemctl reload ssh
```

## For the firewall step, arm a self-healing revert

Do not rely on a provider console you have never opened. Make recovery empirical:

```
systemd-run --on-active=5min --unit=ufw-failsafe /usr/sbin/ufw allow OpenSSH   # arm
ufw allow in on tailscale0 to any port 22 proto tcp comment "ssh: private only"
ufw --force delete allow OpenSSH
# ...verify...
systemctl stop ufw-failsafe.timer                                             # cancel once proven
```

Add the new rule *before* deleting the old one, and scope by **interface** (`in on tailscale0`) rather
than source CIDR — an interface cannot be spoofed from outside. Note the caveat: interface rules match by
name, so anything that recreates the adapter under a different name silently stops matching.

## Verify from a NEW connection — the established one proves nothing

Both an sshd reload and a firewall change leave existing sessions untouched. Testing in the shell you are
already in will succeed no matter how badly you have broken access.

```
ssh -o BatchMode=yes user@host 'echo ok'                                  # fresh connection: must work
ssh -o BatchMode=yes -o PubkeyAuthentication=no \
    -o PreferredAuthentications=password user@host true                   # must be refused
ssh -o ConnectTimeout=8 user@<public-ip> true                             # must time out
curl -sS -o /dev/null -w '%{http_code}\n' https://<a-site-on-the-box>/    # unrelated services unaffected
```

A refused password attempt should read `Permission denied (publickey)`. A closed firewall port gives a
timeout rather than a refusal, since the default policy drops rather than rejects.

## What remains after, and is easy to forget

### Test the console in this order, and know what it actually gives you

A provider "console" is usually a **VNC view of the virtual monitor** — a getty login prompt, not a root
shell. It therefore needs the OS's own root password, which the hardening above made irrelevant to ssh and
which may never have been recorded. So:

1. **Log into the panel first.** Every recovery branch is gated on it and it is free to test. Note whether
   2FA is enrolled and where its recovery codes live — the panel is now on the critical path.
2. **Set a known root password over the live ssh session.** `passwd` is zero downtime: no reboot, no
   service restart, nothing re-reads `/etc/shadow`. Store it in the secret manager in the same action.
   `passwd -S root` reports `P`/`L`/`NP` for set/locked/empty, and a `P` dated to provisioning day usually
   means the value is whatever the provider mailed — which is not a value anyone has.
3. **Then log in at the console** and confirm that password works there.

**Choose it for typeability, not entropy.** The console may render a different keyboard layout than yours
(QWERTZ is common on European hosts), hides the field while typing, and blocks paste. Letters and digits
only, avoiding characters that transpose between layouts. It cannot be brute-forced over the network — ssh
password auth is off and the console sits behind the panel login — so a 40-character monster you mistype
four times in an emergency is strictly worse than a memorable 16.

Confirm the console can reach a prompt at all: `getty@tty1` or `serial-getty@ttyS0` active, a `console=`
entry on `/proc/cmdline`, no `/etc/securetty` restricting root, and at least one account with a login shell.

### The branches that skip the OS credentials cost downtime

Panel-side password reset and rescue-system boots typically require the server **powered off** first, so
they cannot be exercised casually. If a reboot is already pending, that window is when to test them — the
power-off is paid for either way. Take a provider snapshot first where one is offered; it converts
"however long recovery takes" into a revert.

Watch for a bootloader that will not help: check whether `grub.cfg` sets `timeout=0` inside the
`recordfail` branch. If it does, a failed boot shows no menu and will not fall back to the previous kernel
on its own, leaving the rescue system as the only route — another reason to have proven it.

**Measured once the branches were actually exercised**, and three of these were better or worse than the
documentation implied:

- **The rescue system may hand you root at the console with no credential at all.** A Grml-based rescue
  drops to a root shell on a keypress. So that branch survives losing the panel's one-time password, and it
  is genuinely independent of the OS root password you set above — the two tests are not redundant.
- **A rescue system usually takes the production public IP, with sshd up and the firewall disabled.** That
  is the exact posture the hardening removed, on an address that is being probed continuously. Verify it
  from off-box (the host key it presents should match the one the console printed — that proves the console
  and the network endpoint are the same machine), then get out. Do not leave a rescue image running.
- **Mount the real root while you are in there** (`mount /dev/vda1 /mnt && ls /mnt`, expect `etc opt var`).
  A rescue shell that cannot reach the disk is the half of the branch that does not help.
- **Provider snapshots are often copy-on-write and effectively instant**, regardless of disk size. Measure
  it once: if it is instant, "snapshot first" stops being a cost-benefit call and becomes unconditional.

### Upgrading the daemon that IS your access path — detach it from the session

Upgrading tailscaled, wireguard, sshd or anything else you are connected through restarts it mid-`dpkg`.
If your ssh dies at that moment, dpkg is interrupted and apt is left wedged needing
`dpkg --configure -a` — from a box you can no longer reach. Run it decoupled from the session instead, so
the transaction completes whether or not your connection survives:

```
systemd-run --unit=pkg-upgrade --collect --property=Type=oneshot \
  --setenv=DEBIAN_FRONTEND=noninteractive \
  /usr/bin/apt-get -y -o Dpkg::Options::=--force-confold install <pkg>
```

Then reconnect and read `systemctl show pkg-upgrade.service -p Result -p ExecMainStatus` plus
`journalctl -u pkg-upgrade.service`. Confirm with `dpkg --audit` (empty means nothing half-configured).
Hold it back from a bulk `upgrade` first (`apt-mark hold`) and do it alone, so if anything breaks the cause
is unambiguous rather than one of twenty packages.

### Removing a package can make a *different* package rewrite something

Removing a package hands its role to whatever remains, and that survivor's postinst may then run. Removing
the legacy BIOS `grub-pc` from a UEFI machine triggered `grub-efi`'s postinst to re-run `grub-install`,
rewriting the EFI binaries on the ESP — a prediction that "removing an unused package cannot affect what
boots" was simply wrong.

The remedy is not to avoid the removal but to stop predicting: capture the relevant state before, diff it
after, and verify the rewrite is legitimate rather than merely present.

```
efibootmgr -v > /tmp/efi.before; ls -l /boot/efi/EFI/*/ > /tmp/esp.before
# ...the change...
diff /tmp/efi.before <(efibootmgr -v)
sha256sum /boot/efi/EFI/ubuntu/grubx64.efi /usr/lib/grub/x86_64-efi-signed/grubx64.efi.signed
```

Matching checksums against the packaged signed binary prove it wrote what it should have. Matching *sizes*
do not — a same-length rewrite is exactly the case that slips through an `ls -l` comparison.

### A package upgrade can corrupt `grubenv`, and only a failed unit says so

Observed 2026-08-30: `systemctl --failed` was empty, an ordinary `apt-get upgrade` ran, and afterwards
`grub2-common.service` failed with `grub-editenv: error: invalid environment block`. The file was still the
correct 1024 bytes; its contents were not a valid environment block. Grub tolerates this at boot by falling
back to defaults, so nothing would have surfaced until someone looked.

The remedy is one command, and worth doing before any planned reboot rather than after:

```
grub-editenv /boot/grub/grubenv list      # errors if invalid
cp -a /boot/grub/grubenv /boot/grub/grubenv.corrupt-$(date +%Y%m%d)
grub-editenv /boot/grub/grubenv create
systemctl restart grub2-common.service    # must reach Result=success
```

The general lesson is the sequencing one: after any upgrade that touches boot artifacts — grub, initramfs,
the kernel — run `systemctl --failed` **before** rebooting. `reboot-required` is not set for most of them,
so nothing prompts you, and a boot-time defect discovered weeks later is attributed to whatever happened
most recently instead of to the upgrade that caused it.

## What remains after, and is easy to forget

Narrowing ssh to a private network makes the provider's console the sole remaining way in. A failsafe
proves recovery for *that change* and then expires. Confirm the console opens, gives a root shell, and
that its credentials are recorded somewhere findable — while everything is still healthy. The moment you
need it is the moment you cannot test it.
