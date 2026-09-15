# excluded-parent

Git will not re-include a path whose parent directory is excluded, so no `!` line below this rule
can bring the memory directory or the convention record back. Turning the entry into `.claude/*`
with explicit re-includes changes what every other file under it does, so apply must refuse.
