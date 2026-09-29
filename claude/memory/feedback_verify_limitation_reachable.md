---
name: feedback_verify_limitation_reachable
description: Before presenting a limitation, gap or caveat, verify its triggering condition is actually reachable in the flow it applies to
metadata:
  type: feedback
---

Before presenting a limitation, gap or caveat to the user, verify its **triggering condition is actually
reachable** in the flow it applies to.

**Why:** a reorientation gap was reported as "supports=off gets no offer", but the customer wizard always
sets supports to auto — there is no customer control, and operators set off or forced only in an admin
re-slice — so the state never occurs in the path the caveat described. It was noise, and it under-sold the
feature, because the overhang case it was meant for *is* served. The user caught it with "don't we have
support=auto always?"

**How to apply:** trace whether the edge state can actually be produced in the path the caveat applies to,
before listing it as a limitation. A caveat for an unreachable state is worse than none, because it
misleads about what the thing does. Related: [[feedback_check_the_limit_is_real]] is the adjacent rule for
a limit you are about to *design around* rather than report, and [[feedback_verify_before_justifying]]
applies the same check backwards, to claims defending code that already exists.
