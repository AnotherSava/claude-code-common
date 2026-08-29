---
name: feedback_encryption_key_travel
description: Before encrypting something, ask where the decryption key must end up — encryption that sends a broad key somewhere worse than the data is a net loss
metadata:
  type: feedback
---

Encryption changes **who can read a thing**. Deciding to encrypt is therefore only half a decision: the other half is where the **decryption key** has to travel for the thing to stay usable. If the key must reach a machine less trustworthy than the data is sensitive, encrypting made the exposure worse, not better.

Ask it in this order: *who reads this file, and on what machine?* A file read only on trusted workstations can be encrypted for free. A file read by a process on a production box means the key goes on the production box.

**Why:** on 2026-08-28, `host.env` in a shared-proxy repo looked like an obvious encryption candidate — a tailnet address and an alert email, no credential. Two facts killed it. The email was already the git author address on every commit, so encrypting the file hid nothing about it. And the file is read by a tool running **on the box**, from a real checkout there, so encrypting it required the shared passphrase on an internet-facing machine fronting a commercial site — a key that decrypted every encrypted file in every repo. Trading a broad key exposure for one unroutable CGNAT address is the wrong direction. Its sibling `publish.env` was the opposite case and was encrypted happily: nothing on the box reads it, verified — no `config/` directory in the box's checkout at all — so ciphertext sits there inert and the key never travels.

**How to apply:** before proposing encryption, trace every reader. Then check whether the content is already exposed by another channel (commit metadata, a public URL, DNS) — encrypting one copy of something published elsewhere buys nothing. Where the key would have to travel badly, the alternatives are usually better: keep the value out of the repo entirely (a names-not-values file supplied at deploy time), keep the repo private, or accept the disclosure and record it. And note the inverse trap: an *unlocked* checkout is not required for an encrypted file to be harmless — where nothing reads it, ciphertext is inert, and adding the tooling there is what would break it. Related: [[feedback_check_destination_visibility]].
