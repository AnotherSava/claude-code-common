---
name: feedback_ascii_repo_paths
description: Committed and served paths should be Latin/ASCII and lowercase-hyphenated, with ordering in a manifest not a filename prefix
metadata:
  type: feedback
---

Paths that get committed or served should be Latin/ASCII, lowercase and hyphenated — and reading
order belongs in the data that already describes the structure, not in a numeric filename prefix.

**Why:** An archive of a Russian site published each gallery under a folder named from its
Cyrillic title, with a two-digit position prefix for ordering:
`/Events/21 Эльбрус(январь 2004)/03 Эльбрус. Заключение/index.html`. Encoded, the worst URL ran
to 324 characters — six per Cyrillic letter, plus `%20` and `%28` for the spaces and parens. The
user's questions were the right ones: "why do we need cyrillic in folder names in repository?
same for the number prefix". Transliterating and dropping the prefix took it to 64 characters,
and the ordering was already in the manifest the site reads anyway.

**How to apply:** Transliterate for the path and leave the *displayed* heading in the original
script — the reader still sees `Эльбрус (часть третья)`; only the address is Latin. Keep ordering
in the manifest rather than the names. Watch for content words that look like noise and aren't:
dropping a month beside its year shortens `Эльбрус(январь 2004)` correctly, but the same rule
applied blindly turns the holiday `9 мая! Покатушки…` into `9-pokatushki…` — require that no day
number precedes the month. Same instinct as [[feedback_no_underline_links]]: strip what carries
no meaning, keep what does.
