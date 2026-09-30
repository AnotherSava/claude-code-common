#!/usr/bin/env bash
# Pin the behaviour of git/hooks/pre-commit, which every commit on both machines runs.
#
# Most cases commit through git and assert on git's exit status. A case expecting a refusal also
# asserts the refusing check's own words in the output, so a commit git turned down for some other
# reason — nothing staged, a missing object — cannot pass as the hook's doing. Most cases run in a
# LOCKED clone: `.gitattributes` marks `*.secret.*` for the crypt filter and nothing configures that
# filter, which is every clone between `git clone` and a transcrypt unlock. Git ignores an
# unconfigured filter, so the hook is the only thing between a secret rewritten there and a plaintext
# commit. The two cases for a git that fails mid-check run the hook directly, with a `git` on PATH
# that fails the one subcommand. The unlocked cases initialise the vendored transcrypt with a
# throwaway password, and are reported NOT COVERED when that fails; so is the real-symlink case where
# this machine cannot make one.
#
# The run is sealed from this machine's own git setup: a temporary global config replaces
# ~/.gitconfig, whose core.hooksPath would otherwise point every scratch repo at the installed hook
# instead of the one under test, and whose signing key would be asked for on every commit. TMPDIR
# points inside the run too, since transcrypt's own check leaves a mktemp file behind.
#
#   bash claude/tests/pre-commit-hook.sh [hook]     default: git/hooks/pre-commit
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK="${1:-$ROOT/git/hooks/pre-commit}"
if [ ! -f "$HOOK" ]; then
    echo "pre-commit hook: no hook at $HOOK, so no case ran"
    exit 1
fi
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT

pass=0 fail=0 skipped=0
check() { if [ "$1" = "$2" ]; then pass=$((pass + 1)); else echo "FAIL $3 (got $1, want $2)"; fail=$((fail + 1)); fi; }
not_covered() { echo "NOT COVERED $2 case(s): $1"; skipped=$((skipped + $2)); }
native() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s\n' "$1"; fi; }
# Commit whatever is staged; prints git's exit status. Extra arguments go to git before `commit`.
commits() { local r=$1; shift; git -C "$r" "$@" commit -q -m x >"$T/last.log" 2>&1; echo $?; }
# A refusal counts only when the output carries the words the refusing check prints: refused REPO
# WORDS LABEL [git args]
refused() { local r=$1 words=$2 label=$3 got; shift 3; got=$(commits "$r" "$@"); check "$got/$(grep -c -- "$words" "$T/last.log" | grep -c '^[1-9]')" "1/1" "$label"; }
# A fresh repo with one commit, the crypt rule, and nothing configuring the filter
locked() { git init -q "$1" && printf '*.secret.* filter=crypt diff=crypt merge=crypt\n' > "$1/.gitattributes" && git -C "$1" add .gitattributes && git -C "$1" commit -q -m init; }
# Stage bytes exactly as given, bypassing any filter, the way a tool that ignores attributes would
stage_raw() { local oid; oid=$(printf '%s' "$3" | git -C "$1" hash-object -w --no-filters --stdin) && git -C "$1" update-index --add --cacheinfo "${4:-100644},$oid,$2"; }
# The shape transcrypt writes, `openssl enc -a` output: base64 opening with the "Salted__" magic,
# 64-character lines with the last at most 64, `=` padding only at the end, whole AES blocks decoded.
# CIPHER is one line (32 bytes), MULTI ends on a short padded line (128), FULL on a full one (96).
# The filler is Q, since a line of any hex digit alone is refused as an appended token.
CIPHER="$(printf 'U2FsdGVkX1%033d=' 0 | tr 0 Q)"
MULTI="$(printf 'U2FsdGVkX1%054d\n%064d\n%043d=' 0 0 0 | tr 0 Q)"$'\n'
FULL="$(printf 'U2FsdGVkX1%054d\n%064d' 0 0 | tr 0 Q)"$'\n'

