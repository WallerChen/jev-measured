import json, laya
S = json.load(open("btzsc-sample.json"))
agent = laya.load("convaiinnovations/laya")
QS = {"amazonpolarity": "Is this product review positive overall?",
      "wikitoxic_toxicaggregated": "Does this Wikipedia talk-page comment contain toxic language: insults, threats, obscenity or hate?"}
out = {}
for set_, cfg in S.items():
    if cfg["type"] != "noul": continue
    variants = {
        "statement+criteria (harness)": {"type": "noul", "instructions": cfg["instructions"], "criteria": {"true": "Yes", "false": "No"}},
        "statement, no criteria": {"type": "noul", "instructions": cfg["instructions"]},
        "question, no criteria": {"type": "noul", "instructions": QS[set_]},
    }
    for name, q in variants.items():
        ok = 0
        for it in cfg["items"]:
            p = agent.predict(it["text"], {"q": q})["answers"]["q"]["noul"]
            ok += (p >= 0.5) == (it["label"] == cfg["yes"])
        out[f"{set_} | {name}"] = ok / len(cfg["items"])
        print(set_, "|", name, ok, "/", len(cfg["items"]), flush=True)
json.dump(out, open("variants.json", "w"), indent=1)
