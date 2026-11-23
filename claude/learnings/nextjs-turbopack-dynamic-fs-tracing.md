# Next.js file tracing and a filesystem root read from the environment

`next build` with Turbopack (measured on Next 16.4) warns `Dynamic filesystem access causes tracing of the whole
project` on every `fs` and `path` call whose argument it cannot bound statically. A data directory read from an
environment variable at run time, such as a file store mounted into the container, is the usual cause. Each warning
is one call site, so a module that joins, stats, reads and lists under that root can print a dozen of them, and the
tracer then copies every source file and the public folder into the standalone server output to be safe.

## The fix: one ignore comment where the root is computed

Put the opt-out on the expression that produces the root, inside the one function every call site goes through:

```ts
export function storeDir(): string {
  return resolve(/*turbopackIgnore: true*/ process.env.STORE_DIR ?? '/data/store');
}
```

Measured on a module with eleven warnings across `join`, `stat`, `readFile`, `readdir` and a `resolve(...).startsWith`
containment guard: all eleven cleared, and the source and public files listed across every `.next/server/**/*.nft.json`
went from 2,730 entries to zero, and each route's trace roughly halved (the largest, 564 files to 313). Annotating each call site is
not needed: the value the ignored call returns is no longer traced, so the downstream calls stop being dynamic.

`resolve` makes the returned root absolute, which changes nothing for callers that join under it or compare resolved
paths, but check any caller that compares the raw string.

## How to measure it

Read the traces rather than the warning count:

```python
import glob, json
n = sum(len([f for f in json.load(open(p))['files'] if '/src/' in f.replace('\\', '/') or '/public/' in f.replace('\\', '/')])
        for p in glob.glob('.next/server/**/*.nft.json', recursive=True))
print(n)
```

## The alternatives Next's message offers

- **Scope the path under a static root** (`path.join(process.cwd(), 'data', id)`). Wrong for a store that is a
  bind mount elsewhere in production.
- **Use it in development only.** Not an option for a store the production server reads.
- **Remove the call.** Not an option for the same reason.

The ignore comment is the only one that fits a run-time root, and a comment beside it saying why the path is dynamic
keeps it from reading as a silenced warning.
