// Scenario landing pages of /visualizaciones/sistema/escenarios/<slug>/: one question people search, one lever set,
// every number computed at build time by the same engine the simulator runs (scenarios.test.mjs keeps them finite).
// Plain module (no "use client"): the server pages, the share cards and node --test all import it.
import { CLOSURES, DEFAULT_LEVERS, centralParams, encodeState, quintileImpact, runEnsemble, simulate } from "./engine.mjs";

export const SIM_PATH = "/visualizaciones/sistema/";
export const SCENARIOS_PATH = "/visualizaciones/sistema/escenarios/";
export const DRAWS = 200; // same as the simulator, so the preloaded scenario shows the same range
export const CLOSURE_DRAWS = 160; // same as the «¿quién lo paga?» figure of the main page
export const YEARS = [2035, 2050];

// The levers of the simulator in plain words (featureList of the WebApplication and the lever list of the page).
export const LEVER_LIST = [
  "Revalorización de las pensiones sobre el IPC",
  "Edad efectiva de jubilación",
  "Cotizaciones sociales",
  "IRPF en todos los tramos",
  "IRPF por encima de 60.000 euros",
  "IVA general (21 %)",
  "IVA reducido (10 %)",
  "Impuesto sobre Sociedades",
  "Vivienda pública en alquiler",
  "Suelo liberado",
  "Tope del alquiler en zonas tensionadas",
  "Retirada de viviendas turísticas",
  "Límites a las hipotecas (precio y renta)",
  "Inmigración y tipos de interés como contexto",
  "Cómo se paga: deuda, cotizaciones, IVA o IRPF",
];

export const PERSONAS_ES = {
  p1: { name: "Lucía", who: "25–34 años, asalariada, vive sola de alquiler en Madrid", case: 1 },
  p2: { name: "Ana y Javi", who: "pareja de 30–44 años con dos hijos y dos sueldos", case: 2 },
  p4: { name: "Carmen", who: "jubilada de 65 años o más, vive sola, con la casa pagada", case: 4 },
  p5: { name: "Laura", who: "45–54 años, universitaria, profesional en Madrid", case: 5 },
};

export const CLOSURE_ES = {
  deuda: { pay: "Con deuda", use: "A reducir deuda" },
  cotizaciones: { pay: "Con cotizaciones", use: "A bajar cotizaciones" },
  iva: { pay: "Con IVA", use: "A bajar el IVA" },
  irpf: { pay: "Con IRPF", use: "A bajar el IRPF" },
};

// Outputs a page can show. scale turns the engine unit into the shown one; meur = % of GDP to millions of euros.
export const METRICS = {
  cost: { key: "net_cost_pp", unit: "meur", label: "Coste neto para las cuentas públicas, al año", good: -1 },
  debt: { key: "debt_dev_pp", unit: "pp", label: "Deuda pública extra (si se paga con deuda), puntos de PIB", good: -1 },
  pension: { key: "pension_gross_pp", unit: "pp", label: "Gasto en pensiones, puntos de PIB", digits: 2, good: 0 },
  migPension: { key: "migration_pp", unit: "pp", label: "Gasto en pensiones por la inmigración, puntos de PIB", digits: 2, good: 0 },
  jobs: { key: "employment_k", unit: "k", label: "Empleo, miles de personas", good: 1 },
  prices: { key: "price_level_dev", unit: "pct", scale: 100, label: "Nivel de precios", digits: 2, good: -1 },
  rent: { key: "hs_rent_unc", unit: "pct", scale: 100, label: "Alquiler de un contrato nuevo", good: -1 },
  rentCov: { key: "hs_rent_cov", unit: "pct", scale: 100, label: "Alquiler de un contrato nuevo con tope", good: -1 },
  rentUnc: { key: "hs_rent_unc", unit: "pct", scale: 100, label: "Alquiler de un contrato nuevo fuera del tope", good: -1 },
  price: { key: "hs_price", unit: "pct", scale: 100, label: "Precio de la vivienda", good: 0 },
  stock: { key: "hs_stock_k", unit: "k", label: "Viviendas, miles más que con la ley actual", good: 1 },
  rentalStock: { key: "hs_rental_stock_k", unit: "k", label: "Pisos de alquiler de mercado, miles", good: 1 },
  young: { key: "hs_emancipated_k", unit: "k", label: "Jóvenes que se emancipan, miles", good: 1 },
  migHouseholds: { key: "hs_migration_hh_k", unit: "k", label: "Hogares más por la inmigración, miles", good: 0 },
  hsCost: { key: "hs_cost_pp", unit: "meur", label: "Coste público neto de la vivienda, al año", good: -1 },
};

