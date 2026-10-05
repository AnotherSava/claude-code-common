#!/usr/bin/env bash
#
# reclaim-disk.sh — reclaim regenerable disk space on this machine, and say
# when free space is running out.
#
# Written after this Mac reached 510 MiB free on a 228 GiB volume with no
# warning at all: a tool call failed with ENOSPC, and the cause was a single
# Rust target directory at 42 GB. Two halves follow from that, and this script
# is both of them — a BROOM that removes what is regenerable, and an ALARM that
# reports a low volume before a build discovers it. The alarm is the half that
# would have caught that day; a broom that runs weekly still lets a bad week
# fill the disk on a Wednesday.
#
# Usage:
#   reclaim-disk.sh                 Report only. Deletes nothing. Default.
#   reclaim-disk.sh --apply         Delete every candidate classed FREE or
#                                   REBUILD. RUNNING rows are never touched.
#   reclaim-disk.sh --alarm         Only measure free space and notify. What
#                                   the LaunchAgent runs; never deletes.
#   reclaim-disk.sh --install       Install + load the daily alarm LaunchAgent.
#   reclaim-disk.sh --uninstall     Unload + remove it.
#   reclaim-disk.sh --age-days N    Age gate for build artifacts (default 21).
#   reclaim-disk.sh --dead-days N   Age gate for tool caches (default 60).
#   reclaim-disk.sh --clone-age-days N
#                                   Age gate for signed-bundle clones (7).
#   reclaim-disk.sh --warn-gib N --crit-gib N
#                                   Alarm floors in GiB (15 and 8). A machine
#                                   with a different disk wants different ones,
#                                   and raising --warn-gib is how the send path
#                                   is exercised deliberately.
#
# The three gates are separate because the question each answers is different:
# a build artifact is stale when nothing has needed it for a few weeks, a tool
# cache is dead when the tool itself has not run for a couple of months, and a
# signed clone is orphaned as soon as the app it belongs to has been updated
# past it. Raising one is also how a rule is taken out of a single run.
#
# Every candidate is printed with a CLASS, and the class is what authorizes a
# delete. The classes exist because "regenerable" is not one property:
#
#   FREE     Regenerable at no cost but a re-download or a re-generation, with
#            nothing live depending on it. --apply removes these.
#   REBUILD  Regenerable, but getting it back costs a compile. --apply removes
#            these too; the class is kept as a label because the report should
#            still say which rows cost a cold build, and the summary counts them
#            separately so the price is visible before you type --apply.
#   RUNNING  Regenerable, but something live depends on it right now (a VM, a
#            browser holding its code-sign clone). Reported only.
#   REFUSED  A guard said no. The reason is printed.
#
# Guards, each of which exists because something nearly went wrong:
#
#   * A path is judged after `realpath`, and judged in BOTH spellings, case
#     insensitively — this volume is case-insensitive, so `~/.CLAUDE` resolves
#     fine and would slip a case-sensitive denylist.
#   * `rm -rf` takes a DIRECTORY, so the denylist must also refuse a directory
#     that CONTAINS a protected file. A file-granular check cannot protect
#     `config/local.json` from an `rm -rf` of the directory above it.
#   * `git check-ignore -q` decides disposability inside a repo — never `-v`,
#     whose exit status reports whether a pattern matched rather than the
#     ignore verdict. Exit 128 means the path is outside any work tree, which
#     is NOT a "no": it is an unanswered question, so only a rule explicitly
#     marked as living outside a repo may proceed on it.
#   * lsof is asked whether a clone is held, and is first asked a question
#     whose answer is known (this shell's own handles). An lsof that cannot
#     look returns the same empty output as an lsof that looked and found
#     nothing, so without that positive control "unheld" and "unmeasured" are
#     the same string — and the difference is a browser's text pages.
#   * Deletes name one directory, never a file list: one target/debug/deps here
#     holds 45,000 files, which is past ARG_MAX, and `rm` refuses the whole
#     invocation rather than part of it.
#
# Free space is read with `df -k`, never derived from `du`: cargo hard-links
# heavily, so a du total over target/ reads more than twice the allocated
# bytes. Note that APFS releases a large delete's blocks lazily — measured
# here, a 15 GiB removal showed 9.8 GiB free immediately and 37 GiB twenty
# minutes later — so a reported delta is a floor, not the final figure.
#
# Output: one line per candidate, a summary, and a measured df delta under
# --apply. Exit 0 when the run completed, 1 when something could not be
# measured (an unmeasurable check must not read as a clean one), 2 on usage.
set -uo pipefail

