"""Jev versus LLMs on the same decision, measured.

Every "Jev is Nx cheaper and Mx faster" number in circulation is TypeSafe's
own. This runs both sides ourselves, through one gateway, on one fixture, and
reports what the API billed.

The comparison is deliberately generous to the LLMs: they get the same
criteria text Jev gets, an explicit JSON shape, and they are scored on whether
that JSON parsed at all — which is the tax Jev does not pay.

    python3 -m bench.headtohead
    python3 -m bench.headtohead --case content-moderation --repeats 5
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.request
from pathlib import Path

from bench.fixtures import CASES

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "headtohead.json"

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
JEV_MODEL = "typesafe/jev-1.13"

# Cheap-to-midrange chat models. Batch variants are excluded: they are priced
# lower precisely because they are not answering now, and latency is half of
# what is being measured.
LLM_MODELS = [
    "openai/gpt-5-nano",
    "google/gemini-2.5-flash-lite",
    "mistralai/mistral-small-3.2-24b-instruct",
]


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def post(url: str, payload: dict, key: str) -> tuple[dict, float]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "content-type": "application/json",
            "authorization": f"Bearer {key}",
            "HTTP-Referer": "https://jev-agent.com",
            "X-Title": "jev-agent.com",
        },
    )
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    return data, (time.perf_counter() - started) * 1000


def run_jev(case: dict, key: str) -> dict:
    payload = {"model": JEV_MODEL, "state": case["state"], "questions": case["questions"]}
    data, ms = post(DECISIONS_URL, payload, key)
    usage = data.get("usage", {}) or {}
    return {
        "latency_ms": ms,
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "cost_usd": usage.get("cost"),
        "answers": data.get("answers", {}),
        "parsed": True,  # there is nothing to parse; the shape is the contract
    }


def llm_prompt(case: dict) -> str:
    """Same criteria Jev sees, plus the JSON shape it does not need told."""
    lines = ["Answer these questions about the text. Reply with ONLY a JSON object, no prose, no fences.", ""]
    shape = {}
    for qid, q in case["questions"].items():
        if q["type"] == "choice":
            opts = ", ".join(f'"{k}" ({v})' for k, v in q["criteria"].items())
            lines.append(f'- {qid}: {q["instructions"]} Choose one of: {opts}')
            shape[qid] = "<one option key>"
        elif q["type"] == "score":
            levels = ", ".join(f"{i}={lab}" for i, lab in enumerate(q["criteria"]))
            lines.append(f'- {qid}: {q["instructions"]} Rate on: {levels}')
            shape[qid] = "<number 0..n-1>"
        else:
            c = q["criteria"]
            lines.append(f'- {qid}: {q["instructions"]} true when {c["true"]}; false when {c["false"]}')
            shape[qid] = "<probability 0..1>"
    lines += ["", f"JSON shape: {json.dumps(shape)}", "", "TEXT:", case["state"]]
    return "\n".join(lines)


def run_llm(model: str, case: dict, key: str) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": llm_prompt(case)}],
        "usage": {"include": True},
    }
    data, ms = post(CHAT_URL, payload, key)
    usage = data.get("usage", {}) or {}
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""

    parsed, answers = True, None
    try:
        cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        answers = json.loads(cleaned)
    except Exception:
        parsed = False

    return {
        "latency_ms": ms,
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "cost_usd": usage.get("cost"),
        "answers": answers,
        "parsed": parsed,
        "raw": None if parsed else text[:200],
    }


def type_violations(case: dict, answers: dict | None) -> list[str]:
    """Did the reply have the TYPE that was asked for, not just valid JSON?

    This is the measurement that matters and the one everyone skips. Parsing
    is easy; modern models emit clean JSON almost every time. Returning the
    declared type is a separate problem — a question asked for a probability
    between 0 and 1 and answered with `true` parsed perfectly and is still
    unusable by code expecting a float. Booleans are checked before numbers
    because in Python `True` is an int.
    """
    if answers is None:
        return ["no parseable object"]
    bad = []
    for qid, q in case["questions"].items():
        if qid not in answers:
            bad.append(f"{qid}: missing")
            continue
        v = answers[qid]
        if q["type"] == "choice":
            if not isinstance(v, str) or v not in q["criteria"]:
                bad.append(f"{qid}: {v!r} is not one of the options")
        elif q["type"] == "score":
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                bad.append(f"{qid}: {v!r} is not a number")
            elif not 0 <= v <= len(q["criteria"]) - 1:
                bad.append(f"{qid}: {v!r} outside 0..{len(q['criteria']) - 1}")
        else:  # noul — a probability, and `true` is not one
            if isinstance(v, bool):
                bad.append(f"{qid}: {v!r} is a boolean, not a probability")
            elif not isinstance(v, (int, float)) or not 0 <= v <= 1:
                bad.append(f"{qid}: {v!r} is not a probability in 0..1")
    return bad


def normalise_jev(answers: dict) -> dict:
    """Flatten Jev's typed answers to the same shape the LLMs were asked for."""
    out = {}
    for qid, a in answers.items():
        if "choice" in a:
            out[qid] = a["choice"]
        elif "score" in a:
            out[qid] = a["score"]
        elif "noul" in a:
            out[qid] = a["noul"]
    return out


