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

  // 4a. Immigration and age-related spending (tolerance fixed 2026-11-11, README §14.2): with the official high variant and
  // services that grow with demand, the change of health + long-term care + education spending in % of GDP against the
  // Ageing Report's (total cost of ageing minus pensions). Pensions are reported beside it, without a tolerance.
  const Lb = model.labour;
  const t2050 = model.years.length - 1;
  if (Lb) {
    const hi = simulate(model, { ...DEFAULT_LEVERS, migScale: 1 });
    const denom = 1 + hi.gdp_dev[t2050] / 100;
    const baseSvc = Lb.health.spend_pct[t2050] + Lb.health.ltc_pct[t2050] + Lb.education.spend_pct[t2050];
    const ours = (baseSvc + hi.mig_health_pp[t2050] + hi.mig_ltc_pp[t2050] + hi.mig_edu_pp[t2050]) / denom - baseSvc;
    const ar = Lb.age_related_mig_pp.hi[t2050] - model.baseline.migration_high_pp[t2050];
    const ratio = ours / ar;
    const pens = (model.baseline.pension_pct[t2050] + hi.mig_pension_pp[t2050]) / denom - model.baseline.pension_pct[t2050];
    out.push({
      id: "migracion_gasto_edad",
      ok: Math.sign(ours) === Math.sign(ar) && ratio >= 1 / 3 && ratio <= 3,
      tolerance: "mismo signo y dentro de ×3",
      label: "Inmigración y gasto ligado a la edad.",
      text: `Con la variante alta oficial y los servicios creciendo con la población, sanidad, dependencia y educación pasan a pesar ${n(ours, 2)} puntos de PIB en 2050 (más gente que atender, pero más PIB); el Ageing Report da ${n(ar, 2)} (su coste total del envejecimiento menos pensiones). En pensiones, el modelo da ${n(pens, 2)} puntos y el Ageing Report ${n(model.baseline.migration_high_pp[t2050], 2)}: el modelo cuenta solo a quien llega con 65 o más años antes de 2050 y deja fuera las pensiones que generan sus cotizaciones después.`,
    });

    // 4b. Health demand from age alone against the Ageing Report demographic scenario (gate of the exporter, ±5 points).
    const mix = Lb.health.mix_growth_2050 * 100;
    const arDemo = Lb.health.ar_demo_growth_2050 * 100;
    out.push({
      id: "sanidad_demografia",
      ok: Math.abs(mix - arDemo) <= 5,
      tolerance: "±5 puntos",
      label: "Envejecimiento y gasto sanitario.",
      text: `Con el perfil de gasto por edad de Funcas y la población de EUROPOP2023, el gasto sanitario en % del PIB crece un ${n(mix)} % de 2025 a 2050 solo por la edad; el escenario demográfico del Ageing Report da un ${n(arDemo)} %.`,
    });

    // 4c. Immigration and jobs 2019-2025: new employed foreign citizens per new foreign resident aged 15-64 (LFS) against
    // the employment rate the model gives a new resident of working age (±10 points).
    const bt = Lb.backtest_foreign;
    const prof = Lb.mig_profile;
    const work = ["16_29", "30_44", "45_64"];
    const P = centralParams(model);
    const rate = (work.reduce((a, s) => a + prof[s] * Lb.emp_rate.FOR[s], 0) / work.reduce((a, s) => a + prof[s], 0)) * P.ajuste_empleo_inmigrante;
    out.push({
      id: "inmigracion_empleo",
      ok: Math.abs(rate - bt.observed_rate) * 100 <= 10,
      tolerance: "±10 puntos",
      label: `Inmigración y empleo, ${bt.from}–${bt.to}.`,
      text: `Según la EPA, los extranjeros de 15 a 64 años pasaron de ${n(bt.for_pop_k[0] / 1000, 2)} a ${n(bt.for_pop_k[1] / 1000, 2)} millones y sus ocupados de ${n(bt.for_emp_k[0] / 1000, 2)} a ${n(bt.for_emp_k[1] / 1000, 2)} millones: ${n(bt.observed_rate * 100, 0)} ocupados nuevos por cada 100 residentes nuevos. El modelo pone a trabajar a ${n(rate * 100, 0)} de cada 100 residentes nuevos de 16 a 64 años. Las nacionalizaciones sacan del grupo a extranjeros ya empleados, así que la comparación es aproximada.`,
    });
  }

  // 4d. SMI +22.3 % in 2019 (tolerance fixed 2026-11-11): jobs lost in the model, long run, with the 2019 affected workers,
  // against the published range (same sign, within [min/2, max×2]).
  const smi = bm.B08_smi_2019;
  if (smi) {
    const P = centralParams(model);
    const affected = smi.extra.find((x) => x.name === "afectados_smi_2019")?.central;
    if (affected) {
      const lost = -P.elasticidad_empleo_smi * 22.3 * affected / 100;
      const lo = Math.min(smi.low, smi.high);
      const hiV = Math.max(smi.low, smi.high);
      out.push({
        id: "smi_2019",
        ok: lost >= Math.max(0, lo / 2) && lost <= hiV * 2,
        tolerance: "dentro de la mitad del mínimo y el doble del máximo publicados",
        label: "Subida del SMI del 22,3 % en 2019.",
        text: `Con ${n(affected / 1000, 1)} millones de trabajadores afectados y la elasticidad central (${n(P.elasticidad_empleo_smi, 2)}), el modelo da unos ${n(lost, 0)} mil empleos menos a largo plazo; las estimaciones publicadas van de ${n(lo, 0)} mil a ${n(hiV, 0)} mil (mediana ${n(smi.value, 0)} mil).`,
      });
    }
  }
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
  // Housing (slice 2). Tolerances fixed on 2026-10-19 before the cards were filled (README §13).
  const P = centralParams(model);
  const pct = (v, d = 1) => `${v >= 0 ? "+" : "−"}${n(Math.abs(v), d)} %`;

  // 7. Catalan rent cap of 2020 (Ley 11/2020): the cap arithmetic with the compliance card against the measured effect.
  const cat = bm.B05_catalonia_2020;
  if (cat) {
    const x = Object.fromEntries((cat.extra || []).map((e) => [e.name, e.central]));
    const mandated = (x.cuota_sobre_indice_2020 ?? 0) * (x.brecha_sobre_indice_2020 ?? 0); // % of the average covered rent
    const model_ = -P.cumplimiento_tope * mandated;
    const measured = cat.value;
    const supply = (model.params.respuesta_oferta_tope.debate?.schools || []).map((s) => `«${s.label}» ${pct(-s.central * -model_, 0)}`);
    out.push({
      id: "tope_cataluna_2020",
      ok: Math.sign(model_) === Math.sign(measured) && Math.abs(model_ - measured) <= 0.5 * Math.abs(measured),
      tolerance: "mismo signo y ±50 % del efecto medido",
      label: "Tope catalán del alquiler de 2020.",
      text: `Con un ${n((x.cuota_sobre_indice_2020 ?? 0) * 100, 0)} % de contratos por encima del índice y una brecha media del ${n(x.brecha_sobre_indice_2020 ?? 0, 0)} %, la ley exigía bajar de media un ${n(mandated)} % el alquiler cubierto; con el cumplimiento de la ficha (${n(P.cumplimiento_tope * 100, 0)} %), el modelo da ${pct(model_)}, frente al ${pct(measured)} medido. La oferta de alquiler cubierta cambiaría ${supply.join("; ")}, frente a ${pct(x.efecto_oferta_cataluna_2020 ?? 0, 0)} medido. ${cat.same_study ? "El cumplimiento sale en parte del mismo estudio: es una prueba de coherencia, no independiente." : ""}`,
    });
  }

  // 8. Housing boom 2000-2007: how much of the rise in price-to-wage the credit term explains, against the literature.
  const boomCard = bm.B06_boom_credit;
  const boom = model.housing?.boom;
  if (boomCard && boom) {
    const credit = Math.log(boom.credit_to / boom.credit_from);
    const price = Math.log(boom.years_income_to / boom.years_income_from);
    const share = (P.elasticidad_precio_credito * credit) / price;
    const extraHomes = boom.completed - boom.net_households;
    const stockOnly = -P.respuesta_alquiler_parque * (extraHomes / 1000 / model.housing.households_k[0]);
    out.push({
      id: "boom_credito",
      ok: share >= boomCard.low - 0.15 && share <= boomCard.high + 0.15,
      tolerance: "dentro del rango publicado ±15 puntos",
      label: `Burbuja de ${boom.from}–${boom.to}.`,
      text: `El crédito a la vivienda pasó del ${n(boom.credit_from)} % al ${n(boom.credit_to)} % del PIB y el precio de ${n(boom.years_income_from, 2)} a ${n(boom.years_income_to, 2)} años de salario. Con su elasticidad, el término de crédito del modelo da cuenta de un ${n(share * 100, 0)} % de esa subida; los estudios atribuyen al crédito y a la financiación entre un ${n(boomCard.low * 100, 0)} % y un ${n(boomCard.high * 100, 0)} %. El canal de parque por hogar apunta al revés: se terminaron ${n(extraHomes / 1e6, 2)} millones de viviendas más que hogares nuevos, lo que en el modelo bajaría el alquiler un ${n(Math.abs(stockOnly) * 100, 0)} %. No fue escasez: el modelo no explica la burbuja sin crédito, tipos y expectativas.`,
    });
  }

  // 9. Tourist rentals: the model's chain (conversion × inverse demand) against the Barcelona quasi-experiment.
  const tour = bm.B07_tourist_rents;
  if (tour) {
    const model_ = P.conversion_turistica * P.respuesta_alquiler_parque; // % rent per 1 pp of the stock in tourist use
    const ratio = model_ / tour.value;
    out.push({
      id: "turistico_barcelona",
      ok: ratio >= 1 / 3 && ratio <= 3,
      tolerance: "entre un tercio y el triple",
      label: "Viviendas turísticas y alquiler.",
      text: `En el modelo, que un punto del parque deje de ser turístico baja el alquiler un ${n(model_, 2)} % (conversión × respuesta del alquiler al parque); el estudio cuasi-experimental de Barcelona da ${n(tour.value, 2)} % por punto. ${ratio > 1 ? "El modelo da más" : "El modelo da menos"} (${n(ratio, 1)} veces): el efecto local de un barrio no es el de todo un mercado.`,
    });
  }
  return out;
}
