# Giving a Tauri dev run a port it did not have at build time

A Tauri dev run needs one port in two places at once. The frontend dev server binds it, and the Tauri
CLI has to point the webview at the same number through `build.devUrl` — a field in `tauri.conf.json`,
which is static. So a port decided at launch has to reach both, and the obvious shortcuts each fail in a
way that looks like success.

Measured against tauri-cli 2.12.1 on macOS, October 2026, except where a line names another platform.

## Override devUrl per run with `--config`, pointing at a file

`tauri dev -c/--config` takes, in the CLI's own words, "JSON strings or paths to JSON, JSON5 or TOML
files to merge with the default configuration file". Pass a **path**, not inline JSON: the inline form is
a single argument full of quotes and braces, and on Windows an args array handed to
`spawnSync(..., {shell: true})` is concatenated without escaping, so cmd.exe reparses it and the JSON
does not survive. Measured on Windows 11 with Node v24.19.0, that form splits an argument at its first
space outright. A pre-quoted single command line does survive, so the shell route is not hopeless — and a
file path is the better argument regardless, being one token with no quotes or braces of its own to
mangle. It still needs whatever quoting the route needs: on Windows the temp directory sits inside the
user profile, so an override written to `C:\Users\First Last\AppData\Local\Temp\…` carries a space like
any other path. Write the override to a temp file and hand over its name.

```js
writeFileSync(overridePath, JSON.stringify({ build: { devUrl: `http://localhost:${port}` } }))
spawnSync(cli, ["dev", "--config", overridePath], { stdio: "inherit" })
```

Give the file a name carrying the pid. A fixed basename is shared by every checkout of the project, and
with a per-run port two concurrent dev runs then cross-wire: measured, run A's CLI read run B's
`devUrl`, so A's window loaded B's frontend with nothing reporting it. Remove it after `spawnSync`
returns — the CLI has exited by then, so nothing is still watching the file.

## The merge is verifiable without launching the app

`devUrl` is validated as a URI while the config is merged, before any Rust build starts. Feeding the
override a deliberately bad value is therefore enough to prove the file was read:

```
$ echo '{"build":{"devUrl":"not-a-url"}}' > /tmp/probe.json
$ tauri dev -c /tmp/probe.json
   Error `"tauri.conf.json"` error on `build > devUrl`: "not-a-url" is not a "uri"
```

That exits immediately, with no compile and no window — which makes it the cheap way to confirm a
`--config` path reaches the field. `tauri info` cannot substitute: it rejects `-c` outright with
`unexpected argument '-c' found`.

## `devUrl: null` selects a different dev server, on 1430

Dropping the value looks like the clean way to say "resolved elsewhere". It is not the absence of a
setting — it is the documented trigger for the CLI's own built-in static-file server. The same binary
carries `--no-dev-server` ("Disable the built-in dev server for static files"), `--port <PORT>`
("Specify port for the built-in dev server for static files. Defaults to 1430", env `TAURI_CLI_PORT`)
and the schema text "If you don't have a dev server or don't want to use one, ignore this option and use
`frontendDist` … and Tauri CLI will run its built-in dev server".

So with `devUrl` null, anything invoking `tauri dev` outside the wrapper serves `frontendDist` — usually
a gitignored `dist/` holding the last production build — on a port nothing allocated, and opens a window
with no error at all. A stale bundle presenting as a working app is worse than a failure, and the
machine it happens on is the developer's, because theirs is the one with a `dist/`.

## A port-less devUrl is accepted, not refused

The next idea is `"http://localhost"`, keeping the field non-null while naming no number. The CLI accepts
it: `tauri info` prints `devUrl: http://localhost/`, and a real `tauri dev` logs

```
Warn Waiting for your frontend dev server to start on http://localhost/...
```

and waits. The binary does contain a "no port number in the dev URL" string, but it does not fire on
`tauri dev`. Reading that string and concluding the refusal existed is a mistake worth naming, because
the string is exactly what a grep of the binary surfaces.

So the static `devUrl` keeps a real port and is overridden every run. The committed value is then read
only by something that bypasses the wrapper, where it is the difference between a loud wait on a
reachable address and a silent stale bundle.

## The wrapper goes on the script that starts the CLI

The Tauri CLI runs `beforeDevCommand` itself, so the frontend dev script is invoked by the CLI rather than
by whoever started the app. That settles where the port has to be resolved: before the CLI runs, because it
reads `devUrl` from its config before any frontend server exists. So the wrapper replaces the script that
launches the CLI, and the frontend script stays bare and inherits `PORT` from the environment the CLI was
handed. In tauri-dashboard that is `"tauri": "node scripts/dev.mjs"` against `"dev": "vite"`, with
`"beforeDevCommand": "npm run dev"` in `src-tauri/tauri.conf.json`.

Wrapping the frontend script instead resolves the port after the CLI has already read `devUrl`, so the
frontend server binds the registry's number while the webview opens on the committed one. A wrapper that
forwards its unrecognised subcommands to the CLI turns that into a loop: the CLI runs `npm run dev`, which
re-enters the wrapper, which hands the frontend command back to the CLI as a subcommand. Read off those
three files rather than run — starting the chain opens a window.

## Where the frontend half lives

Getting the resolved port into the frontend dev server is the other half of the same launch, and it is
convention 015's step 3, in `conventions/versions/015-ports-from-registry/README.md`: Vite reads no `PORT`
from the environment, so its config has to read it, and the refusal for a run that arrives without one
belongs in a `configureServer` hook rather than at config load. Everything above is the Tauri CLI's half.
