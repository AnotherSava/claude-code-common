# A UTF-16 .gitattributes is silently ignored

Check the file's encoding first when an attribute seems to have no effect: `file .gitattributes`, or `head -c 2 .gitattributes | od -An -tx1`, where `ff fe` is the UTF-16 LE byte-order mark. Git parses the file as bytes, so in a UTF-16 file every pattern carries a NUL between its characters and matches nothing. Git reports no error, and the rules simply never apply.

## What it looks like

Measured 2026-09-28 on a repo whose only line was `*.3mf filter=lfs diff=lfs merge=lfs -text`, committed nine months earlier:

- `git check-attr -a -- <a .3mf>` lists only what the global attributes file supplies (`text: auto`, `eol: lf`) and no `filter: lfs`.
- The committed blobs are raw content rather than LFS pointers (a `.3mf` blob opens with `PK`, the zip header), and `git lfs ls-files` prints nothing.
- `grep "filter=lfs" .gitattributes` exits 1, like a grep for any other ASCII pattern. A check built on grep reads the file as not holding the rule, which is a false negative rather than evidence.
- A Python reader opening it as UTF-8 raises `UnicodeDecodeError` on byte `0xff`.

Windows PowerShell 5.1 is the likely source: its `>` and `Out-File` write UTF-16 LE with a BOM by default, where PowerShell 7 writes UTF-8. `git lfs track` writes the file correctly, so the suspect is a line typed as `echo … > .gitattributes`.

## Fixing it switches the rules on

Rewrite the file as UTF-8 with LF endings, for example `printf '%s\n' '<the line>' > .gitattributes`, then confirm with `git check-attr`. Every rule then takes effect at once, and for an LFS rule that changes how files are stored:

- Git runs the clean filter from then on, and the next commit of a modified matching file stores the pointer. Plain `git diff` cannot show this: it prints `Binary files … differ` before and after the fix, because `diff=lfs` names a driver nothing configures and the raw blob on the index side is binary. `git diff --stat` shows the size falling to about 130 bytes, and `git diff --text` shows the pointer lines.
- Unmodified matching files keep their raw blobs only while their stat data is unchanged. A `touch`, a checkout or an editor save that rewrites identical bytes makes git re-clean the file, so it shows as modified and the next `git add -u`, `git add -A` or `git commit -a` converts it inside whatever else that commit holds. Convert them in one deliberate `git add --renormalize .` commit instead. History before the fix keeps its raw blobs either way.
- Every clone needs git-lfs installed from the first commit that stores a pointer.

Deleting the file instead leaves storage exactly as it has been, since the rule never worked. So the real decision is whether to start using LFS now, not how to repair a setting.
