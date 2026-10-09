// Fold run.jsonl + latency.json into the file /decisions-api renders.
import fs from "node:fs";
const R = JSON.parse(fs.readFileSync("results.json", "utf8"));
const L = JSON.parse(fs.readFileSync("latency.json", "utf8"));
const SAMPLE = JSON.parse(fs.readFileSync("btzsc-sample.json", "utf8"));
const IDS = { // OpenRouter id -> the id this site takes (lib/decision-models.ts)
  "typesafe/jev-1.13": "jev-latest", "openai/gpt-6-luna-decisions": "gpt-6-luna",
};
const idOf = (m) => IDS[m] ?? m;
const avg = (xs) => { const v = xs.filter((x) => typeof x === "number"); return v.length === xs.length && v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
const models = Object.entries(R).map(([m, r]) => {
  const s = (k) => r.sets[k]?.acc ?? null;
  const lat = L[idOf(m)] ?? null;
  return {
    id: idOf(m),
    sets: Object.fromEntries(Object.entries(r.sets).map(([k, v]) => [k, Math.round(v.acc * 1000) / 1000])),
    unsupported: Object.keys(r.unsupported),
    common: avg([s("agnews"), s("tickets")]),
    emotion: s("emotiondair"),
    manyOptions: avg([s("massive"), s("banking77")]),
    yesNo: avg([s("wikitoxic_toxicaggregated"), s("amazonpolarity")]),
    choiceECE: r.choiceECE, noulBrier: r.noulBrier,
    highConfWrong: r.highConfWrong, highConfShare: r.highConfShare,
    ticketConfClear: r.ticketConfClear, ticketConfAmbiguous: r.ticketConfAmbiguous,
    medianInputTokens: r.medianTokens, usdPer1kDecisions: r.costPer1k,
    latencyP50: lat?.p50 ?? null, latencyP90: lat?.p90 ?? null,
  };
});
// Jev "@typesafe" only means TypeSafe direct when production has a TypeSafe key;
// on 2026-10-08 it did not (/api/health: available [openrouter]), so it is not used.
const jevDirect = null;
const out = {
  measuredAt: "2026-10-08",
  gateway: "OpenRouter /api/alpha/decisions",
  latencyFrom: "Vercel iad1 (Washington, D.C.), 20 sequential calls after one warm-up, one 5-option choice question",
  jevDirectLatency: jevDirect ? { p50: jevDirect.p50, p90: jevDirect.p90 } : null,
  items: Object.fromEntries([...Object.entries(SAMPLE).map(([k, v]) => [k, { n: v.items.length, labels: v.labels.length, type: v.type }]), ["tickets", { n: 27, labels: 5, type: "choice" }], ["tickets-ambiguous", { n: 6, labels: 5, type: "choice" }]]),
  models,
};
fs.writeFileSync(new URL("../../data/decision-models/summary.json", import.meta.url), JSON.stringify(out, null, 1));
console.log("wrote", models.length, "models");
