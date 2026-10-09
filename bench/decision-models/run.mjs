// Every decision model on OpenRouter's Decisions API, same items, one question per request.
//   node run.mjs [model ...]   (resumable: skips lines already in run.jsonl)
import fs from "node:fs";
// Reads OPENROUTER_API_KEY from the environment (or a .env file in the repo root).
try { process.loadEnvFile(new URL("../../.env", import.meta.url)); } catch {}
const KEY = process.env.OPENROUTER_API_KEY;
const SAMPLE = JSON.parse(fs.readFileSync("btzsc-sample.json", "utf8"));
const TICKETS = JSON.parse(fs.readFileSync("tickets.json", "utf8"));
const ALL = JSON.parse(fs.readFileSync("./or-decision-models.json", "utf8")).data.map((m) => m.id)
  .filter((id) => id !== "~typesafe/jev-latest" && id !== "respan/span-01-lite"); // alias of jev-1.13; same model as the :free tier
const MODELS = process.argv.slice(2).length ? process.argv.slice(2) : ALL;
const NOUL_ONLY = (m) => m.startsWith("respan/");
const pretty = (l) => l.replace(/_/g, " ").replace(/\s+/g, " ").trim();

const tasks = [];
for (const [set, cfg] of Object.entries(SAMPLE)) {
  cfg.items.forEach((it, i) => {
    if (cfg.type === "choice") {
      const criteria = Object.fromEntries(cfg.labels.map((l) => [l, pretty(l)]));
      tasks.push({ set, i, kind: "choice", gold: it.label, state: it.text, q: { type: "choice", instructions: cfg.instructions, criteria } });
    } else {
      tasks.push({ set, i, kind: "noul", gold: it.label === cfg.yes, state: it.text, q: { type: "noul", instructions: cfg.instructions, criteria: { true: "Yes", false: "No" } } });
    }
  });
}
const queues = TICKETS.queues;
TICKETS.unambiguous.forEach((t, i) => tasks.push({ set: "tickets", i, kind: "choice", gold: t.label, state: t.text, q: { type: "choice", instructions: "Which queue should this support ticket go to?", criteria: queues } }));
TICKETS.ambiguous.forEach((t, i) => tasks.push({ set: "tickets-ambiguous", i, kind: "choice", gold: null, state: t, q: { type: "choice", instructions: "Which queue should this support ticket go to?", criteria: queues } }));

const OUT = "run.jsonl";
const done = new Set(fs.existsSync(OUT) ? fs.readFileSync(OUT, "utf8").trim().split("\n").filter(Boolean).map((l) => { const r = JSON.parse(l); return `${r.model}|${r.set}|${r.i}`; }) : []);
const sleep = (ms) => new Promise((s) => setTimeout(s, ms));

async function ask(model, t) {
  for (let attempt = 0; attempt < 6; attempt++) {
    const started = Date.now();
    let status = 0, body = {};
    try {
      const r = await fetch("https://openrouter.ai/api/alpha/decisions", {
        method: "POST",
        headers: { "content-type": "application/json", authorization: `Bearer ${KEY}`, "HTTP-Referer": "https://github.com/WallerChen/jev-measured", "X-Title": "jev-measured" },
        body: JSON.stringify({ model, state: t.state, questions: { q: t.q } }),
        signal: AbortSignal.timeout(90_000),
      });
      status = r.status; body = await r.json().catch(() => ({}));
    } catch (e) { status = 0; body = { error: { message: e.message } }; }
    const ms = Date.now() - started;
    if (status === 429 || status >= 500 || status === 0) { await sleep(Math.min(60_000, 3000 * 2 ** attempt)); continue; }
    return { status, ms, body, attempts: attempt + 1 };
  }
  return { status: 429, ms: 0, body: { error: { message: "gave up after retries" } }, attempts: 6 };
}

async function runModel(model) {
  const mine = tasks.filter((t) => (!NOUL_ONLY(model) || t.kind === "noul") && !done.has(`${model}|${t.set}|${t.i}`));
  const free = model.endsWith(":free");
  const width = free ? 1 : 4;
  let next = 0, n = 0;
  async function worker() {
    while (next < mine.length) {
      const t = mine[next++];
      const res = await ask(model, t);
      const a = res.body?.answers?.q;
      fs.appendFileSync(OUT, JSON.stringify({
        model, set: t.set, i: t.i, kind: t.kind, gold: t.gold, status: res.status, ms: res.ms, attempts: res.attempts,
        error: res.status === 200 ? null : (res.body?.error?.message ?? JSON.stringify(res.body)).slice(0, 300),
        choice: a?.choice ?? null, confidence: a?.confidence ?? null, noul: a?.noul ?? null, probabilities: t.kind === "choice" && t.set === "tickets-ambiguous" ? a?.probabilities ?? null : undefined,
        in_tok: res.body?.usage?.input_tokens ?? null, cost: res.body?.usage?.cost ?? null, served: res.body?.model ?? null,
      }) + "\n");
      if (++n % 50 === 0) console.log(`${model} ${n}/${mine.length}`);
      if (free) await sleep(3200);
    }
  }
  await Promise.all(Array.from({ length: width }, worker));
  console.log(`${model} done (${mine.length} calls)`);
}
console.log(`tasks ${tasks.length}, models ${MODELS.length}`);
await Promise.all(MODELS.map(runModel));
