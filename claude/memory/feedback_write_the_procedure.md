---
name: Write the procedure to find the missing artifact
description: Review asks "is this right"; a step-by-step procedure asks "does this exist" — only the second finds the thing nobody built
metadata:
  type: feedback
---

Adversarial review of code and designs cannot find a **missing** artifact, because review examines things that exist. Writing the human procedure — the runbook, the cutover doc, the numbered steps someone will actually follow — is what surfaces the step whose input was never produced.

**Why:** observed 2026-08-25 on a three-project migration. Six rounds of adversarial review across multiple agents, over the compose files, the proxy config, the publish script and the linter, found several real defects and never noticed that the single most important cutover artifact — the tenant vhost the central step installs — did not exist in any repo and was on nobody's list. It surfaced within minutes of someone sitting down to write `cutover.md`, because a sentence naming a file forces you to go and look for that file. Reviews had asked "is this correct" of everything present; the procedure asked "does this exist" of everything referenced.

The same round produced the corollary: a document written against an assumption **reproduces** that assumption. The cutover doc told the operator to expect two `NOT COVERED` lines from a command. Someone ran it, and the command printed nothing of the sort — the tool had the same blind spot the doc did. The doc was wrong in precisely the way the tool was wrong, and running the command was the only thing that could reveal either.

**How to apply:** for any migration, cutover or multi-step operation, write the procedure before declaring the design done, and treat every artifact it names as a checklist item to verify exists. Then **execute the commands the document quotes** and paste their real output, rather than describing what they will print — prose that predicts output is an untested assertion. Related: [[feedback_not_run_is_not_pass]], and the general habit in [[feedback_live_values_source_of_truth]].
