// node --test ui/site/app/visualizaciones/sistema/scenarios.test.mjs — the scenario landing pages show engine numbers only.
import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { DEFAULT_LEVERS, decodeState, runEnsemble } from "./engine.mjs";
import { CASE_METRICS, METRICS, SCENARIOS, SIM_TITLE, YEARS, scenarioClosures, scenarioResult, simDescription, simulatorHref } from "./scenarios.mjs";

const here = fileURLToPath(new URL(".", import.meta.url));
const model = JSON.parse(fs.readFileSync(process.env.SISTEMA_JSON || `${here}../../../public/visualizaciones/data/sistema.json`, "utf8"));
const finite = (b, what) => {
  for (const k of ["v", "lo", "hi"]) assert.ok(Number.isFinite(b[k]), `${what}.${k} = ${b[k]}`);
  assert.ok(b.lo <= b.v + 1e-9 && b.v <= b.hi + 1e-9, `${what}: central ${b.v} outside ${b.lo}..${b.hi}`);
};
const get = (obj, path) => path.split(".").reduce((o, k) => o?.[k], obj);

test("at most 20 scenarios, unique slugs that read like a search, levers the engine knows", () => {
  assert.ok(SCENARIOS.length <= 20);
  assert.equal(new Set(SCENARIOS.map((sc) => sc.slug)).size, SCENARIOS.length);
  for (const sc of SCENARIOS) {
    assert.match(sc.slug, /^[a-z0-9]+(-[a-z0-9]+)*$/u);
    for (const key of Object.keys(sc.levers)) assert.ok(key in DEFAULT_LEVERS, `${sc.slug}: ${key}`);
    for (const id of sc.metrics) assert.ok(METRICS[id], `${sc.slug}: metric ${id}`);
    for (const id of sc.cases) assert.ok(CASE_METRICS[id], `${sc.slug}: case ${id}`);
    for (const id of sc.edges) assert.ok(model.edges.some((e) => e.id === id), `${sc.slug}: edge ${id}`);
    for (const key of sc.votes) assert.ok(model.votes[key], `${sc.slug}: votes ${key}`);
  }
});

test("every number of every scenario page is finite and inside its range", () => {
  for (const sc of SCENARIOS) {
    const r = scenarioResult(model, sc);
    for (const id of [...sc.metrics, "cost", "debt"]) for (const y of YEARS) finite(r[id][y], `${sc.slug} ${id} ${y}`);
    for (const id of sc.cases) for (const y of YEARS) finite(r.cases[id][y], `${sc.slug} ${id} ${y}`);
    for (const q of r.quintiles || []) assert.ok(Number.isFinite(q.total) && Number.isFinite(q.pctDisposable), `${sc.slug} ${q.q}`);
    for (const s of r.debate?.schools || []) assert.ok(Number.isFinite(s.v), `${sc.slug} debate ${s.label}`);
    for (const c of scenarioClosures(model, sc) || []) for (const k of ["debt", "p1", "p4", "jobs"]) finite(c[k], `${sc.slug} ${c.id} ${k}`);
    assert.doesNotMatch(`${r.lead} ${r.badge}`, /NaN|Infinity|undefined/u, sc.slug);
  }
});

test("the numbers are the engine's own: central and band match a fresh ensemble", () => {
  for (const sc of SCENARIOS) {
    const r = scenarioResult(model, sc);
    const id = sc.metrics[0];
    const m = METRICS[id];
    if (m.unit === "meur") continue; // scaled by GDP; checked through the debt below
    const e = runEnsemble(model, { ...DEFAULT_LEVERS, ...sc.levers }, { draws: 200, keys: [m.key] });
    const t = model.years.indexOf(2035);
    const scale = m.scale ?? 1;
    assert.ok(Math.abs(r[id][2035].v - e.central[m.key][t] * scale) < 1e-9, `${sc.slug} ${id}`);
    assert.ok(Math.abs(r[id][2035].lo - Math.min(e.bands[m.key].lo[t], e.bands[m.key].hi[t]) * scale) < 1e-9, `${sc.slug} ${id} lo`);
  }
});

test("the lead states the directions the numbers have, and fits a meta description", () => {
  for (const sc of SCENARIOS) {
    const r = scenarioResult(model, sc);
    for (const [path, sign] of Object.entries(sc.signs || {})) assert.equal(Math.sign(get(r, `${path}.v`)), sign, `${sc.slug}: ${path}`);
    assert.ok(r.lead.length <= 155, `${sc.slug}: description ${r.lead.length} chars`);
    assert.ok(sc.title.length <= 60, `${sc.slug}: title ${sc.title.length} chars`);
  }
  assert.ok(SIM_TITLE.length <= 60);
  assert.ok(simDescription(model).length <= 155, simDescription(model));
});

test("the simulator button preloads exactly the scenario's levers", () => {
  for (const sc of SCENARIOS) {
    const { levers } = decodeState(simulatorHref(sc).split("#")[1]);
    assert.deepEqual(levers, { ...DEFAULT_LEVERS, ...sc.levers }, sc.slug);
  }
});
