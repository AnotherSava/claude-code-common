# Auto-mode permission denials — what they mean and what they don't

In auto mode a classifier decides, per Bash call, whether to run it. A denial reads:

```
Permission for this action was denied by the Claude Code auto mode classifier.
```

Three things about it are easy to get wrong, and getting them wrong wastes a lot of turns.

## It judges per COMMAND, not per category

The tempting model — "state-changing calls to production or third parties are blocked" — is false. Observed in
one session, against one box and one set of credentials, all with the user's explicit approval:

| Command | Verdict |
| --- | --- |
| `ssh root@host 'git pull --ff-only'` | allowed |
| `ssh root@host 'ssh-keygen -t ed25519 …'` | allowed |
| `ssh root@host 'cat >> /root/.ssh/config …'` | allowed |
| `gh api repos/OWNER/REPO/keys -X POST …` | allowed |
| `ssh root@host 'bin/host-publish && docker compose up -d --build …'` | denied |
| `curl -X POST https://api.cloudflare.com/…/dns_records` | denied |
| `curl -X PATCH https://api.tailscale.com/…/dns/split-dns` | denied |

Every one of those changes state, four on a production host. Creating a GitHub deploy key went through;
patching a DNS record did not. So **do not generalise from one denial to a class** — and if you already have,
say so when the next command in that "class" succeeds, because a wrong model gets repeated to other people.

Approval in chat does not change a verdict. In another session (2026-09-27),
`git push --force-with-lease=main:<old-sha> origin main` was denied after the user had approved the history
rewrite and then the push itself. The user ran the identical command through `!` and it went through. A
force-push to a published branch is worth planning as the user's own step from the start.

## A heredoc wrapper can be the thing that is denied

Write the sequence plainly before concluding that any tool in it is refused. Measured 2026-09-29:
`bash <<'BASH' … BASH` carrying a four-line transcrypt unlock was denied, and the same four commands on
one line, joined by `&&` and `;`, ran. The work was identical; only whether the classifier could read it
changed. A heredoc hands the tool one `bash` invocation whose body is data, so `bash` is what gets judged.

Unwrapping is the opposite of reshaping a command to slip past — it shows the classifier what the wrapper
hid. Say so when it turns out to be the cause, and unwrap before asking for a permission rule, since the
rule is the more expensive answer and one of these obstacles was never there.

**It does not explain every `transcrypt` denial, and `--rekey` is where it breaks down.** Three sessions on
this machine report incompatible results from 2026-09-29. One was refused three times — inside a `set -x`
block, as a plain multi-line sequence, and alone as the only command on the line — then succeeded on a later
invocation. A second was refused with nothing wrapping it. A third ran it unblocked *inside a bash heredoc*,
the shape the section above identifies as the problem. So the wrapper is not the discriminator for this
subcommand. `transcrypt --list` and `--version` were refused in none of the three.

**A `Bash(transcrypt:*)` rule is not the remedy, however plausible it reads.** In the session that recovered,
the user was asked for exactly that rule and agreed — and no settings file on this machine grants transcrypt
anything. Verified 2026-09-29 from a second session: `~/.claude/settings.json` carries `defaultMode: auto`
and two `Read(...)` entries, `~/.claude/settings.local.json` does not exist, nor does that project's
`.claude/settings.local.json`, and the dotfiles repo's own local settings hold two `Bash(grep …)` rules and
nothing else. The single `transcrypt` string in the user settings is a PreToolUse hook matcher.

Three routes could have granted it, and each is closed by something measured rather than argued:

- A Bash **"Yes, and don't ask again"** saves to `.claude/settings.local.json` at the git repository root and
  lasts "permanently per repository and command". That file is absent in the session's own repo — and present
  in the dotfiles repo, holding an unrelated `Bash(grep *)`, which is what the route looks like when taken.
- A rule added through **`/permissions`** "follows the row for the settings file you save it to". No settings
  file changed.
- A prompt can offer an option that **allows the action for the rest of the session** and is written to no
  file. A classifier denial arrives with no prompt at all, so nothing was offering it.

So the grant nobody can find is most likely a grant that never happened: the classifier's verdict on one
unchanged command is not stable across invocations. The alternative is an action outside the session that
nobody observed, and neither is something a rule can encode.

