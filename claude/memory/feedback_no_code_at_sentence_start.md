---
name: Don't open a sentence with code-formatted text
description: In prose (docs, comments, READMEs), avoid starting a sentence or line with backtick-wrapped code when regular text follows; lead with a word instead.
type: feedback
---

In prose — documentation, README, comments — do not begin a sentence or line with code-formatted (backtick-wrapped) text when ordinary prose follows it. Lead with a real word and fold the code reference in after it.

**Examples**
- "The `notifications` block controls alerts." not "`notifications` controls alerts."
- "Location of the `config.json` file:" not "`config.json` lives under:"
- "Set `server_port` to change the port." not "`server_port` changes the port."

**Why:** A sentence that opens with a code span reads as a code fragment rather than a sentence, and renders awkwardly (monospace start, no capital). User flagged this repeatedly while reviewing docs. Pairs with [[feedback_sentence_case_ui]] as a prose-style default.

**How to apply:** When writing or editing prose, scan each sentence/line opener — if it's a backtick span followed by regular text, prepend a lead-in word ("The", "Set", "Location of the", the field's role, etc.). **Exception:** term-definition list items where the code identifier is the subject being defined (e.g. a glossary bullet `` - `always_on_top` — keep the widget above other windows``) are the standard pattern and fine to leave. The rule targets running prose, not definition lists.
