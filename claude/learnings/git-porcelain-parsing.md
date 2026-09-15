# Parsing `git status --porcelain` safely

The first 2 characters of every porcelain line are the X (staged) and Y
(unstaged) status columns. **EITHER column can be a space.** Common
shapes:

    "M  file"   — staged modified   (X=M,     Y=space)
    " M file"   — unstaged modified (X=space, Y=M)
    "?? file"   — untracked
    " D file"   — unstaged deletion
    "MM file"   — both staged and unstaged modified
    "R  old -> new" — staged rename

The path always starts at offset 3 (after the two status chars and one
space separator).

## The `.strip()` trap

If you `.strip()` the entire porcelain output before splitting into
lines, the **leading space of the first line is consumed**. For
` M file` you'll end up parsing `M file` — losing one whole status
column and corrupting downstream path slicing:

    line[3:]   # for " M file"   → "file"     ✓
    line[3:]   # for "M file" (after bad strip) → "ile"  ✗

Use `.rstrip("\n")` instead — trims only trailing newlines, no
whitespace-leaning per line:

    output = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                            capture_output=True, text=True).stdout
    output = output.rstrip("\n")

`splitlines()` itself is safe; the issue is the prior strip. Per-line
operations after `splitlines()` see each line with its true leading
whitespace intact.

## Renames

A rename line is `RX old -> new`. The actual path is the destination
after the ` -> ` separator:

    path = line[3:]
    if " -> " in path:
        path = path.split(" -> ", 1)[1]

## `core.quotepath` mangles non-ASCII paths in every listing command

`git ls-files`, `git status` and friends escape non-ASCII bytes by default and wrap the
path in quotes, so a Cyrillic, accented or CJK filename comes back as octal escapes:

    "content/druzya/\320\232\320\270\321\200\320\260.jpg"

Compare that output against a filesystem listing and the files silently look **missing**.
Real case: a repo of 2454 files reported 1390 tracked, and the 1064 "absent" ones were
just the photographs whose captions were Cyrillic. `git check-ignore` reporting nothing
for them was the tell — no rule was excluding them, the two lists simply disagreed about
their names.

Pass `-z` for NUL-separated, unescaped output:

    raw = subprocess.run(["git", "ls-files", "--others", "--cached",
                          "--exclude-standard", "-z"],
                         capture_output=True).stdout   # no text=True — decode yourself
    listed = {p.decode("utf-8") for p in raw.split(b"\0") if p}

`-z` also removes the "what if a filename contains a newline" question. The same flag
works for `git status -z`, `git diff --name-only -z`, `git ls-tree -z`.

`git -c core.quotepath=false …` stops the escaping but still quotes paths containing
spaces, so it is not enough on its own. Prefer `-z` whenever the output is parsed rather
than shown to a human.

## Display tip

When echoing porcelain back to a human, replace the X/Y spaces with a
center dot so the columns line up visually:

    code = line[:2].replace(" ", "·")
    print(f"  {code}{line[2:]}")
    # → "  ·M file"  (unstaged modify)
    # → "  M· file"  (staged modify)
    # → "  ?? file"  (untracked)

## `--ignored` collapses a directory; `--ignored=matching` expands it, and which you want depends

Asked which files an ignore rule currently hides — before deleting that rule, say — the default
`--ignored` (traditional mode) answers with the *topmost* ignored directory and nothing inside it.
Measured 2026-09-15 on a scratch repo whose `.gitignore` is one line, `**/config/deploy.env`, with
that file the only thing under `web/`:

    $ git status --porcelain --ignored
    !! web/
    $ git status --porcelain --ignored=matching
    !! web/config/deploy.env

Nothing matches `web/` at all — traditional mode collapses a directory whenever *everything inside
it* is ignored, whether or not the directory itself matched a pattern. A caller that then asks
`git check-ignore -v web/` which rule hides it gets a directory git attributes to no rule, so a
guard built this way sees no files and reports that nothing could be exposed.

Matching mode still collapses a directory that **does** match a pattern, and that is the property
worth keeping: `node_modules/` stays one entry instead of thirty thousand. Both facts together are
the whole rule, and testing only the second shape makes the two modes look identical:

    # .gitignore holds `web/` — the directory itself matches
    --ignored            -> !! web/
    --ignored=matching   -> !! web/            # same; the collapse is correct here

A third combination is worth knowing and is usually not what you want: `--ignored -uall` expands
*every* ignored file individually, `node_modules/` included. On the largest repo in one fleet the
matching-mode call returned in 13 ms where the expanded one took 1571 ms.

So: `--ignored=matching` to learn which files a *rule* hides, `--ignored` when a directory-level
answer is enough, and `-uall` only when you genuinely need every path.
