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

## Display tip

When echoing porcelain back to a human, replace the X/Y spaces with a
center dot so the columns line up visually:

    code = line[:2].replace(" ", "·")
    print(f"  {code}{line[2:]}")
    # → "  ·M file"  (unstaged modify)
    # → "  M· file"  (staged modify)
    # → "  ?? file"  (untracked)
