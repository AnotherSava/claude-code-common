# rustls crypto providers, and the Windows NASM trap

Applies to rustls 0.23.x. Verified 2026-08-27 against rustls 0.23.42, aws-lc-rs 1.17.3,
aws-lc-sys 0.43.0, ring 0.17.14, reqwest 0.13.4.

## Installing NASM on Windows CI is usually the *cause*, not the cure

The reflex when a Rust build fails on `aws-lc-sys` for want of an assembler is to add
`ilammy/setup-nasm` to the workflow. That is backwards for anything that reaches aws-lc-sys
*through rustls*, because rustls already turns on the escape hatch:

```toml
# rustls-0.23.42/Cargo.toml
aws_lc_rs = ["dep:aws-lc-rs", "webpki/aws-lc-rs", "aws-lc-rs/aws-lc-sys", "aws-lc-rs/prebuilt-nasm"]
```

`aws-lc-sys` ships 26 pre-assembled `.obj` files in `builder/prebuilt-nasm/` — one per `.asm`
source in `builder/cc_builder/win_x86_64.rs` — but only uses them as a *fallback*
(`builder/main.rs`, `use_prebuilt_nasm()`):

```
windows && x86_64 && !is_no_asm() && !test_nasm_command() && !is_disable_prebuilt_nasm() && is_prebuilt_nasm()
```

Upstream states it plainly (aws.github.io/aws-lc-rs/requirements/windows.html): *"If a NASM
assembler is detected in your build environment, it is always used… Prebuilt NASM objects are
only used as a fallback."* So `!test_nasm_command()` — NASM **not** on PATH — is the condition,
and installing NASM is the single thing preventing the no-assembler build.

Confirm the feature is live in your own graph before deleting anything:

```bash
cargo tree --target x86_64-pc-windows-msvc -e features -i aws-lc-sys | grep prebuilt-nasm
```

A hit means the step can go. Both outcomes build, so the change is safe either way: NASM present
→ real assembly, NASM absent → prebuilt objects. Caveats: the fallback is x86_64 only, and a
`fips` build is excluded from it (FIPS re-imposes a hard NASM dependency).

The general shape, worth carrying beyond this: **a CI step that exists to satisfy a build
requirement can be the reason the cheaper path is skipped.** Re-read what the requirement is
actually conditioned on before treating the step as load-bearing.

## Choosing between aws-lc-rs and ring

aws-lc-rs is rustls 0.23's default provider. Differences that actually matter:

| | aws-lc-rs | ring |
|---|---|---|
| Post-quantum KX (X25519MLKEM768) | in `DEFAULT_KX_GROUPS` | **absent** — `ALL_KX_GROUPS = [X25519, SECP256R1, SECP384R1]` |
| TLS 1.3 / 1.2 cipher suites | same 3 + 6, same order | same |
| Signature algorithms | 19, incl. P-521 and ECDSA-SHA512 | 14 |
| FIPS | available | `fn fips() -> bool { false }` |
| Windows build | prebuilt NASM objects (above) | committed pre-assembled COFF objects, "no Perl, no nasm" |
| Releases | ~15/year, corporate | last crates.io release 0.17.14 (2025-03), 500+ commits unreleased, bus factor 1 |

Do **not** justify a switch on "ring is unmaintained": RUSTSEC-2025-0007 was *withdrawn* in
2025-02 after the rustls team took crates.io ownership, and both providers are advisory-clean at
current versions.

The PQ gap is the real cost, and it is silent — nothing errors, the handshake just negotiates a
classical group. Worth checking what your endpoints actually do before deciding
(`openssl s_client -brief <host>:443` prints the negotiated group).

### reqwest has no ring feature

reqwest 0.13's `rustls` feature is hard-wired to aws-lc-rs (`rustls = ["__rustls-aws-lc-rs", …]`).
Going to ring means `rustls-no-provider` + a direct rustls dep with `features = ["ring"]` + an
explicit `CryptoProvider::install_default()`. Omit that call and it **compiles clean and panics**
in `Client::build()` — including for a client that only ever speaks plain HTTP, since the rustls
`ClientConfig` is built unconditionally. Feature unification can also drag aws-lc-rs back in
silently (rustls's *default* features include `aws_lc_rs`), leaving you building both and running
one.

## Enabling a feature on a transitive dependency

To turn on a feature of a crate you don't import, declare it as a direct dependency naming only
that feature — Cargo unifies additively:

```toml
reqwest = { version = "0.13", default-features = false, features = ["json", "query", "rustls"] }
# not imported anywhere; exists solely to add one feature to reqwest's rustls
rustls  = { version = "0.23.4", default-features = false, features = ["prefer-post-quantum"] }
```

reqwest pins rustls with `features = ["std", "tls12"]`, which leaves X25519MLKEM768 offered but
ranked last — so a server that selects it costs a HelloRetryRequest round trip on every full
handshake. `prefer-post-quantum` promotes it to first choice. Verify with
`cargo tree -e features -i rustls`, and leave a comment: an unimported dependency reads as dead
weight otherwise.
