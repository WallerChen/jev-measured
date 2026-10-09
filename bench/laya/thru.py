import json, time, laya
S = json.load(open("btzsc-sample.json"))
cfg = S["agnews"]
q = {"q": {"type": "choice", "instructions": cfg["instructions"], "criteria": {l: l for l in cfg["labels"]}}}
states = [it["text"] for it in cfg["items"]]
agent = laya.load("convaiinnovations/laya")
agent.predict_batch(states[:8], q, batch_size=8)  # warm-up
for bs in (1, 16, 32):
    t = time.perf_counter(); res = agent.predict_batch(states, q, batch_size=bs); dt = time.perf_counter() - t
    print(f"batch {bs}: {len(states)/dt:.1f} decisions/s ({dt*1000/len(states):.1f} ms each)", flush=True)