**That is an observation, not a licence to retry.** The harness instruction is that a denied call means the
user declined it and the response is to adjust rather than re-issue, and it carves out no exception for the
auto-mode case where no person ever saw the command. Nor is the instability established well enough to build
a step on: the unobserved-action reading fits the same evidence. What it does change is what a denial entitles
you to *say*. It is a verdict on this invocation in this session, so report "refused here" rather than "the
tool is blocked", and never carry a refusal in one clone over to another.

Every surviving explanation is session-local, which is the part that changes what other sessions should do:
nothing that unblocked one session carries to the next, survives a `/clear`, or reaches another project. A
rekey still pending elsewhere gains nothing from a rekey that succeeded here.

A classifier denial arrives with **no permission prompt attached**, so there is nothing to approve into and
waiting for one is a stall. Where a bare, unwrapped single command is still refused, hand it to the user as
their own step — see "What to do with a real denial" below — rather than reaching for a permission rule
whose effect on this command nobody has measured.

## A denial means the command did NOT run

The check happens before execution. Nothing partial, nothing queued, no side effects.

This matters when reconciling state afterwards. If the thing you were denied appears to have happened, it
happened by another route — the user ran it, or a colleague did — and saying "my denied command must have
slipped through" plants a belief that denials are porous. They are not. Check who actually did it.

## `dangerouslyDisableSandbox: true` is not a skeleton key

The Bash tool's `dangerouslyDisableSandbox` runs the command unsandboxed, and it does change the outcome for
*some* denied commands — the `git pull` above was denied, then allowed with the flag. It is still evaluated:
the `host-publish` and Tailscale calls were denied **with** the flag set.

So it is worth one retry on a command you are confident about, and it is not a way to force anything through.
Setting it does not make a risky command safe; it removes an isolation layer, and the classifier still gets a
vote.

## What to do with a real denial

The denial text says it: stop and explain, and let the user decide. Concretely:

- **Do not reshape the command to slip past.** Splitting a compound command to find *which half* is refused is
  legitimate diagnosis; rewording it to look benign is not, and the difference is whether you would describe
  what you did in the same words to the user.
- **Do ask whether the *goal* has a read-only form.** Reaching the same answer with strictly less privilege is
  not evasion — it is a smaller action that is often also the better test. A denied plan to render a secrets
  file to a scratch path on a production box (to diff against the live one) was replaced by hashing the render
  locally and asking the host for `sha256sum` of the file it already had: no secret transmitted, no write to
  production, nothing to clean up, and a byte-identical verdict rather than an eyeballed diff. The line is
  intent — narrowing what you *do* is fine, disguising it is not. See `secrets-render-to-remote-host.md`.
- **Hand over the exact command.** Safe to run via the `!` prefix as long as no plaintext secret is in the
  text — `"$(doppler secrets get KEY -p proj -c cfg --plain)"` *fetches* the value rather than embedding it,
  so the transcript records the fetch, not the secret. A literal token in the command text is not safe there;
  that needs a terminal outside the session.
- **Mention the permission rule.** `Bash(ssh root@host:*)` in settings lifts it for future runs — while noting
  what else that rule would cover, which for a shared host is every destructive command on it.

## The removal check is a separate gate, and no rule lifts it

A denial that opens `Permission for this command was denied by a built-in Claude Code safety check, not by
the user` comes from a check on `rm`, not from the classifier. No permission rule can allow it; only a person
running the command can. Two triggers, measured 2026-09-26 in Git Bash on Windows:

- **A target computed at run time.** `rm -f "$S"`, with `S` set from `git rev-parse --git-path ...`, was
  refused because the variable could resolve to the repository root. A `${S:?}` guard does not help, since the
  value is not empty. `rm -f /tmp/adopt-snapshot`, a literal absolute path, went through. A procedure written
  for agents to follow therefore has to name what it deletes literally, or every agent following it is refused
  at the cleanup step.
- **A directory the session has adopted as its working directory.** A Bash call that `cd`s into a scratch
  directory without a subshell moves the session there, and the harness reports a new primary working
  directory. Removing that directory then failed with `Device or resource busy`, and the retry was refused as
  removing a workspace directory. Set up probes inside `( cd ... )` so the scratch directory never becomes
  the working directory and stays deletable. Where one already has, `cd` back out in a call of its own
  first: once the harness reported the old working directory again, `rm -rf` of a second such probe went
  through on 2026-09-27.

When the user has to run the removal, the `!` prefix runs Git Bash, not PowerShell, so hand it over in bash
form: `rm -rf <literal path>`.
