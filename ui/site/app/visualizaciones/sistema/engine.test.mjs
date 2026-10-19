// node --test ui/site/app/visualizaciones/sistema/engine.test.mjs — the same engine the page runs.
import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { DEFAULT_LEVERS, HOUSING_KEYS, LAYERS, applyLayer, centralParams, decodeState, encodeState, quintileImpact, runEnsemble, simulate } from "./engine.mjs";
import { computeBacktests } from "./backtests.mjs";

const here = fileURLToPath(new URL(".", import.meta.url));
// SISTEMA_JSON: a development export (scripts/export_public_viz_system.py --out); the default is the published file.
const model = JSON.parse(fs.readFileSync(process.env.SISTEMA_JSON || `${here}../../../public/visualizaciones/data/sistema.json`, "utf8"));
const END = model.years.length - 1;
const DEVS = ["debt_dev_pp", "pension_gross_pp", "employment_k", "p1_month", "p4_month", "gdp_dev", "price_level_dev", ...HOUSING_KEYS];

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
  const levers = { ...DEFAULT_LEVERS, reval: -0.5, closure: "iva", migration: "low", ltiCap: 4.5, capCov: 50, capCut: 10 };
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

// ---- Housing (slice 2)
const T35 = model.years.indexOf(2035);

test("housing stock identity: extra dwellings are the sum of completions plus tourist conversions", () => {
  const run = simulate(model, { ...DEFAULT_LEVERS, pubHomes: 20, land: 10, tourCut: 30, ltvCap: 80 });
  let cum = 0;
  for (let t = 1; t < model.years.length; t += 1) {
    cum += run.hs_completions_k[t];
    assert.ok(Math.abs(cum + run.hs_tourist_k[t] - run.hs_stock_k[t]) < 1e-9, String(model.years[t]));
  }
});

test("building lowers rents, emancipates young adults (B2) and the cost reaches debt or taxes", () => {
  const run = simulate(model, { ...DEFAULT_LEVERS, pubHomes: 20 });
  assert.ok(run.hs_stock_k[T35] > 0 && run.hs_rent[T35] < 0 && run.hs_emancipated_k[T35] > 0);
  assert.ok(run.hs_cost_pp[T35] > 0 && run.debt_dev_pp[T35] > 0);
  const iva = simulate(model, { ...DEFAULT_LEVERS, pubHomes: 20, closure: "iva" });
  assert.ok(iva.p1_month[T35] < 0, "paying with VAT costs case 1");
  // Without emancipation the same dwellings lower rents more: B2 absorbs part of what is built.
  const p = { ...centralParams(model), elasticidad_emancipacion: 0 };
  const noB2 = simulate(model, { ...DEFAULT_LEVERS, pubHomes: 20 }, p);
  assert.ok(noB2.hs_rent[T35] < run.hs_rent[T35]);
});

test("rent cap: covered contracts pay the cut in the accounting layer; behaviour adds supply exit and spillover", () => {
  const lv = { ...DEFAULT_LEVERS, capCov: 50, capCut: 10 };
  const acc = simulate(model, lv, applyLayer(model, centralParams(model), "contable"));
  assert.ok(Math.abs(acc.hs_rent_cov[T35] + 0.1) < 1e-12);
  assert.ok(acc.hs_rental_stock_k[T35] === 0 && acc.hs_rent_unc[T35] === 0);
  const full = simulate(model, lv);
  assert.ok(full.hs_rent_cov[T35] < 0 && full.hs_rent_unc[T35] >= 0 && full.hs_rental_stock_k[T35] <= 0);
  // Every school of the contested supply response keeps covered rents down.
  const d = model.params.respuesta_oferta_tope.debate;
  d.schools.forEach((_, i) => assert.ok(simulate(model, lv, centralParams(model, { [d.id]: i })).hs_rent_cov[T35] < 0));
});

test("mortgage caps cut credit and prices; the credit-price loop (R2) amplifies the fall", () => {
  const lv = { ...DEFAULT_LEVERS, ltvCap: 80, ltiCap: 4.5 };
  const run = simulate(model, lv);
  assert.ok(run.hs_credit[T35] < 0 && run.hs_price[T35] < 0 && run.hs_binding[T35] > 0);
  const noLoop = simulate(model, lv, { ...centralParams(model), elasticidad_credito_precio: 0 });
  assert.ok(run.hs_price[T35] < noLoop.hs_price[T35]);
  assert.ok(run.p2b_upfront_eur[T35] > 0, "a 4.5 LTI cap binds for case 2's purchase");
});

test("housing converges for every parameter draw (no explosive credit loop)", () => {
  const e = runEnsemble(model, { ...DEFAULT_LEVERS, ltvCap: 70, ltiCap: 4.5, pubHomes: 60, capCov: 100, capCut: 20, tourCut: 100, migration: "high" });
  for (const run of e.runs) {
    for (const key of ["hs_price", "hs_rent", "hs_rent_unc", "hs_credit"]) assert.ok(run[key].every((v) => Number.isFinite(v) && Math.abs(v) < 1), key);
  }
});

test("more immigration means more households and higher rents", () => {
  const run = simulate(model, { ...DEFAULT_LEVERS, migration: "high" });
  assert.ok(run.hs_migration_hh_k[T35] > 0 && run.hs_rent[T35] > 0);
});

test("illustrative extremes stay finite and a tax cut never returns more than a case pays", () => {
  const t = model.years.indexOf(2035);
  const extremes = [
    { irpfAll: -35 }, { irpfAll: -35, closure: "iva" }, { vatStd: -21 }, { vatRed: 11 }, { reval: 10 }, { reval: -10 },
    { contrib: -41 }, { corp: -25 }, { age: 10 }, { pubHomes: 500, closure: "irpf" }, { capCut: 50, capCov: 100 },
  ];
  for (const lv of extremes) {
    const run = simulate(model, { ...DEFAULT_LEVERS, ...lv });
    for (const [key, values] of Object.entries(run)) {
      if (Array.isArray(values)) assert.ok(values.every((v) => typeof v !== "number" || Number.isFinite(v)), `${JSON.stringify(lv)} ${key}`);
    }
  }
  const noIrpf = simulate(model, { ...DEFAULT_LEVERS, irpfAll: -35 });
  for (const id of ["p1", "p2", "p4", "p5"]) {
    assert.ok(noIrpf[`${id}_month`][t] * 12 <= model.personas[id].irpf_paid + 1, id);
  }
});