# Everything below stays inside bash 3.2, which is what /bin/bash is on macOS
# and therefore what the LaunchAgent runs — no ${var^^}, no associative arrays.
[ "$(uname -s)" = "Darwin" ] || {
  echo "reclaim-disk.sh is macOS-only today (it reads df on /System/Volumes/Data, lsof and the" >&2
  echo "Darwin per-user scratch root). The Windows half is not written." >&2
  exit 2
}

# ---- configuration -----------------------------------------------------------

LABEL="com.anothersava.broom"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/broom.log"
LOG_MAX_BYTES=1048576
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/broom"
ALARM_STATE="$STATE_DIR/alarm.state"

# Absolute, because launchd hands a job PATH=/usr/bin:/bin:/usr/sbin:/sbin and
# nothing else — a tool found only through a shell profile is not found here.
DF=/bin/df
LSOF=/usr/sbin/lsof
GETCONF=/usr/bin/getconf
GIT=/usr/bin/git
FIND=/usr/bin/find
DATE=/bin/date
STAT=/usr/bin/stat

# The volume every path below lives on. /System/Volumes/Data is the writable
# one; `/` is the sealed system snapshot and reports its own numbers.
VOLUME=/System/Volumes/Data

# Warn at 15 GiB, critical at 8. Absolute rather than a percentage, because the
# thing that fails is a build and not a ratio: a cold release build of the
# dashboard needs 3.7 GiB (measured), a cold debug build 4-6, and the worst
# single day of churn measured in its target dir was 3.1 — 15 absorbs all three
# at once. The conventional 10%-free default would be 22.8 GiB on this volume,
# a level that is genuinely fine, so it would fire once and then be ignored.
WARN_GIB=15
CRIT_GIB=8
# Below the floor, say so again only when it got worse or after this long.
REALARM_HOURS=72

AGE_DAYS=21      # build artifacts: untouched this long before they are stale
DEAD_DAYS=60     # tool caches: nothing inside touched this long = dead
CLONE_AGE_DAYS=7 # code-sign clones of a version no longer running

PROJECTS="$HOME/Projects"

# Never, whatever a rule says and whatever git says. Matched case-insensitively
# against both the given and the resolved path, and a directory CONTAINING one
# of these is refused too.
NEVER_RE='/\.claude(/|$)|/\.git(/|$)|/projects/transcripts/data(/|$)|/private/tmp/claude-|/\.ssh(/|$)|/library/containers(/|$)|/library/keychains(/|$)'
# Basenames that are ignored by git yet exist in exactly one copy: the
# per-machine wrappers and env files the deploy/publish skills write, and
# transcrypt material. A directory holding one of these is not disposable,
# however emphatically `git check-ignore` calls it ignored.
PROTECTED_BASENAMES='deploy.env publish.env local.json local.template.json id_rsa id_ed25519'

mode=report

# ---- plumbing ----------------------------------------------------------------

ts() { "$DATE" '+%Y-%m-%dT%H:%M:%S%z'; }

rotate_log() {
  [ -f "$LOG" ] || return 0
  local size
  size="$("$STAT" -f%z "$LOG" 2>/dev/null || echo 0)"
  [ "$size" -gt "$LOG_MAX_BYTES" ] && mv -f "$LOG" "$LOG.1"
  return 0
}

