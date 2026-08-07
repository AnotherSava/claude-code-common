# AES-256-GCM interop between Node and the browser (WebCrypto)

Encrypting on one side (build-time Node) and decrypting on the other (browser) with
AES-GCM fails mysteriously if you mix Node's classic `crypto` API with the browser's
WebCrypto — because they disagree on where the 16-byte GCM **auth tag** lives.

## The trap
- **Node classic** `crypto.createCipheriv("aes-256-gcm", key, iv)` keeps the auth tag
  **separate**: you pull it out with `cipher.getAuthTag()` after `final()` and must
  store/transmit it yourself; to decrypt you call `decipher.setAuthTag(tag)` before
  `final()`.
- **WebCrypto** `crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, data)` **appends**
  the tag to the ciphertext (last 16 bytes), and `subtle.decrypt` expects it appended.
- Mix them (Node `createCipheriv` → browser `subtle.decrypt`, or vice versa) and the tag
  is in the wrong place → `OperationError` / "Cipher job failed" / "unable to
  authenticate data". Looks like a wrong-key or corrupted-data bug; it's actually a tag
  framing mismatch.

## The fix — use `webcrypto.subtle` on BOTH sides
Node ships WebCrypto too. Import it and use the identical subtle API on the Node side, so
both ends produce/consume the exact same byte layout (tag appended):

```js
// Node (ESM): import { webcrypto as crypto } from "node:crypto";
// Browser:    const crypto = window.crypto;   // same subtle API below

async function deriveKey(password, salt, iterations, usage /* ["encrypt"] | ["decrypt"] */) {
  const base = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(password.normalize("NFC")), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations, hash: "SHA-256" },
    base, { name: "AES-GCM", length: 256 }, false, usage);
}

// encrypt: ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, plaintextBytes)
// decrypt: pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ctBytes)  // throws on wrong key
```

Store salt (16B), iv (12B), and iterations in a **self-describing envelope**
(`{ v, kdf, hash, iterations, salt, iv, ct }`, base64) so the KDF cost can be raised later
without breaking old blobs. On decrypt, a wrong password surfaces as a thrown
`OperationError` from `subtle.decrypt` — catch it and report "wrong password" rather than
letting the raw error bubble.

## Gotchas
- **`password.normalize("NFC")`** before encoding, so the same passphrase typed on
  different platforms derives the same key.
- **Secure context required in the browser**: `crypto.subtle` is `undefined` on `file://`
  and plain-HTTP origins — only HTTPS and `localhost` expose it. A "subtle is undefined"
  error at runtime usually means the page is being served insecurely, not a code bug.
- **PBKDF2 cost**: 600k iterations is the current OWASP floor for PBKDF2-HMAC-SHA256. It
  only slows each brute-force guess; it does not rescue a weak password.
- **You can't share one module across both sides**: the Node copy is an ESM module the
  browser can't `import` (it loads as a plain `<script>`). Keep two mirror copies of the
  deriveKey/encrypt/decrypt shapes and note in each that they must stay in sync.
- This is **obfuscation, not access control** when the ciphertext ships publicly — anyone
  can download and brute-force it offline with no rate limit. Security = password entropy
  × KDF cost. Fine for hiding data from casual viewers/scrapers; not for genuinely
  sensitive data.
