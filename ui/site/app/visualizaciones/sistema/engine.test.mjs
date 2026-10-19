// node --test ui/site/app/visualizaciones/sistema/engine.test.mjs — the same engine the page runs.
import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { DEFAULT_LEVERS, LAYERS, applyLayer, centralParams, decodeState, encodeState, quintileImpact, runEnsemble, simulate } from "./engine.mjs";
import { computeBacktests } from "./backtests.mjs";

const here = fileURLToPath(new URL(".", import.meta.url));
const model = JSON.parse(fs.readFileSync(`${here}../../../public/visualizaciones/data/sistema.json`, "utf8"));
const END = model.years.length - 1;
const DEVS = ["debt_dev_pp", "pension_gross_pp", "employment_k", "p1_month", "p4_month", "gdp_dev", "price_level_dev"];

test("current law: every deviation is zero and the baseline is returned unchanged", () => {
  const run = simulate(model, DEFAULT_LEVERS);
  for (const key of DEVS) assert.ok(run[key].every((v) => v === 0), key);
  assert.deepEqual(run.debt_pct, model.baseline.debt_pct);
});

test("debt identity: extra debt accumulates primary deficits and interest", () => {
  const run = simulate(model, { ...DEFAULT_LEVERS, reval: 1 });
  let D = 0;
  for (let t = 1; t < model.years.length; t += 1) {
    const g = model.baseline.nominal_growth[t] / 100;
    D = D / (1 + g) + run.primary_dev_pp[t] + run.interest_dev_pp[t];
    assert.ok(Math.abs(D - run.debt_dev_pp[t]) < 1e-9, String(model.years[t]));
  }
});

test("tax closures pay the cost before second-round effects; only those reach the deficit", () => {
  for (const closure of ["cotizaciones", "iva", "irpf"]) {
    const run = simulate(model, { ...DEFAULT_LEVERS, reval: 1, closure });
    run.primary_dev_pp.forEach((v, t) => assert.ok(Math.abs(v + run.cycle_revenue_pp[t]) < 1e-6, `${closure} ${model.years[t]}`));
  }
});

test("closures converge for every parameter draw", () => {
  for (const closure of ["cotizaciones", "iva", "irpf"]) {
    const e = runEnsemble(model, { ...DEFAULT_LEVERS, reval: 2, closure });
    for (const run of e.runs) {
      const rate = { iva: run.closure_vat_pp, irpf: run.closure_irpf_pp, cotizaciones: run.closure_contrib_pp }[closure];
      assert.ok(rate.every((v) => Number.isFinite(v) && Math.abs(v) < 40), closure);
    }
  }
});

test("signs: more revaluation costs more and helps the pensioner; a later retirement saves and adds jobs", () => {
  const up = simulate(model, { ...DEFAULT_LEVERS, reval: 1 });
  assert.ok(up.debt_dev_pp[END] > 0 && up.p4_month[END] > 0);
  const contrib = simulate(model, { ...DEFAULT_LEVERS, reval: 1, closure: "cotizaciones" });
  assert.ok(contrib.p1_month[END] < 0 && contrib.employment_k[END] < 0);
  const age = simulate(model, { ...DEFAULT_LEVERS, age: 1 });
  assert.ok(age.debt_dev_pp[END] < 0 && age.employment_k[END] > 0);
});

test("accounting layer switches off behaviour: no job losses from contributions", () => {
  const p = applyLayer(model, centralParams(model), "contable");
  const run = simulate(model, { ...DEFAULT_LEVERS, contrib: 1 }, p);
  assert.ok(run.employment_k.every((v) => v === 0));
  assert.deepEqual(LAYERS, ["contable", "comportamiento", "segunda_ronda"]);
});

test("ensemble is deterministic and fast enough for the browser", () => {
  const t0 = performance.now();
  const a = runEnsemble(model, { ...DEFAULT_LEVERS, reval: 1, closure: "iva" });
  const ms = performance.now() - t0;
  const b = runEnsemble(model, { ...DEFAULT_LEVERS, reval: 1, closure: "iva" });
  assert.deepEqual(a.bands.p1_month.lo, b.bands.p1_month.lo);
  assert.ok(ms < 400, `${ms} ms`);
  assert.ok(a.bands.debt_pct.lo[END] <= a.central.debt_pct[END] + 1e-9);
});

test("URL fragment round-trip", () => {
  const levers = { ...DEFAULT_LEVERS, reval: -0.5, closure: "iva", migration: "low" };
  const hash = encodeState(levers, { incidencia: 1 }, { h: 2050 });
  const back = decodeState(`#${hash}`);
  assert.deepEqual(back.levers, levers);
  assert.equal(back.debates.incidencia, 1);
  assert.equal(back.extra.h, "2050");
});

test("backtests stay within their tolerances", () => {
  const results = computeBacktests(model);
  assert.ok(results.length >= 4);
  for (const r of results) assert.ok(r.ok, `${r.id}: ${r.text}`);
});

test("tax levers: zero is zero, raising a tax raises revenue (all but the contested top bracket) and costs the cases", () => {
  const t = model.years.indexOf(model.policy_start);
  for (const key of ["irpfAll", "vatStd", "vatRed", "corp"]) {
    const run = simulate(model, { ...DEFAULT_LEVERS, [key]: 1 });
    const rev = run.irpf_revenue_pp[t] + run.vat_revenue_pp[t] + run.vat_red_revenue_pp[t] + run.corp_revenue_pp[t];
    assert.ok(rev > 0, key);
    assert.ok(run.p1_month[t] < 0, key);
  }
  const top = simulate(model, { ...DEFAULT_LEVERS, irpfTop: 5 });
  for (const id of ["p1", "p2", "p4", "p5"]) assert.equal(top[`${id}_month`][t], 0, id);
});

test("quintile split distributes exactly the statutory burden", () => {
  const t = model.years.indexOf(2030);
  const run = simulate(model, { ...DEFAULT_LEVERS, irpfAll: 1, vatStd: 1, corp: 2, reval: 1 });
  const p = centralParams(model);
  const q = quintileImpact(model, run, t, p);
  const gdpEur = model.start.gdp_meur * 1e6 * model.baseline.real_index[t];
  const irpf = q.reduce((a, r, i) => a + r.byPart.irpf * model.incidence.ecv.quintiles[i].households * 12, 0);
  const expected = -((run.s_irpf_all_pp[t] + run.s_irpf_top_pp[t]) / 100) * gdpEur;
  assert.ok(Math.abs(irpf / expected - 1) < 1e-9);
  assert.ok(q[0].byPart.pensiones > 0 && q[4].byPart.irpf < q[0].byPart.irpf);
});
