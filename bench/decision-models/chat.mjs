// Chat models on the same 633 items as run.mjs, for "which LLM is best at text classification".
// Same items, same instructions, same options; the model is told to reply with one option, at
// temperature 0, reasoning off where the model allows it. A reply that matches no option counts
// as wrong, exactly as a refusal from a decision model does.
//
//   node chat.mjs --limit 10 model ...   (pilot: the first N items of every set)
//   node chat.mjs model ...              (resumable: skips items already answered in chat-run.jsonl)
//   node chat.mjs --reasoning minimal model ...   (models that refuse to run with reasoning off)
//
// Reads OPENROUTER_API_KEY from the environment (or ENV_FILE / a .env in the repo root).
import fs from "node:fs";
for (const f of [process.env.ENV_FILE, new URL("../../.env", import.meta.url)]) {
  if (!f) continue;
  try { process.loadEnvFile(f); break; } catch {}
}
const KEY = process.env.OPENROUTER_API_KEY;
if (!KEY) { console.error("OPENROUTER_API_KEY is not set"); process.exit(1); }

const args = process.argv.slice(2);
const li = args.indexOf("--limit");
const LIMIT = li >= 0 ? Number(args[li + 1]) : 0;
const ri = args.indexOf("--reasoning");
// For models whose endpoint will not run with reasoning off: the lowest effort they accept.
const EFFORT = ri >= 0 ? args[ri + 1] : null;
const flagged = new Set([li, li + 1, ri, ri + 1].filter((i) => i >= 0 && (i === li || i === li + 1 ? li >= 0 : ri >= 0)));
const MODELS = args.filter((a, i) => !flagged.has(i));
const SAMPLE = JSON.parse(fs.readFileSync("btzsc-sample.json", "utf8"));
const TICKETS = JSON.parse(fs.readFileSync("tickets.json", "utf8"));
const pretty = (l) => l.replace(/_/g, " ").replace(/\s+/g, " ").trim();
const norm = (s) => s.toLowerCase().replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();

const tasks = [];
for (const [set, cfg] of Object.entries(SAMPLE)) {
  cfg.items.slice(0, LIMIT || undefined).forEach((it, i) => {
    if (cfg.type === "choice") tasks.push({ set, i, kind: "choice", gold: it.label, text: it.text, instructions: cfg.instructions, labels: cfg.labels });
    else tasks.push({ set, i, kind: "noul", gold: it.label === cfg.yes, text: it.text, instructions: cfg.instructions });
  });
}
const queues = Object.keys(TICKETS.queues);
TICKETS.unambiguous.slice(0, LIMIT || undefined).forEach((t, i) =>
  tasks.push({ set: "tickets", i, kind: "choice", gold: t.label, text: t.text, instructions: "Which queue should this support ticket go to?", labels: queues, describe: TICKETS.queues }));

function prompt(t) {
  if (t.kind === "noul")
    return `Statement: ${t.instructions}\n\nText:\n"""${t.text}"""\n\nIs the statement true of the text? Reply with yes or no only.`;
  const opts = t.labels.map((l) => `- ${pretty(l)}${t.describe ? `: ${t.describe[l]}` : ""}`).join("\n");
  return `${t.instructions}\n\nOptions:\n${opts}\n\nText:\n"""${t.text}"""\n\nReply with exactly one option from the list, copied exactly, and nothing else.`;
}

function parse(t, reply) {
  const r = norm(reply ?? "");
  if (t.kind === "noul") return r.startsWith("yes") ? true : r.startsWith("no") ? false : null;
  const byNorm = new Map(t.labels.map((l) => [norm(pretty(l)), l]));
  if (byNorm.has(r)) return byNorm.get(r);
  // The option named inside a longer reply; longest first so "card payment fee charged" beats "card payment".
  const hit = [...byNorm.keys()].sort((a, b) => b.length - a.length).find((k) => r.includes(k));
  return hit ? byNorm.get(hit) : null;
}

const OUT = "chat-run.jsonl";
const done = new Set(fs.existsSync(OUT) ? fs.readFileSync(OUT, "utf8").trim().split("\n").filter(Boolean).map((l) => JSON.parse(l)).filter((r) => r.status === 200).map((r) => `${r.model}|${r.set}|${r.i}`) : []);
const sleep = (ms) => new Promise((s) => setTimeout(s, ms));

async function ask(model, t) {
  for (let attempt = 0; attempt < 6; attempt++) {
    const started = Date.now();
    let status = 0, body = {};
    try {
      const r = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method: "POST",
        headers: { "content-type": "application/json", authorization: `Bearer ${KEY}`, "HTTP-Referer": "https://github.com/WallerChen/jev-measured", "X-Title": "jev-measured" },
        body: JSON.stringify({
          model,
          temperature: 0,
          max_tokens: EFFORT ? 4000 : 40,
          reasoning: EFFORT ? { effort: EFFORT } : { enabled: false },
          usage: { include: true },
          messages: [
            { role: "system", content: "You are a text classifier. Reply with the label only." },
            { role: "user", content: prompt(t) },
          ],
        }),
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

for (const model of MODELS) {
  const mine = tasks.filter((t) => !done.has(`${model}|${t.set}|${t.i}`));
  let next = 0, n = 0, cost = 0;
  async function worker() {
    while (next < mine.length) {
      const t = mine[next++];
      const { status, ms, body, attempts } = await ask(model, t);
      const reply = body?.choices?.[0]?.message?.content ?? null;
      const answer = status === 200 ? parse(t, reply) : null;
      const u = body?.usage ?? {};
      cost += u.cost ?? 0;
      fs.appendFileSync(OUT, JSON.stringify({
        model, effort: EFFORT ?? "off", set: t.set, i: t.i, kind: t.kind, gold: t.gold, status, ms, attempts,
        error: status === 200 ? null : body?.error?.message ?? null,
        reply: reply?.slice(0, 80) ?? null, answer, correct: answer !== null && answer === t.gold,
        in_tok: u.prompt_tokens ?? null, out_tok: u.completion_tokens ?? null, reasoning_tok: u.completion_tokens_details?.reasoning_tokens ?? null,
        cost: u.cost ?? null, served: body?.model ?? null,
      }) + "\n");
      if (++n % 50 === 0) console.log(`  ${model} ${n}/${mine.length} $${cost.toFixed(4)}`);
    }
  }
  // Free tiers are rate-limited upstream: one request at a time.
  await Promise.all(Array.from({ length: model.endsWith(":free") ? 1 : 4 }, worker));
  console.log(`${model}: ${n} calls, $${cost.toFixed(4)}`);
}