def summarise(case: dict, runs: list[dict]) -> dict:
    ok = [r for r in runs if r.get("latency_ms")]
    viol = [r.get("violations") or [] for r in runs]
    return {
        "runs": len(runs),
        "parse_ok": sum(1 for r in runs if r["parsed"]),
        "type_ok": sum(1 for v in viol if not v),
        "violations": sorted({x for v in viol for x in v}),
        "latency_ms_median": round(statistics.median(r["latency_ms"] for r in ok), 1) if ok else None,
        "input_tokens": ok[0].get("input_tokens") if ok else None,
        "output_tokens": ok[0].get("output_tokens") if ok else None,
        "cost_usd_median": statistics.median([r["cost_usd"] for r in ok if r.get("cost_usd") is not None])
        if any(r.get("cost_usd") is not None for r in ok)
        else None,
        "answers": [r["answers"] for r in runs],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="support-ticket-triage", choices=sorted(CASES))
    ap.add_argument("--repeats", type=int, default=3)
    args = ap.parse_args()

    load_env()
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY is not set. Put it in .env — never in the repo.")

    case = CASES[args.case]
    print(f"case: {args.case} · {args.repeats} runs each\n")

    results: dict[str, dict] = {}

    jev_runs = []
    for _ in range(args.repeats):
        r = run_jev(case, key)
        r["answers"] = normalise_jev(r["answers"])
        r["violations"] = type_violations(case, r["answers"])
        jev_runs.append(r)
    results[JEV_MODEL] = summarise(case, jev_runs)

    for model in LLM_MODELS:
        runs = []
        for _ in range(args.repeats):
            try:
                r = run_llm(model, case, key)
                r["violations"] = type_violations(case, r["answers"])
                runs.append(r)
            except Exception as e:  # a model can be rate limited or gone
                runs.append({"latency_ms": None, "parsed": False, "answers": None,
                             "violations": ["request failed"], "error": str(e)[:120]})
        results[model] = summarise(case, runs)

    hdr = f"{'model':42} {'median ms':>10} {'out tok':>8} {'cost':>13} {'parsed':>7} {'typed':>6}"
    print(hdr)
    print("-" * len(hdr))
    for name, r in results.items():
        cost = f"${r['cost_usd_median']:.8f}" if r["cost_usd_median"] is not None else "—"
        print(
            f"{name:42} {r['latency_ms_median'] or 0:10.1f} {r['output_tokens'] or 0:8} "
            f"{cost:>13} {r['parse_ok']}/{r['runs']:<5} {r['type_ok']}/{r['runs']:<4}"
        )
    for name, r in results.items():
        for v in r["violations"]:
            print(f"    ! {name}: {v}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"case": args.case, "repeats": args.repeats, "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "results": results},
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print(f"\nWrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
