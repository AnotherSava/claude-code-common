# Composing a Caddyfile from several files

How Caddy assembles a config split across a base file, imported fragments and a directory of per-tenant
vhosts — and which of the resulting failures are loud, which are silent, and which name the file that
caused them. Everything here was probed against **Caddy v2.11.4** with `caddy validate` / `caddy adapt`;
re-run them before trusting any of it on a newer build.

Companion: `docker-compose-shared-host-co-tenancy.md`, which covers the naming side of a shared proxy.

## The global options block

- **Exactly one, and it must be first.** A second keyless block, or one placed after a site block, fails
  with `server block without any key is global configuration, and if used, it must be first`.
- **`import` works *inside* it**, and the imported directives take effect — verified by diffing
  `caddy adapt` output against an inline baseline.
- **A glob inside it layers fragments**, so a base file can carry the mechanism while the content lives
  elsewhere:

  ```caddyfile
  {
      import /etc/caddy/global.d/*.conf
  }

  import /etc/caddy/snippets.d/*.caddy
  import /etc/caddy/conf.d/*.caddy
  ```

- **A glob matching zero files is valid**, and so is one over a directory that does not exist. A layer
  nobody uses needs no placeholder file.
- **A missing *literal* file is fatal**: `File to import not found: <path>`. So optional layers must be
  globs, never literal paths.
- **Later-sorting fragment wins — for scalars only.** Two fragments both containing a `servers { }` block
  hard-fail with `cannot have 'servers' global options with duplicate listener addresses`. The rule is one
  fragment per directive *name*, not one per concern, which defeats the obvious "90-override.conf" scheme
  for exactly the block-shaped options most likely to differ between machines.
- `automatic_https` is the key in the **adapted JSON**, not a directive. As a directive it gives
  `unrecognized global option: automatic_https`; the directive is `auto_https off`.

## An empty global block does not reserve the namespace

If the base config has **no** global options block — or one that is empty or comment-only — then any
imported file may open its own, and it applies to the whole server. On a proxy that imports a directory
other people write into, that means a dropped-in file can set box-wide options with `caddy validate` green
and nothing in any log.

**One real directive closes it.** With a non-empty block present, an imported file's keyless block is
rejected by the "must be first" rule above. Pick something already at its default so the claim changes no
behaviour — `admin localhost:2019` works — and say in a comment that the directive exists to *occupy* the
block, or someone will remove it as redundant.

## Two files can claim one hostname without erroring

- `host.example { }` in one file and `host.example/ { }` in another **both adapt, rc=0**, and the path form
  takes `/`. Nothing warns. Two individually valid files silently decide which one serves the hostname.
- Exact duplicates *do* error — `ambiguous site definition: host.example` — but see the locality section:
  that error names no file.
- A bare `:443 { }` adapts fine and becomes the catch-all for every hostname without a named block. It
  adapts to a route with `match: null`, so it contributes **no hostname**: any check that compares "hostnames
  served" against "hostnames allowed" cannot see it, and needs a separate catch-all clause.

## `path /x/*` does not match `/x`

Caddy's `path` matcher is exact per pattern. `/api/inbox/*` matches `/api/inbox/anything`; it does **not**
match `/api/inbox` itself. So a gate written as

```caddyfile
@writeOffnet {
	path /admin/* /api/inbox/*
	not remote_ip 100.64.0.0/10
}
respond @writeOffnet 404
```

protects every decorative sub-path and leaves the bare endpoint — usually the one that actually accepts a
POST — reachable by anyone. Nothing warns about it: the config validates, the sub-paths behave, and the hole
is one path segment wide.

List both forms, every time:

```caddyfile
	path /admin /admin/* /api/inbox /api/inbox/*
```

The same asymmetry bites a checker written to verify this. A helper that treats `/x/*` as covering its own
bare prefix will pass the broken config it was written to catch — so test the checker against the *failure*,
not only against the fixed file.

## Snippets are a second flat namespace

- A snippet must be imported **before** the file that calls it, or you get
  `File to import not found: <name>` — the same message as a missing file, which sends the reader hunting
  the filesystem for something that is not a path at all.
- **Redeclaring a snippet is fatal for everyone**: `redeclaration of previously declared snippet <name>`
  refuses the whole config, not just the offending file.
- An **empty** snippet is worse than a missing one. `(tls-dns) { }` adapts clean and silently contributes
  nothing, so a site expecting it falls back to defaults. If a capability is unavailable, omit the file and
  take the loud import error.

## Import cycles are caught only in the absolute form

A file inside the imported directory that re-imports that directory by **absolute** path gives
`a cycle of imports exists between …`. The **relative** form (`import conf.d/*.caddy`) resolves against the
importing file's own directory, finds nothing, warns, and exits 0 — so Caddy never catches that shape.

## Error locality is wildly uneven, and it dictates how you validate

Some failures name the file, the line and the whole import chain:

```
Error: adapting config using caddyfile: redeclaration of previously declared snippet dup,
  at /etc/caddy/conf.d/tenant.caddy:1 import chain ['Caddyfile:4 (import)']
```

Others name **nothing at all** — no file, no line:

- `server block without any key is global configuration, and if used, it must be first`
- `ambiguous site definition: host.example`

Both of those are exactly the errors a dropped-in file causes, so on a config assembled from a directory
you cannot rely on the message to tell you which file broke it. **Adapt each candidate file on its own
first**, with the base and nothing else, and only then adapt the whole set. The solo pass is what makes the
blame certain; the full pass is the only thing that finds cross-file conflicts.

Related: an unterminated quote is reported against the *next* file alphabetically, for the same reason.

## The stock image ships a config that validates

`caddy:2` contains a placeholder `/etc/caddy/Caddyfile` (~769 bytes,
`:80 { root * /usr/share/caddy; file_server }`). If your real config is bind-mounted over it and the mount
is ever missing, `caddy validate --config /etc/caddy/Caddyfile` **passes green** against the welcome page.
A validation step that does not first prove it is looking at *your* file is checking the placeholder — assert
something only your config contains (the `import` line is a good marker) before trusting the result.
