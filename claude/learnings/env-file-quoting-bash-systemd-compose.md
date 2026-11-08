# One env file read by bash, systemd and docker compose

A rendered `KEY=value` file is often read by three parsers at once: a human's `. .env` (or `set -a; . .env`) while
debugging, systemd's `EnvironmentFile=`, and docker compose's dotenv for `${VAR}` interpolation. They agree only on a
narrow form, and an unquoted value that the two machine parsers accept can still break the human's `source`.

## The form all three read identically

Single-quote every value: `KEY='value'`. Measured 2026-11-08 (bash 5, systemd user instance via
`systemd-run --user --wait --pipe -p EnvironmentFile=…`, Docker Compose v5.3 `docker compose config --format json`).
Inside single quotes all three return the value literally for:

- spaces and tabs (`--with github.com/caddy-dns/porkbun`), so `. .env` no longer tries to execute the second word
- `$HOME`, `${X}` and backticks (no expansion; compose's `config` output shows `$$`, its escaping of a literal `$`)
- `#`, with or without surrounding spaces (not a comment inside quotes)
- `"` and mid-value backslash sequences (`\n`, `\t`, `\\`, `\s`, `\$` all come back as the literal characters)

## Where they disagree

- **A single quote** inside the value has no single-quoted form any of them accepts.
- **A newline** cannot be carried.
- **A trailing backslash**: bash and systemd read `K='end\'` as `end\`; compose reads `\'` as an escaped quote even
  inside single quotes, runs on to the next line and fails with `unexpected character "'" in variable name`.

So a renderer should refuse those three cases loudly (naming the key, never echoing the value, since these files
usually hold secrets) rather than reach for `shlex.quote`, whose `'"'"'` splice compose and systemd do not read.

## The reader trap

Anything that reads the rendered file back with a hand-rolled parser (to detect a rotated credential, say) must strip
the quotes too, or every value looks changed on every run. Strip only a leading `'` up to its closing `'`, and handle
inline `#` comments only for unquoted values, or a quoted value containing `#` is truncated.
