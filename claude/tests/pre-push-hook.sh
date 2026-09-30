#!/usr/bin/env bash
# Pin the behaviour of git/hooks/pre-push, which every push on both machines runs.
#
# Most cases are a real push to a bare repo on disk, so what is asserted is what git does with the
# hook's exit status and what reaches the remote, not what the script prints. The few that need
# input a real push never produces — an unfetched remote sha, an empty ref list, a PATH without
# git-lfs — hand the hook its stdin directly. Several cases pin defects a review found in earlier
# versions: a SHA-256 branch deletion refused, an object under a relocated `lfs.storage` never
# uploaded, and a mirror push of a clone holding pointers without objects allowed through.
#
# The run is sealed from this machine's own git setup. A temporary GPG home holds a throwaway
# signing key, so no passphrase prompt can stall the gate and the user's key is never used, and a
# temporary global config replaces ~/.gitconfig, whose core.hooksPath would otherwise point every
# scratch repo at the installed hook instead of the one under test.
#
# Cases needing git-lfs, or an object format this git lacks, are reported NOT COVERED rather than
# skipped silently, and the tally line counts each case that did not run.
#
#   bash claude/tests/pre-push-hook.sh [hook]     default: git/hooks/pre-push
set -u

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK="${1:-$ROOT/git/hooks/pre-push}"
if [ ! -f "$HOOK" ]; then
    echo "pre-push hook: no hook at $HOOK, so no case ran"
    exit 1
fi
HOOK="$(cd "$(dirname "$HOOK")" && pwd)/$(basename "$HOOK")"
T="$(mktemp -d)"
trap 'gpgconf --kill gpg-agent >/dev/null 2>&1; rm -rf "$T"' EXIT

