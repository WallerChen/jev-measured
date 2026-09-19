# jev-measured

Measured cost, latency and raw output from the live **Jev** API (TypeSafe AI's System One decision model) across eight realistic use cases. Reproducible: bring your own key and re-run it.

Published because most numbers circulating about Jev are either the vendor's own or arithmetic from the rate card. These are what the API actually returned.

- **Measured:** 2026-09-18
- **Model:** `typesafe/jev-1.13` via OpenRouter
- **Raw data:** [`data/measured.json`](data/measured.json)
- **Cost of the whole run:** under one cent

---

## Three findings

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

Not an accuracy benchmark. There are no ground-truth labels here, so nothing in this repo says whether Jev is *right* — only what it costs, how long it takes, and what shape comes back. For accuracy, see [anisselbd/jev-phishing-bench](https://github.com/anisselbd/jev-phishing-bench) (2,000 labelled emails, Jev vs Claude Haiku 4.5).

Not affiliated with TypeSafe AI. Where this disagrees with [docs.typesafe.ai](https://docs.typesafe.ai), the official docs are correct — please open an issue so it can be fixed here.

Longer write-ups of each use case, with the code, are at [jev-agent.com/use-cases](https://jev-agent.com/use-cases).

## Licence

MIT. Quote the figures freely; attribution appreciated but not required.