// Typical cases: euros a month (base-year prices) vs current law.
export const CASE_METRICS = {
  p1: { key: "p1_month", who: "p1", label: "renta disponible" },
  p2: { key: "p2_month", who: "p2", label: "renta disponible" },
  p4: { key: "p4_month", who: "p4", label: "pensión y precios" },
  p5: { key: "p5_month", who: "p5", label: "renta disponible" },
  p1Rent: { key: "p1_rent_unc_month", who: "p1", label: "alquiler de un piso nuevo", good: -1 },
  p1RentCov: { key: "p1_rent_cov_month", who: "p1", label: "alquiler de un piso nuevo con tope", good: -1 },
  p1RentUnc: { key: "p1_rent_unc_month", who: "p1", label: "alquiler de un piso nuevo fuera del tope", good: -1 },
  p2Rent: { key: "p2r_rent_unc_month", who: "p2", label: "alquiler de un piso nuevo", good: -1 },
  p2Pay: { key: "p2b_payment_month", who: "p2", label: "cuota de la hipoteca si compran", good: -1 },
  p2Up: { key: "p2b_upfront_eur", who: "p2", label: "ahorro que necesitan para comprar (euros, una vez)", good: -1, once: true },
};

const PENSION_EDGES = ["E01_pension_turnover", "E15_cpi_pension_rule", "E04_pension_irpf", "E06_transfer_multiplier", "E18_deficit_debt", "E16_debt_risk_premium"];
const FISCAL_CASES = ["p1", "p2", "p4", "p5"];

