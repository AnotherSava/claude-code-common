---
name: clean-code
description: Remove dead code, fix duplication, enforce naming conventions, and optimize imports in modified files
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(git diff:*), Bash(git status:*)
---

# Clean Code

Audit modified files for dead code, duplication, naming conventions, and import hygiene. Fix issues with user approval.

## Context
- Uncommitted changes: !`git status --short`
- Diff summary: !`git diff HEAD --stat`
- Full diff: !`git diff HEAD`

## Process

1. **Remove debug prints** (`print()`, `console.log()`, `Debug.Log()`, etc.) added during development — do not commit temporary debug output

2. **Dead code audit — iterate until clean:**
   Start with modified files, then expand outward: use Grep to find all production files that import, call, or reference symbols defined in modified files. These consumers may now contain dead code if the symbols they depended on were changed, removed, or renamed. For each file in this expanded set, look for:
   - **Dead methods/functions**: defined but never called from production code (only from tests or not at all). Trace callers — if a method is only called from another dead method, both are dead.
   - **Dead fields/variables**: only written (never read), or only set to a constant value that makes guarding branches unreachable.
   - **Dead imports**: symbols imported but unused after other cleanup.
   - **Dead type members**: union/enum members never constructed or matched.
   - **Cascading dead code**: after each removal, re-check whether anything new became unreachable (deleted code may have been the only caller of other code).

   For each finding, describe what you found, why it's dead, and propose removal. If the user agrees, make the change. If the user disagrees or wants to keep it, move on. **Keep iterating** — after each batch of removals, re-scan the affected files for newly dead code. Stop only when a full pass finds nothing actionable, or the user says to stop.

   Production code that is public only because tests call it directly (e.g. unit-testing internal methods) is NOT dead — it runs in production via internal calls and is exposed for testability. Do not flag these.

3. **Duplication audit:**
   Check modified files for duplicated logic — repeated code blocks, near-identical functions, copy-pasted patterns with minor variations. For each finding:
   - Describe the duplication and where it occurs
   - Propose a consolidation (shared function, base class method, helper, etc.)
   - Wait for user approval before refactoring

   Only flag duplication that hurts maintainability — two similar 2-line blocks are fine; three similar 10-line blocks are not.

4. **Naming convention audit (Python files only):**
   Check visibility naming in modified Python files:
   - A method or module-level function referenced only from inside its own class/module should carry a `_` prefix.
   - A `_`-prefixed member referenced from outside its class/module should either lose the prefix or have the external access refactored away.

   Skip dunder methods and members that are public API by design (a library's surface stays public even while temporarily uncalled; tests calling an internal member directly do not make it public). For each mismatch, propose the rename and wait for approval; when renaming, update every usage including tests.

5. **Optimize imports in modified source code files**

6. **Report** what was cleaned up. If nothing was found, say so.

## Out of scope

- Do NOT change code logic or behavior — only remove dead code, consolidate duplicates, and clean imports
- Do NOT touch files that aren't modified or directly affected by modifications
