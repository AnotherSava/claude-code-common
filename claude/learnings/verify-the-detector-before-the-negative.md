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

## Two corollaries

**Print the size of the haystack next to the verdict.** "No secrets found in 0 bytes read" and "no
secrets found in 400 MB" are the same sentence and different facts. An empty input passes every test.

**A pipe discards the exit code.** `cmd | sed` reports sed's status, so a failing command reads as
success — the same shape of error one level up. Assert on the status of the command you care about,
or drop the pipe.

The underlying rule generalizes past searching: any instrument that has only ever returned the
comfortable answer is untested, and an untested instrument is not evidence.
