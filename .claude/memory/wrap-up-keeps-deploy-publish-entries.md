---
name: wrap-up-keeps-deploy-publish-entries
description: wrap-up's allowed-tools keeps bash scripts/publish.sh and the deploy run.sh on purpose; the grant ends with the turn that invoked the skill, so step 9's runs after the gate's answer are checked like any other call
metadata:
  type: project
---

The `allowed-tools` line in `claude/skills/wrap-up/SKILL.md` lists `Bash(bash scripts/publish.sh)` and `Bash(bash ~/.claude/skills/deploy/scripts/run.sh:*)`, the deploy entry point. The user kept both on 2026-10-09. Do not propose removing them again, and do not read them as an oversight when auditing the frontmatter.

On a run that stops at the gate, they do not let `/wrap-up` publish or deploy without a permission check. A skill's `allowed-tools` grant covers only the turn that invoked the skill (`claude/learnings/claude-code-auto-mode-permissions.md`), the gate's answer starts a later turn, and step 9 makes both offers after that answer and the push. In every recorded `/wrap-up` publish the grant had cleared by then, so auto mode's classifier decided the call, as it decides a publish anywhere else, and refused some, most as `[Production Deploy]`; in manual mode the call prompts. Step 9 carries the hand-off for a refusal. The skill's own rule, asking for the verb by name before publishing, comes before that check.

The all-empty summary has no gate, so a run on that path can reach step 9 with the grant still live, as the `allowed-tools` bullet under Important in `claude/skills/wrap-up/SKILL.md` says. The learning, under "A skill's `allowed-tools` grant lasts one turn", says whether the user's answer to an offer ends the grant. Where the grant outlives that answer, these entries can admit a deploy or publish with no permission check, and the user's answer to the offer is then the only check: for publish it has to name the verb, as step 9 requires, and for deploy it is the yes to the offer, which step 9 makes the machine-takeover ask for every deploy type but `dev-server`. Whether either entry matches the redirected command step 9 runs has not been measured.

Measured 2026-11-16 from the Windows machine's transcripts: of the 58 `bash scripts/publish.sh` calls since 2026-10-21, `/wrap-up`'s included, none was decided by a rule; the classifier accepted 46 and refused 11, and the user rejected the other.
