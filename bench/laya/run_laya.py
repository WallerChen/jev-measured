# Laya on the same 633 items jev-measured ran through OpenRouter on 2026-10-08.
# Same questions as bench/decision-models/run.mjs: one question per request.
import json, time, os, sys, statistics
import laya, torch

SAMPLE = json.load(open("btzsc-sample.json"))
TICKETS = json.load(open("tickets.json"))
pretty = lambda l: " ".join(l.replace("_", " ").split())
tasks = []
for set_, cfg in SAMPLE.items():
    for i, it in enumerate(cfg["items"]):
        if cfg["type"] == "choice":
            q = {"type": "choice", "instructions": cfg["instructions"], "criteria": {l: pretty(l) for l in cfg["labels"]}}
            tasks.append(dict(set=set_, i=i, kind="choice", gold=it["label"], state=it["text"], q=q))
        else:
            q = {"type": "noul", "instructions": cfg["instructions"], "criteria": {"true": "Yes", "false": "No"}}
            tasks.append(dict(set=set_, i=i, kind="noul", gold=it["label"] == cfg["yes"], state=it["text"], q=q))
tq = {"type": "choice", "instructions": "Which queue should this support ticket go to?", "criteria": TICKETS["queues"]}
for i, t in enumerate(TICKETS["unambiguous"]):
    tasks.append(dict(set="tickets", i=i, kind="choice", gold=t["label"], state=t["text"], q=tq))
for i, t in enumerate(TICKETS["ambiguous"]):
    tasks.append(dict(set="tickets-ambiguous", i=i, kind="choice", gold=None, state=t, q=tq))

name = sys.argv[1] if len(sys.argv) > 1 else "laya"
sub = {"laya": None, "laya-multilingual": "multilingual"}[name]
t0 = time.time()
agent = laya.load("convaiinnovations/laya", subfolder=sub) if sub else laya.load("convaiinnovations/laya")
print("loaded", name, round(time.time() - t0, 1), "s; device", getattr(agent, "device", "?"), flush=True)
agent.predict("warm up", {"q": tq})
out = open(f"run-{name}.jsonl", "w")
lat = []
for n, t in enumerate(tasks):
    s = time.perf_counter()
    r = agent.predict(t["state"], {"q": t["q"]})
    ms = (time.perf_counter() - s) * 1000
    lat.append(ms)
    a = r["answers"]["q"]
    probs = a.get("probabilities")
    row = dict(model=name, set=t["set"], i=t["i"], kind=t["kind"], gold=t["gold"], status=200, ms=round(ms, 1), attempts=1, error=None,
               choice=a.get("choice"), confidence=(max(probs.values()) if probs else None) if t["kind"] == "choice" else None,
               entropy_confidence=a.get("confidence"), noul=a.get("noul"), in_tok=(r.get("usage") or {}).get("input_tokens"), cost=0, served=r.get("model"))
    if t["set"] == "tickets-ambiguous":
        row["probabilities"] = probs
    out.write(json.dumps(row) + "\n")
    if (n + 1) % 100 == 0:
        print(n + 1, "done", flush=True)
out.close()
lat.sort()
print("p50 ms", round(statistics.median(lat), 1), "p90 ms", round(lat[int(0.9 * len(lat))], 1), "n", len(lat))
