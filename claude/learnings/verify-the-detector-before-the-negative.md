# A detector that cannot find the thing reports a clean negative

A search returning nothing has two explanations — the thing is absent, or the search could never have
found it — and they look identical. Reporting the first without excluding the second is how a confident,
wrong answer gets delivered. Four real cases from a single session, each of which produced a stated
conclusion that was false:

| The check | Why it could not work | What it wrongly concluded |
| --- | --- | --- |
| `grep -oE '^[A-Z_]+=' env` to list variable names | `[A-Z_]` excludes digits, so `B2_ACCOUNT_ID=` can never match | "this env file holds no B2 credentials" — it held two |
| Raw substring search of pasted content against transcripts | Transcripts store content **JSON-escaped**; every `\n` is a literal backslash-n, quotes are escaped. Real content cannot match | "84% of this data exists nowhere else" — the true figure was 6% |
| Counting occurrences of `BEGIN OPENSSH PRIVATE KEY` | Counted the *marker string*, never checked what followed it | "private keys are in the corpus" — all 21 hits were the literal string inside grep patterns and prose; zero had key material |
| `len(filename) == 41` to match `<uuid>.jsonl` | A UUID is 36 chars, plus `.jsonl` is 42 | "0 sessions on disk" — there were 87 |

Note the direction is not consistent: two produced false negatives, one a false positive, one a
nonsense zero. The common factor is not optimism, it is an unvalidated instrument.

## The habit that prevents all four

**Before believing a negative, prove the detector finds a known positive.** Construct one if none
exists. A scan that finds nothing and has never found anything has demonstrated nothing.

For the escaping case specifically: normalize both sides before comparing, and prefer a targeted
replacement over `codecs.decode(s, 'unicode_escape')`, which emits a `DeprecationWarning` per stray
backslash and mangles non-ASCII:

```python
unescaped = text.replace("\\n", "\n").replace('\\"', '"').replace("\\t", "\t")
```

For pattern-shaped evidence, **assert the payload, not the marker**. A prefix, sentinel or header is
present in every discussion *about* the thing — including your own tooling and notes — so matching it
proves only that the topic was mentioned. Check that plausible content follows:

```python
m = re.search(r'PREFIX', text)
body = re.match(r'[A-Za-z0-9+/=_-]*', text[m.end():]).group(0)
verdict = "real" if len(body) >= 40 else "prefix only"
```

**Plant the known positive outside the subject the tool resolves, or the control tests the wrong
thing and still reports clean.** A checker that takes a path and widens it to the repo containing
it — anything calling `git rev-parse --show-toplevel`, which is the ordinary way to accept "a path
inside a project" — reads the *enclosing* repo rather than the file you planted. Put the fixture in
a scratch directory under the repo under test and the tool measures that repo, finds it conforming,
and prints the same clean line it prints for a working detector; the fixture is never consulted.
Measured 2026-10-08: a port-literal rule was handed a planted violation in `tmp/` inside the repo,
reported clean, and read as a broken detector until the function's own docstring named the trap. Build
the control as a standalone repo somewhere the tool cannot widen out of — `git init` in a temp dir —
and name it after whatever identity the tool derives, since that identity is usually the directory
name and decides which rules apply.

**A scratch directory hides a fixture a second way, so the standalone repo does not rescue it on its
own.** A scanner that enumerates with `git ls-files --exclude-standard` — which the port rule's
`_launch_path_files` does, saying in its own docstring that a `package.json` in a scratch `tmp/` is
nobody's declaration — skips every ignored path whatever root it was given, and `/tmp/` is ignored at
the root of every repo on this machine by the global excludes file. So a fixture under `tmp/` is
unread in a fresh `git init` dir too. Plant it where the tool's own globs look, and confirm the
enumeration lists it before reading any verdict from the run.

## Two of these are commands whose silence is routine, and both destroyed something

The cases above are searches somebody wrote. The sharper version is a *standard tool* whose
"nothing found" is indistinguishable from "could not look", because then the detector was never
suspected at all. Both of these were measured on 2026-10-04 inside one disk-reclaim script, and both
reached the point of deleting data:

| The check | Why it could not work | What it cost |
| --- | --- | --- |
| `lsof -- <dir>` to ask whether a code-sign clone is in use | A process holds a *mapped file several levels down*, not the directory. The non-recursive form returns **zero lines** while Chrome is executing out of that very tree; only `lsof +D` sees it | Reported all 54 clones as unheld. Applying it would have pulled the executable out from under two running browsers |
| `find <dir> -type f -newermt "$cut"` to ask whether a cache is still in use | BSD `find` cannot evaluate a **pre-1970** cutoff and silently matches nothing, so a gate meant to *exclude* live caches read them as dead | Deleted ~12 GiB of live tool caches while trying to exclude them |

Both were fixed the same way, and it is the habit above applied to a tool rather than to a regex:
**ask the instrument a question whose answer you already know, in the same invocation style, and
refuse to interpret the real answer until the control passes.** For lsof, that this shell's own
handles are visible (`lsof -p $$` must print something). For find, that a file is newer than
`1970-01-02` — true of every real file, so an empty answer there means find could not evaluate the
test on this directory at all.

The second lesson is about *which* way to fail. A guard that cannot measure must return the answer
that does nothing: "still in use", "not dead", "do not touch". Both of these failed open, toward
action, which is the only reason either was expensive. See `~/.claude/memory/feedback_not_run_is_not_pass.md`
for the rule; these are what it looks like when the unmeasured case is wired to a delete.

Also worth knowing when parsing the fixed form: `lsof`'s COMMAND field contains spaces
(`Google Chrome`), so column splitting mangles it — use the field output (`-Fcn`) instead.

## Corollaries

**A second check that shares the first one's assumption is not a second check.** Real case
2026-09-13: a script written to verify that every skill's `allowed-tools` covers the commands that
skill runs matched only parenthesised `Bash(...)` entries, and had no case for a bare `Bash` — which
is unrestricted and therefore covers everything. It reported a skill as having zero coverage for a
helper it invokes. The follow-up check, meant to establish whether the gap predated the session,
read the file's first twelve lines while the field sits on the fifteenth, and agreed. Two
independent-looking confirmations, one blind spot between them, and a defect reported to the user
that had never existed. Agreement between checks is worth only as much as their independence, so
ask what both would miss before trusting it — and run each against a case whose answer you already
know, in **both** directions, since a checker that only ever sees failures is as untested as one
that only ever sees passes.

**Print the size of the haystack next to the verdict.** "No secrets found in 0 bytes read" and "no
secrets found in 400 MB" are the same sentence and different facts. An empty input passes every test.

**A pipe discards the exit code.** `cmd | sed` reports sed's status, so a failing command reads as
success — the same shape of error one level up. Assert on the status of the command you care about,
or drop the pipe.

The underlying rule generalizes past searching: any instrument that has only ever returned the
comfortable answer is untested, and an untested instrument is not evidence.
