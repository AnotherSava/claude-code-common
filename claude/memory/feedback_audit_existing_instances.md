---
name: feedback_audit_existing_instances
description: A setup skill's rules reach a repo only on scaffolding day — audit an existing instance against the current rules instead of assuming it complies
metadata:
  type: feedback
---

When a task touches something a skill knows how to set up — a docs site, a deploy, a backup, a
heartbeat — audit the existing instance against that skill's current rules before assuming it was
built to them. The existence of a skill is not evidence of compliance.

**Why:** a skill's rules reach a repo only on the day that repo is scaffolded. Every rule added
afterwards silently governs fewer instances than it appears to, and a greenfield "setup" workflow
never revisits an older one, so the gap widens quietly and is found by a human noticing the symptom.

Found 2026-09-08: the user spotted the just-the-docs attribution footer on a published site. The
`github-pages` skill had documented both that fix and the theme pin since 2026-09-01; that site was
built on 2026-07-11, seven weeks earlier. Auditing six local docs sites then found three still
serving the footer and four with an unpinned theme, every one of them scaffolded before the rules
existed. Nothing had failed; nothing had ever re-checked.

**How to apply:**
- The audit is usually a few greps across the instances. Write it *into the skill* as its own
  section rather than carrying it in your head, so the next session runs it too — a fix that lives
  only in one conversation leaves the same gap behind.
- Verify against the **deployed artifact**, not the source, wherever the two can diverge. A cached
  or unpinned dependency lets correct-looking sources sit above a stale deploy, which reads exactly
  like a change that did nothing.
- Run the audit command rather than predicting its output; the first version of that one printed two
  values per row because `grep -c` exits non-zero on a count of zero. See
  [[feedback_write_the_procedure]].
- Fix each instance in its own repo's own commit, and park the ones you are not doing now as memos
  there rather than carrying them forward in conversation.
