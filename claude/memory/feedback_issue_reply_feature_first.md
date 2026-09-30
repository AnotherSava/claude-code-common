---
name: feedback_issue_reply_feature_first
description: Replies to issue reporters describe what they will get, not how it works inside; a reason is a short aside in the example or brackets
metadata:
  type: feedback
---

In a reply to an issue reporter, describe what they will get: the feature and the settings they will see. Leave out mechanism, such as queue behaviour, what the emulator rewrites and when, or which internal source a value comes from. When a choice needs a reason, give it as a short aside, folded into the example or in brackets, never as the sentence that introduces the feature.

**Why:** drafting the issue #10 reply in the achievement-overlay repo (2026-09-29), the user cut "if a newer value arrives while one is still waiting, it replaces it" as too deep, reordered a sentence that opened on the reason ("GBE rewrites the file on every step, so…") to open on the feature, then moved the justification into the example ("…then the unlock popup - instead of every one of 100 increments"). Two paragraphs of implementation detail were removed in the same pass.

**How to apply:** after drafting, strike every sentence a reporter could not act on or notice in the running app. Keep questions about their setup (versions, files, what writes the file), since those are theirs to answer. Complements [[feedback_peer_register_not_support]].
