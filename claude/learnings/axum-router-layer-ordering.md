# axum: a layer guards only the routes registered before it

Verified against axum 0.8 on 2026-08-30, while moving four per-handler auth checks into one middleware.

`Router::layer` applies to routes already added, and to nothing added afterwards. From axum's own
`docs/routing/layer.md`:

> Additional routes added after `layer` is called will not have the middleware added.

So this is correct:

```rust
Router::new()
    .route("/api/a", post(a))
    .route("/api/b", get(b))
    .layer(middleware::from_fn_with_state(state, guard))   // guards a and b
    .with_state(app)
```

and appending one line in the obvious place silently ships an unauthenticated route:

```rust
    .layer(middleware::from_fn_with_state(state, guard))
    .route("/api/c", post(c))    // NO guard. no source check, no token.
    .with_state(app)
```

`route_layer` has the same ordering rule; it only differs in returning 405 rather than falling through.

## Why this is worse than an ordinary footgun

The unguarded version **compiles, type-checks, and passes every existing test**. Nothing about the types
distinguishes a guarded router from an unguarded one, and the tests that cover the guard are typically
unit tests of the guard's *predicate*, which still pass. The failure is invisible in review too, because
the diff is a single well-formed `.route(...)` line that looks exactly like its neighbours.

The dangerous moment is precisely when someone extends the router later — which is when the original
author is not present and the comment above the layer is the only thing carrying the rule. Writing
"a new route is covered by construction" in that comment (an easy thing to believe) is worse than writing
nothing: it removes the reason to check.

## Testing it when you cannot build the router

The natural test — serve the real router and assert every route 401s without credentials — needs whatever
state the router carries. In a Tauri app that is an `AppHandle`, which a unit test cannot construct, and
similar blockers are common (a DB pool, a client with real credentials).

When that blocks you, assert the *ordering invariant against the source text*. It is unusual, and it is
the only thing that fails when someone adds the natural next route in the natural next place:

```rust
#[test]
fn guard_covers_every_route() {
    let src = include_str!("sync.rs");
    let start = src.find("let router = Router::new()").expect("router construction moved");
    let expr = &src[start..];
    let expr = &expr[..expr.find(".with_state(").expect("router must end with .with_state")];

    let layer_at = expr.find(".layer(").expect("the guard layer is gone");
    let last_route_at = expr.rfind(".route(").expect("no routes found");
    assert!(last_route_at < layer_at, "a route is registered BELOW the guard layer");
    // Pin the count too, or the assert passes vacuously once routes move elsewhere.
    assert_eq!(expr.matches(".route(").count(), 4, "route count changed — check the new one is above the layer");
}
```

The count assertion is the part people leave out. Without it the test keeps passing after the routes are
refactored out of that expression, at which point it is asserting nothing.

### The second vacuity mode: the test can match its own source

`include_str!("thing.rs")` pulls in the **whole file, the test module included**, so every literal the
test searches for and asserts on is itself present in the text being searched. The test above is safe by
construction — its slice is bounded to the router expression, well above the `mod tests` block — but that
is a property of the bounds, not of the technique, and it is easy to lose.

The failure looks like this — a test locating a call site and asserting a flag is set on it:

```rust
let at = src.find("let mut cmd = Command::new(&bin);").expect("the spawn moved");
let body = &src[at..src[at..].find(".spawn()").unwrap() + at];
assert!(body.contains("creation_flags(CREATE_NO_WINDOW)"));
```

Delete the real call site and `find` does not fail — it lands on the *test's own* copy of that string,
slices to the test's own `".spawn()"`, and the assert is satisfied by the test's own assert line. It
passes while guarding nothing. Anchoring on a string unique to production code helps, but that is a
property nobody re-checks when editing the test later.

**Negative-control it once, on purpose.** Delete or comment out the thing the test guards, run it,
confirm it fails with the message you wrote, then restore. That costs one rebuild and is the only
evidence a source-scanning test is not tautological — reading it is not enough, since both vacuity modes
look correct on the page. Do it when you write the test, and again when one is handed to you by someone
who could not run it themselves.

## Better, when you can

If the router's state is constructible in tests, prefer serving it on an ephemeral loopback port and
asserting each path returns 401/403 rather than 200 — that tests behaviour instead of text. Build the
route list as a `const` the router is constructed *from*, so a new route cannot exist without appearing in
the list the test iterates.