export const SCENARIOS = [
  {
    slug: "subir-pensiones-ipc-mas-1",
    signs: { "cost.2035": 1, "debt.2050": 1 }, // directions the lead states in words (scenarios.test.mjs)
    group: "Pensiones",
    short: "Pensiones: IPC + 1 punto",
    question: "¿Cuánto cuesta subir las pensiones un punto más que el IPC?",
    title: "Subir las pensiones IPC + 1: cuánto cuesta",
    keywords: ["revalorización pensiones", "pensiones IPC", "subir pensiones", "coste pensiones", "deuda pensiones"],
    levers: { reval: 1 },
    metrics: ["cost", "debt", "pension"],
    cases: FISCAL_CASES,
    edges: PENSION_EDGES,
    votes: ["reval"],
    lead: (r, f) =>
      `Subir las pensiones un punto sobre el IPC cada año cuesta ${f.meur(r.cost[2035].v)} en 2035 y suma ${f.ppAbs(r.debt[2050].v, 0)} puntos de deuda en 2050 si se paga con deuda.`,
    badge: (r, f) => `${f.pp(r.debt[2050].v, 0)} pp de deuda en 2050`,
  },
  {
    slug: "pensiones-por-debajo-del-ipc",
    signs: { "cases.p4.2035": -1, "debt.2050": -1 }, // directions the lead states in words (scenarios.test.mjs)
    group: "Pensiones",
    short: "Pensiones: IPC − 1 punto",
    question: "¿Qué pasa si las pensiones suben un punto menos que el IPC?",
    title: "Pensiones por debajo del IPC: qué pasa",
    keywords: ["pensiones IPC", "congelar pensiones", "pérdida poder adquisitivo pensiones", "revalorización pensiones"],
    levers: { reval: -1 },
    metrics: ["cost", "debt", "pension"],
    cases: FISCAL_CASES,
    edges: [...PENSION_EDGES, "B02_irp_savings"],
    votes: ["reval"],
    lead: (r, f) =>
      `Si las pensiones suben un punto menos que el IPC, Carmen pierde ${f.eurAbs(r.cases.p4[2035].v)} al mes en 2035 y la deuda de 2050 baja ${f.ppAbs(r.debt[2050].v, 0)} puntos de PIB.`,
    badge: (r, f) => `Carmen: ${f.eur(r.cases.p4[2035].v)} al mes en 2035`,
  },
  {
    slug: "retrasar-edad-jubilacion",
    signs: { "pension.2050": -1, "jobs.2035": 1, "debt.2050": -1 }, // directions the lead states in words (scenarios.test.mjs)
    caveat: "La palanca mueve la edad efectiva, no la legal. El Ageing Report da efectos mayores al congelar la edad legal, porque también mueve el empleo de toda la franja de 55 a 74 años; y el modelo no dice si la edad efectiva puede subir de verdad.",
    group: "Pensiones",
    short: "Jubilarse 2 años más tarde",
    question: "¿Qué pasa si nos jubilamos dos años más tarde?",
    title: "Retrasar la jubilación dos años: qué pasa",
    keywords: ["retrasar edad de jubilación", "jubilación 67", "jubilación 68", "edad efectiva de jubilación", "pensiones"],
    levers: { age: 2 },
    metrics: ["cost", "debt", "pension", "jobs"],
    cases: FISCAL_CASES,
    edges: ["E02_retirement_cohort", "E03_delay_employment", "E11_revenue_per_job", "E20_labour_output", "E18_deficit_debt"],
    votes: ["age"],
    lead: (r, f) =>
      `Jubilarse dos años más tarde baja el gasto en pensiones ${f.ppAbs(r.pension[2050].v, 2)} puntos de PIB en 2050, suma ${f.num(r.jobs[2035].v, 0)} mil empleos en 2035 y baja la deuda ${f.ppAbs(r.debt[2050].v, 0)} puntos.`,
    badge: (r, f) => `${f.pp(r.debt[2050].v, 0)} pp de deuda en 2050`,
  },
  {
    slug: "subir-cotizaciones",
    signs: { "cost.2035": -1, "cases.p1.2035": -1 }, // directions the lead states in words (scenarios.test.mjs)
    caveat: "Cuánto empleo se pierde depende de qué parte de la cotización empresarial acaba en salarios, un valor en disputa (abajo, según cada escuela).",
    group: "Pensiones",
    short: "Cotizaciones: +1 punto",
    question: "¿Qué pasa si se suben las cotizaciones sociales un punto?",
    title: "Subir las cotizaciones un punto: quién lo paga",
    keywords: ["subir cotizaciones", "cotizaciones sociales", "MEI", "coste laboral", "empleo"],
    levers: { contrib: 1 },
    metrics: ["cost", "debt", "jobs"],
    cases: FISCAL_CASES,
    edges: ["E10_ssc_base", "E19_mei_path", "E08_ssc_incidence", "E09_labour_demand", "E11_revenue_per_job"],
    votes: ["contrib"],
    debate: { param: "traslado_cotizacion_salario", metric: "jobs", year: 2035 },
    lead: (r, f) =>
      `Un punto más de cotización recauda ${f.meurAbs(r.cost[2035].v)} netos al año en 2035, cambia el empleo en ${f.k(r.jobs[2035].v)} personas y a Lucía le cuesta ${f.eurAbs(r.cases.p1[2035].v)} al mes.`,
    badge: (r, f) => `Empleo ${f.k(r.jobs[2035].v)} en 2035`,
  },
  {
    slug: "subir-iva",
    signs: { "cost.2035": -1 }, // directions the lead states in words (scenarios.test.mjs)
    group: "Impuestos",
    short: "IVA general: +1 punto",
    question: "¿Qué pasa si se sube el IVA un punto, del 21 % al 22 %?",
    title: "Subir el IVA un punto: cuánto recauda y quién paga",
    keywords: ["subir IVA", "IVA 22", "IVA general", "quién paga el IVA", "recaudación IVA"],
    levers: { vatStd: 1 },
    metrics: ["cost", "debt", "prices"],
    cases: FISCAL_CASES,
    quintiles: true,
    edges: ["E12_vat_yield", "E13_vat_passthrough", "E13b_vat_basket", "E14_wage_indexation"],
    votes: ["iva"],
    lead: (r, f) =>
      `Subir el IVA del 21 % al 22 % recauda ${f.meurAbs(r.cost[2035].v)} netos al año en 2035 y pesa más en el 20 % con menos renta (${f.num(-r.quintiles[0].pctDisposable, 2)} %) que en el más rico (${f.num(-r.quintiles[4].pctDisposable, 2)} %).`,
    badge: (r, f) => f.revShort(r.cost[2035].v),
  },
  {
    slug: "iva-al-23",
    signs: { "cost.2035": -1, "prices.2035": 1, "cases.p2.2035": -1 }, // directions the lead states in words (scenarios.test.mjs)
    group: "Impuestos",
    short: "IVA general al 23 %",
    question: "¿Qué pasa si el IVA general sube al 23 %?",
    title: "IVA al 23 %: cuánto recauda y quién paga",
    keywords: ["IVA 23", "subir IVA", "IVA general", "quién paga el IVA"],
    levers: { vatStd: 2 },
    metrics: ["cost", "debt", "prices"],
    cases: FISCAL_CASES,
    quintiles: true,
    edges: ["E12_vat_yield", "E13_vat_passthrough", "E13b_vat_basket", "E14_wage_indexation"],
    votes: ["iva"],
    lead: (r, f) =>
      `Con el IVA general al 23 % se recaudan ${f.meurAbs(r.cost[2035].v)} netos al año en 2035, los precios suben un ${f.num(r.prices[2035].v, 2)} % y a Ana y Javi les cuesta ${f.eurAbs(r.cases.p2[2035].v)} al mes.`,
    badge: (r, f) => f.revShort(r.cost[2035].v),
  },
  {
    slug: "bajar-iva",
    signs: { "cost.2035": 1, "debt.2050": 1, "cases.p2.2035": 1 }, // directions the lead states in words (scenarios.test.mjs)
    group: "Impuestos",
    short: "IVA general: −2 puntos",
    question: "¿Qué pasa si se baja el IVA general dos puntos, al 19 %?",
    title: "Bajar el IVA al 19 %: cuánto cuesta",
    keywords: ["bajar IVA", "IVA 19", "rebaja IVA", "IVA general"],
    levers: { vatStd: -2 },
    metrics: ["cost", "debt", "prices"],
    cases: FISCAL_CASES,
    quintiles: true,
    edges: ["E12_vat_yield", "E13_vat_passthrough", "E13b_vat_basket", "E14_wage_indexation", "E18_deficit_debt"],
    votes: ["iva"],
    lead: (r, f) =>
      `Bajar el IVA general al 19 % cuesta ${f.meur(r.cost[2035].v)} al año en 2035 y suma ${f.ppAbs(r.debt[2050].v, 0)} puntos de deuda en 2050 si no se compensa; Ana y Javi ganan ${f.eurAbs(r.cases.p2[2035].v)} al mes.`,
    badge: (r, f) => `${f.pp(r.debt[2050].v, 1)} pp de deuda en 2050`,
  },
  {
    slug: "bajar-irpf",
    signs: { "cost.2035": 1, "debt.2050": 1, "cases.p5.2035": 1, "cases.p1.2035": 1 }, // directions the lead states in words (scenarios.test.mjs)
    group: "Impuestos",
    short: "IRPF: −1 punto",
    question: "¿Cuánto cuesta bajar el IRPF un punto en todos los tramos?",
    title: "Bajar el IRPF un punto: cuánto cuesta",
    keywords: ["bajar IRPF", "rebaja IRPF", "tramos IRPF", "cuánto cuesta bajar impuestos"],
    levers: { irpfAll: -1 },
    metrics: ["cost", "debt"],
    cases: FISCAL_CASES,
    quintiles: true,
    edges: ["T01_irpf_yield_all", "T03_eti_general", "B04_irpf_concentration", "E18_deficit_debt"],
    votes: ["irpf"],
    lead: (r, f) =>
      `Bajar un punto todos los tramos del IRPF cuesta ${f.meur(r.cost[2035].v)} al año en 2035 y suma ${f.ppAbs(r.debt[2050].v, 1)} puntos de deuda en 2050; Laura gana ${f.eurAbs(r.cases.p5[2035].v)} al mes, Lucía ${f.eurAbs(r.cases.p1[2035].v)}.`,
    badge: (r, f) => f.revShort(r.cost[2035].v),
  },
  {
    slug: "subir-irpf",
    signs: { "cost.2035": -1 }, // directions the lead states in words (scenarios.test.mjs)
    group: "Impuestos",
    short: "IRPF: +1 punto",
    question: "¿Qué pasa si se sube el IRPF un punto en todos los tramos?",
    title: "Subir el IRPF un punto: cuánto recauda y quién paga",
    keywords: ["subir IRPF", "tramos IRPF", "quién paga el IRPF", "recaudación IRPF"],
    levers: { irpfAll: 1 },
    metrics: ["cost", "debt"],
    cases: FISCAL_CASES,
    quintiles: true,
    edges: ["T01_irpf_yield_all", "T03_eti_general", "B04_irpf_concentration"],
    votes: ["irpf"],
    lead: (r, f) =>
      `Un punto más de IRPF en cada tramo recauda ${f.meurAbs(r.cost[2035].v)} netos en 2035 y pesa ${f.num(r.quintiles[4].pctDisposable / r.quintiles[0].pctDisposable, 1)} veces más en la renta del 20 % más rico que en la del más pobre.`,
    badge: (r, f) => f.revShort(r.cost[2035].v),
  },
  {
    slug: "irpf-rentas-altas",
    signs: {}, // directions the lead states in words (scenarios.test.mjs)
    caveat: "Si subir el tramo alto recauda o no depende de cuánto reaccionan las rentas altas, y no hay una estimación española para ellas; la encuesta también recoge peor las rentas más altas.",
    group: "Impuestos",
    short: "IRPF alto: +3 puntos",
    question: "¿Cuánto recauda subir 3 puntos el IRPF a las rentas de más de 60.000 euros?",
    title: "Subir el IRPF a las rentas altas: cuánto recauda",
    keywords: ["IRPF rentas altas", "subir impuestos a los ricos", "tramo alto IRPF", "más de 60.000 euros"],
    levers: { irpfTop: 3 },
    metrics: ["cost", "debt"],
    cases: FISCAL_CASES,
    quintiles: true,
    edges: ["T02_irpf_yield_top", "T03b_eti_top", "B04_irpf_concentration"],
    votes: ["irpf"],
    debate: { param: "eti_alta", metric: "cost", year: 2035 },
    lead: (r, f) =>
      `Subir 3 puntos el IRPF por encima de 60.000 € ${f.rev(r.cost[2035].v)} en 2035 con la reacción central; con otro supuesto, ${f.rev(f.otherSchool(r).v)}.`,
    badge: (r, f) => `${r.cost[2035].v < 0 ? "Recauda" : "Pierde"} ${f.meurAbs(r.cost[2035].v)} al año (valor central)`,
  },
  {
    slug: "subir-impuesto-sociedades",
    signs: { "cost.2035": -1, "cases.p5.2035": -1 }, // directions the lead states in words (scenarios.test.mjs)
    caveat: "Qué parte del impuesto acaba en salarios más bajos está en disputa; el modelo no calcula la inversión ni la localización de las empresas más allá de los beneficios que dejan de declararse.",
    group: "Impuestos",
    short: "Sociedades al 30 %",
    question: "¿Qué pasa si el Impuesto sobre Sociedades sube del 25 % al 30 %?",
    title: "Impuesto sobre Sociedades al 30 %: quién paga",
    keywords: ["impuesto de sociedades", "subir impuesto sociedades", "sociedades 30", "impuestos empresas"],
    levers: { corp: 5 },
    metrics: ["cost", "debt"],
    cases: FISCAL_CASES,
    quintiles: true,
    edges: ["T05_corp_yield", "T06_corp_incidence", "T07_wage_bill"],
    votes: ["corp"],
    debate: { param: "traslado_sociedades_salarios", metric: "caseP5", year: 2035 },
    lead: (r, f) =>
      `Sociedades al 30 % recauda ${f.meurAbs(r.cost[2035].v)} netos al año en 2035; una parte se traslada a salarios: a Laura le cuesta ${f.eurAbs(r.cases.p5[2035].v)} al mes, cifra en disputa.`,
    badge: (r, f) => f.revShort(r.cost[2035].v),
  },
  {
    slug: "tope-alquiler",
    signs: {}, // directions the lead states in words (scenarios.test.mjs)
    caveat: "Cuántos caseros dejan el alquiler con un tope es el supuesto más disputado del simulador: los estudios de Cataluña y San Francisco no coinciden. El modelo es nacional; en un barrio concreto el efecto puede ser otro.",
    group: "Vivienda",
    short: "Tope del alquiler",
    question: "¿Baja el alquiler con un tope? Un 10 % menos en la mitad del mercado",
    title: "¿Baja el alquiler con un tope? Qué dice el modelo",
    keywords: ["tope alquiler", "limitar alquiler", "zonas tensionadas", "ley de vivienda", "control de alquileres"],
    levers: { capCov: 50, capCut: 10 },
    metrics: ["rentCov", "rentUnc", "rentalStock", "price"],
    cases: ["p1RentCov", "p1RentUnc"],
    edges: ["V01_rent_cap_supply", "V05_rent_cap_compliance", "V06_rental_scarcity_spillover", "V07_rent_renewal", "B05_catalonia_2020"],
    votes: ["tope"],
    debate: { param: "respuesta_oferta_tope", metric: "rentUnc", year: 2035 },
    lead: (r, f) =>
      `Un tope del 10 % en la mitad del alquiler ${f.verb(r.rentCov[2035].v)} el contrato nuevo con tope en 2035 y ${f.verb(r.rentUnc[2035].v)} el de quien busca fuera (supuesto en disputa).`,
    badge: (r, f) => `Con tope ${f.pct(r.rentCov[2035].v)} · fuera ${f.pct(r.rentUnc[2035].v)}`,
  },
  {
    slug: "construir-vivienda-publica",
    signs: { "hsCost.2035": 1 }, // directions the lead states in words (scenarios.test.mjs)
    caveat: "La obra pública tarda unos años en terminarse y el modelo no le da efecto sobre el PIB ni el empleo; cuánta obra privada desplaza está en disputa.",
    group: "Vivienda",
    short: "20.000 viviendas públicas al año",
    question: "¿Baja el alquiler si se construyen 20.000 viviendas públicas al año?",
    title: "Construir vivienda pública: ¿baja el alquiler?",
    keywords: ["vivienda pública", "construir vivienda", "alquiler social", "bajar el alquiler", "parque público"],
    levers: { pubHomes: 20 },
    metrics: ["rent", "stock", "young", "hsCost", "debt"],
    cases: ["p1Rent", "p2Rent"],
    edges: ["V08_public_lag", "V09_public_cost", "V10_crowd_out", "V12_rent_stock_elasticity", "V13_emancipation_rent"],
    votes: ["publica"],
    debate: { param: "desplazamiento_obra_privada", metric: "rent", year: 2035 },
    lead: (r, f) =>
      `20.000 viviendas públicas más al año ${f.verbPl(r.rent[2035].v)} el alquiler de un contrato nuevo en 2035 y ${f.verbPl(r.rent[2050].v)} en 2050; cuestan ${f.meur(r.hsCost[2035].v)} en 2035.`,
    badge: (r, f) => `Alquiler ${f.pct(r.rent[2035].v)} en 2035`,
  },
  {
    slug: "pisos-turisticos",
    signs: {}, // directions the lead states in words (scenarios.test.mjs)
    caveat: "El modelo es nacional: en los barrios con muchos pisos turísticos el efecto puede ser varias veces mayor. Cuántos pisos retirados vuelven a vivienda habitual es un supuesto sin estimación.",
    group: "Vivienda",
    short: "Retirar la mitad de los pisos turísticos",
    question: "¿Baja el alquiler si se retira la mitad de los pisos turísticos?",
    title: "Retirar pisos turísticos: ¿baja el alquiler?",
    keywords: ["pisos turísticos", "viviendas de uso turístico", "prohibir pisos turísticos", "alquiler"],
    levers: { tourCut: 50 },
    metrics: ["rent", "stock", "price"],
    cases: ["p1Rent", "p2Rent"],
    edges: ["V04_tourist_conversion", "B07_tourist_rents", "V12_rent_stock_elasticity"],
    votes: ["turistico"],
    lead: (r, f) =>
      `Retirar la mitad de los pisos turísticos ${f.verb(r.rent[2035].v, 2)} el alquiler medio de un contrato nuevo en España en 2035; en barrios con muchos puede ser mayor.`,
    badge: (r, f) => `Alquiler ${f.pct(r.rent[2035].v, 2)} en 2035`,
  },
  {
    slug: "liberar-suelo",
    signs: {}, // directions the lead states in words (scenarios.test.mjs)
    caveat: "Cuánto del suelo liberado acaba construido es un supuesto sin estimación publicada para España.",
    group: "Vivienda",
    short: "Suelo para 20.000 viviendas al año",
    question: "¿Baja el alquiler si se libera suelo para 20.000 viviendas al año?",
    title: "Liberar suelo: ¿baja el precio de la vivienda?",
    keywords: ["liberar suelo", "suelo urbanizable", "construir más vivienda", "precio de la vivienda"],
    levers: { land: 20 },
    metrics: ["rent", "price", "stock", "young"],
    cases: ["p1Rent", "p2Rent"],
    edges: ["V11_land_absorption", "V02_private_supply_elasticity", "V12_rent_stock_elasticity", "V13_emancipation_rent"],
    votes: ["suelo"],
    lead: (r, f) =>
      `Liberar suelo para 20.000 viviendas al año ${f.verb(r.rent[2035].v)} el alquiler de un contrato nuevo en 2035 y ${f.verb(r.rent[2050].v)} en 2050; lo construido es un supuesto.`,
    badge: (r, f) => `Alquiler ${f.pct(r.rent[2035].v)} en 2035`,
  },
  {
    slug: "limitar-hipotecas",
    signs: {}, // directions the lead states in words (scenarios.test.mjs)
    caveat: "Los límites de precio y de renta se tratan como independientes, y cuántos compradores pasan a alquilar es un supuesto sin estimación verificada.",
    group: "Vivienda",
    short: "Hipotecas: 80 % y 4,5 veces la renta",
    question: "¿Baja el precio de la vivienda si se limitan las hipotecas al 80 % y a 4,5 veces la renta?",
    title: "Limitar las hipotecas: ¿baja el precio?",
    keywords: ["limitar hipotecas", "hipoteca 80", "LTV", "precio de la vivienda", "Banco de España"],
    levers: { ltvCap: 80, ltiCap: 4.5 },
    metrics: ["price", "rent"],
    cases: ["p2Pay", "p2Up", "p1Rent"],
    edges: ["V03_mortgage_binding_share", "V15_constrained_credit_loss", "V16_price_credit_elasticity", "V17_credit_price_feedback", "V18_tenure_substitution"],
    votes: ["credito"],
    lead: (r, f) =>
      `Limitar las hipotecas al 80 % del precio y a 4,5 veces la renta ${f.verb(r.price[2035].v)} el precio en 2035 y ${f.verb(r.rent[2035].v)} el alquiler (más gente alquila).`,
    badge: (r, f) => `Precio ${f.pct(r.price[2035].v)} en 2035`,
  },
  {
    slug: "mas-inmigracion",
    signs: {}, // directions the lead states in words (scenarios.test.mjs)
    caveat: "La inmigración es contexto, no una palanca: las pensiones siguen la variante oficial del Ageing Report 2024 y los hogares nuevos suben el alquiler; el resto de ingresos y gastos públicos de quien llega (impuestos, sanidad, educación) no entra en el modelo.",
    group: "Población",
    short: "Un tercio más de inmigración",
    question: "¿Qué pasa con las pensiones y el alquiler si llega un tercio más de inmigrantes?",
    title: "Más inmigración: pensiones, deuda y alquiler",
    keywords: ["inmigración pensiones", "inmigración alquiler", "inmigración deuda", "Ageing Report"],
    levers: { migration: "high" },
    metrics: ["migPension", "debt", "migHouseholds", "rent"],
    cases: ["p1Rent"],
    edges: ["E21_migration_pensions", "V14_new_household_size", "V12_rent_stock_elasticity"],
    votes: [],
    lead: (r, f) =>
      `Con un tercio más de inmigración (Ageing Report) el gasto en pensiones ${f.ppVerb(r.migPension[2050].v, 2)} puntos de PIB en 2050 y el alquiler nuevo ${f.verb(r.rent[2035].v)} en 2035.`,
    badge: (r, f) => `Deuda ${f.pp(r.debt[2050].v, 0)} pp en 2050`,
  },
  {
    slug: "menos-inmigracion",
    signs: {}, // directions the lead states in words (scenarios.test.mjs)
    caveat: "La inmigración es contexto, no una palanca: las pensiones siguen la variante oficial del Ageing Report 2024 y los hogares que no se forman bajan el alquiler; el resto de ingresos y gastos públicos (impuestos, sanidad, educación) no entra en el modelo.",
    group: "Población",
    short: "Un tercio menos de inmigración",
    question: "¿Qué pasa con las pensiones y el alquiler si llega un tercio menos de inmigrantes?",
    title: "Menos inmigración: pensiones, deuda y alquiler",
    keywords: ["inmigración pensiones", "menos inmigración", "inmigración alquiler", "Ageing Report"],
    levers: { migration: "low" },
    metrics: ["migPension", "debt", "migHouseholds", "rent"],
    cases: ["p1Rent"],
    edges: ["E21_migration_pensions", "V14_new_household_size", "V12_rent_stock_elasticity"],
    votes: [],
    lead: (r, f) =>
      `Con un tercio menos de inmigración (Ageing Report) el gasto en pensiones ${f.ppVerb(r.migPension[2050].v, 2)} puntos de PIB en 2050 y el alquiler nuevo ${f.verb(r.rent[2035].v)} en 2035.`,
    badge: (r, f) => `Deuda ${f.pp(r.debt[2050].v, 0)} pp en 2050`,
  },
];

