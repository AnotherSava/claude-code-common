# Running a POSIX-only test suite from Windows through WSL

When a repo's tests import `fcntl`, shell out to Linux binaries, or otherwise assume POSIX, native Windows
Python cannot run them, and the fix is to hand the run to WSL from the Git Bash gate rather than to port
the tests.

## Delegating from Git Bash

```bash
case "$(uname -s)" in
  MINGW* | MSYS* | CYGWIN*)
    exec wsl --cd "$(pwd -W)" -e sh -lc 'exec bash tests/run' ;;
esac
```

- `wsl --cd` takes the **Windows** path (`pwd -W`) and maps it to `/mnt/<drive>/…` itself.
- `wsl` propagates the inner exit status, so the gate's verdict survives the hop.
- Anything that reads the Windows user's home (`~/.claude/…`) has to stay on the native side: WSL's `$HOME`
  is a different directory.

## Why `sh -l` and not `bash -l`

A login `bash` reads the first of `~/.bash_profile`, `~/.bash_login`, `~/.profile` and stops. Ubuntu puts
`~/.local/bin` on PATH in `~/.profile`, so a WSL account that has any `~/.bash_profile` never gets it, and
binaries installed there are invisible to `bash -lc`. A login `sh` (dash) reads `~/.profile` only, so
`sh -lc '… bash …'` picks the PATH up and the inner `bash` inherits it. Measured: `bash -lc 'command -v
caddy'` found nothing while `sh -lc` returned `~/.local/bin/caddy`.

## Userland tools without sudo

WSL's `sudo` usually wants a password a non-interactive session cannot give, so install into `~/.local`:

- **A static binary** (Caddy and similar Go tools): download the release tarball and drop the binary in
  `~/.local/bin`. Match the version the production host runs, since a suite that asserts Caddy's config grammar is testing that binary.
- **A newer OpenSSL than the distro ships.** Ubuntu 24.04 has 3.0; `openssl x509 -req -not_before/-not_after`
  needs 3.4+. Build the release tarball with
  `./Configure --prefix=$HOME/.local/openssl-3.5 --libdir=lib no-tests no-docs && make -j && make install_sw install_ssldirs`.
  `install_sw` alone omits `ssl/openssl.cnf`, and `openssl req` then fails with `Can't open …/openssl.cnf`.
  Put a wrapper in `~/.local/bin/openssl` that sets `LD_LIBRARY_PATH` to the prefix's `lib` and execs the
  real binary, so it shadows the system one only on PATH.
