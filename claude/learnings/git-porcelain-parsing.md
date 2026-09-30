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

## Feeding paths back in: text-mode stdin appends `\r` on Windows

Hand paths to a `--stdin` command (`check-attr`, `check-ignore`) as bytes, NUL-separated, never
through `text=True`. On Windows, Python's text-mode stdin writes every `\n` as `\r\n`, and git
reads the `\r` as part of the path. Nothing fails. Each lookup quietly runs against a name that
does not exist, and whether the answer changes depends on the pattern: a glob such as
`*.secret.*` still matches `x.secret.md\r`, while an exact path such as `config/publish.env`
never matches `config/publish.env\r`. Measured 2026-09-28: a survey of which repos hold
transcrypt-encrypted files reported one repo as having none, when it held one encrypted by that
exact path. Its own session caught the error before the wrong advice was acted on.

    files = subprocess.run(["git", "ls-files", "-z"], capture_output=True).stdout
    out = subprocess.run(["git", "check-attr", "-z", "--stdin", "filter"],
                         input=files, capture_output=True).stdout.split(b"\0")
    # -z output is path, attribute, value, repeated
    crypt = [out[i] for i in range(0, len(out) - 2, 3) if out[i + 2] == b"crypt"]

The tell, had anything been looking: `check-attr` echoes the path back quoted, with the `\r`
visible, whenever a path carries one.

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

## Let pathspec magic choose the paths, and neutralise the caller's pathspec mode

A script that needs only some of the index — files carrying an attribute, files at one path at any depth —
should have git select them rather than looping over every name in the shell. A shell loop reads a pipe one
byte per syscall, and in a pre-commit hook that turned a 30,000-file commit from 0.3 s into 30 s on Windows.
The selections that did the work:

```bash
git ls-files -s -z -- ':(attr:filter=crypt)'     # "mode oid stage<TAB>path" for every entry the attribute marks
git diff --cached --name-only -z -- ':(glob)**/config/publish.env'   # `**/` matches the root path too
git ls-tree HEAD -- ":(literal)$path"            # HEAD's "mode type oid" for exactly this name, or nothing
```

`attr:` reads `.gitattributes` from the working tree, as `git add` does, so an unstaged edit changes what it
selects. It matches one value exactly: `filter=crypt` does not match `filter=crypt-ops`.

**The caller's environment can switch all of it off.** `git --literal-pathspecs`, which Magit passes by default,
exports `GIT_LITERAL_PATHSPECS=1` to every child, hooks included, and under it `:(attr:filter=crypt)` is a file
name that matches nothing — so a check built on it passes everything, silently. A script that relies on magic
starts with:

```bash
unset GIT_LITERAL_PATHSPECS GIT_GLOB_PATHSPECS GIT_NOGLOB_PATHSPECS GIT_ICASE_PATHSPECS
```

Two smaller traps sit in the same place. A name opening with `:` reads as magic unless it is wrapped in
`:(literal)`, so `ls-tree HEAD -- ":x.env"` finds `x.env`. And a pathspec-limited `git diff --cached` pairs
renames only within the pathspec, so a file moved in from outside it shows as `A`, while `--diff-filter=ACMR`
leaves out `T`, the typechange that replacing a committed symlink with a regular file produces.
