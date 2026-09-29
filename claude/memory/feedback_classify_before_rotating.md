---
name: feedback_classify_before_rotating
description: A decrypted secret-file dump needs its contents classified before proposing rotation or a scrub
metadata:
  type: feedback
---

When a transcrypt-encrypted committed file is decrypted into a transcript — a `diff=crypt` textconv
in a skill's Context is the known route — classify what it holds before proposing any remedy. A
`config/publish.env` holds coordinates: SSH host, container name, compose directory, verify URLs,
vhost path, and the *names* of the Doppler project and config. The authenticators are never in it;
the publish script fetches them at run time and writes them straight to the box. Nothing to rotate.

**Why:** the same coordinates are committed in plaintext, deliberately, in each repo's deploy doc,
compose file, caddy vhost, `.env.example` and systemd units — measured 2026-09-29 as 35 tracked
files across six repos. A dump adds no exposure, and scrubbing transcripts buys nothing while
irreversibly rewriting hundreds of files: the same scan found the values in 4,759 lines across 367
transcript files in ten project directories, because they are the ordinary vocabulary of every
publish-related session.

**How to apply:** say which of the two it is — [[feedback_rotate_dont_abandon]] governs a real
authenticator. Measure the reach before *offering* a destructive remedy, not after agreement; the
offer's stated scope is what gets answered. Check by key name and count, never by printing values
([[feedback_never_dump_secret_bearing_config]]).
