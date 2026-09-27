# Git Bash's grep aborts on `-i` with `-F`

Use `-i` without `-F`, or `-F` without `-i`, in Git Bash on Windows. The GNU grep 3.0 that
ships with Git for Windows aborts with a core dump on every `-i -F` combination, whatever the
pattern and whether it matches. The shell prints `Aborted (core dumped)`, the exit status is
134, and a `grep.exe.stackdump` appears in the working directory. Measured 2026-09-26:
`-ciF`, `-iF` and `-ciwF` all abort, while `-cwF`, `-ciw` and `-ciwE` do not.

It is easy to miss inside a script. With the call in `$(...)` and stderr redirected, the
count comes back empty rather than `0`, and a following `[ "$c" != 0 ]` then reads every
pattern as a hit. A literal pattern that needs case-folding works as `-i` with the
metacharacters escaped, or in Python with `re.escape` and `(?i)`. The Grep tool is ripgrep
and is not affected.

Delete the stackdump afterwards. It is a crash artifact, not something to gitignore.
