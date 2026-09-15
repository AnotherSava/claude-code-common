# Fixture: a rule this step must refuse rather than skip

One readable `filter=crypt` rule that needs normalizing, and one quoted pattern that cannot be
turned into a path this step can check. Applying here must exit 3 and write nothing — fixing the
first line and leaving the second unchanged would report a normalized repo while one crypt rule
still churns, which is idempotence rule 6.

`before/` cannot carry this case: that tree is the one apply has to transform, so a line stopping
apply there would turn the authoring gate red.
