"""Run every use-case fixture against the real Jev API and record what came back.

The point of this script is that jev-agent.com should never publish a code
sample nobody ran. Whatever lands in data/measured.json is literally what the
API returned, including the cases where Jev is unsure or wrong — those are the
most useful ones to show.

Usage
-----
    export TYPESAFE_API_KEY=...            # or put it in .env
    uv run bench/run.py --limit 1          # smoke test, prints raw answers
    uv run bench/run.py                    # all cases -> data/measured.json

Nothing here is clever. It calls the official SDK, times the call, and writes
down the answer.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from bench.net_floor import floor_for

# bench.fixtures is imported lazily inside main(): it constructs SDK objects at
# module level, so importing it early turns a missing dependency into a
# traceback instead of a one-line "run pip install" message.

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "measured.json"

# Transport is chosen by which key is present. OpenRouter needs the
# /api/alpha/decisions path — chat/completions rejects a decisions model.
if os.environ.get("TYPESAFE_API_KEY"):
    TRANSPORT = "typesafe"
    BASE_URL = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
    ENDPOINT = BASE_URL + "/v1/systemone"
    MODEL = os.environ.get("TYPESAFE_MODEL", "jev-latest")
    API_KEY_NAME = "TYPESAFE_API_KEY"
else:
    TRANSPORT = "openrouter"
    BASE_URL = "https://openrouter.ai"
    ENDPOINT = BASE_URL + "/api/alpha/decisions"
    MODEL = os.environ.get("JEV_MODEL", "typesafe/jev-1.13")
    API_KEY_NAME = "OPENROUTER_API_KEY"
# $ per input token. Output is free — there is none.
PRICE_PER_INPUT_TOKEN = 0.042 / 1_000_000


def _load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _serialise_answer(answer) -> dict:
    """Record whatever fields the answer actually carries.

    The three primitives genuinely differ (verified live 2026-09-18):
      choice -> choice, probabilities{option}, confidence
      score  -> score (0-1 float), legend{index: label}, probabilities{index}, confidence
      noul   -> noul (0-1 float), and nothing else
    So nothing is assumed; we take what is there. Works for both the SDK's
    objects and a plain dict from the HTTP API.
    """
    def get(field):
        if isinstance(answer, dict):
            return answer.get(field)
        return getattr(answer, field, None)

    out: dict = {}
    for field in ("type", "choice", "score", "noul", "confidence"):
        value = get(field)
        if value is not None:
            out[field] = value

    for field in ("legend", "probabilities"):
        value = get(field)
        if value is not None:
            try:
                out[field] = dict(value)
            except (TypeError, ValueError):
                out[field] = value

    if not out:  # unexpected shape — keep the repr so we can see what happened
        out["raw"] = repr(answer)
    return out


def call(api_key: str, state: str, questions: dict) -> dict:
    """One request. Plain HTTP against the verified endpoint — no SDK needed."""
    import urllib.request

    body = json.dumps({"model": MODEL, "state": state, "questions": questions}).encode()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if TRANSPORT == "openrouter":
        headers["HTTP-Referer"] = "https://jev-agent.com"
        headers["X-Title"] = "jev-agent.com"
    req = urllib.request.Request(ENDPOINT, data=body, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def run_case(api_key: str, slug: str, case: dict, repeats: int) -> dict:
    timings: list[float] = []
    response = None

    for _ in range(repeats):
        started = time.perf_counter()
        response = call(api_key, case["state"], case["questions"])
        timings.append((time.perf_counter() - started) * 1000)

    answers = {key: _serialise_answer(value) for key, value in response.get("answers", {}).items()}

    usage = response.get("usage") or {}
    input_tokens = usage.get("input_tokens")
    cost = usage.get("cost")

    record = {
        "slug": slug,
        "state": case["state"],
        "note": case.get("note"),
        "answers": answers,
        "latency_ms": {
            "min": round(min(timings), 1),
            "median": round(statistics.median(timings), 1),
            "runs": len(timings),
        },
    }
    if input_tokens is not None:
        record["input_tokens"] = input_tokens
    # Prefer the cost the API reports over our own arithmetic.
    record["cost_usd"] = cost if cost is not None else (
        round(input_tokens * PRICE_PER_INPUT_TOKEN, 10) if input_tokens else None
    )
    record["model"] = response.get("model", MODEL)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="only run the first N cases")
    parser.add_argument("--repeats", type=int, default=3, help="calls per case; median is reported")
    parser.add_argument("--only", type=str, default="", help="run a single slug")
    args = parser.parse_args()

    _load_dotenv()
    api_key = os.environ.get(API_KEY_NAME)
    if not api_key:
        print(f"{API_KEY_NAME} is not set. Put it in the environment or in .env — never in the repo.")
        return 1

    from bench.fixtures import CASES

    print(f"Transport: {TRANSPORT} -> {ENDPOINT}  (model {MODEL})")

    print(f"Measuring network floor to {BASE_URL} ...")
    floor = floor_for(BASE_URL)
    if floor.get("ok"):
        print(f"  median TCP handshake {floor['median_ms']}ms (min {floor['min_ms']}ms)")
    else:
        print("  could not measure — latency will be reported raw only")

    slugs = [args.only] if args.only else list(CASES)
    if args.limit:
        slugs = slugs[: args.limit]

    results: dict[str, dict] = {}
    for slug in slugs:
        case = CASES.get(slug)
        if case is None:
            print(f"  ! unknown slug {slug}")
            continue
        print(f"\n→ {slug}")
        try:
            record = run_case(api_key, slug, case, args.repeats)
        except Exception as exc:  # a failure is a finding; record it, don't hide it
            print(f"  FAILED: {type(exc).__name__}: {exc}")
            results[slug] = {"slug": slug, "error": f"{type(exc).__name__}: {exc}"}
            continue

        results[slug] = record
        for key, answer in record["answers"].items():
            verdict = answer.get("choice") or answer.get("score") or answer.get("noul")
            confidence = answer.get("confidence")
            suffix = f"  (confidence {confidence:.2f})" if isinstance(confidence, (int, float)) else ""
            print(f"  {key:<18} {verdict}{suffix}")
        print(f"  median {record['latency_ms']['median']}ms over {record['latency_ms']['runs']} runs")

    payload = {
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODEL,
        "transport": TRANSPORT,
        "endpoint": ENDPOINT,
        "network_floor": floor,
        "price_per_1m_input_usd": 0.042,
        "cases": results,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {OUT.relative_to(ROOT)} — {len(results)} case(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
