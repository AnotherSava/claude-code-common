# Rendering secrets from a manager onto a remote host

A box needs an env file — a systemd `EnvironmentFile`, a container env file — whose values live in a secret
manager. The obvious procedure (install the manager's CLI on the box, render in place) is the wrong one, the
write itself has a mode trap, and the whole thing is only ever exercised during a rebuild, when nobody is in a
position to debug it.

## Don't install the secret-manager CLI on the box those secrets protect

An account credential for a secret manager reaches every project and environment in that account. The file it
renders holds a handful of values scoped to one job. Putting the CLI — and therefore its token — on the box
inverts the blast radius: compromising the machine those few values protect now yields everything.

Render from a workstation and push over ssh. The box never holds a manager credential, and the absence is
deliberate, so say so in the runbook or someone will "fix" it by installing the CLI.

## Pipe over ssh; don't interpolate into a remote command

```bash
for k in KEY_A KEY_B KEY_C; do
  printf '%s=%s\n' "$k" "$(<manager> get "$k" --plain)"
done | ssh root@<host> 'umask 077; mkdir -p /etc/<app> && cat > /etc/<app>/env'
```

Values travel on stdin. They land in neither side's shell history and in no process argv, where `ps` would
show them to every user on the box. The remote command text names only paths.

## `umask 077` up front, not `chmod` afterwards

```bash
BAD:   ... > /etc/<app>/env && chmod 600 /etc/<app>/env
GOOD:  umask 077; ... | ssh root@<host> 'cat > /etc/<app>/env'
```

root's default umask is `022` on a stock Ubuntu, so the first form creates the file **0644** and tightens it
one step later. In between, the passphrase is world-readable to every process on the box. The window is short
and it is real. Confirm rather than assume, with throwaway files:

```bash
( umask 022; : > a ); ( umask 077; : > b )
stat -c '%a' a b     # Linux    -> 644 600
stat -f '%Lp' a b    # macOS/BSD -> 644 600
```

## Verify the render without moving secrets or touching the target

To confirm a documented render command still reproduces the live file, do **not** write a scratch copy to the
box. Compare digests instead — render locally into a hash, and ask the host for the hash of the file it
already has:

```bash
LOCAL=$(for k in KEY_A KEY_B KEY_C; do
  printf '%s=%s\n' "$k" "$(<manager> get "$k" --plain)"
done | shasum -a 256 | awk '{print $1}')
REMOTE=$(ssh root@<host> 'sha256sum /etc/<app>/env' | awk '{print $1}')
[ "$LOCAL" = "$REMOTE" ] && echo identical || echo DIFFER
```

Nothing sensitive leaves the workstation, the target is untouched, no cleanup is owed, and the answer is
stronger than a diff would give: byte-identical or not. It also answers *how the live file was originally
made* when nobody wrote that down — if the digests match, whatever was run then is equivalent to what the
runbook says now.

This is also the move when a permission classifier refuses the scratch-file write. Achieving the same
verification read-only is not slipping past a denial; it is a strictly smaller action that happens to be a
better test. See `claude-code-auto-mode-permissions.md`.

## Pre-flight the values, printing none of them

A value carrying an embedded newline, a stray CR, surrounding quotes, or an unresolved `${...}` manager
reference silently yields a malformed env file. All of that is checkable without revealing anything:

```bash
<manager> get "$k" --plain | wc -l          # 1 => single line, safe for KEY=value
V=$(<manager> get "$k" --plain); echo ${#V}  # length only
case "$V" in '${'*) echo UNRESOLVED;; esac
```

**A newline test written as `case "$V" in *"$(printf '\n')"*)` is broken and always reports a match.** Command
substitution strips trailing newlines, so `$(printf '\n')` is the empty string and the pattern degrades to
`*""*`, which every string matches. Count lines on the raw output with `wc -l`; don't pattern-match for a
newline through `$( )`.

## The rebuild-time landmine

This procedure runs exactly once per rebuild and is otherwise dead text, so an error in it survives
indefinitely. A runbook that calls a CLI the box does not have yields a unit that loads fine and a job that
cannot authenticate — every layer reports success. Run the commands a runbook quotes, on the machine it names,
rather than reading them and judging them correct.