export const scenarioBySlug = (slug) => SCENARIOS.find((sc) => sc.slug === slug);
export const scenarioPath = (sc) => `${SCENARIOS_PATH}${sc.slug}/`;
export const simulatorHref = (sc) => `${SIM_PATH}#${encodeState({ ...DEFAULT_LEVERS, ...sc.levers })}`;

// ---- Formatting (Spanish), shared by the page, the share card and the descriptions.
const MINUS = "−";
const n = (v, d = 1) => Number(v).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: "always" });
const signOf = (r) => (r > 0 ? "+" : r < 0 ? MINUS : "");
const rounded = (v, d) => Math.round(v * 10 ** d) / 10 ** d;
const signed = (v, d) => `${signOf(rounded(v, d))}${n(Math.abs(rounded(v, d)), d)}`;
const meurText = (v) => {
  const a = Math.abs(v);
  return a >= 1000 ? `${n(a / 1000, 1)} mil millones` : `${n(a, 0)} millones`;
};
export const fmt = {
  num: (v, d = 1) => n(v, d),
  pp: (v, d = 1) => signed(v, d),
  ppAbs: (v, d = 1) => n(Math.abs(v), d),
  ppRange: (b, d = 1) => `rango ${signed(b.lo, d)} a ${signed(b.hi, d)}`,
  pct: (v, d = 1) => `${signed(v, d)} %`,
  pctRange: (b, d = 1) => `rango ${signed(b.lo, d)} % a ${signed(b.hi, d)} %`,
  verbPl: (v, d = 1) => (rounded(v, d) === 0 ? "apenas mueven" : v < 0 ? `bajan un ${n(-v, d)} %` : `suben un ${n(v, d)} %`),
  verb: (v, d = 1) => (rounded(v, d) === 0 ? "apenas mueve" : v < 0 ? `baja un ${n(-v, d)} %` : `sube un ${n(v, d)} %`),
  k: (v) => `${signed(v, 0)} mil`,
  kRange: (b) => `rango ${signed(b.lo, 0)} a ${signed(b.hi, 0)} mil`,
  eur: (v) => `${signed(v, 0)} €`,
  eurAbs: (v) => `${n(Math.abs(v), 0)} €`,
  meur: (v) => `${v < 0 ? MINUS : ""}${meurText(v)} €`,
  meurAbs: (v) => `${meurText(v)} €`,
  rev: (v) => (v < 0 ? `recauda ${meurText(v)} €` : `pierde ${meurText(v)} €`), // v = net cost
  revShort: (v) => (v < 0 ? `Recauda ${meurText(v)} al año` : `Cuesta ${meurText(v)} al año`),
  ppVerb: (v, d = 1) => (v < 0 ? `baja ${n(-v, d)}` : `sube ${n(v, d)}`),
  otherSchool: (r) => r.debate.schools.find((sc) => Math.sign(sc.v) !== Math.sign(r.cost[2035].v)) || r.debate.schools[1],
  meurRangeAbs: (b) => {
    const [a, c] = [-b.hi, -b.lo]; // revenue = minus the net cost
    return `rango ${a < 0 ? MINUS : ""}${meurText(a)} a ${c < 0 ? MINUS : ""}${meurText(c)}`;
  },
};

