# Docker from Git Bash and Node on Windows

Invoking a container (e.g. the OrcaSlicer `orca-spike` image, or any `docker run`)
on this Windows box hits two path-translation traps, plus a heredoc gotcha.

## Git Bash mangles container-absolute paths (`MSYS_NO_PATHCONV`)

MSYS2/MINGW (Git Bash) auto-rewrites Unix-looking *arguments* into Windows paths.
A container-side path passed to `docker run` — `/out/build-profiles.sh`,
`/opt/orcaslicer/bin/orca-slicer`, the container side of a `-v host:/prof` mount,
even a `/tmp/x.mjs` arg handed to `node` — gets silently rewritten to e.g.
`C:/Program Files/Git/out/...`, so the command fails with "No such file or directory."

Fix: prefix the command with `MSYS_NO_PATHCONV=1`. (Double-slash `//out/...` is an
alternative but applies per-arg and reads worse.)

```bash
MSYS_NO_PATHCONV=1 docker run --rm \
  -v "$PWD/web/slicer/profiles:/out" \
  --entrypoint bash img /out/build.sh
```

## Spawning docker from Node: forward-slash + drive-letter mounts

`child_process.spawn` bypasses MSYS, but Node hands you backslash host paths.
Docker Desktop accepts forward-slash absolute paths *with* the drive letter —
`D:/projects/x:/prof:ro` — so normalize with `p.replace(/\\/g, "/")` before
building the `-v` spec. Docker Desktop shares `D:` and
`C:\Users\…\AppData\Local\Temp` (i.e. `os.tmpdir()`) by default, so staging temp
dirs there mounts without extra config.

```js
const slash = (p) => path.resolve(p).replace(/\\/g, "/");
spawn("docker", ["run", "--rm", "-v", `${slash(hostDir)}:/out`, image, ...]);
```

## Heredoc eats backslashes — use the Write tool

Writing a JS file via `cat > f.mjs <<'EOF' … EOF` collapsed `\\` to `\` (breaking a
`/\\/g` regex) *even with a quoted delimiter*. For any file containing
backslashes/regex escapes, use the Write tool, not a Bash heredoc.
