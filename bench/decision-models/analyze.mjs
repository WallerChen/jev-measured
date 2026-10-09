import fs from "node:fs";
const rows = fs.readFileSync("run.jsonl", "utf8").trim().split("\n").map(JSON.parse);
const CHOICE = ["agnews", "emotiondair", "massive", "banking77", "tickets"];
const NOUL = ["wikitoxic_toxicaggregated", "amazonpolarity"];
const models = [...new Set(rows.map((r) => r.model))];
const q = (xs, p) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.min(s.length - 1, Math.floor(p * s.length))] : null; };
function ece(pairs, bins = 10) { // [confidence, correct]
  if (!pairs.length) return null;
  const b = Array.from({ length: bins }, () => ({ n: 0, c: 0, a: 0 }));
  for (const [p, ok] of pairs) { const i = Math.min(bins - 1, Math.floor(p * bins)); b[i].n++; b[i].c += p; b[i].a += ok ? 1 : 0; }
  return b.reduce((s, x) => s + (x.n ? (x.n / pairs.length) * Math.abs(x.c / x.n - x.a / x.n) : 0), 0);
}
const out = {};
for (const m of models) {
  const mine = rows.filter((r) => r.model === m);
  const ok = mine.filter((r) => r.status === 200);
  const res = { calls: mine.length, ok: ok.length, sets: {}, unsupported: {} };
  for (const set of [...CHOICE, ...NOUL]) {
    const all = mine.filter((r) => r.set === set);
    if (!all.length) continue;
    const good = all.filter((r) => r.status === 200);
    if (good.length < all.length * 0.5) { res.unsupported[set] = (all.find((r) => r.status !== 200)?.error ?? "").slice(0, 120); continue; }
    const correct = good.filter((r) => (r.kind === "choice" ? r.choice === r.gold : (r.noul >= 0.5) === r.gold)).length;
    res.sets[set] = { n: good.length, acc: correct / good.length };
  }
  const choiceSets = CHOICE.filter((s) => res.sets[s]);
  const noulSets = NOUL.filter((s) => res.sets[s]);
  res.choiceAcc = choiceSets.length ? choiceSets.reduce((a, s) => a + res.sets[s].acc, 0) / choiceSets.length : null;
  res.choiceSetsScored = choiceSets.length;
  res.noulAcc = noulSets.length ? noulSets.reduce((a, s) => a + res.sets[s].acc, 0) / noulSets.length : null;
  // Calibration: choice confidence vs correctness; noul probability vs label.
  const cPairs = ok.filter((r) => r.kind === "choice" && r.gold !== null && typeof r.confidence === "number" && CHOICE.includes(r.set) && res.sets[r.set]).map((r) => [r.confidence, r.choice === r.gold]);
  const nPairs = ok.filter((r) => r.kind === "noul" && typeof r.noul === "number").map((r) => [r.noul, r.gold]);
  res.choiceECE = ece(cPairs);
  res.noulBrier = nPairs.length ? nPairs.reduce((s, [p, y]) => s + (p - (y ? 1 : 0)) ** 2, 0) / nPairs.length : null;
  res.noulECE = ece(nPairs.map(([p, y]) => [p >= 0.5 ? p : 1 - p, (p >= 0.5) === y]));
  // Confidence separation on the support tickets: clear vs deliberately ambiguous.
  const conf = (set) => ok.filter((r) => r.set === set && typeof r.confidence === "number").map((r) => r.confidence);
  const avg = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
  res.ticketConfClear = avg(conf("tickets"));
  res.ticketConfAmbiguous = avg(conf("tickets-ambiguous"));
  // Confident and wrong: share of answers at confidence >= 0.9 that were wrong.
  const hi = cPairs.filter(([p]) => p >= 0.9);
  res.highConfWrong = hi.length ? hi.filter(([, c]) => !c).length / hi.length : null;
  res.highConfShare = cPairs.length ? hi.length / cPairs.length : null;
  // Tokens and cost as the gateway reported them.
  const tok = ok.map((r) => r.in_tok).filter((x) => typeof x === "number");
  res.medianTokens = q(tok, 0.5);
  const costs = ok.map((r) => r.cost).filter((x) => typeof x === "number");
  res.costPer1k = costs.length ? (costs.reduce((a, b) => a + b, 0) / costs.length) * 1000 : null;
  res.p50msLocal = q(ok.map((r) => r.ms), 0.5);
  res.served = [...new Set(ok.map((r) => r.served))].slice(0, 3);
  out[m] = res;
}
fs.writeFileSync("results.json", JSON.stringify(out, null, 1));
const pct = (x) => (x == null ? "  —  " : (x * 100).toFixed(1).padStart(5));
console.log("model".padEnd(40), "choice", "noul ", "agnew", "emot ", "massv", "bank ", "tickt", "toxic", "amzn ", "cECE ", "nBrier", "hiWrong", "clear/amb", "tok", "$/1k");
for (const [m, r] of Object.entries(out).sort((a, b) => (b[1].choiceAcc ?? 0) - (a[1].choiceAcc ?? 0))) {
  const s = (k) => pct(r.sets[k]?.acc);
  console.log(m.padEnd(40), pct(r.choiceAcc), pct(r.noulAcc), s("agnews"), s("emotiondair"), s("massive"), s("banking77"), s("tickets"), s("wikitoxic_toxicaggregated"), s("amazonpolarity"),
    r.choiceECE == null ? "  —  " : r.choiceECE.toFixed(3), r.noulBrier == null ? "  —  " : r.noulBrier.toFixed(3), pct(r.highConfWrong),
    r.ticketConfClear == null ? "—" : `${r.ticketConfClear.toFixed(2)}/${r.ticketConfAmbiguous?.toFixed(2)}`, r.medianTokens, r.costPer1k?.toFixed(4));
}