export function metricText(id, value, d) {
  const m = METRICS[id] || CASE_METRICS[id];
  const digits = d ?? m.digits ?? 1;
  if (m.unit === "meur") return `${signed(value / 1000, 1)} mil mill.`;
  if (m.unit === "pp") return `${signed(value, digits)} pp`;
  if (m.unit === "pct") return `${signed(value, digits)} %`;
  if (m.unit === "k") return `${signed(value, 0)} mil`;
  return `${signed(value, 0)} €`;
}

// ---- Computation at build time (memoised per model and slug: page, metadata and share card share one run).
const cache = new WeakMap();
const isCostLever = (levers) => ["reval", "age", "contrib", "irpfAll", "irpfTop", "vatStd", "vatRed", "corp", "pubHomes"].some((k) => levers[k]);

export function scenarioResult(model, sc) {
  let memo = cache.get(model);
  if (!memo) cache.set(model, (memo = new Map()));
  if (memo.has(sc.slug)) return memo.get(sc.slug);
  const levers = { ...DEFAULT_LEVERS, ...sc.levers };
  const idx = Object.fromEntries(YEARS.map((y) => [y, model.years.indexOf(y)]));
  const toMeur = (t) => (pp) => (pp / 100) * model.start.gdp_meur * (model.baseline.real_index?.[t] ?? 1);
  const pick = (ens, m, t) => {
    const scale = m.unit === "meur" ? toMeur(t) : (v) => v * (m.scale ?? 1);
    const lo = scale(ens.bands[m.key].lo[t]);
    const hi = scale(ens.bands[m.key].hi[t]);
    return { v: scale(ens.central[m.key][t]), lo: Math.min(lo, hi), hi: Math.max(lo, hi), sameSign: ens.bands[m.key].sameSign[t] };
  };
  const byYear = (ens, m) => Object.fromEntries(YEARS.map((y) => [y, pick(ens, m, idx[y])]));
  const keys = [...new Set([...sc.metrics.map((id) => METRICS[id].key), ...sc.cases.map((id) => CASE_METRICS[id].key), "net_cost_pp", "debt_dev_pp"])];
  const ens = runEnsemble(model, levers, { draws: DRAWS, keys });
  const out = { slug: sc.slug, levers, cases: {} };
  for (const id of sc.metrics) out[id] = byYear(ens, METRICS[id]);
  if (!out.cost) out.cost = byYear(ens, METRICS.cost);
  if (!out.debt) out.debt = byYear(ens, METRICS.debt);
  for (const id of sc.cases) out.cases[id] = byYear(ens, CASE_METRICS[id]);
  const t35 = idx[2035];
  if (sc.quintiles) out.quintiles = quintileImpact(model, ens.central, t35, centralParams(model)).map((q) => ({ q: q.q, total: q.total, pctDisposable: q.pctDisposable }));
  out.revenue = out.cost[2035].v < 0;
  // A contested assumption: the headline metric under each school (central parameters with that school).
  if (sc.debate) {
    const p = model.params[sc.debate.param];
    const t = idx[sc.debate.year];
    const m = sc.debate.metric === "caseP5" ? CASE_METRICS.p5 : METRICS[sc.debate.metric];
    out.debate = {
      param: sc.debate.param,
      edge: p.edge,
      metric: sc.debate.metric === "caseP5" ? "p5" : sc.debate.metric,
      year: sc.debate.year,
      schools: p.debate.schools.map((school, i) => {
        const run = simulate(model, levers, centralParams(model, { [p.debate.id]: i }));
        const raw = run[m.key][t];
        const v = m.unit === "meur" ? toMeur(t)(raw) : raw * (m.scale ?? 1);
        return { label: school.label, central: school.central, v };
      }),
    };
  }
  out.lead = sc.lead(out, fmt);
  out.badge = sc.badge(out, fmt);
  memo.set(sc.slug, out);
  return out;
}

