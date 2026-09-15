# Fixture: a repo already in the target shape

Both `filter=crypt` rules carry `text=auto eol=lf`, and `verify` must pass here without touching
anything. This is the path four of the five repos carrying a crypt rule actually take, so it is
where the free `applied` line comes from.

The `filter=lfs` rules keep their `-text`, which is what proves the step's reading is scoped to
crypt rules rather than to every line holding the word `text`.

The same rule as in `before/` about matching files applies: none ships here, because a nested
`.gitattributes` governs the dotfiles repo too and a crypt-marked fixture file would be stored
encrypted there.
