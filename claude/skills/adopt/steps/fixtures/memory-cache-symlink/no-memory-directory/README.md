# Fixture repo

A repo with a .claude/ and no committed memory directory. This step never creates one, so
apply must refuse rather than let the linking script mkdir -p it into existence.
