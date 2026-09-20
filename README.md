# jev-measured

Measured cost, latency and raw output from the live **Jev** API (TypeSafe AI's System One decision model) across eight realistic use cases. Reproducible: bring your own key and re-run it.

Published because most numbers circulating about Jev are either the vendor's own or arithmetic from the rate card. These are what the API actually returned.

- **Measured:** 2026-09-18 (cost/latency/shape), 2026-09-20 (accuracy)
- **Model:** `typesafe/jev-1.13` via OpenRouter
- **Raw data:** [`data/measured.json`](data/measured.json)
- **Cost of the whole run:** under one cent

---

## Findings

### 1. A real decision costs ~20× less than the figure in circulation

The number you see quoted for Jev is **~$0.0004 per decision**. Across eight real use cases, the API reported:

| Use case | Input tokens | Cost reported by the API |
|---|---:|---:|
| rag-reranking | 364 | $0.0000153 |
| llm-model-routing | 369 | $0.0000155 |
| agent-tool-selection | 403 | $0.0000169 |
| content-moderation | 420 | $0.0000176 |
| lead-scoring | 472 | $0.0000198 |
| agent-output-guardrails | 474 | $0.0000199 |
| phishing-detection | 533 | $0.0000224 |
| support-ticket-triage | 539 | $0.0000226 |

**$0.0000153 – $0.0000226**, i.e. roughly 20× below $0.0004.

This is not a discount and not a vendor error. Pricing is $0.042 per 1M input tokens with no output tokens billed, and cost therefore scales with **one thing only**: your state plus your questions. A real support ticket is a few hundred tokens, not a few thousand. The $0.0004 figure describes a much larger state than most workloads send.

**The practical consequence:** the only number that matters for your budget is your own average state length. Multiply it by $0.042/1M. Nothing else moves the bill.

And since questions share one state and run in parallel, ask everything in one call — three separate calls pay for the state three times.

### 2. Quote latency twice, or don't quote it

Raw wall-clock medians here are **458–563 ms**. That number is close to meaningless on its own: measured from this machine, the **TCP handshake alone** to the host had a median of **198.8 ms** (7 samples, 191.2–266.4 ms).

| | median |
|---|---:|
| Raw round trip | 458–563 ms |
| Measured network floor | 198.8 ms |
| Remainder | **259–364 ms** |

So this run says little about Jev's speed and a lot about the distance between this machine and the host. `bench/net_floor.py` measures the floor so the two can be separated. Anyone publishing a Jev latency number without doing this is publishing their own geography.

*(Method borrowed from [anisselbd/jev-phishing-bench](https://github.com/anisselbd/jev-phishing-bench), which measures a floor before quoting anything.)*

### 3. `Score` is not 0–1, and `Noul` has no confidence field

Two response shapes that are easy to get wrong, both confirmed across every call in this dataset.

**`Score` returns the probability-weighted mean of the rubric indices, `0..n-1`** — not a normalised float. From `support-ticket-triage`:

```json
{
  "type": "score",
  "score": 2.68,
  "confidence": 0.68,
  "legend": {"0": "Low", "1": "Normal", "2": "High", "3": "Urgent"},
  "probabilities": {"0": 0, "1": 0, "2": 0.32, "3": 0.68}
}
```

`2×0.32 + 3×0.68 = 2.68`. A four-level rubric can return 2.68, meaning "between High and Urgent, leaning Urgent". Round it for the band; the fraction tells you which way the mass leans.

Recomputing the score from the returned `probabilities` reproduces it to **within ±0.02** — the probabilities are rounded to two decimals in the response, while `score` is computed from the full-precision distribution. Don't treat a small mismatch as a bug.

Note also that `probabilities` is keyed `"0"`, `"1"`, `"2"`… — by **index, never by label**. Use `legend` to map back.

**`Noul` ships no `confidence` field.** All 13 Noul answers in this dataset:

```json
{"type": "noul", "noul": 0.99}
```

That is the entire object. If you need a confidence gate on a Noul, distance from 0.5 is what you have.

---

## 4. We measured Jev against chat models, published a wrong conclusion, and corrected it

`bench/headtohead.py` puts the same fixtures to Jev and to three chat models
through one gateway. Across eight fixtures, five runs each:

| Model | Median | Mean cost | vs Jev |
|---|---:|---:|---:|
| typesafe/jev-1.13 | 352 ms | $0.0000188 | 1.0x |
| mistral-small-3.2-24b | 1,343 ms | $0.0000255 | 1.4x |
| gemini-2.5-flash-lite | 877 ms | $0.0000323 | 1.7x |
| gpt-5-nano | 7,504 ms | $0.0003434 | 18.3x |

Two things worth taking from that before the correction. A cheap chat model is
**1.4–1.7x** the cost, not two orders of magnitude — on a single-question
fixture `mistral-small` came out *cheaper* than Jev. And the large multiple
belongs to a reasoning model spending output tokens on thinking, which is a
different claim from "decision models are cheaper".

**The correction.** We first ran the chat models with a plain prompt and found
they returned the wrong *type* — asked for a probability between 0 and 1,
`gemini-2.5-flash-lite` answered `true` on three runs of five, `gpt-5-nano`
returned probabilities as strings, `mistral` dropped a field. We published
that as the argument for a typed model.

It was an artifact of how we asked. Every major chat API supports structured
output and we had not switched it on. Same prompt, same fixtures, one extra
field in the request body:

```
                        plain   json_schema
  gemini-2.5-flash-lite   2/5          5/5
  gpt-5-nano              4/5          5/5
  mistral-small-3.2       5/5          5/5
```

`response_format: {"type": "json_schema", "strict": true}` removes every
violation we found, on every fixture. So **type reliability is not a reason to
choose Jev** — it is one line in your request body. Check both halves:

```bash
python3 -m bench.headtohead --repeats 5            # plain prompt
python3 -m bench.headtohead --repeats 5 --schema   # the way you would actually do it
python3 -m bench.headtohead --repeats 5 --frontier # adds GPT-5.6 Sol/Terra and Opus 5
```

Measuring a model without the feature built for the job tests your prompt, not
the model. The wrong version is left in the history rather than deleted,
because a benchmark that only ever confirms its author is not worth reading.

## 5. The gateway is not free, and its tail is worse than its median

Same state and questions, alternating between routes twelve times so both see
the same network at the same minute:

| Route | p50 | p90 | Reports cost |
|---|---:|---:|---|
| api.typesafe.ai | 313 ms | 423 ms | no |
| OpenRouter `/api/alpha/decisions` | 734 ms | 1,739 ms | yes |

A first attempt ran the routes in sequence rather than interleaved and put the
gap at 497 ms; interleaving corrected it to 421 ms, and benchmark runs a few
hours earlier had OpenRouter at 339–453 ms. **The gateway tax is not one
number** — measure your own route at your own hour.

Two undocumented differences, both worth knowing before you pick:

- The model id differs. First-party answers as `jev-1.13.0`, OpenRouter as
  `typesafe/jev-1.13-20260917`. `GET /v1/models` lists only `jev-latest` and
  `jev-preview`, yet `jev-1.13.0` is accepted — while `jev-1.13` without the
  patch number is rejected as an unknown model.
- The first-party API reports `input_tokens` and `output_tokens` but **no
  cost**. That field is OpenRouter's addition.

## 6. Five questions in one request cost the same as one

From `x-envoy-upstream-service-time`, the server's own clock, rather than by
subtracting an estimated network floor:

| Questions in one request | Server time |
|---:|---:|
| 1 | 70 ms |
| 3 | 72 ms |
| 4 | 81 ms |
| 5 | 74 ms |

"Questions are evaluated in parallel" is a vendor claim everywhere else. This
is it read off the server's own header. Same practical advice the cost numbers
give: ask everything you want to know in one call.

## 7. Accuracy: Jev does not win, it ties

Everything above is cost, latency and output shape. None of it says whether an
answer is *right*. `bench/labelled.py` adds 27 support tickets with a correct
label, plus 6 deliberately ambiguous ones carrying no label at all. Every model
runs the whole set three times.

| Model | Correct | Per pass | Confidence, clear | Confidence, ambiguous |
|---|---:|---:|---:|---:|
| typesafe/jev-1.13 | 27/27 | 27 · 27 · 27 | 0.979 | 0.841 |
| mistral-small-3.2-24b | 27/27 | 27 · 27 · 27 | — | — |
| gemini-2.5-flash-lite | 26/27 | 26 · 26 · 26 | — | — |
| gpt-5-nano | 26/27 | 26 · 26 · 26 | — | — |

**"Jev is more accurate" is not supported by this.** It ties `mistral-small`, a
general chat model that costs 1.4x as much and answers four times slower — but
answers just as correctly, on every pass. Both misses across every model were
the *same* ticket: a 419 advance-fee scam, filed as `sales` by Gemini and
`billing` by GPT-5 nano rather than `spam`, on all three passes. That is a
reproducible disagreement about one ticket, not a general accuracy gap.

The confidence columns are the part only Jev can produce. Certainty falls from
0.979 on the clear set to 0.841 on the ambiguous one — calibrated in the right
direction, though by a smaller margin than you might want if you intend to
route on a threshold. The chat models return no confidence field at all.

### 7b. We nearly published a second artifact

The first version of this ran one pass and put gemini at 26/27; re-running it
gave 25/27 on the same tickets. Widening to three passes at **default
sampling** produced this, which looked like a finding:

| Model | Per pass, default sampling | With `temperature: 0` |
|---|---:|---:|
| gemini-2.5-flash-lite | 26 · 25 · 26 | 26 · 26 · 26 |
| gpt-5-nano | 24 · 26 · 26 | 26 · 26 · 26 |
| mistral-small-3.2 | 27 · 27 · 27 | 27 · 27 · 27 |
| typesafe/jev-1.13 | 27 · 27 · 27 | 27 · 27 · 27 |

An answer that changes between identical calls is a serious problem for
anything you route on, and "chat models are inconsistent, Jev is not" was a
finished paragraph before we checked it. `temperature: 0` removes it entirely.

That is the **second** time in this repo that the same mistake produced a
flattering result — see finding 4 for the first. Both times the fix was a field
in the request body. Both runs are kept: `data/accuracy.json` is the published
one, `data/accuracy-sampling-default.json` is the comparison.

```bash
python3 -m bench.accuracy                     # 3 passes, temperature 0
python3 -m bench.accuracy --sampling-default  # send no temperature at all
python3 -m bench.accuracy --only jev --repeats 5
```

**Limits.** Twenty-seven tickets written by us, on one task, in English, three
passes each. Enough to retire the claim that Jev is more accurate; not enough
to establish that anything else is. For a real accuracy study on independent
data, see [anisselbd/jev-phishing-bench](https://github.com/anisselbd/jev-phishing-bench)
(2,000 labelled emails).

---

## Reproduce it

```bash
git clone https://github.com/WallerChen/jev-measured
cd jev-measured
cp .env.example .env     # add one key — see below
python -m bench.net_floor              # measure your own network floor first
python -m bench.run                    # all 8 cases -> data/measured.json
```

Python 3.10+. The OpenRouter path needs **no dependencies at all** (stdlib `urllib`); `pip install -r requirements.txt` is only needed for the first-party TypeSafe SDK path.

Which transport runs is decided by which key is present:

| Key set | Transport | Model |
|---|---|---|
| `TYPESAFE_API_KEY` | First-party API | `jev-latest` |
| `OPENROUTER_API_KEY` | OpenRouter | `typesafe/jev-1.13` |

Other useful invocations:

```bash
python -m bench.run --limit 1                          # smoke test, prints raw answers
python -m bench.run --only phishing-detection --repeats 5
```

### ⚠️ Gateway gotcha

If you go through OpenRouter: **Jev will not appear in the model catalogue, and `/api/v1/chat/completions` will reject it.** Its modality is `text->decisions` rather than `text->text`, so listings built for chat models filter it out, and it reports an empty `supported_parameters`. Searching a gateway for "jev" can return nothing while the model is live and serving traffic.

Address it by exact id, and don't send `temperature` or `max_tokens` — none apply.

```bash
# Confirm it is live even though the catalogue omits it:
curl -s https://openrouter.ai/api/v1/models/typesafe/jev-1.13/endpoints
```

---

## How the fixtures are built

Eight use cases in [`bench/fixtures.py`](bench/fixtures.py), each a plain dict: a `state` and the typed questions asked about it.

- **Several states are deliberately ambiguous.** A fixture that returns 1.00 confidence every time teaches nothing about what the probabilities are for. Please don't "improve" them into easy cases.
- **Failures are recorded, not hidden.** An errored call keeps its error in the output rather than vanishing.
- **Latency is always reported raw and floor-adjusted.**

## What this is not

Not a broad accuracy benchmark. The eight main fixtures have no ground-truth labels at all — they measure cost, latency and response shape only. `bench/accuracy.py` adds 27 labelled tickets on one task, three passes each, which is enough to show Jev ties rather than wins, and not enough to rank anything. For accuracy at scale see [anisselbd/jev-phishing-bench](https://github.com/anisselbd/jev-phishing-bench) (2,000 labelled emails, Jev vs Claude Haiku 4.5).

Not affiliated with TypeSafe AI. Where this disagrees with [docs.typesafe.ai](https://docs.typesafe.ai), the official docs are correct — please open an issue so it can be fixed here.

Longer write-ups of each use case, with the code, are at [jev-agent.com/use-cases](https://jev-agent.com/use-cases).

## Licence

MIT. Quote the figures freely; attribution appreciated but not required.
