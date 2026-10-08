---
name: feedback_denial_is_not_absence
description: An auth refusal for a guessed identity is not evidence the host is closed; read the coordinates file's own command before reporting unreachable
metadata:
  type: feedback
---

An authentication refusal for an identity you guessed is not evidence the host is closed. `Permission denied (publickey,password,keyboard-interactive)` is the same error for a wrong username, a missing key, and a port that answers but rejects everyone, so it cannot tell them apart — and the file holding the machine's coordinates usually carries the working invocation verbatim.

**Why:** On 2026-10-08 `ssh <mac-account>@<peer>` was refused twice, and the refusal was reported to the user as that box being unreachable — first as a closing concern, then as the reason to file a memo for work only that box could do. The coordinates memory opens its section for that direction with the correct command, naming a different account; the accounts differ per direction, and the section had been grepped for headings rather than read. The user's correction was "try again", and the box answered on the first attempt with the documented command. The conclusion had already shaped two user-facing messages by then.

**How to apply:** Before reporting a host, service, or credential as unreachable, read the coordinates file's own command rather than grepping around it, and quote which invocation was refused so the claim is checkable. Where a sibling tool reaches the same machine successfully — a status script, a sync helper — read its invocation instead of concluding from yours. The generalisation past ssh is any error that cannot distinguish *wrong identity* from *no access*: a 401 or 403 on an API, a database role that does not exist, a token scoped elsewhere. Closest neighbour is [[feedback_check_the_limit_is_real]], which is about the evidence the system already holds; this is the narrower case where the evidence is a command somebody wrote down. See also [[feedback_read_upward_from_the_match]] for why the grep was the wrong instrument, and [[machines-private.secret]] for where these invocations live.