// How it is paid for (a cost) or what the money goes to (net revenue): the four closures of the simulator, each with
// its own ensemble (heavier: only the scenario page itself asks for it).
export function scenarioClosures(model, sc) {
  const base = scenarioResult(model, sc);
  if (!isCostLever(sc.levers) || Math.abs(base.cost[2035].v) <= 50) return null;
  let memo = cache.get(model);
  const memoKey = `${sc.slug}::closures`;
  if (memo.has(memoKey)) return memo.get(memoKey);
  const levers = base.levers;
  const t35 = model.years.indexOf(2035);
  const t50 = model.years.indexOf(2050);
  const pick = (e, key, t) => ({ v: e.central[key][t], lo: e.bands[key].lo[t], hi: e.bands[key].hi[t] });
  const keys = ["debt_dev_pp", "p1_month", "p4_month", "employment_k", "closure_contrib_pp", "closure_vat_pp", "closure_irpf_pp"];
  const out = CLOSURES.map((c) => {
    const e = runEnsemble(model, { ...levers, closure: c }, { draws: CLOSURE_DRAWS, keys });
    const rateKey = { cotizaciones: "closure_contrib_pp", iva: "closure_vat_pp", irpf: "closure_irpf_pp" }[c];
    return {
      id: c,
      label: CLOSURE_ES[c][base.revenue ? "use" : "pay"],
      rate: rateKey ? e.central[rateKey][t35] : null,
      debt: pick(e, "debt_dev_pp", t50),
      p1: pick(e, "p1_month", t35),
      p4: pick(e, "p4_month", t35),
      jobs: pick(e, "employment_k", t35),
      href: `${SIM_PATH}#${encodeState({ ...levers, closure: c })}`,
    };
  });
  memo.set(memoKey, out);
  return out;
}

