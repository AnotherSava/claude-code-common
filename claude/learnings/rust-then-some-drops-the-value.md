# A `then_some` guard runs `Drop` on the branch it meant to reject

A null-pointer guard written with `then_some` is memory-unsafe in exactly the case it exists to
handle. This shipped in a macOS FFI wrapper and was caught by review rather than by the compiler,
by a test, or by `RUSTFLAGS="-D warnings" cargo check`.

```rust
// WRONG — the null branch calls CFRelease(NULL) and traps.
(!r.is_null()).then_some(CfString(r))

// Right — nothing is constructed unless the pointer is good.
if r.is_null() { None } else { Some(CfString(r)) }
// or, lazily:
(!r.is_null()).then(|| CfString(r))
```

## Why

The signature is the whole explanation, and it reads as harmless:

```rust
pub fn then_some<T>(self, t: T) -> Option<T>
```

`t` is taken **by value**, so the argument is evaluated and moved in *before* `then_some` looks at
the bool. On `false` the value is never moved out, so it is dropped at the end of the call. If `T`
has a `Drop` impl, that impl runs — on a value the guard just decided was invalid.

The lazy `then(|| …)` takes a closure instead, so nothing is constructed on the false branch. The
two read almost identically at the call site, which is what makes the substitution so easy to make.

## Why it is invisible

Every normal defence misses it:

- **The compiler is happy.** `then_some` is being used exactly as designed.
- **Tests miss it.** The bad branch fires only when the underlying call fails, which for a fixed
  ASCII literal means an allocator failure — unreachable in any ordinary test.
- **The `Err` path looks implemented.** In the case below, `hold()` carried a perfectly good
  `.ok_or_else(|| "could not build the assertion-type string")` that was **dead code**: control
  trapped inside the constructor and never returned to produce it.
- **Grep does not sort it out.** A crate can have a dozen `then_some` call sites and only one of
  them matters. The predicate is not "is this `then_some`" but "does this `T` have a `Drop` impl
  that does something". Numerics, `&str`, `Copy` types are all fine.

## The worked case

A CoreFoundation string wrapper:

```rust
struct CfString(CFStringRef);

impl Drop for CfString {
    fn drop(&mut self) {
        unsafe { CFRelease(self.0) };   // no null check — by construction there shouldn't be one
    }
}

impl CfString {
    fn new(s: &str) -> Option<Self> {
        let c = CString::new(s).ok()?;
        let r = unsafe { CFStringCreateWithCString(ptr::null(), c.as_ptr(), UTF8) };
        (!r.is_null()).then_some(Self(r))     // ← the bug
    }
}
```

`CFRelease`'s documented contract is that its argument must not be NULL, and on macOS 15 it is not
merely undefined — a one-line C program calling `CFRelease(NULL)` exits **133** (SIGTRAP, `os_trap`
inside CoreFoundation). So the failure mode is not a leak or a wrong value: the whole process dies,
taking every other subsystem with it.

## The general rule

Any combinator that takes the value by value evaluates it unconditionally. Reach for the
lazy sibling whenever the value is expensive, fallible, or owns a resource:

| Eager (argument by value) | Lazy (closure) |
|---|---|
| `bool::then_some(t)` | `bool::then(\|\| t)` |
| `Option::unwrap_or(t)` | `Option::unwrap_or_else(\|\| t)` |
| `Option::ok_or(e)` | `Option::ok_or_else(\|\| e)` |
| `Result::unwrap_or(t)` | `Result::unwrap_or_else(\|_\| t)` |
| `Option::or(opt)` | `Option::or_else(\|\| opt)` |

For the first row the usual advice is about *cost*. With a `Drop` type it is about *correctness*,
which is why it belongs in a guard's review checklist rather than a performance one.

An RAII wrapper around a raw handle is where this bites hardest, because the wrapper's whole
purpose is that `Drop` releases something — so the wrapper is precisely the `T` for which the eager
form is unsafe. When a fallible constructor wraps a raw handle, construct it inside the success
branch and nowhere else.
