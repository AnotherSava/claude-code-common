---
name: feedback_no_unshipped_back_compat
description: Don't write compatibility shims for a format/key/API that never shipped — check it was in a release before adding fallback or migration code
metadata:
  type: feedback
---

Don't write compatibility shims for a format, config key, or API that has never been released. Before
adding a fallback branch, a migration, or a "still accepted" note, establish that the old form
actually shipped — was in a tagged release, or exists in a config on a machine other than this one.
If it only ever existed in earlier commits of the work in progress, delete it outright.

**Why:** I added a `scale` config key to a project, reshaped it twice within the same session, and
then wrote parsing for its earlier `"auto"` spelling *and documented it in the README as supported* —
for a format no user had ever had. The user cut it: "we don't need this." Compatibility with an
unreleased format is dead code that also makes a false public promise, and the promise is the worse
half: it commits future maintenance to a shape nobody is using.

**How to apply:** the question is never "could someone have the old form?" but "did the old form ever
leave this machine?" Same-session refactors, unpushed commits and not-yet-released branches all
answer no. Say so explicitly when removing it, so the reasoning is visible rather than looking like a
dropped requirement.

Related: [[feedback_no_permanent_logic_for_one_time]], [[feedback_research_to_production_cleanup]].
