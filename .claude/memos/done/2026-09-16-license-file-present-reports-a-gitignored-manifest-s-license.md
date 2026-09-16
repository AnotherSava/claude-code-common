---
created: 2026-09-16 04:38:35
---

# license-file-present reports a gitignored manifest's license as this project's

Found 2026-09-15 by an adversarial review of the adopt-walk change set, and waived rather than fixed there because it sits outside what that diff was about. The waiver comment is in the file, marked `walk-unfiltered:` and naming this defect rather than a case the filter does not apply to.

## What it does

v10 `license-file-present.py` has its own `manifests()` — unrelated to `node_manifests.manifests` — that enumerates the repo root plus one directory level with `os.listdir`, skipping only dotted names and `node_modules`. It asks git nothing. So a `package.json` in a gitignored `tmp/`, `dist/` or a scratch clone one level down is read and reported.

Measured on a scratch repo with `/tmp/` gitignored and `tmp/package.json` declaring GPL-3.0:

    license-file-present.py apply <root> --dry-run

printed `also: tmp/package.json declares "license": (GPL-3.0)` followed by the standing advice that "A manifest naming a different license contradicts the file and is what dependency scanners read". Both sentences are about a file no clone receives.

## Why it was left

It is report-only, and that bounds the damage precisely:

- `cmd_verify` never calls `manifests()` — it asserts a LICENSE exists at the repo root and nothing else. So no recorded `applied` line depends on this list, which is also why fixing it later cannot retroactively change what any repo asserted.
- `cmd_apply` always exits 3 and writes nothing.
- `cmd_probe` returns 2 unconditionally, so `/adopt` puts the question to the user without ever printing this list. Only a hand-run `apply` shows it.

So the cost is a human reading advice about the wrong file during a license decision, not a wrong record and not a wrong write.

## The fix, when it is taken

Narrow that enumeration the way `node_manifests.manifests` now is — `_gitignore.ignored_untracked(root, paths)`, the plain index-consulting form, keeping only hides whose source is tracked and in the repo. The one thing to decide first: the same function also lists the repo root for LICENSE candidates, and a gitignored LICENSE is a different question from a gitignored manifest. Filter the manifest half; leave the root listing alone, or say why not.

Do it with the `walk-unfiltered:` waiver deleted in the same change, so the gate goes back to holding the rule for this file.