export GIT_CONFIG_GLOBAL="$T/gitconfig" GIT_CONFIG_NOSYSTEM=1 TMPDIR="$T/tmp"
mkdir -p "$T/hooks" "$TMPDIR"
if ! cp "$HOOK" "$T/hooks/pre-commit"; then
    echo "pre-commit hook: could not copy $HOOK, so no case ran"
    exit 1
fi
cat > "$GIT_CONFIG_GLOBAL" <<EOF
[user]
	name = Pre-commit Test
	email = pre-commit@test.invalid
[commit]
	gpgsign = false
[init]
	defaultBranch = main
[core]
	hooksPath = $(native "$T/hooks")
	autocrlf = false
EOF

# A repo with no crypt attribute is untouched
git init -q "$T/plain" && echo x > "$T/plain/notes.md" && git -C "$T/plain" add notes.md
check "$(commits "$T/plain")" 0 "a repo without transcrypt commits normally"

# ── check 2 in a locked clone: a secret written in plaintext must not enter a commit ──
locked "$T/locked"
echo 'my password' > "$T/locked/notes.secret.md" && git -C "$T/locked" add notes.secret.md
refused "$T/locked" 'notes.secret.md, which is not ciphertext' "a plaintext secret is refused in a locked clone"
git -C "$T/locked" rm -q --cached notes.secret.md && rm "$T/locked/notes.secret.md"

mkdir -p "$T/locked/dir é" && echo 'my password' > "$T/locked/dir é/x.secret.md" && git -C "$T/locked" add "dir é"
refused "$T/locked" 'x.secret.md, which is not ciphertext' "a plaintext secret under a non-ASCII, spaced path is refused"
git -C "$T/locked" rm -q -r --cached "dir é" && rm -r "$T/locked/dir é"

# What a locked clone holds for a secret it has not touched: the ciphertext, staged as it reads
stage_raw "$T/locked" kept.secret.md "$CIPHER"
check "$(commits "$T/locked")" 0 "ciphertext commits in a locked clone"
echo y > "$T/locked/other.md" && git -C "$T/locked" add other.md
check "$(commits "$T/locked")" 0 "an unrelated change commits beside an encrypted secret"

stage_raw "$T/locked" kept.secret.md "my password"
refused "$T/locked" 'kept.secret.md, which is not ciphertext' "an encrypted secret modified to plaintext is refused"
stage_raw "$T/locked" kept.secret.md "$CIPHER"

# The working copy of a secret in a locked clone IS its ciphertext, so an append keeps the magic
stage_raw "$T/locked" multi.secret.md "$MULTI" && stage_raw "$T/locked" full.secret.md "$FULL"
check "$(commits "$T/locked")" 0 "multi-line ciphertext commits, whether its last line is short or a full 64"
stage_raw "$T/locked" multi.secret.md "${MULTI}TOKEN=hunter2"$'\n'
refused "$T/locked" 'Text was added to its ciphertext' "a plaintext line appended to ciphertext is refused"
stage_raw "$T/locked" multi.secret.md "$MULTI" && stage_raw "$T/locked" full.secret.md "${FULL}hunter2"$'\n'
refused "$T/locked" 'full.secret.md, which is not ciphertext' "a base64-only word appended after a full last line is refused"
stage_raw "$T/locked" full.secret.md "${FULL}$(printf '%064x' 3054)"$'\n'
refused "$T/locked" 'full.secret.md, which is not ciphertext' "a 64-character hex token appended after a full last line is refused"
stage_raw "$T/locked" full.secret.md "${FULL}$(printf '%064X' 48879)"$'\n'
refused "$T/locked" 'full.secret.md, which is not ciphertext' "the same token in uppercase hex is refused"
stage_raw "$T/locked" full.secret.md "${FULL}$(printf 'dEaDbEeF%.0s' 1 2 3 4 5 6 7 8)"$'\n'
refused "$T/locked" 'full.secret.md, which is not ciphertext' "a mixed-case hex token is refused"
stage_raw "$T/locked" full.secret.md "$FULL" && stage_raw "$T/locked" crlf.secret.md "${MULTI//$'\n'/$'\r\n'}"
check "$(commits "$T/locked")" 0 "ciphertext with CRLF line endings commits"

