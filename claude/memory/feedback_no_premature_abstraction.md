---
name: feedback-no-premature-abstraction
description: Don't build interfaces/registries when there's only one concrete example; let abstractions emerge from 2-3 instances of duplication
metadata:
  type: feedback
---

Don't build shared abstractions (interfaces, plugin registries, type bases, dispatchers) when there's only one concrete implementation. Implement the first 1-2 instances as straightforward, self-contained modules. Wait for a third instance or concrete pain before extracting a shared interface.

**Why:** During the Chrome Assistant Summary tab work I proposed a generic `SummaryView<T>` interface + plugin registry + IndexedDB extraction store *before* any view's extraction logic existed. The user pushed back: "avoid going too format from the beginning, since there is not enough information on how processing will looks like, what data will it take into account, etc.; keep potential future complexity in mind, but don't burry in the boilerplate from day 1 to express it." Two unknowns can't drive a correct interface; it ends up either too tight (forcing awkward fits) or too loose (`unknown` everywhere, no value).

**How to apply:** When the user describes a feature with multiple variants (sub-tabs, parsers, providers, strategies, plugins), implement the first 1-2 instances as duplicated, self-contained modules sharing only conventions (function-name parity, parameter shape) — no enforced interface. Extract abstractions only when a third instance or concrete maintenance pain shows the right shape. Two duplicated 150-line modules beats one wrong interface plus two awkward conformers.
