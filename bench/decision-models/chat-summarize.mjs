// Fold chat-run.jsonl into data/decision-models/chat-summary.json, with the same set
// groupings as summarize.mjs so chat models and decision models sit in one table.
// Only models that answered every labelled item are kept; a retry's answer replaces a
// failed attempt at the same item.
import fs from "node:fs";
const rows = fs.readFileSync("chat-run.jsonl", "utf8").trim().split("\n").map((l) => JSON.parse(l));
const SAMPLE = JSON.parse(fs.readFileSync("btzsc-sample.json", "utf8"));
const TICKETS = JSON.parse(fs.readFileSync("tickets.json", "utf8"));
const expected = Object.values(SAMPLE).reduce((n, s) => n + s.items.length, 0) + TICKETS.unambiguous.length;

const latest = new Map();
for (const r of rows) {
  const k = `${r.model}|${r.set}|${r.i}`;
  if (r.status === 200 || !latest.has(k)) latest.set(k, r);
}
const byModel = new Map();
for (const r of latest.values()) {
  if (!byModel.has(r.model)) byModel.set(r.model, []);
  byModel.get(r.model).push(r);
}
const avg = (xs) => (xs.every((x) => typeof x === "number") ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
const models = [];
for (const [model, rs] of byModel) {
  const answered = rs.filter((r) => r.status === 200);
  if (answered.length < expected) { console.log(`skip ${model}: ${answered.length}/${expected}`); continue; }
  const acc = (set) => { const s = answered.filter((r) => r.set === set); return s.length ? s.filter((r) => r.correct).length / s.length : null; };
  const sets = Object.fromEntries([...Object.keys(SAMPLE), "tickets"].map((k) => [k, Math.round(acc(k) * 1000) / 1000]));
  const cost = answered.reduce((a, r) => a + (r.cost ?? 0), 0);
  models.push({
    id: model,
    effort: answered[0].effort ?? "off",
    sets,
    common: avg([acc("agnews"), acc("tickets")]),
    emotion: acc("emotiondair"),
    manyOptions: avg([acc("massive"), acc("banking77")]),
    yesNo: avg([acc("wikitoxic_toxicaggregated"), acc("amazonpolarity")]),
    unparsed: answered.filter((r) => r.answer === null).length,
    medianInputTokens: answered.map((r) => r.in_tok ?? 0).sort((a, b) => a - b)[Math.floor(answered.length / 2)],
    usdPer1kItems: (cost / answered.length) * 1000,
    served: [...new Set(answered.map((r) => r.served).filter(Boolean))],
  });
}
const out = {
  measuredAt: new Date().toISOString().slice(0, 10),
  gateway: "OpenRouter /api/v1/chat/completions",
  setup: "temperature 0, reasoning off (or the lowest effort a model accepts), system prompt 'You are a text classifier. Reply with the label only.', one item per request; a reply naming no option counts as wrong",
  items: expected,
  models,
};
fs.writeFileSync(new URL("../../data/decision-models/chat-summary.json", import.meta.url), JSON.stringify(out, null, 1));
console.log("wrote", models.length, "chat models");
