---
name: feedback-no-cache-cheap-derivations
description: Use plain @property for cheap derived values; reserve @cached_property for expensive computation
metadata:
  type: feedback
---

When a derived value is cheap to recompute (e.g. constructing a small object from a few primitives), use plain `@property` instead of `@cached_property`.

**Why:** The user pushed back when I reached for `@cached_property` to memoize a `SmartBox` construction: *"it's just a box, you don't have to cache its creation"*. `@cached_property` carries hidden costs — it requires the class to be non-frozen, the cached value is mutable per-instance state that lives until the instance dies, and there are subtle gotchas around shared mutation. Those costs aren't justified for cheap operations.

**How to apply:**
- Default to plain `@property` for derived values.
- Only reach for `@cached_property` when profiling or reasoning shows the computation is genuinely expensive (e.g. a complex OCC boolean op, a network call, a parsing pass).
- "Cheap" includes: arithmetic, constructing small primitives, dictionary/list lookups, calling other cheap properties.
