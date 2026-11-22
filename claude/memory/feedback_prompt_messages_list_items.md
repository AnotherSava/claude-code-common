---
name: feedback_prompt_messages_list_items
description: Messages shown to a person around a terminal prompt put one sentence per line, list the affected items rather than counting them, and carry no script-name prefix
metadata:
  type: feedback
---

Text a person reads at a terminal prompt, such as a `[y/N]` question and the lines explaining it, puts each sentence on a line of its own. A line never breaks mid-sentence: rephrase until each sentence fits. The text names the affected items one per line, indented, where a count would otherwise stand. It carries no `script-name:` prefix, even where the same script's error lines keep one.

**Why:** on 2026-11-21 the remote-session restart prompt said "ends the 7 remote agent(s) running there", wrapped mid-sentence and prefixed with `cc-session:` and `attach:`. The user asked to drop the prefixes and rephrase so no sentence splits across lines, then said: "i'd rather see a list of sessions (one in a line) than just count".

**How to apply:** any message written for a person at an interactive prompt, in a script or a CLI. Error output that only gets read when something breaks can keep its prefix, since there the prefix says which layer is speaking. Related: [[feedback_minimal_ui_chrome]].
