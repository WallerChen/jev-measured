import fs from "node:fs";
import { parquetReadObjects } from "hyparquet";
import { compressors } from "hyparquet-compressors";
function rng(seed) { return () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 2 ** 32); }
const SETS = {
  agnews: { type: "choice", n: 100, instructions: "What is this news article about?" },
  emotiondair: { type: "choice", n: 100, instructions: "Which emotion does this tweet express?" },
  massive: { type: "choice", n: 100, instructions: "What does the user want the voice assistant to do?" },
  banking77: { type: "choice", n: 100, instructions: "What is this bank customer asking about?" },
  wikitoxic_toxicaggregated: { type: "noul", n: 100, instructions: "This Wikipedia talk-page comment contains toxic language: insults, threats, obscenity or hate.", yes: "toxicaggregated" },
  amazonpolarity: { type: "noul", n: 100, instructions: "This product review is positive overall.", yes: "positive" },
};
const out = {};
for (const [c, cfg] of Object.entries(SETS)) {
  const buf = fs.readFileSync(`./${c}.parquet`);
  const rows = await parquetReadObjects({ file: buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength), compressors, columns: ["text", "labels", "label_text"] });
  const labels = [...new Set(rows.map((r) => r.label_text))].sort();
  const seen = new Set(), items = [];
  for (const r of rows) if (r.labels === 1n && !seen.has(r.text)) { seen.add(r.text); items.push({ text: r.text, label: r.label_text }); }
  const rand = rng(20261008);
  for (let i = items.length - 1; i > 0; i--) { const k = Math.floor(rand() * (i + 1)); [items[i], items[k]] = [items[k], items[i]]; }
  const sample = items.filter((x) => x.text.length <= 1500).slice(0, cfg.n);
  out[c] = { ...cfg, labels, pool: items.length, items: sample };
  const dist = {}; for (const s of sample) dist[s.label] = (dist[s.label] || 0) + 1;
  console.log(c, "pool", items.length, "labels", labels.length, cfg.type === "noul" ? JSON.stringify(dist) : `classes in sample ${Object.keys(dist).length}`, "avg chars", Math.round(sample.reduce((a, s) => a + s.text.length, 0) / sample.length));
}
fs.writeFileSync("btzsc-sample.json", JSON.stringify(out, null, 1));
