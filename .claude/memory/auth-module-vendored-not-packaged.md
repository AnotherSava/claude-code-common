---
name: auth-module-vendored-not-packaged
description: The auth skill's sign-in module is copied unchanged into each app rather than shipped as an npm package; why, and who decided
metadata:
  type: project
---

The sign-in module, `claude/skills/auth/module/signin.ts`, reaches an app as an unchanged copy, and `cmp` against the skill's file is the drift check. An npm package was considered and not built.

**Why:** a package needs a registry, or a git dependency with git and credentials inside every app's Docker build. Measured 2026-11-12: the app images are `node:24-alpine` and `ubuntu:24.04` with no git, and no app carries a non-registry dependency. Claude recommended the copy; the user accepted it by approving the build on 2026-11-12 without discussing the alternative further.

**How to apply:** do not turn the module into a package unprompted. If copies start drifting, or a consumer appears that cannot take a copied file, raise it with the user with that cost stated. [[feedback_delete_the_copy_dont_reconcile]] pulls the other way, which is why this is written down.