// Title shaped for the searches; the description carries the consolidated figure's finding with engine numbers.
export const SIM_TITLE = "Simulador de pensiones, impuestos y vivienda: quién paga";
export function simDescription(model) {
  const m = mainFindings(model);
  return `Subir las pensiones 1 punto sobre el IPC suma ${fmt.ppAbs(m.debt50, 0)} puntos de deuda en 2050 o le cuesta a una joven de ${fmt.num(m.p1Min, 0)} a ${fmt.num(m.p1Max, 0)} € al mes en 2035. Prueba IVA, IRPF y alquiler.`;
}

// Headline numbers of the main page (the consolidated figure: +1 pp on pensions, four ways to pay).
export function mainFindings(model) {
  let memo = cache.get(model);
  if (!memo) cache.set(model, (memo = new Map()));
  if (memo.has("__main")) return memo.get("__main");
  const t35 = model.years.indexOf(2035);
  const tEnd = model.years.length - 1;
  const runs = Object.fromEntries(CLOSURES.map((c) => [c, simulate(model, { ...DEFAULT_LEVERS, reval: 1, closure: c })]));
  const taxPaid = ["cotizaciones", "iva", "irpf"].map((c) => -runs[c].p1_month[t35]);
  const out = {
    debt50: runs.deuda.debt_dev_pp[tEnd],
    p1Min: Math.min(...taxPaid),
    p1Max: Math.max(...taxPaid),
    p4Debt: runs.deuda.p4_month[t35],
    costMeur35: (runs.deuda.net_cost_pp[t35] / 100) * model.start.gdp_meur * (model.baseline.real_index?.[t35] ?? 1),
  };
  memo.set("__main", out);
  return out;
}