pass=0 fail=0 skipped=0
check() { if [ "$1" = "$2" ]; then pass=$((pass + 1)); else echo "FAIL $3 (got $1, want $2)"; fail=$((fail + 1)); fi; }
not_covered() { echo "NOT COVERED $2 case(s): $1"; skipped=$((skipped + $2)); }
# Paths handed to git and git-lfs themselves take the drive-letter form on Windows: both are native
# programs, which resolve Git Bash's /tmp/... against their own install prefix and /d/... not at all.
native() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s\n' "$1"; fi; }
url() { local p; p=$(native "$1"); case "$p" in /*) echo "file://$p" ;; *) echo "file:///$p" ;; esac; }
push() { git -C "$1" push "${@:2}" >"$T/last.log" 2>&1; echo $?; }
on_remote() { local oid; oid=$(git -C "$1" show "HEAD:$2" | sed -n 's/^oid sha256://p'); [ -f "$3/lfs/objects/${oid:0:2}/${oid:2:2}/$oid" ] && echo yes || echo no; }
hook_direct() { (cd "$1" && bash "$T/hooks/pre-push" origin x >"$T/last.log" 2>&1; echo $?); }
# After a push that had to be refused, put both sides back, so a wrong accept cannot leave the next
# case passing on git's own non-fast-forward refusal instead of the hook's.
undo() { git -C "$T/plain" reset -q --hard HEAD~1; git -C "$T/plain.git" update-ref refs/heads/main "$(git -C "$T/plain" rev-parse HEAD)"; }

export GNUPGHOME="$T/gnupg" GIT_CONFIG_GLOBAL="$T/gitconfig" GIT_CONFIG_NOSYSTEM=1
mkdir -p "$GNUPGHOME" "$T/hooks" && chmod 700 "$GNUPGHOME"
if ! cp "$HOOK" "$T/hooks/pre-push"; then
    echo "pre-push hook: could not copy $HOOK, so no case ran"
    exit 1
fi
if ! gpg --batch --passphrase '' --quick-gen-key 'pre-push test <pre-push@test.invalid>' ed25519 sign never >/dev/null 2>&1; then
    echo "pre-push hook: could not create a throwaway GPG key, so no case ran"
    exit 1
fi
cat > "$GIT_CONFIG_GLOBAL" <<EOF
[user]
	name = Pre-push Test
	email = pre-push@test.invalid
	signingkey = pre-push@test.invalid
[commit]
	gpgsign = true
[init]
	defaultBranch = main
[core]
	hooksPath = $(native "$T/hooks")
	autocrlf = false
[filter "lfs"]
	clean = git-lfs clean -- %f
	smudge = git-lfs smudge -- %f
	process = git-lfs filter-process
	required = true
EOF
HAVE_LFS=$(command -v git-lfs >/dev/null 2>&1 && echo yes || echo no)
repo() { git init -q "${@:2}" "$1"; }
commit() { git -C "$1" add -A && git -C "$1" commit -q "${@:3}" -m "$2"; }
lfs_rule() { mkdir -p "$1"; printf '*.bin filter=lfs diff=lfs merge=lfs -text\n' > "$1/.gitattributes"; }

# Signing and attribution
git init -q --bare "$T/plain.git"; repo "$T/plain"
echo a > "$T/plain/a.txt"; commit "$T/plain" a; git -C "$T/plain" remote add origin "$(url "$T/plain.git")"
check "$(push "$T/plain" -u origin main)" 0 "signed push"
echo u > "$T/plain/u.txt"; commit "$T/plain" u --no-gpg-sign
check "$(push "$T/plain" origin main)" 1 "unsigned commit rejected"; undo
# Git for Windows reads a hook killed by SIGPIPE as success, and a caller cutting the refusal short
# (`| head -1`) is what sends it; two unsigned commits give the hook writes to make after that
echo u2 > "$T/plain/u2.txt"; commit "$T/plain" u2 --no-gpg-sign; echo u3 > "$T/plain/u3.txt"; commit "$T/plain" u3 --no-gpg-sign
before=$(git -C "$T/plain.git" rev-parse main); git -C "$T/plain" push -q origin main 2>&1 | head -1 >/dev/null
check "$(git -C "$T/plain.git" rev-parse main)" "$before" "a refusal read only in part through a pipe still blocks the push"
git -C "$T/plain" reset -q --hard HEAD~2; git -C "$T/plain.git" update-ref refs/heads/main "$before"
echo v > "$T/plain/v.txt"; GIT_AUTHOR_NAME=Claude GIT_AUTHOR_EMAIL=noreply@anthropic.com commit "$T/plain" v
check "$(push "$T/plain" origin main)" 1 "Claude author rejected"; undo
echo w > "$T/plain/w.txt"; commit "$T/plain" "w" --trailer "Co-Authored-By: Claude <noreply@anthropic.com>"
check "$(push "$T/plain" origin main)" 1 "Claude co-author trailer rejected"; undo

# Ranges the hook cannot bound from the remote sha
echo z > "$T/plain/z.txt"; commit "$T/plain" z --no-gpg-sign
printf 'refs/heads/main %s refs/heads/main %s\n' "$(git -C "$T/plain" rev-parse HEAD)" 1111111111111111111111111111111111111111 > "$T/stdin"
check "$(hook_direct "$T/plain" < "$T/stdin")" 1 "unsigned commit behind an unfetched remote sha rejected"
check "$(grep -c 'not GPG-signed' "$T/last.log")" 1 "the refusal names the unsigned commit"
git -C "$T/plain" reset -q --hard HEAD~1
echo s > "$T/plain/s.txt"; commit "$T/plain" s
printf 'refs/heads/main %s refs/heads/main %s\n' "$(git -C "$T/plain" rev-parse HEAD)" 1111111111111111111111111111111111111111 > "$T/stdin"
check "$(hook_direct "$T/plain" < "$T/stdin")" 0 "signed commit behind an unfetched remote sha allowed"
git -C "$T/plain" reset -q --hard HEAD~1
git -C "$T/plain" checkout -q -b fresh; echo n > "$T/plain/n.txt"; commit "$T/plain" n --no-gpg-sign
check "$(push "$T/plain" origin fresh)" 1 "unsigned commit on a new branch rejected"
git -C "$T/plain.git" update-ref -d refs/heads/fresh 2>/dev/null; git -C "$T/plain" checkout -q main

# Lines that carry no commits
check "$(printf '' | hook_direct "$T/plain")" 0 "empty stdin"
git -C "$T/plain" push -q origin main:tmpb 2>/dev/null
check "$(push "$T/plain" origin :tmpb)" 0 "SHA-1 branch deletion"
if git init -q --bare --object-format=sha256 "$T/r256.git" 2>/dev/null; then
    repo "$T/w256" --object-format=sha256; echo a > "$T/w256/a.txt"; commit "$T/w256" a
    git -C "$T/w256" remote add origin "$(url "$T/r256.git")"
    git -C "$T/w256" push -q -u origin main 2>/dev/null; git -C "$T/w256" push -q origin main:tmpb 2>/dev/null
    check "$(push "$T/w256" origin :tmpb)" 0 "SHA-256 branch deletion"
else
    not_covered "SHA-256 branch deletion (this git has no --object-format)" 1
fi

# A bare mirror with no LFS content pushes like any other repo
git clone -q --mirror "$T/plain.git" "$T/plain-mirror.git" 2>/dev/null; git init -q --bare "$T/plain-target.git"
check "$(git -C "$T/plain-mirror.git" push -q --mirror "$(url "$T/plain-target.git")" >"$T/last.log" 2>&1; echo $?)" 0 "mirror push without LFS content"

# LFS content possible, git-lfs absent: refused, since pushing would send pointers without objects
repo "$T/nolfs"; lfs_rule "$T/nolfs"; commit "$T/nolfs" rule
# Only git and gpg are shimmed into the sealed PATH: gpg lives outside /usr/bin on macOS, and without
# it the signature check would refuse first and the case would pass for the wrong reason.
mkdir -p "$T/shim"
for tool in git gpg; do printf '#!/bin/sh\nexec "%s" "$@"\n' "$(command -v "$tool")" > "$T/shim/$tool"; chmod +x "$T/shim/$tool"; done
printf 'refs/heads/main %s refs/heads/main %s\n' "$(git -C "$T/nolfs" rev-parse HEAD)" 0000000000000000000000000000000000000000 > "$T/stdin"
check "$(cd "$T/nolfs" && PATH="$T/shim:/usr/bin:/bin" bash "$T/hooks/pre-push" origin x <"$T/stdin" >"$T/last.log" 2>&1; echo $?)" 1 "blocked when LFS content is possible and git-lfs is missing"
check "$(grep -c 'git-lfs is not on PATH' "$T/last.log")" 1 "the refusal names the missing git-lfs"

# LFS uploads, through each of the conditions that decide whether the hook calls git-lfs
if [ "$HAVE_LFS" = yes ]; then
    git init -q --bare "$T/lfs.git"; repo "$T/lfs"; lfs_rule "$T/lfs"; head -c 3000 /dev/urandom > "$T/lfs/a.bin"
    commit "$T/lfs" a; git -C "$T/lfs" remote add origin "$(url "$T/lfs.git")"
    check "$(push "$T/lfs" -u origin main)" 0 "LFS push exits 0"
    check "$(on_remote "$T/lfs" a.bin "$T/lfs.git")" yes "LFS object uploaded"

    # A rule only in a subdirectory: the root .gitattributes says nothing, the local store decides
    git init -q --bare "$T/sub.git"; repo "$T/sub"; lfs_rule "$T/sub/assets"; head -c 3000 /dev/urandom > "$T/sub/assets/c.bin"
    commit "$T/sub" c; git -C "$T/sub" remote add origin "$(url "$T/sub.git")"
    check "$(push "$T/sub" -u origin main)" 0 "push with a subdirectory LFS rule exits 0"
    check "$(on_remote "$T/sub" assets/c.bin "$T/sub.git")" yes "object uploaded under a subdirectory rule"

    # A relocated store: no local lfs/objects, so lfs.storage decides even with a subdirectory rule
    git init -q --bare "$T/moved.git"; repo "$T/moved"; git -C "$T/moved" config lfs.storage "$(native "$T/shared-lfs")"
    lfs_rule "$T/moved/assets"; head -c 3000 /dev/urandom > "$T/moved/assets/b.bin"
    commit "$T/moved" b; git -C "$T/moved" remote add origin "$(url "$T/moved.git")"
    check "$(push "$T/moved" -u origin main)" 0 "push with lfs.storage exits 0"
    check "$(on_remote "$T/moved" assets/b.bin "$T/moved.git")" yes "object uploaded from a relocated store"

    git clone -q --mirror "$T/lfs.git" "$T/mirror.git" 2>/dev/null; git init -q --bare "$T/target.git"
    check "$(git -C "$T/mirror.git" push -q --mirror "$(url "$T/target.git")" >"$T/last.log" 2>&1; echo $?)" 1 "mirror push refused while objects are missing"
    check "$(grep -ci 'lfs' "$T/last.log" | grep -c '^[1-9]')" 1 "the refusal comes from git-lfs"

    # Git runs pre-push with an empty ref list on an up-to-date push; that must not reach git-lfs,
    # which would open an SSH connection and an ls-remote for nothing
    check "$(cd "$T/lfs" && printf '' | GIT_TRACE=1 bash "$T/hooks/pre-push" origin x 2>&1 | grep -c 'git-lfs')" 0 "no git-lfs call for an up-to-date push"
else
    not_covered "the LFS upload cases (git-lfs is not installed)" 9
fi

# A repo with no LFS never calls git-lfs, which would cost every push an SSH handshake
check "$(cd "$T/plain" && echo x > x.txt && git add x.txt && git commit -q -m x && GIT_TRACE=1 git push -q origin main 2>&1 | grep -c 'git-lfs')" 0 "no git-lfs call without LFS content"

echo "pre-push hook: $pass passed, $fail failed$([ "$skipped" -gt 0 ] && echo ", $skipped NOT COVERED")"
[ "$fail" = 0 ]
