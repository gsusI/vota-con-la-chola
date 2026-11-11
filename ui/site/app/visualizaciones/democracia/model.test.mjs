// node --test ui/site/app/visualizaciones/democracia/model.test.mjs
// Every figure the page states comes from the published JSON, is finite, and the copy stays within length and wording rules.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { democracyModel, democracySeo } from "./model.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const data = JSON.parse(readFileSync(join(here, "../../../public/visualizaciones/data/democracia.json"), "utf8"));
const page = readFileSync(join(here, "page.js"), "utf8");

test("only reviewed safeguards are published, all classified", () => {
  const m = democracyModel(data);
  assert.equal(m.n, data.safeguards.length, "unclassified safeguard published");
  assert.equal(m.byClass.buena_voluntad.length + m.byClass.tercero_tarde.length + m.byClass.tercero_a_tiempo.length, m.n);
  for (const p of data.pending || []) assert.ok(!data.safeguards.some((s) => s.id === p.id), `${p.id} both published and pending`);
});

test("stated figures are finite numbers", () => {
  const m = democracyModel(data);
  for (const [name, value] of Object.entries({
    rdl: m.current.rdl_per_month,
    maxEarlier: m.maxEarlierRate,
    libdem: m.libdem.ESP,
    hun: m.libdem.HUN,
    peak: m.esPeak.value,
    prorrogued: m.prorrogued.length,
    longest: m.longest?.days_expired,
    medianDelay: m.medianDelay,
  })) {
    assert.ok(Number.isFinite(value), `${name} = ${value}`);
  }
  for (const row of m.partyRows) assert.ok(Number.isFinite(row.per10) && row.years > 0, row.party);
});

test("SEO copy fits and has no unresolved values", () => {
  const seo = democracySeo(data);
  assert.ok(seo.title.length <= 95, seo.title);
  assert.ok(seo.description.length <= 160, `${seo.description.length}: ${seo.description}`);
  for (const text of [seo.title, seo.description]) assert.doesNotMatch(text, /undefined|NaN|null/);
});

test("no causal verbs or motives in the page copy", () => {
  for (const banned of ["gracias a", "por culpa de", "para evitar que", "con el fin de bloquear", "para ocultar"]) {
    assert.ok(!page.toLowerCase().includes(banned), banned);
  }
  for (const sg of data.safeguards) {
    for (const ep of sg.episodes) {
      for (const banned of ["para evitar", "con el objetivo de", "pretendía", "buscaba"]) {
        assert.ok(!ep.summary.toLowerCase().includes(banned), `${sg.id}/${ep.id}: «${banned}»`);
      }
    }
  }
});