log() {
  # Both to stdout (a human ran it) and to the log (launchd ran it). launchd
  # cannot open StandardErrorPath in a directory that does not exist, so the
  # directory is made here rather than only at install time.
  mkdir -p "$(dirname "$LOG")" 2>/dev/null
  printf '%s %s\n' "$(ts)" "$*" | tee -a "$LOG"
}

# Per-item detail for a rule that reports in groups: the log keeps every path
# so an --apply is auditable line by line, while the terminal gets the group
# summary. 54 clone paths on screen bury the four rows a reader must decide on.
log_detail() {
  mkdir -p "$(dirname "$LOG")" 2>/dev/null
  printf '%s %s\n' "$(ts)" "$*" >> "$LOG"
}

# Candidate accounting. Totals are in KiB, as df reports.
#
# Apparent bytes are tracked apart from real ones because du cannot measure a
# clonefile: macOS's signed-bundle clones share extents, so du charges each of
# the 52 Chrome clones its full 2 GiB and sums to 106 GiB where the volume only
# holds about 25. Summing those into one reclaimable figure produced a headline
# of 121 GiB on a 228 GiB disk, which is not a conservative estimate but a
# wrong number. Nothing can derive the real figure from du, so the apparent
# total is reported as apparent and the truth comes from the df delta.
total_free_kib=0 total_apparent_kib=0 total_rebuild_kib=0
n_free=0 n_apparent=0 n_refused=0 n_removed=0
exit_code=0

gib() { awk -v k="$1" 'BEGIN{ printf "%.2f GiB", k/1048576 }'; }

free_kib() {
  local v
  v="$("$DF" -k -- "$VOLUME" 2>/dev/null | awk 'NR==2{print $4}')"
  case "$v" in ''|*[!0-9]*) return 1 ;; esac
  printf '%s\n' "$v"
}

dir_kib() {
  # -x so a mount point inside never inflates the figure.
  du -skx -- "$1" 2>/dev/null | awk '{print $1}'
}

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

