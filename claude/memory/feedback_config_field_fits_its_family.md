---
name: feedback_config_field_fits_its_family
description: A new setting copies its siblings' placement, naming and on/off idiom, and its default depends on which audience receives the build
metadata:
  type: feedback
---

Before adding a config field, find the family it belongs to and copy that family's shape. Placement first: put it beside the settings that answer the same kind of question, not at whatever level was convenient to reach. Then the idiom. Where the neighbours use a value that doubles as its own switch (a threshold whose `null` or `0` disables the feature), do that instead of adding a boolean, because a separate on/off flag beside a value is a second thing to keep in step with it.

**Why:** corrected twice in a row on one field. A Telegram alert toggle went in at the top level as `notify_stale_tab` while every other alert knob lived under `notifications.telegram`, and then as a bare boolean where a delay would have served the user better. Both were caught by the user rather than by me, and in both cases the evidence was sitting in fields I had already read.

**How to apply:** read the sibling fields before writing the new one, and say which family you matched it to. Watch for false precedents: a flag at the top level may be there because it is a cross-cutting modifier over several features, or a feature switch whose notification is a side effect, rather than an alert knob like the one you are adding. That is exactly the misreading that produced the first mistake.

**Defaults belong to an audience, not to the code.** A default that is useful to someone who built the binary can be an unexplained surprise to someone who just installed it, so split them by build channel rather than picking one and defending it. The signal is the release workflow: set an explicit environment variable in the step that produces the installer and bake it in at build time. Do not infer it from `CI` or `debug_assertions`, which both answer a different question, since a local deploy also builds `--release` and a CI check workflow runs in CI while shipping nothing. An explicit value in the config file must still win over either default.
