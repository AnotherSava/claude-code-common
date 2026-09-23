---
name: feedback_read_email_means_attachments
description: "Read the original email" always includes every attachment — reporting on the body alone answers a question that was not asked, and the attachment is usually where the facts are
metadata:
  type: feedback
---

**"Check it in the original email" means the whole message, attachments included.** Said on 2026-09-22, as a
standing rule rather than a correction to one task: *"when i mention reading original email, i always mean
including all the attachments."*

**Why:** a large class of senders puts the covering letter in the body and the document in the attachment, so
a body-only read produces a confident, specific, wrong answer — "the email does not state the province" about
a message whose ticket PDF may say it on the first line. The same shape cost the trips project a queue item that
reported cost, seats and station addresses as "not provided" while its boarding pass carried all three
([[project_extraction_is_stored_not_recomputed]]). A report that says "the email does not say X" is a claim
about every part of the message; making it from the body alone is the error.

**How to apply:** enumerate the attachments before answering, and say which ones were read. The Gmail MCP
connector hands over attachment *metadata* and never bytes, so getting the text needs a route around it —
`~/.claude/learnings/gmail-api.md` has the two, and `claude-in-chrome-probing.md` has the working browser
harvest. If an attachment genuinely cannot be read, say so and name it rather than reporting on the body as
though it were the message. See [[feedback_read_the_evidence_you_have]] for the same reflex one level up.