# resolve <path> — print the resolved absolute path, or refuse.
resolve() {
  local p="$1"
  case "$p" in
    /*) ;;
    *) printf 'REFUSED not an absolute path: %s\n' "$p" >&2; return 1 ;;
  esac
  case "$p" in
    *..*) printf 'REFUSED path contains ..: %s\n' "$p" >&2; return 1 ;;
  esac
  [ -e "$p" ] || return 2   # absent is not a refusal, just nothing to do
  local real
  real="$(cd -- "$(dirname -- "$p")" 2>/dev/null && pwd -P)/$(basename -- "$p")" || {
    printf 'REFUSED cannot resolve: %s\n' "$p" >&2; return 1
  }
  local given_l real_l
  given_l="$(lower "$p")"; real_l="$(lower "$real")"
  if printf '%s' "$given_l" | grep -Eq "$NEVER_RE" || printf '%s' "$real_l" | grep -Eq "$NEVER_RE"; then
    printf 'REFUSED on the never-list: %s\n' "$real" >&2; return 1
  fi
  printf '%s\n' "$real"
}

# contains_protected <dir> — true when an rm -rf of this directory would take a
# file that exists in exactly one copy.
contains_protected() {
  local dir="$1" base
  for base in $PROTECTED_BASENAMES; do
    if "$FIND" "$dir" -maxdepth 4 -name "$base" -print -quit 2>/dev/null | grep -q .; then
      printf '%s' "$base"; return 0
    fi
  done
  return 1
}

# git_vouches <path> — 0 ignored (disposable), 1 tracked or not ignored,
# 2 outside any work tree (unanswered).
git_vouches() {
  local p="$1" parent
  parent="$(dirname -- "$p")"
  "$GIT" -C "$parent" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 2
  "$GIT" -C "$parent" check-ignore -q -- "$p" && return 0
  return 1
}

# lsof_can_look — the positive control. An lsof that cannot look is silent in
# exactly the way an lsof that found nothing is.
lsof_can_look() {
  [ -x "$LSOF" ] || return 1
  "$LSOF" -p "$$" 2>/dev/null | grep -q .
}

# clone_census <app-clone-dir> — print "<clone-dir-name>\t<command>" for every
# clone under it that a live process holds a file inside.
#
# It must be +D (recursive). `lsof -- <dir>` on the directory itself answers
# with ZERO lines here while Chrome is executing out of a clone inside it —
# measured — because what the browser holds is a mapped file several levels
# down, not the directory. A guard built on the non-recursive form reports
# every clone as unheld and would delete the one a running browser is paging
# from, which is the single worst thing in this script's reach.
#
# -Fcn rather than columns because the COMMAND field contains a space
# ("Google Chrome") and splitting on whitespace silently mangles it.
clone_census() {
  "$LSOF" +D "$1" -Fcn 2>/dev/null | awk '
    substr($0,1,1)=="c" { cmd=substr($0,2); next }
    substr($0,1,1)=="n" {
      p=substr($0,2)
      if (match(p, "code_sign_clone\\.[^/]+")) print substr(p, RSTART, RLENGTH) "\t" cmd
    }' | sort -u
}

# sane_days <n> — a gate must be a whole number of days inside a range find can
# actually evaluate. 1..3650 keeps every cutoff after 1970, which is the range
# `find -newermt` answers honestly; a value outside it is refused rather than
# clamped, since a silently adjusted gate is how a rule stops covering what the
# caller asked it to cover.
sane_days() {
  case "$1" in
    ''|*[!0-9]*) echo "reclaim-disk.sh: $1 is not a whole number of days" >&2; return 1 ;;
  esac
  if [ "$1" -lt 1 ] || [ "$1" -gt 3650 ]; then
    echo "reclaim-disk.sh: $1 is outside 1..3650 days" >&2; return 1
  fi
  printf '%s\n' "$1"
}

cutoff_date() { "$DATE" -v-"$1"d '+%Y-%m-%d'; }

# nothing_newer_than <dir> <days> — true when no file inside was touched since.
#
# FAILS CLOSED, because the first version failed open and deleted three live
# caches. `find -newermt` answers an unusable cutoff by matching nothing, which
# is byte-identical to the answer for a directory nothing has touched in years
# — so "no match" alone cannot mean dead. Measured: a cutoff of 1926-10-29
# (`--dead-days 36500`, pre-epoch) matched no file in a directory whose only
# file had just been created, and the caller read that as a dead cache.
#
# So the instrument is asked a question whose answer is known first: every real
# file is newer than 1970-01-02. If that control finds nothing, find could not
# evaluate the test on this directory and the answer is "not dead".
nothing_newer_than() {
  local dir="$1" days="$2" cut
  cut="$(cutoff_date "$days")" || { log "WARN     [age] cannot compute a ${days}d cutoff; treating $dir as live"; exit_code=1; return 1; }
  if ! "$FIND" "$dir" -type f -newermt '1970-01-02' -print -quit 2>/dev/null | grep -q .; then
    log "WARN     [age] find cannot date files under $dir (control found nothing); treating it as live"
    exit_code=1
    return 1
  fi
  ! "$FIND" "$dir" -type f -newermt "$cut" -print -quit 2>/dev/null | grep -q .
}

# ---- the one destructive primitive ------------------------------------------

# remove_dir <resolved-dir> <rule> — one directory argument, never a file list.
# The protected-file check happens in candidate(), before the row is counted as
# FREE, so a refusal never appears in the reclaimable total.
remove_dir() {
  local dir="$1" rule="$2" before after
  if [ "$mode" != apply ]; then
    return 0
  fi
  before="$(free_kib)" || { log "REFUSED  [$rule] cannot read free space"; exit_code=1; return 1; }
  rm -rf -- "$dir" || { log "FAILED   [$rule] rm -rf: $dir"; exit_code=1; return 1; }
  after="$(free_kib)" || after="$before"
  n_removed=$((n_removed + 1))
  log "REMOVED  [$rule] $dir (df +$(gib $((after - before))))"
}

# candidate <class> <rule> <dir> <note> [apparent] [grouped]
#   apparent  the size is du's and du cannot measure this storage honestly
#   grouped   the per-item line goes to the log only; the rule prints a summary
candidate() {
  local class="$1" rule="$2" dir="$3" note="${4:-}" apparent="${5:-0}" grouped="${6:-0}"
  local kib protected emit=log unit=""
  kib="$(dir_kib "$dir")"; kib="${kib:-0}"
  [ "$grouped" = 1 ] && emit=log_detail
  [ "$apparent" = 1 ] && unit=" apparent"
  if [ "$class" = FREE ] && protected="$(contains_protected "$dir")"; then
    log "REFUSED  [$rule] holds $protected, which exists in exactly one copy: $dir"
    n_refused=$((n_refused + 1)); return 0
  fi
  case "$class" in
    FREE)
      if [ "$apparent" = 1 ]; then
        total_apparent_kib=$((total_apparent_kib + kib)); n_apparent=$((n_apparent + 1))
      else
        total_free_kib=$((total_free_kib + kib)); n_free=$((n_free + 1))
      fi
      "$emit" "FREE     [$rule] $(gib "$kib")$unit  $dir ${note:+— $note}"
      remove_dir "$dir" "$rule"
      ;;
    REBUILD)
      total_rebuild_kib=$((total_rebuild_kib + kib))
      "$emit" "REBUILD  [$rule] $(gib "$kib")$unit  $dir ${note:+— $note}"
      remove_dir "$dir" "$rule"
      ;;
    RUNNING)
      "$emit" "RUNNING  [$rule] $(gib "$kib")$unit  $dir ${note:+— $note}"
      ;;
  esac
}

# ---- rules -------------------------------------------------------------------

# A cargo target dir carries CACHEDIR.TAG, which is what tells it apart from a
# source directory someone happened to call "target".
rule_cargo() {
  local t
  while IFS= read -r t; do
    [ -f "$t/CACHEDIR.TAG" ] || continue
    local real
    real="$(resolve "$t")" || continue

    # The incremental cache: whole session directories, judged on the
    # directory's own mtime. No filename is parsed, so a change to cargo's
    # naming cannot make this delete the wrong thing.
    if [ -d "$real/debug/incremental" ]; then
      git_vouches "$real/debug/incremental"
      local vouch=$?
      if [ "$vouch" -eq 0 ]; then
        local d
        while IFS= read -r d; do
          [ -n "$d" ] || continue
          candidate FREE cargo-incremental "$d" "untouched ${AGE_DAYS}d+, cargo rebuilds it"
        done < <("$FIND" "$real/debug/incremental" -mindepth 1 -maxdepth 1 -type d -mtime +"$AGE_DAYS" 2>/dev/null)
      else
        log "REFUSED  [cargo-incremental] git does not call it ignored (check-ignore said $vouch): $real/debug/incremental"
        n_refused=$((n_refused + 1))
      fi
    fi

    # Everything else under debug/ is regenerable only by compiling, so it
    # carries the REBUILD class and the note names cargo's own command — the
    # honest way back, since cargo knows what belongs to the profile. --apply
    # removes the directory directly: it IS the dev profile's output, it is
    # git-ignored, and `rm -rf` needs no toolchain to be installed.
    if [ -d "$real/debug" ]; then
      candidate REBUILD cargo-debug "$real/debug" \
        "cargo clean --profile dev --manifest-path $(dirname "$real")/Cargo.toml"
    fi
  done < <("$FIND" "$PROJECTS" -maxdepth 4 -type d -name target 2>/dev/null)
}

# macOS copies an app's signed bundle into a per-user scratch tree when it
# validates it, and leaves the old ones behind on every update. The root is
# derived rather than hardcoded: the folder name is a per-user hash.
rule_scratch_clones() {
  local root x
  root="$(dirname -- "$("$GETCONF" DARWIN_USER_CACHE_DIR 2>/dev/null)")" || return 0
  x="$root/X"
  [ -d "$x" ] || return 0
  if ! lsof_can_look; then
    log "REFUSED  [scratch-clones] lsof cannot see this shell's own handles, so an empty answer"
    log "         would not mean a clone is unheld. Skipping the whole rule."
    n_refused=$((n_refused + 1)); exit_code=1; return 0
  fi
  # One summary line per app, because the apps are what a reader decides about
  # — 54 individual clone paths on screen bury every other rule's rows. The
  # paths themselves still go to the log, so an --apply stays auditable.
  local app app_name clone real holder census free_n held_n held_who held_note
  while IFS= read -r app; do
    [ -n "$app" ] || continue
    app_name="$(basename "$app" .code_sign_clone)"
    # One recursive lsof per app, not per clone: 1.5s for Chrome's 52 against
    # 52 separate walks of the same tree.
    census="$(clone_census "$app")"
    free_n=0 held_n=0 held_who=""
    while IFS= read -r clone; do
      [ -n "$clone" ] || continue
      real="$(resolve "$clone")" || continue
      holder="$(printf '%s\n' "$census" | awk -F'\t' -v c="$(basename "$real")" '$1==c{print $2; exit}')"
      if [ -n "$holder" ]; then
        held_n=$((held_n + 1)); held_who="$holder"
        candidate RUNNING scratch-clones "$real" "held by $holder" 1 1
        continue
      fi
      free_n=$((free_n + 1))
      candidate FREE scratch-clones "$real" "orphaned signed copy of $app_name" 1 1
    done < <("$FIND" "$app" -mindepth 1 -maxdepth 1 -type d -name 'code_sign_clone.*' -mtime +"$CLONE_AGE_DAYS" 2>/dev/null)
    [ "$free_n" -eq 0 ] && [ "$held_n" -eq 0 ] && continue
    held_note=""
    [ "$held_n" -gt 0 ] && held_note=", $held_n held by ${held_who:-a live process} and kept"
    log "FREE     [scratch-clones] $app_name: $free_n orphaned clone(s)$held_note — paths in $LOG"
  done < <("$FIND" "$x" -mindepth 1 -maxdepth 1 -type d -name '*.code_sign_clone' 2>/dev/null)
  [ "$n_apparent" -gt 0 ] && log "         clone sizes are du's and du cannot see shared extents: $(gib "$total_apparent_kib") apparent is worth far less on the volume. The df delta under --apply is the real figure."
  return 0
}

# Tool caches that no longer have a tool. Each is FREE only if nothing inside
# has been touched in DEAD_DAYS — the age test is what keeps a cache the user
# still relies on out of the sweep, and it is why this table needs no
# per-entry judgment about whether the tool is still in use.
rule_dead_caches() {
  local p real
  for p in \
    "$HOME/.gradle/caches" \
    "$HOME/.cache/puppeteer" \
    "$HOME/Library/Caches/ms-playwright" \
    "$HOME/Library/Developer/Xcode/DerivedData"
  do
    real="$(resolve "$p")" || continue
    if nothing_newer_than "$real" "$DEAD_DAYS"; then
      candidate FREE dead-cache "$real" "nothing touched in ${DEAD_DAYS}d; re-downloads if that tool returns"
    else
      candidate RUNNING dead-cache "$real" "used within ${DEAD_DAYS}d, left alone"
    fi
  done
}

# Regenerable, and reclaiming either visibly breaks something until it is: a
# colima VM needs stopping and recreating, and the Claude desktop sandbox
# images are rebuilt on next use. Reported so they are not a surprise, never
# swept, because "regenerable" and "free" part company here.
rule_running_state() {
  local p real
  for p in "$HOME/.colima" "$HOME/Library/Application Support/Claude/vm_bundles"; do
    real="$(resolve "$p")" || continue
    candidate RUNNING heavy-state "$real" "regenerable, but recreating it is a visible outage"
  done
  real="$(resolve "$HOME/.npm/_cacache")" && [ -n "$real" ] && \
    log "RUNNING  [npm-cache] $(gib "$(dir_kib "$real")")  $real — npm never prunes this; \`npm cache verify\` is its only GC and is non-destructive"
  return 0
}

# ---- the alarm ---------------------------------------------------------------

notify_telegram() {
  local text="$1"
  # The credentials already exist on this machine, in the dashboard's config.
  # Read by python so the token is never a shell word, never echoed, and never
  # reaches the log or a process listing.
  local py
  for py in /usr/bin/python3 /opt/homebrew/bin/python3; do [ -x "$py" ] && break; done
  [ -x "$py" ] || { log "WARN     [alarm] no python3 to send with"; return 1; }
  TEXT="$text" "$py" - <<'PY'
import json, os, sys, urllib.request, urllib.parse
cfg = os.path.expanduser("~/Library/Application Support/com.anothersava.claude-code-dashboard/config.json")
try:
    with open(cfg) as fh:
        tg = ((json.load(fh).get("notifications") or {}).get("telegram") or {})
except Exception as exc:
    print(f"config unreadable: {exc}", file=sys.stderr); sys.exit(1)
token, chat = tg.get("bot_token"), tg.get("chat_id")
if not token or not chat:
    print("no telegram credentials configured", file=sys.stderr); sys.exit(1)
body = urllib.parse.urlencode({"chat_id": chat, "text": os.environ["TEXT"]}).encode()
req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=body)
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        sys.exit(0 if resp.status == 200 else 1)
except Exception as exc:
    print(f"send failed: {exc}", file=sys.stderr); sys.exit(1)
PY
}

alarm() {
  local kib gib_free level last_level last_sent now age_h
  kib="$(free_kib)" || { log "FAILED   [alarm] df gave no answer for $VOLUME"; return 1; }
  gib_free="$(awk -v k="$kib" 'BEGIN{printf "%.1f", k/1048576}')"
  if awk -v g="$gib_free" -v c="$CRIT_GIB" 'BEGIN{exit !(g < c)}'; then level=critical
  elif awk -v g="$gib_free" -v w="$WARN_GIB" 'BEGIN{exit !(g < w)}'; then level=warn
  else level=ok; fi

  mkdir -p "$STATE_DIR" 2>/dev/null
  last_level=ok; last_sent=0
  if [ -f "$ALARM_STATE" ]; then
    read -r last_level last_sent < "$ALARM_STATE" 2>/dev/null || { last_level=ok; last_sent=0; }
  fi
  now="$("$DATE" +%s)"
  age_h=$(( (now - ${last_sent:-0}) / 3600 ))

  if [ "$level" = ok ]; then
    [ "$last_level" != ok ] && log "OK       [alarm] free space recovered to ${gib_free} GiB"
    printf 'ok %s\n' "$now" > "$ALARM_STATE"
    log "OK       [alarm] ${gib_free} GiB free on $VOLUME (warn below ${WARN_GIB})"
    return 0
  fi

  log "$(printf '%-8s [alarm] %s GiB free on %s' "$(printf '%s' "$level" | tr '[:lower:]' '[:upper:]')" "$gib_free" "$VOLUME")"
  # Re-send only when it got worse, or after the quiet window. A level that is
  # merely still bad has already been reported once.
  local worse=0
  [ "$level" = critical ] && [ "$last_level" != critical ] && worse=1
  [ "$last_level" = ok ] && worse=1
  if [ "$worse" -eq 1 ] || [ "$age_h" -ge "$REALARM_HOURS" ]; then
    if notify_telegram "$(printf 'Disk %s: %s GiB free on %s.\nRun: broom (report) then broom --apply' "$level" "$gib_free" "$(hostname -s)")"; then
      printf '%s %s\n' "$level" "$now" > "$ALARM_STATE"
      log "SENT     [alarm] telegram notified"
    else
      log "FAILED   [alarm] telegram send failed; state not advanced so the next run retries"
      return 1
    fi
  else
    log "HELD     [alarm] already reported ${age_h}h ago, re-sends after ${REALARM_HOURS}h"
  fi
  return 0
}

# ---- LaunchAgent -------------------------------------------------------------

install_agent() {
  local self
  self="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)/$(basename -- "${BASH_SOURCE[0]}")"
  mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
  cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$self</string>
        <string>--alarm</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>20</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/dev/null</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/broom.err.log</string>
    <key>LowPriorityIO</key>
    <true/>
    <key>Nice</key>
    <integer>5</integer>
</dict>
</plist>
PLISTEOF
  /usr/bin/plutil -lint "$PLIST" >/dev/null || { log "FAILED   [install] plist is not valid"; return 1; }
  launchctl bootout "gui/$UID/$LABEL" 2>/dev/null
  launchctl bootstrap "gui/$UID" "$PLIST" || { log "FAILED   [install] launchctl bootstrap"; return 1; }
  log "OK       [install] $LABEL loaded; --alarm runs daily at 09:20 and at login"
  log "         Why 09:20 and not the small hours: a laptop asleep at 04:00 defers the run to"
  log "         whenever it next wakes, which is a time nobody chose. A slot while you are"
  log "         plausibly at the machine means the alarm reaches you when you can act on it,"
  log "         and the job reads one df — there is nothing to keep off your working hours."
}

uninstall_agent() {
  launchctl bootout "gui/$UID/$LABEL" 2>/dev/null
  rm -f -- "$PLIST"
  log "OK       [uninstall] $LABEL unloaded and removed"
}

# ---- main --------------------------------------------------------------------

while [ $# -gt 0 ]; do
  case "$1" in
    --apply) mode=apply ;;
    --alarm) mode=alarm ;;
    --install) mode=install ;;
    --uninstall) mode=uninstall ;;
    --age-days) AGE_DAYS="$(sane_days "${2:?--age-days needs a number}")" || exit 2; shift ;;
    --dead-days) DEAD_DAYS="$(sane_days "${2:?--dead-days needs a number}")" || exit 2; shift ;;
    --clone-age-days) CLONE_AGE_DAYS="$(sane_days "${2:?--clone-age-days needs a number}")" || exit 2; shift ;;
    --warn-gib) WARN_GIB="${2:?--warn-gib needs a number}"; shift ;;
    --crit-gib) CRIT_GIB="${2:?--crit-gib needs a number}"; shift ;;
    -h|--help) sed -n '2,80p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "reclaim-disk.sh: unknown argument $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done

rotate_log

case "$mode" in
  install) install_agent; exit $? ;;
  uninstall) uninstall_agent; exit $? ;;
  alarm) alarm; exit $? ;;
esac

start_kib="$(free_kib)" || { log "FAILED   df gave no answer for $VOLUME"; exit 1; }
log "---- broom ${mode} — $(gib "$start_kib") free on $VOLUME ----"
[ "$mode" = report ] && log "Report only. Nothing is deleted. Re-run with --apply to remove the FREE rows."

rule_cargo
rule_scratch_clones
rule_dead_caches
rule_running_state

end_kib="$(free_kib)" || end_kib="$start_kib"
log "---- $n_free FREE $(gib "$total_free_kib") + $n_apparent clone(s) $(gib "$total_apparent_kib") apparent | REBUILD $(gib "$total_rebuild_kib") (costs a cold build) | $n_refused refused ----"
if [ "$mode" = apply ]; then
  log "---- removed $n_removed, df $(gib "$start_kib") -> $(gib "$end_kib") (+$(gib $((end_kib - start_kib)))) ----"
  log "     APFS releases a large delete's blocks lazily, so expect this to keep rising for a few minutes."
fi
exit $exit_code
