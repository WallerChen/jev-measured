"""Accuracy, and whether confidence means anything.

    python3 -m bench.accuracy

Two measurements, because one of them is not possible honestly:

  ACCURACY on the unambiguous set, where the label is a property of how the
  ticket was written. A wrong answer here is wrong, not a matter of opinion.

  CONFIDENCE SEPARATION between the unambiguous and ambiguous sets. This is
  the one that cannot be faked by a lookup table: a model that is equally sure
  about "I was charged twice" and about a ticket with two signals in tension
  is telling you nothing, however well it scores. Jev is the only model here
  that returns a confidence at all — the chat models are scored on accuracy
  only, and that asymmetry is the point rather than an oversight.

Chat models get response_format: json_schema, because measuring them without
the feature built for the job tests the prompt rather than the model. We
learned that the hard way and it invalidated an earlier conclusion.

Everything runs several passes by default. The first version of this script ran
once; re-running it moved gemini from 26/27 to 25/27 on the same 27 tickets. A
single pass over a small set is a coin flip dressed as a measurement, so the
output reports the spread across passes and how often each ticket was missed,
not one number.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.request
from pathlib import Path

from bench.labelled import AMBIGUOUS, QUEUES, UNAMBIGUOUS, choice_question

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "accuracy.json"

DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

CHAT_MODELS = [
    "google/gemini-2.5-flash-lite",
    "mistralai/mistral-small-3.2-24b-instruct",
    "openai/gpt-5-nano",
]


def load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def post(url: str, payload: dict, key: str, extra: dict | None = None) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", "authorization": f"Bearer {key}", **(extra or {})},
    )
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def ask_jev(text: str) -> tuple[str | None, float | None]:
    ts = os.environ.get("TYPESAFE_API_KEY")
    if ts:
        d = post(TYPESAFE_URL, {"model": "jev-latest", "state": text, "questions": {"queue": choice_question()}}, ts)
    else:
        d = post(
            DECISIONS_URL,
            {"model": "typesafe/jev-1.13", "state": text, "questions": {"queue": choice_question()}},
            os.environ["OPENROUTER_API_KEY"],
            {"HTTP-Referer": "https://jev-agent.com", "X-Title": "jev-agent.com"},
        )
    a = (d.get("answers") or {}).get("queue") or {}
    return a.get("choice"), a.get("confidence")


def ask_chat(model: str, text: str, key: str, temperature: float | None = None) -> str | None:
    opts = ", ".join(f"{k} ({v})" for k, v in QUEUES.items())
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": f"Which team should handle this ticket? Choose one of: {opts}\n\nTICKET:\n{text}",
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "routing",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"queue": {"type": "string", "enum": list(QUEUES)}},
                    "required": ["queue"],
                },
            },
        },
    }
    # Only sent when asked for. Some reasoning models reject the field
    # outright, and a default we did not have to send is a default we cannot
    # accidentally blame a model for.
    if temperature is not None:
        payload["temperature"] = temperature
    d = post(CHAT_URL, payload, key, {"HTTP-Referer": "https://jev-agent.com", "X-Title": "jev-agent.com"})
    txt = (d.get("choices") or [{}])[0].get("message", {}).get("content", "") or ""
    try:
        return json.loads(txt.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()).get("queue")
    except Exception:
        return None


def score(
    label_for: dict,
    ask,
    repeats: int,
) -> tuple[list[int], dict[str, dict]]:
    """Run `repeats` passes and return per-pass scores plus per-ticket misses.

    Misses are keyed by ticket so a question that fails every pass is visibly
    different from one that fails occasionally — the first is a disagreement
    about the label, the second is sampling noise.
    """
    per_pass: list[int] = []
    misses: dict[str, dict] = {}
    for _ in range(repeats):
        right = 0
        for text, label in label_for.items():
            try:
                got = ask(text)
            except Exception as e:  # a transport error is a miss, but a labelled one
                got = f"ERROR:{str(e)[:40]}"
            if got == label:
                right += 1
            else:
                m = misses.setdefault(text, {"text": text[:70], "expected": label, "got": [], "passes": 0})
                m["passes"] += 1
                if got not in m["got"]:
                    m["got"].append(got)
        per_pass.append(right)
    return per_pass, misses


def summarise(per_pass: list[int], total: int, misses: dict, **extra) -> dict:
    return {
        "total": total,
        "repeats": len(per_pass),
        "correct_per_pass": per_pass,
        "accuracy_mean": round(statistics.mean(per_pass) / total, 3),
        "accuracy_min": round(min(per_pass) / total, 3),
        "accuracy_max": round(max(per_pass) / total, 3),
        **extra,
        "errors": sorted(misses.values(), key=lambda m: -m["passes"]),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    # Substring rather than exact id: `--only jev` and `--only gpt-5-nano` both
    # do the obvious thing, and nobody has to remember whether the prefix is
    # `mistralai/` or `mistral/`.
    ap.add_argument("--only", metavar="SUBSTRING", help="run just the models whose id contains this")
    ap.add_argument("--repeats", type=int, default=3, help="passes over the whole set (default 3)")
    # Run-to-run flapping is only the model's fault if you asked it not to
    # sample. Measuring a chat model at its default temperature and calling the
    # variance a defect is the same error as measuring it without json_schema.
    ap.add_argument("--temperature", type=float, default=0.0, help="sent to chat models (default 0)")
    ap.add_argument(
        "--sampling-default",
        action="store_true",
        help="send no temperature at all — shows how much the answers move when you forget",
    )
    args = ap.parse_args()
    if args.sampling_default:
        args.temperature = None
    wanted = lambda m: args.only is None or args.only.lower() in m.lower()  # noqa: E731

    load_env()
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is not set. Put it in .env — never in the repo.")
    or_key = os.environ["OPENROUTER_API_KEY"]
    labels = dict(UNAMBIGUOUS)

    results: dict = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "unambiguous_n": len(UNAMBIGUOUS),
        "ambiguous_n": len(AMBIGUOUS),
        "repeats": args.repeats,
        "models": {},
    }

    print(f"{len(UNAMBIGUOUS)} labelled tickets x {args.repeats} passes, {len(AMBIGUOUS)} deliberately ambiguous\n")

    def line(name: str, per_pass: list[int], tail: str = "") -> None:
        spread = f"{min(per_pass)}-{max(per_pass)}" if min(per_pass) != max(per_pass) else str(per_pass[0])
        print(f"{name:42} {spread}/{len(UNAMBIGUOUS)}  passes {per_pass}  {tail}")

    # --- Jev -------------------------------------------------------------
    if wanted("typesafe/jev-1.13"):
        conf_clear: list[float] = []
        conf_murky: list[float] = []

        def ask(text: str) -> str | None:
            got, conf = ask_jev(text)
            if conf is not None:
                conf_clear.append(conf)
            return got

        per_pass, misses = score(labels, ask, args.repeats)
        for _ in range(args.repeats):
            for text in AMBIGUOUS:
                _, conf = ask_jev(text)
                if conf is not None:
                    conf_murky.append(conf)

        results["models"]["typesafe/jev-1.13"] = summarise(
            per_pass,
            len(UNAMBIGUOUS),
            misses,
            mean_confidence_unambiguous=round(statistics.mean(conf_clear), 3) if conf_clear else None,
            mean_confidence_ambiguous=round(statistics.mean(conf_murky), 3) if conf_murky else None,
        )
        line(
            "typesafe/jev-1.13",
            per_pass,
            f"conf clear {statistics.mean(conf_clear):.3f} / murky {statistics.mean(conf_murky):.3f}",
        )

    # --- Chat models -----------------------------------------------------
    for model in (m for m in CHAT_MODELS if wanted(m)):
        per_pass, misses = score(
            labels, lambda t, m=model: ask_chat(m, t, or_key, args.temperature), args.repeats
        )
        results["models"][model] = summarise(
            per_pass,
            len(UNAMBIGUOUS),
            misses,
            # Chat models return no confidence field, which is the asymmetry
            # this benchmark exists to show rather than a gap in the data.
            mean_confidence_unambiguous=None,
            mean_confidence_ambiguous=None,
        )
        line(model, per_pass)

    if not results["models"]:
        raise SystemExit(f"--only {args.only!r} matched no model.")

    # A filtered run would otherwise overwrite a full one with a partial file.
    results["chat_temperature"] = args.temperature

    # A filtered run would overwrite the dataset with a partial one.
    def report() -> None:
        for model, r in results["models"].items():
            for e in r["errors"]:
                got = "/".join(str(g) for g in e["got"])
                print(
                    f"  miss {e['passes']}/{args.repeats}  {model.split('/')[-1]:24} "
                    f"expected {e['expected']:10} got {got:14} | {e['text']}"
                )

    if args.only is not None:
        print(f"\nNot written to {OUT.name} — a filtered run is not the dataset.")
        report()
        return
    # temperature 0 is the published condition; anything else is a comparison
    # run and gets its own file rather than quietly replacing the headline.
    out = OUT if args.temperature == 0.0 else OUT.with_name("accuracy-sampling-default.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(f"\nWrote {out.relative_to(ROOT)}")
    report()


if __name__ == "__main__":
    main()
