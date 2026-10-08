---
name: Match the use, not the name
description: A check asking whether anything consumes X must match the consuming construct; a repo that documents its own rules satisfies a grep for the rule's subject
metadata:
  type: feedback
---

A check asking "does anything consume X" must match the consuming **construct**, not the name. A repo that documents its own rules will satisfy a grep for any rule's subject, so the enforcement is defeated by its own explanation — and the failure is silent, because the check still reports a pass.

**Why:** a new check refused a declared secret that nothing reads, counting "read" as the name appearing anywhere under `bin/`. Two comments explaining that very rule quoted `{env.PORKBUN_API_KEY}`, so the credential read as consumed and the check could never fire for the one name it most needed to cover. A review agent found it; deleting the line that really does consume it, and watching nothing be reported, confirmed it. The second attempt then added `$NAME` as a shell-read pattern and matched `{$PORKBUN_API_KEY:}` in the same comment — a config placeholder spelled like a shell variable.

**How to apply:** match what actually uses the thing — `os.environ["X"]`, `getenv("X")`, an import, a call. Prefer too few patterns to too many: an unrecognised consumer reported as missing is loud and gets fixed, while one pattern loose enough to match prose silently excuses every mention of the subject. Then pin it with a case whose fixture is a comment naming the thing, asserting it does **not** count — see [[feedback_not_run_is_not_pass]] for the family this belongs to, and [[feedback_fixture_must_exceed_the_cap]] for the same shape in a fixture that never reaches the branch.
