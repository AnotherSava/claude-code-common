---
created: 2026-09-18 20:16:33
---

# A universal rule for the npm pin the machine stopped honouring

Convention v5 tells every Node repo to pin its manager with `packageManager` and run `corepack enable npm` once on each machine. Upgrading Node silently undoes the second half: the upgrade replaces the install directory and takes corepack's shims with it, so `npm -v` goes back to answering with the bundled npm while the pinned field is untouched. Measured 2026-09-18 on Windows — `winget upgrade --id OpenJS.NodeJS.LTS` took Node 24.13.0 to 24.19.0 and npm from the pinned 12.0.2 back to 11.17.0. Full mechanics in claude/learnings/corepack-packagemanager-pin.md.

Nothing reports it. The v5 rule `package-manager-pin` asserts the field's SHAPE, so it passes exactly as before; there is no error, and the install still works. The only honest check is `npm -v` inside the project compared against the field.

This belongs in claude/conventions/universal/ rather than as a new version, and it meets authoring.md's two-part test for that class: the property is per-machine, so no number could ever be true of both boxes at once, and the failure is silent, so nothing else would report the violation. Sketch: no-op where the repo has no package.json a person maintains (reuse `_node`'s existing helper and its gitignore-aware walk), no-op where no `packageManager` field is declared, otherwise compare `npm -v` against the pinned version and report the disagreement. It must raise rather than pass when npm is not on PATH at all — unmeasured is not a pass. FIX is mandatory for a universal rule: `corepack enable npm`, which on Windows needs an elevated shell.

Two things to settle before writing it. A universal rule reaches every repo the moment it is committed with no adoption in between, so check what it would say today across the fleet before committing it. And `claude/conventions/tests.py` requires a conforming tree, a violating tree and a git-cannot-answer tree for every rule, which for this one means faking `npm -v` rather than the filesystem — decide how before starting.
