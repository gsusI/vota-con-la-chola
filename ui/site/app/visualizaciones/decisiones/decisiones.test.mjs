// node --test ui/site/app/visualizaciones/decisiones/decisiones.test.mjs
// Checks the published decisiones.json against the page's own helpers: vote counts add up, verdicts are backed by
// graded evidence, no causal wording, and the copy uses only numbers computed from the file.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CAUSAL_WORDS, count, headline, ledger, movedWith, pageDescription, pageTitle } from "./model.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(fs.readFileSync(path.resolve(here, "../../../public/visualizaciones/data/decisiones.json"), "utf8"));

test("party counts add up to the published totals of each vote", () => {
  for (const m of data.measures) {
    const sum = { S: 0, N: 0, A: 0 };
    for (const r of Object.values(m.parties)) for (const k of ["S", "N", "A"]) sum[k] += r[k];
    assert.deepEqual([sum.S, sum.N, sum.A], m.totals_published, m.measure_id);
  }
});

test("a verdict other than no_evaluado rests on at least one A or B ex-post source", () => {
  for (const m of data.measures.filter((x) => ["positivo", "negativo", "mixto"].includes(x.verdict))) {
    const grades = [...(m.ex_post || []), ...(m.evidence_against || [])].map((s) => s.grade);
    assert.ok(grades.some((g) => g === "A" || g === "B"), m.measure_id);
  }
});

test("no causal wording in measure copy", () => {
  for (const m of data.measures) {
    for (const field of ["what_changes", "stated_goal", "verdict_reason"]) {
      assert.ok(!CAUSAL_WORDS.test(m[field] || ""), `${m.measure_id}.${field}`);
    }
  }
  for (const m of data.measures) for (const mv of m.indicator_moves || []) assert.ok(!CAUSAL_WORDS.test(movedWith(mv)));
});

test("ledger counts match the measure list", () => {
  const rows = ledger(data);
  for (const row of rows) {
    for (const d of data.domains) {
      const cell = row.domains[d.id];
      const expected = data.measures.filter((m) => m.domains.includes(d.id) && ["backed", "opposed", "abstained"].includes(m.parties[row.party]?.stance)).length;
      assert.equal(count(cell, "backed") + count(cell, "opposed") + count(cell, "abstained"), expected, `${row.party}/${d.id}`);
    }
  }
});

test("title and description carry computed numbers and fit search limits", () => {
  const h = headline(data);
  assert.ok(pageTitle(h).includes(String(h.measures)));
  assert.ok(pageDescription(h).length <= 200, pageDescription(h));
  assert.equal(h.measures, data.measures.length);
});

test("counterfactuals never took effect and carry no ex-post without a later route", () => {
  for (const m of data.measures.filter((x) => x.unit === "contrafactual")) {
    assert.equal(m.took_effect, false, m.measure_id);
    if (m.ex_post?.length) assert.ok(m.later_route || m.ex_post.every((s) => s.grade !== "A"), m.measure_id);
  }
});
