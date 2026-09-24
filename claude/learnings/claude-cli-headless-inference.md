# Driving `claude -p` as a batch inference engine

An app that needs text turned into JSON can shell out to the Claude CLI instead of calling the API, and on a
subscription that is the cheaper arrangement — no API key, no per-token bill. What it costs is that you are
running an **agent** to do a **transform**, and the defaults that make an agent good make a transform slow.
One extraction took 85 seconds until the settings below were measured; the same work now takes 16.

Everything here was measured against Claude Code 2.1.238 in a container, on two real confirmation emails put
through a schema-constrained extraction prompt.

## Extended thinking is on by default and will dominate the run

This is the single largest lever, and the numbers are not subtle. A four-leg travel confirmation, same prompt,
same model:

| | API time | output tokens | of which thinking |
| --- | --- | --- | --- |
| default | 78.6s | 9,197 | 7,470 (81%) |
| `MAX_THINKING_TOKENS=0` | 14.5s | 1,740 | 0 |

A second document gave 86.5s versus 9.6s. Both settings produced the same segment count and the same
identifiers; four further runs per document with thinking off stayed correct. For a transform this is pure
overhead — the schema is supplied, every value is stated in the document, and there is nothing to reason
towards.

Set it in the spawn environment:

```js
spawn('claude', ['-p', prompt, '--output-format', 'json', '--model', model], {
  env: { ...process.env, MAX_THINKING_TOKENS: '0' },
})
```

## `--effort low` is NOT thinking off

The obvious-looking knob is the wrong one, and it is wrong by 3×. Measured on the same document:

| | API time | thinking tokens |
| --- | --- | --- |
| `--effort low` | 46.2s | 3,780 |
| `MAX_THINKING_TOKENS=0` | 14.5s | 0 |

Effort scales thinking; it does not switch it off. Across `low medium high xhigh max` on four models the
latency ranged from 13s to 136s and **every cell produced a correct answer** — so on a schema-constrained
transform, effort buys nothing but time. `~/.claude/learnings/claude-code-effort-and-ultracode.md` has what
effort is and how it resolves; this is only the measurement that it is the wrong instrument here.

Two model-specific findings from that matrix:

- **Haiku's effort curve is non-monotonic** — 46s at `low`, 44s at `high`, 91s at `xhigh`. It thinks heavily
  at every level, so effort is a weak lever on it specifically.
- **`MAX_THINKING_TOKENS=0` is not honoured by every model.** Three of four models it zeroed; one kept
  spending hundreds to thousands of thinking tokens regardless. Assert on `usage.output_tokens_details.
  thinking_tokens` in the envelope rather than assuming the variable took.

## Pick the cheap model; the expensive ones buy nothing here

All four models tested got every identifier and every segment count right on both documents. The spread was
entirely cost and time — the cheapest model with thinking off was also the fastest cell in 41 runs, and the
most expensive single run cost 60× the cheapest. On a constrained extraction, the model is not the variable
worth tuning; thinking is.

One model-specific failure worth knowing: with thinking disabled, one model reliably prefixed a sentence of
prose before the JSON ("That tool search wasn't needed for this task — here's the extraction."), reproduced
three times out of three, in direct violation of a prompt saying *return ONLY a JSON array, no prose and no
code fence*. The same model under `--effort` did not do it. Strip a leading fence and any leading prose
before parsing, whatever the prompt says.

## The prompt goes in as `argv`, so there is a hard size cliff

`claude -p "<prompt>"` passes the whole document as a command-line argument, and the OS argument limit ends
the run with `spawn E2BIG` — an error naming neither the cause nor the fix. Measured: fine at 100k characters,
dead at 130k.

Pipe the prompt on stdin instead. If you must keep `argv`, cap the document and say so in the error, because
the failure mode is a hard stop rather than a truncation.

## A ~17k-token agent harness ships on every call

Even `claude -p "Reply with the single word OK."` reports `cache_read_input_tokens: 15448` plus about 2,200
created — the system prompt and the tool definitions, including definitions for tools you passed
`--disallowed-tools` for. It is cached, so it is cheap in money, and it is why a trivial call still takes
about 3 seconds wall (1.9s of it API).

That fixed floor is the honest argument for calling the Messages API directly instead. The honest argument
against is billing: the CLI runs on a subscription credential, and going direct means an API key and
per-token charges. At a few documents a day the subscription wins; the calculation flips with volume.

## Read the run's own accounting rather than timing it from outside

`--output-format json` returns an envelope that already answers most performance questions:

```
duration_api_ms          time in the API, as opposed to your wall clock
num_turns                >1 means it went agentic on you
usage.output_tokens      total generated
  .output_tokens_details.thinking_tokens
usage.cache_read_input_tokens / cache_creation_input_tokens
total_cost_usd
```

Wall time minus `duration_api_ms` is process startup, which measured about 0.3s — so if those two diverge by
much, look at what your own code is doing rather than at the model.

**That envelope is not reliably parseable JSON.** The `result` field is written with raw newlines inside the
string, so `JSON.parse` fails with *Bad control character in string literal*. Escape control characters
first, and trim before you do — escaping the file's own trailing newline puts a stray `\n` after the closing
brace and trades one parse error for another:

```js
const CTRL = { '\n': '\\n', '\r': '\\r', '\t': '\\t' }
const repaired = text.trim().replace(/[\u0000-\u001F]/g, (c) => CTRL[c] ?? '')
JSON.parse(repaired)
```

## Benchmark against ground truth the document already carries

Comparing a run to a previously stored answer only tells you the two models agree. Where a message carries a
structured attachment — a calendar part, an embedded JSON-LD block — that attachment states the facts
outright, and scoring against it is the difference between "it produced something" and "it produced the right
thing". Score on identifiers and counts, not on a diff of the whole object, which drifts on field ordering
and on nulls nobody cares about.

Budget for it: a four-model × five-effort × two-document matrix ran to about $6.70, one cell of it $1.18.
Decide the axes before spending, and run the cheap candidate repeatedly rather than the expensive one once —
a single run per cell is enough to rank latency and not enough to claim accuracy.
