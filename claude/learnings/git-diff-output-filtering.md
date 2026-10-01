# Filtering `git diff` output without eating its content

A grep over a diff answers "does this change carry anything but noise", and the usual way of dropping the `+++`/`---` headers destroys the answer. The pattern `^[-+][-+]` matches a header, and it matches just as well any content line whose own first character is `-` or `+` — which in a markdown tree is every added or removed list item.

Measured 2026-10-01 against a file holding four content lines and three headers:

```
$ git diff | grep -vE '^[-+][-+]'
diff --git a/f.md b/f.md
index 4adeb90..89efa4a 100644
@@ -1,4 +1,2 @@
 keep
```

Every content line went and all three headers stayed — the exact inverse of the intent. The same change showed as one insertion under `git diff --numstat`, which is how the empty-looking grep was caught.

**No header pattern is exact, so do not reach for a better one.** The `--- ` form carries the same collision one character further out: a removed line whose content begins with `--` arrives in the diff as `--- `, so `grep -E '^[-+]' | grep -vE '^(\+\+\+ |--- )'` drops it along with the header. Verified in the same run, where a line reading `-- a dash line` disappeared.

**Judge a diff's content with `git diff --numstat <path>`, and read a grep's silence against that count.** A grep printing nothing beside a non-zero insertion count is a broken filter rather than an empty diff. The count cannot be fooled by a pattern, and the disagreement between the two is the only thing that reports this at all.