# Each rule of the shape, broken alone in a blob that satisfies every other one
for rule in "magic:$(printf '%064d\n%064d' 0 0)" "alphabet:$(printf 'U2FsdGVkX1-%032d=' 0)" "line width:$(printf 'U2FsdGVkX1%022d\n%032d' 0 0)" \
    "padding inside:$(printf 'U2FsdGVkX1%053d=\n%064d' 0 0)" "last line over 64:$(printf 'U2FsdGVkX1%0118d' 0)" "whole blocks:$(printf 'U2FsdGVkX1%030d' 0)"; do
    stage_raw "$T/locked" rule.secret.md "$(printf '%s' "${rule#*:}" | tr 0 Q)"$'\n'
    refused "$T/locked" 'rule.secret.md, which is not ciphertext' "a blob breaking only the ${rule%%:*} rule is refused"
done
git -C "$T/locked" rm -q --cached rule.secret.md

: > "$T/locked/empty.secret.md" && git -C "$T/locked" add empty.secret.md
check "$(commits "$T/locked")" 0 "an empty secret commits, since transcrypt never encrypts one"

stage_raw "$T/locked" blank.secret.md $'\n\n\n\n\n\n\n\n\nmy password'
refused "$T/locked" 'blank.secret.md, which is not ciphertext' "plaintext opening with blank lines is not mistaken for an empty file"
git -C "$T/locked" rm -q --cached blank.secret.md

# Git for Windows reads a hook killed by SIGPIPE as success, and a caller cutting the refusal short
# (`| head -1`) is what sends it; the commit must still be refused
echo 'my password' > "$T/locked/piped.secret.md" && git -C "$T/locked" add piped.secret.md
before=$(git -C "$T/locked" rev-parse HEAD) && git -C "$T/locked" commit -q -m x 2>&1 | head -1 >/dev/null
check "$(git -C "$T/locked" rev-parse HEAD)" "$before" "a refusal read only in part through a pipe still stops the commit"
git -C "$T/locked" rm -q --cached piped.secret.md && rm "$T/locked/piped.secret.md"

# A binary secret with a NUL in its first bytes is refused without bash complaining about the NUL
printf '\060\202\000\003' | git -C "$T/locked" hash-object -w --no-filters --stdin > "$T/oid" && git -C "$T/locked" update-index --add --cacheinfo "100644,$(cat "$T/oid"),bin.secret.p12"
check "$(commits "$T/locked")/$(grep -c 'bin.secret.p12, which is not ciphertext' "$T/last.log")/$(grep -c 'null byte' "$T/last.log")" "1/1/0" "a binary secret with a NUL in its first bytes is refused without a null-byte warning"
git -C "$T/locked" rm -q --cached bin.secret.p12

# HEAD is looked up by name, and a name opening with ':' reads as pathspec magic unless taken
# literally: here it would find x.secret.md's plaintext in HEAD and give the history warning instead
locked "$T/colon" && git -C "$T/colon" config core.protectNTFS false && stage_raw "$T/colon" x.secret.md "my password" && git -C "$T/colon" commit -q --no-verify -m leak
git -C "$T/colon" rm -q --cached x.secret.md && stage_raw "$T/colon" :x.secret.md "my password"
refused "$T/colon" ':x.secret.md, which is not ciphertext' "a name opening with ':' is looked up in HEAD as itself"

stage_raw "$T/locked" lit.secret.md "my password"
refused "$T/locked" 'lit.secret.md, which is not ciphertext' "a plaintext secret is refused under git --literal-pathspecs" --literal-pathspecs
stage_raw "$T/locked" lit.secret.md "$CIPHER"
check "$(commits "$T/locked" --literal-pathspecs)" 0 "ciphertext commits under git --literal-pathspecs"

awk 'BEGIN { l = sprintf("%64s", ""); gsub(/ /, "Q", l); print "U2FsdGVkX1" substr(l, 11); for (i = 1; i < 4700; i++) print l }' > "$T/big.txt" && stage_raw "$T/locked" big.secret.md "$(cat "$T/big.txt")"$'\n'
check "$(commits "$T/locked")/$(grep -c 'fatal' "$T/last.log")" "0/0" "a large ciphertext commits without a fatal line from the check"

# Git keeps a symlink's mode when the plain file standing in for it is overwritten, as on Windows
# without core.symlinks. A symlink entry is exempt while it is a real symlink or unchanged from HEAD.
stage_raw "$T/locked" link.secret.md "target.md" 120000
refused "$T/locked" 'link.secret.md, which is not ciphertext' "a new symlink entry whose checkout is not a symlink is read like a file"
git -C "$T/locked" commit -q --no-verify -m link && echo w > "$T/locked/w.md" && git -C "$T/locked" add w.md
check "$(commits "$T/locked")" 0 "a symlink entry unchanged from HEAD commits even where it checks out as a plain file"
if (cd "$T/locked" && MSYS=winsymlinks:nativestrict ln -s other.md real.secret.md 2>/dev/null) && [ -L "$T/locked/real.secret.md" ] \
    && git -C "$T/locked" -c core.symlinks=true add real.secret.md && [ "$(git -C "$T/locked" ls-files -s real.secret.md | cut -c1-6)" = 120000 ]; then
    check "$(commits "$T/locked")" 0 "a new real symlink marked crypt commits, since its blob is a path"
else
    not_covered "a real symlink marked crypt (this machine could not make one git records as a link)" 1
fi

# Rebase, am, cherry-pick, revert and a merge that needs no resolution commit without running
# pre-commit; --no-verify stands in for them here. The leak must be refused at the next ordinary
# commit rather than never.
stage_raw "$T/locked" leak.secret.md "my password" && git -C "$T/locked" commit -q --no-verify -m leak
echo z > "$T/locked/z.md" && git -C "$T/locked" add z.md
refused "$T/locked" 'HEAD already holds leak.secret.md' "a plaintext secret already in HEAD is refused at the next commit"
stage_raw "$T/locked" leak.secret.md "my other password"
refused "$T/locked" 'HEAD already holds leak.secret.md' "a plaintext secret in HEAD edited again still gets the history warning"
git -C "$T/locked" rm -q --cached leak.secret.md && git -C "$T/locked" commit -q --no-verify -m unleak
# Renormalizing cannot repair ciphertext with text added, so that history gets its own remedy
stage_raw "$T/locked" grown.secret.md "${FULL}hunter2"$'\n' && git -C "$T/locked" commit -q --no-verify -m grown
echo z2 > "$T/locked/z.md" && git -C "$T/locked" add z.md
refused "$T/locked" "HEAD's copy is ciphertext with text added" "ciphertext with text added in HEAD gets the restore remedy, not renormalize"
git -C "$T/locked" rm -q --cached grown.secret.md && git -C "$T/locked" commit -q --no-verify -m ungrown

# HEAD holding a symlink's target is not a leak; staged as a regular file it is simply not ciphertext
stage_raw "$T/locked" relink.secret.md "target.md" 120000 && git -C "$T/locked" commit -q --no-verify -m relink
stage_raw "$T/locked" relink.secret.md "target.md"
refused "$T/locked" 'relink.secret.md, which is not ciphertext' "a symlink restaged as a regular file is not reported as a leak in HEAD"
git -C "$T/locked" rm -q --cached relink.secret.md && git -C "$T/locked" commit -q --no-verify -m unrelink

# A git that fails mid-check must refuse rather than read as nothing to check. The hook runs
# directly, with a `git` first on PATH that fails the one subcommand and passes the rest through.
mkdir -p "$T/shim"
printf '#!/usr/bin/env bash\ncase " $* " in *" %s "*) exit 128 ;; esac\nexec "%s" "$@"\n' ls-files "$(command -v git)" > "$T/shim/git" && chmod +x "$T/shim/git"
check "$(cd "$T/locked" && PATH="$T/shim:$PATH" bash "$T/hooks/pre-commit" >"$T/last.log" 2>&1; echo $?)/$(grep -c 'could not list the files marked' "$T/last.log")" "1/1" "a failed listing of the marked files refuses"
# The diff is the first command of check 1's pipeline, so only pipefail can carry its failure out
printf '#!/usr/bin/env bash\ncase " $* " in *" %s "*) exit 128 ;; esac\nexec "%s" "$@"\n' diff "$(command -v git)" > "$T/shim/git"
check "$(cd "$T/locked" && PATH="$T/shim:$PATH" bash "$T/hooks/pre-commit" >"$T/last.log" 2>&1; echo $?)/$(grep -c 'could not list the staged publish.env' "$T/last.log")" "1/1" "a failed publish.env listing refuses"

git init -q "$T/fresh" && printf '*.secret.* filter=crypt\n' > "$T/fresh/.gitattributes" && echo 'my password' > "$T/fresh/s.secret.md" && git -C "$T/fresh" add -A
refused "$T/fresh" 's.secret.md, which is not ciphertext' "a plaintext secret is refused in a repo's first commit"

# ── check 1: publish.env is refused unless the path is marked for encryption at all ──
git init -q "$T/publish" && mkdir -p "$T/publish/config" && echo 'HOST=box' > "$T/publish/config/publish.env" && git -C "$T/publish" add config
refused "$T/publish" 'unmarked for encryption' "publish.env with no crypt rule is refused"
printf 'config/publish.env filter=crypt diff=crypt merge=crypt\n' > "$T/publish/.gitattributes" && git -C "$T/publish" add .gitattributes
refused "$T/publish" 'publish.env, which is not ciphertext' "publish.env marked for crypt is still refused by check 2 as plaintext while locked"
printf 'config/publish.env filter=crypt-ops diff=crypt-ops merge=crypt-ops\n' > "$T/publish/.gitattributes" && git -C "$T/publish" add .gitattributes && stage_raw "$T/publish" config/publish.env "$CIPHER"
check "$(commits "$T/publish")" 0 "publish.env marked with a named transcrypt context passes check 1"

git init -q "$T/moved" && echo 'HOST=box' > "$T/moved/notes.txt" && git -C "$T/moved" add notes.txt && git -C "$T/moved" commit -q -m init
mkdir -p "$T/moved/config" && git -C "$T/moved" mv notes.txt config/publish.env
refused "$T/moved" 'unmarked for encryption' "publish.env moved into place from outside the pattern is refused"
git -C "$T/moved" commit -q --no-verify -m moved && mkdir -p "$T/moved/b" && git -C "$T/moved" mv config b/config
check "$(git -C "$T/moved" diff --cached --name-status -- ':(glob)**/config/publish.env' | cut -c1)" R "the move between two publish.env paths is a rename to git"
refused "$T/moved" 'unmarked for encryption' "publish.env renamed from one config dir to another is refused"

git init -q "$T/typed" && stage_raw "$T/typed" config/publish.env "elsewhere.env" 120000 && git -C "$T/typed" commit -q --no-verify -m link
stage_raw "$T/typed" config/publish.env "HOST=box"
refused "$T/typed" 'unmarked for encryption' "publish.env changed from a symlink to a plaintext file is refused"

git init -q "$T/nested" && mkdir -p "$T/nested/app é/config" && echo 'HOST=box' > "$T/nested/app é/config/publish.env" && git -C "$T/nested" add "app é"
refused "$T/nested" 'unmarked for encryption' "publish.env under a non-ASCII, spaced path is refused"
# The refusal's own suggested line has to cover the nested path it just refused
sed -n "s/^ *echo '\(.*\)' >> \.gitattributes$/\1/p" "$T/last.log" > "$T/nested/.gitattributes" && git -C "$T/nested" add .gitattributes
stage_raw "$T/nested" "app é/config/publish.env" "$CIPHER"
check "$(commits "$T/nested")" 0 "the line the refusal suggests makes that nested path commit once it is ciphertext"

# ── check 2 in an unlocked clone: the hook's own reading, then transcrypt's check through the copy init writes ──
locked "$T/unlocked"
if (cd "$T/unlocked" && bash "$ROOT/claude/scripts/transcrypt" -y -c aes-256-cbc -p 'throwaway test key' >"$T/init.log" 2>&1); then
    echo 'my password' > "$T/unlocked/notes.secret.md" && git -C "$T/unlocked" add notes.secret.md 2>"$T/last.log"
    check "$(commits "$T/unlocked")" 0 "a secret staged through the filter commits once unlocked"
    check "$(git -C "$T/unlocked" cat-file blob HEAD:notes.secret.md | head -c 8)" U2FsdGVk "what was committed is ciphertext"
    check "$(ls "$T/hooks")" pre-commit "init left no helper hook beside the one under test"
    echo 'my password' > "$T/unlocked/raw.secret.md" && stage_raw "$T/unlocked" raw.secret.md "my password"
    refused "$T/unlocked" 'staged around the crypt filter' "a secret staged around the filter is refused with the re-stage remedy"
    git -C "$T/unlocked" add --renormalize -- raw.secret.md 2>/dev/null
    check "$(commits "$T/unlocked")" 0 "following that remedy stages the file encrypted and it commits"
    # Plaintext already in HEAD gets the history warning, which transcrypt's own check must not pre-empt
    stage_raw "$T/unlocked" leak.secret.md "my password" && git -C "$T/unlocked" commit -q --no-verify -m leak
    echo y > "$T/unlocked/y.md" && git -C "$T/unlocked" add y.md
    refused "$T/unlocked" 'HEAD already holds leak.secret.md' "plaintext already in HEAD gets the history warning in an unlocked clone too"
    git -C "$T/unlocked" rm -q --cached leak.secret.md && git -C "$T/unlocked" commit -q --no-verify -m unleak
    # The clean filter passes a file that already opens with the magic through unchanged
    printf '%s' "${FULL}hunter2"$'\n' > "$T/unlocked/app.secret.md" && git -C "$T/unlocked" add app.secret.md 2>"$T/last.log"
    refused "$T/unlocked" 'Text was added to its ciphertext' "ciphertext with a line appended is refused through the filter too"
    git -C "$T/unlocked" rm -q --cached app.secret.md && rm -f "$T/unlocked/app.secret.md"
    stage_raw "$T/unlocked" nl.secret.md $'\n\n\n\n\n\n\n\n\nmy password'
    refused "$T/unlocked" 'staged around the crypt filter' "plaintext opening with blank lines, which transcrypt's own check passes, is refused"
    git -C "$T/unlocked" rm -q --cached nl.secret.md
    # Transcrypt's own check still runs after the hook's reading, and covers a named context that
    # `:(attr:filter=crypt)` cannot see
    printf '*.ops.* filter=crypt-ops diff=crypt-ops merge=crypt-ops\n' >> "$T/unlocked/.gitattributes" && git -C "$T/unlocked" add .gitattributes && git -C "$T/unlocked" commit -q -m ops
    if (cd "$T/unlocked" && bash "$ROOT/claude/scripts/transcrypt" --context=ops -y -c aes-256-cbc -p 'throwaway ops key' >"$T/ops.log" 2>&1); then
        stage_raw "$T/unlocked" x.ops.md "my password"
        refused "$T/unlocked" 'Transcrypt managed file is not encrypted' "a named-context file staged around the filter is refused by transcrypt's own check"
        git -C "$T/unlocked" rm -q --cached x.ops.md
    else
        not_covered "the named context (transcrypt --context init failed: $(tail -n 1 "$T/ops.log"))" 1
    fi
    # Flushing keeps transcrypt's copy but drops the filter, so git stages plaintext again
    if (cd "$T/unlocked" && "$(git rev-parse --git-common-dir)/crypt/transcrypt" --flush-credentials -y >"$T/flush.log" 2>&1); then
        stage_raw "$T/unlocked" after.secret.md "my password"
        refused "$T/unlocked" 'no crypt filter set up' "a flushed clone is refused by the hook's own reading with the unlock remedy"
    else
        not_covered "the flushed clone (transcrypt --flush-credentials failed: $(tail -n 1 "$T/flush.log"))" 1
    fi
else
    not_covered "the unlocked cases (transcrypt init failed: $(tail -n 1 "$T/init.log"))" 10
fi

echo "pre-commit hook: $pass passed, $fail failed$([ "$skipped" -gt 0 ] && echo ", $skipped NOT COVERED")"
[ "$fail" = 0 ]
