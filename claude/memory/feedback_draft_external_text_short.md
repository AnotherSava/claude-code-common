---
name: Draft external-facing text short
description: Issue replies, PR bodies and release notes default to short — lead with the actionable thing, park secondary questions for a follow-up
type: feedback
---
When drafting text for an external audience — a GitHub issue reply, PR body, release note, support answer — default to short. Lead with the actionable thing, state limitations in one clause, and cut anything the reader can discover themselves.

**Why:** a first draft of a reply to an issue reporter ran ~20 lines covering the fix, the test build, two design questions and a diagnostic request; the response was "make it shorter and more to the point", and the version that survived was about a third of it. The maintainer's own issue replies run two or three lines. A long reply buries the ask — the reporter has one job (test the build and report back) and every extra paragraph competes with it.

**How to apply:**
- One paragraph of what changed, the link, what working looks like, what to send if it doesn't.
- Park secondary questions for a follow-up rather than front-loading them; they can be asked once the primary answer arrives.
- This governs drafts *others* will read. It does not change how much detail belongs in analysis addressed to the user — see [[feedback_no_guessed_facts]] for the standard that still applies to both.
