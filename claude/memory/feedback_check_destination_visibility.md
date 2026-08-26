---
name: Check whether a destination is published before putting anything in it
description: Relocating a file to make it reachable everywhere is half the job — the other half is asking whether that destination is public, and untracked is not ignored
metadata:
  type: feedback
---

Before writing or moving anything into a shared config/dotfiles repo, establish **two** things, not one: that it is reachable from where it needs to be, and that it is not published. Check the repo's visibility (`gh repo view <repo> --json isPrivate,visibility`) and whether the path is actually ignored (`git check-ignore -v <path>`). **Untracked is not ignored** — an untracked file is one `git add -A` or one `/commit` sweep away from the internet.

**Why:** near-miss on 2026-08-26. A per-host identity manifest was moved into the dotfiles repo to delete a sibling-clone dependency — three projects needed it, and putting it beside the shared tooling made it resolve identically from every repo on every machine. That reasoning was correct and was verified from four directories. What was never checked was the destination: the dotfiles repo is **public**, and `claude/hosts/` was untracked but not ignored, while commits were being made to that repo throughout the same session. The file would have published the complete hostname inventory of a box fronting a commercial storefront, the exact string each site emits to prove the right application is answering, and prose describing which routes are deliberately hidden and how. A sibling agent caught it before the next commit.

Two properties had to hold. One was optimised carefully and the other was never asked about.

**The trap is that it does not feel sensitive.** There was no credential in it — every individual line looked innocuous, which is exactly why it read as safe to commit. The identity markers were the worst part: they are what an impersonation would have to reproduce to pass the very check they exist for, so publishing them describes what the check looks for.

**How to apply:** treat "is this destination published" as a required question whenever relocating anything, alongside "can it be reached". Do not resolve it by making a shared tooling repo private; that is the wrong lever.

**The first fix — gitignore it and make the absence loud — was itself not good enough, and the sequel is the lesson.** A gitignored machine-local copy inside a public repo lasted hours before it drifted from the original, silently, because a hand-maintained duplicate always does; it was guarded only by an ignore rule that was still uncommitted; and it needed recreate-it-per-machine notes in the install docs for two operating systems. Every one of those is a symptom of *keeping a copy at all*. The answer that holds: **store the data once, in the private repo that owns the thing it describes, and fetch it at the moment of use** — for a publish-time check, `gh api` against that private repo, into a process substitution so it never touches disk. No copy, no sibling-clone requirement, no per-machine chore, no exposure. Removing the need beats documenting around it.

Keep the ignore rule after the file is gone. It costs one line and it is what stops the path being recreated by someone repeating the same sound-looking reasoning. And when a fetch replaces a local file, check what the *consumer* does with a failed fetch: it widens the "could not run" surface to include tokens and networks, so the caller must distinguish that from a real failure — see [[feedback_not_run_is_not_pass]].
