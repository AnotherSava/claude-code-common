---
name: feedback_fix_the_class_not_the_instance
description: A defect in one member of an already-enumerated set is a defect in the set — guard the list, not the item that happened to break
metadata:
  type: feedback
---

When a defect turns up in one member of a set that **already exists and is written down**, guard the
set rather than the member. Look for the list the broken thing came from — an install block, a config
schema, a registry, a manifest — and make the check take that list as its input.

**Why:** this is not the speculative generalisation [[feedback_no_premature_abstraction]] rules out,
and the difference is what makes it safe. There is no hypothetical second case to invent: the other
members are already enumerated by someone who maintains them, so the "class" is a fact rather than a
guess. Fixing only the instance leaves every sibling failing in exactly the way that was just proved
possible.

Measured 2026-09-14: `~/.claude/output-styles` had never been created on one of two machines, so a
committed `outputStyle` setting resolved to nothing and two passes of response-style rules had been
inert there for days while the other machine applied them normally. The proposed fix was a
SessionStart check for that one link. The README's install block listed eleven, and `memory`,
`learnings` and `gitignore` each fail just as quietly in their own way. The user's redirect: *"why
don't you come up with a generic approach for all the symlinks from dotfiles repository?"*

**How to apply:**
- Before building a check, a guard or a fix for one item, go and find the list it belongs to. If one
  exists, the check iterates it.
- The tell is that the thing about to be guarded appears in a list someone maintains. No list, or a
  list of one, means fix the instance.
- Say in the artifact that the list is a second copy of the contract, so the next person adding a
  member knows to add it in both places — or make the checker read the original.
- The same shape is why a per-instance check reads as finished when it is not:
  [[feedback_not_run_is_not_pass]] governs what the check then reports.
