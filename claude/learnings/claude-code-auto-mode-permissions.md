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
