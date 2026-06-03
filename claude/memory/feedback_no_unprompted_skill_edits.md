---
name: feedback-no-unprompted-skill-edits
description: Don't modify a skill's definition unless asked; fixing a skill applies when it fails during use, not when you infer its guidance is suboptimal
metadata:
  type: feedback
---

Don't proactively rewrite a skill's definition (SKILL.md) the user didn't ask about — especially on a premise that may be wrong.

**Why:** During an `/investigate` run I rewrote the skill's Step 5 to forbid reading from `data/`, on the (incorrect) premise that `data/` is bad. The user was clear: they didn't ask me to touch the skill, and `data/` is the *intended* place to download investigation archives. The narrow rule ("committed tests must not read from gitignored `data/`") applies to the test, not to `data/`'s purpose.

**How to apply:** This does not contradict [[feedback-fix-skills]] — fix a skill when it *fails while you're running it*. But don't editorialize a working skill's guidance unprompted, and don't conflate a specific correction with a sweeping change to surrounding design. When unsure whether a skill edit is wanted, ask. (Editing a skill *is* fine when the user explicitly asks for it.)
