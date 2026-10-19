// Checks of the model against real episodes and official projections. The page lists them and engine.test.mjs
// fails the build when one leaves its tolerance (tolerances fixed here, before looking at the results).
import { DEFAULT_LEVERS, centralParams, quintileImpact, realChange, revaluationCost, simulate } from "./engine.mjs";

const n = (v, d = 1) => Number(v).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });

export function computeBacktests(model) {
  const out = [];
  const bi = model.backtest_inputs;
  const bm = model.benchmarks;

  // 1. Revaluation of 2023 (8.5 %): accounting cost on the spending base of 2022.
  if (bm.B01_revaluation_2023_cost) {
    const base = (bi.pension_pct_ar_2022 / 100) * bi.gdp_2022_meur;
    const cost = revaluationCost(0.085, base);
    const official = bm.B01_revaluation_2023_cost.value;
    const gap = cost / official - 1;
    out.push({
      id: "revalorizacion_2023",
      ok: Math.abs(gap) <= 0.15,
      tolerance: "±15 %",
      label: "Revalorización del 8,5 % en 2023.",
      text: `Con el gasto de 2022 del Ageing Report (${n(bi.pension_pct_ar_2022, 2)} % del PIB), el modelo da ${n(cost / 1000)} mil millones el primer año; el Gobierno estimó ${n(official / 1000)} mil millones para las pensiones de la Seguridad Social (${gap >= 0 ? "+" : "−"}${n(Math.abs(gap) * 100, 0)} %). Parte de la diferencia es de alcance: el Ageing Report incluye también las clases pasivas.`,
    });
  }

  // 2. IRP floor (0.25 % a year) in 2014-2017 against prices: real change of an existing pension.
  if (bm.B02_irp_savings) {
    const years = ["2014", "2015", "2016", "2017"];
    const real = realChange(years.map(() => 0.0025), years.map((y) => bi.hicp_rates[y] / 100)) * 100;
    const official = bm.B02_irp_savings.value;
    out.push({
      id: "irp_2014_2017",
      ok: Math.abs(real - official) <= 0.5,
      tolerance: "±0,5 puntos",
      label: "Índice de revalorización (0,25 % al año) en 2014–2017.",
      text: `La aritmética del modelo, con el IPCA de Eurostat, da un cambio real acumulado de ${real >= 0 ? "+" : "−"}${n(Math.abs(real), 2)} % para una pensión que ya existía; con el IPC del INE sale ${official >= 0 ? "+" : "−"}${n(Math.abs(official), 2)} %. Con precios casi planos el suelo del 0,25 % apenas recortó el poder de compra; el recorte dependía de la inflación: en 2017, con el IPCA al ${n(bi.hicp_rates["2017"])} %, esa pensión perdió ${n(bi.hicp_rates["2017"] - 0.25)} puntos en un año.`,
    });
  }

  // 3. No-policy-change debt: our technical baseline against the Commission's Debt Sustainability Monitor.
  if (bm.B03_dsm_spain) {
    const t = model.years.indexOf(2034);
    const ours = model.baseline.debt_pct[t];
    const official = bm.B03_dsm_spain.value;
    out.push({
      id: "deuda_2034",
      ok: Math.abs(ours - official) <= 10,
      tolerance: "±10 puntos",
      label: "Deuda en 2034 sin cambios de política.",
      text: `La línea base de esta página llega al ${n(ours)} % del PIB en 2034; el Debt Sustainability Monitor 2024 de la Comisión, con supuestos de saldo primario propios y todos los costes del envejecimiento, al ${n(official)} %.`,
    });
  }

  // 4. Migration: the context lever reproduces the official sensitivity it is built from.
  const t2050 = model.years.length - 1;
  const low = simulate(model, { ...DEFAULT_LEVERS, migration: "low" });
  const diff = low.pension_pct[t2050] - model.baseline.pension_pct[t2050];
  out.push({
    id: "migracion",
    ok: Math.abs(diff - model.baseline.migration_low_pp[t2050]) < 0.01,
    tolerance: "exacto",
    label: "Un tercio menos de inmigración.",
    text: `El gasto en pensiones sube ${n(diff, 2)} puntos de PIB en 2050 frente a la línea base: la sensibilidad oficial del Ageing Report (${n(model.baseline.migration_low_pp[t2050], 2)} puntos desde ${model.years[0]}).`,
  });
  // 5. IRPF concentration: the survey microsimulation against the tax returns.
  if (bm.B04_irpf_concentration && bi.ecv_top20_base_share != null) {
    const official = bm.B04_irpf_concentration.value;
    const ours = bi.ecv_top20_base_share;
    out.push({
      id: "concentracion_irpf",
      ok: Math.abs(ours - official) <= 10,
      tolerance: "±10 puntos",
      label: "Concentración de la base del IRPF.",
      text: `En la microsimulación con la Encuesta de Condiciones de Vida, el 20 % de contribuyentes con más base tiene el ${n(ours)} % de la base; en las declaraciones de la Agencia Tributaria, el ${n(official)} %. La encuesta recoge peor las rentas más altas, así que el reparto del modelo es algo menos progresivo que el real.`,
    });
  }

  // 6. VAT is regressive in both sources: our spending-based split against Eurostat's experimental VAT-by-quintile.
  if (bi.icw_vat_by_quintile) {
    const t = model.years.indexOf(model.policy_start);
    const q = quintileImpact(model, simulate(model, { ...DEFAULT_LEVERS, vatStd: 1 }), t, centralParams(model));
    const ours = q.map((r) => -r.pctDisposable);
    const icw = ["QU1", "QU3", "QU5"].map((k) => bi.icw_vat_by_quintile[k]);
    out.push({
      id: "iva_regresivo",
      ok: ours[0] > ours[2] && ours[2] > ours[4] && icw[0] > icw[1] && icw[1] > icw[2],
      tolerance: "mismo orden de quintiles",
      label: "El IVA pesa más en las rentas bajas.",
      text: `Un punto más de IVA general cuesta el ${n(ours[0], 2)} % de la renta disponible al quintil 1 y el ${n(ours[4], 2)} % al quintil 5 en el modelo (gasto de la Encuesta de Presupuestos Familiares); en la estadística experimental de Eurostat, el IVA pagado es el ${n(icw[0])} % de la renta bruta en el quintil 1 y el ${n(icw[2])} % en el 5.`,
    });
  }
  return out;
}
