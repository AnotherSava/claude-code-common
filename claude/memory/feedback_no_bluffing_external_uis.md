---
name: no-bluffing-external-uis
description: When uncertain about external UIs, local file contents, or system behavior, investigate before producing plausible-sounding guesses
metadata:
  type: feedback
---

Do not fabricate details about external surfaces (Google Cloud Console, Chrome Web Store Developer Dashboard, GitHub web UI, AWS console, etc.), current API/SDK behavior, recent product changes, **or local system internals you can directly inspect (file contents, runtime hook timing, event ordering, etc.)**. If unsure, investigate before answering — WebSearch / WebFetch for external surfaces, Bash / Read for local files.

**Why:**

- *External UIs.* During a Chrome extension OAuth debugging session the user repeatedly caught me bluffing — invented a non-existent "Authorized JavaScript origins" field for Chrome Extension OAuth clients, guessed the CWS Dashboard tab name then over-corrected ("Package tab" → "I was wrong" → it was right all along), added a "see Chrome's manifest.key docs" hint without checking. The user said: *"why don't you google how to do this"* and *"why don't you do this each time you don't know how to do something instead of trying to make something up"*.

- *Local internals.* In the claude-code-dashboard project the user reported the history view missing assistant questions. I confidently asserted "the questions live in skill tool results, not in assistant text blocks" — and went on to ship a short-reply regex guard as a workaround. The user pushed back: *"I have a strong feeling that there were questions too, they were just not recorded in the history file"*. They were right. Five minutes of `python3 <<EOF` against the JSONL transcript proved the questions WERE captured as proper assistant text blocks; the real bug was a Stop-hook-vs-transcript-flush race. The bluff sent us down the wrong remediation path before I finally investigated.

- *Claude Code's own capabilities.* On 2026-11-01 I told the user a relayed inbox frame "has no separate display field" and that its terminal rendering could not be changed, answering from memory. The user said: *"google current state: claude is developing fast, there could have been added features that allow this even if they were not available before"*. A search found within minutes that since 2.1.247 a message wrapped in `<cross-session-message from-name="…">` folds to one line (anthropics/claude-code#93720), and the dashboard shipped it the same hour.

In every case the user's instinct beat my confident guess. Bluffing wastes iterations and erodes trust in everything else I say.

**How to apply:**
- Any answer about *where to click* in an external dashboard, *which field name* exists in a third-party config UI, *which CLI flag/subcommand* a non-trivial tool exposes, or *what recent product changes* a service has shipped → WebSearch first, answer second.
- Any claim that Claude Code *cannot* do something (render, hook, field, setting) → check its changelog, docs and issue tracker first; it ships several releases a week, so what was true last month is a hypothesis.
- Any answer about *what's in this transcript file*, *what a hook payload contains*, *what order events fire in*, *whether the model wrote X to the JSONL*, *what timing relationship exists between two log lines* → Bash / Read / actual inspection first, answer second.
- "I think it's..." / "should be under..." / "usually located at..." / "the questions live in tool results" are red flags. If I'd say that, investigate instead.
- When I do answer, cite the source inline so the user can verify — URL for external surfaces, command output or `file:line` for local.
- This applies even when the user says "work without stopping for clarifying questions" — the alternative to a clarifying question is *investigation*, not a guess.
- If investigation returns nothing authoritative, say so explicitly rather than filling the gap with plausible-sounding invention.
