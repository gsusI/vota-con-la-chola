// Engine of /visualizaciones/sistema/: pensions, public finances, taxes and housing, annual steps, deviations from the
// Ageing Report 2024 baseline for Spain (housing: INE household projection, completions held constant). Pure functions, no dependencies: the page runs it in the browser and
// `node --test` runs the same file (engine.test.mjs). Sources of every number: sistema.json (`edges`, `constants_notes`)
// and docs/etl/sprints/SISTEMA-COMPLEJO-20261019/README.md.

export const LAYERS = ["contable", "comportamiento", "segunda_ronda"];
export const CLOSURES = ["deuda", "cotizaciones", "iva", "irpf"];
export const QUINTILES = ["Q1", "Q2", "Q3", "Q4", "Q5"];
export const PERSONAS = ["p1", "p2", "p4", "p5"];

export const DEFAULT_LEVERS = {
  reval: 0, // real revaluation over CPI, pp per year
  age: 0, // effective retirement age vs baseline, years (phased in)
  contrib: 0, // extra contribution rate, pp of the contribution base (split like the MEI)
  irpfAll: 0, // every bracket of the IRPF general scale, pp
  irpfTop: 0, // the part of the general base above 60,000 EUR, pp
  vatStd: 0, // standard VAT rate (21 %), pp
  vatRed: 0, // reduced VAT rate (10 %), pp
  corp: 0, // nominal corporate income tax rate (25 %), pp
  closure: "deuda", // how the net cost is paid each year
  pubHomes: 0, // extra public rental completions a year from the programme, thousands (decided from 2026)
  land: 0, // finalist land released for this many dwellings a year, thousands
  ltvCap: 0, // maximum loan-to-price (LTP, the Banco de España measure) of new mortgages, % (0 = no cap, as now)
  ltiCap: 0, // maximum loan-to-income of new mortgages, times gross income (0 = no cap, as now)
  capCov: 0, // rent cap: share of market-rent households in covered (stressed) areas, % (beyond those already covered)
  capCut: 0, // rent cap: average cut the cap imposes on covered rents vs the market, %
  tourCut: 0, // tourist dwellings withdrawn, % of the current stock (licences, bans)
  migration: "base", // legacy context switch (base | low | high): the same as migScale -1 / 0 / +1
  rateShock: 0, // context: market interest rate vs baseline, pp
  // slice 3: employment
  smi: 0, // minimum wage (SMI), % real rise over the baseline from 2026
  hours: 0, // maximum weekly hours cut from 40, hours (monthly pay kept)
  selfQuota: 0, // self-employed monthly contribution, euros a month vs today
  // slice 3: immigration (lever and context), in multiples of the official variant (Eurostat EUROPOP2023 HMIGR/LMIGR,
  // the Ageing Report's «±33 % non-EU immigration», which moves net migration about ±46 % cumulated to 2050)
  migScale: 0,
  // slice 4 (capacity): healthcare
  mir: 0, // extra specialist training places a year (MIR), from 2026
  healthSpend: 0, // extra real public health spending, % of the baseline
  svcFunding: "follow", // do public services grow with population? follow (as the Ageing Report assumes) | fixed (same euros)
};

// Value of each parameter when its layer is switched off (the accounting layer keeps statutory incidence).
export const NEUTRAL = {
  permanencia_empleo: 0,
  prestacion_alternativa: 0,
  traslado_cotizacion_salario: 0,
  elasticidad_empleo_coste: 0,
  traslado_iva_precios: 1,
  indiciacion_salarios: 0,
  prima_por_deuda: 0,
  multiplicador_transferencias: 0,
  multiplicador_impuestos: 0,
  persistencia_multiplicador: 0,
  semielasticidad_saldo: 0,
  eti_general: 0,
  eti_alta: 0,
  semielasticidad_base_sociedades: 0,
  traslado_sociedades_salarios: 0,
  // housing: the accounting layer keeps the arithmetic (dwellings built, cap as the law says) and nothing else
  respuesta_oferta_tope: 0,
  cumplimiento_tope: 1,
  traslado_escasez_alquiler: 0,
  desplazamiento_obra_privada: 0,
  elasticidad_oferta_privada: 0,
  absorcion_suelo: 0,
  conversion_turistica: 0,
  respuesta_alquiler_parque: 0,
  elasticidad_emancipacion: 0,
  perdida_credito_restringido: 0,
  elasticidad_precio_credito: 0,
  elasticidad_credito_precio: 0,
  sustitucion_alquiler: 0,
  // employment, immigration and healthcare: the accounting layer keeps the arithmetic (wages, population, money that
  // becomes care) and nothing else
  elasticidad_empleo_smi: 0,
  elasticidad_empleo_jornada: 0,
  compensacion_productividad_jornada: 0,
  elasticidad_autonomos_cuota: 0,
  ajuste_empleo_inmigrante: 1,
  uso_sanitario_relativo_inmigrante: 1,
  capacidad_por_gasto: 1,
  permanencia_sns_medicos: 1,
  elasticidad_demanda_espera: 0,
};

export const HOUSING_KEYS = ["hs_stock_k", "hs_completions_k", "hs_public_k", "hs_private_k", "hs_tourist_k", "hs_households_k",
  "hs_migration_hh_k", "hs_emancipated_hh_k", "hs_emancipated_k", "hs_at_home_pp", "hs_rent", "hs_rent_cov", "hs_rent_unc",
  "hs_rent_new", "hs_rent_paid", "hs_price", "hs_credit", "hs_new_credit", "hs_credit_cut", "hs_rental_stock_k", "hs_cost_pp",
  "hs_binding", "p1_rent_cov_month", "p1_rent_unc_month", "p1_rent_paid_month", "p2r_rent_cov_month", "p2r_rent_unc_month",
  "p2b_payment_month", "p2b_upfront_eur"];

// Completed share of a programme decided at k = 1 after `lag` years (0 before, 1 after, linear in between).
const ramp = (k, lag) => clamp(k - lag, 0, 1);

export const LABOUR_KEYS = ["lb_smi_k", "lb_hours_k", "lb_self_k", "lb_wage_bill_pct", "lb_hour_cost_pct", "lb_revenue_pp",
  "mig_pop_k", "mig_emp_k", "mig_revenue_pp", "mig_rev_other_pp", "mig_health_pp", "mig_edu_pp", "mig_ltc_pp", "mig_other_pp", "mig_pension_pp",
  "mig_spend_pp", "mig_net_pp", "mig_students_k", "mig_gdp_pct",
  ...["0_15", "16_29", "30_44", "45_64", "65p"].flatMap((s) => [`mig_pop_${s}`, `mig_rev_${s}`, `mig_use_${s}`]),
  "hl_demand_pct", "hl_money_pct", "hl_doctors_k", "hl_capacity_pct", "hl_list_k", "hl_wait_days", "hl_cost_pp", "hl_deterred_k", "hl_wait_dev",
  "svc_per_person_pct"];
export const STAGE_GROUPS = { "0_15": ["0_15"], "16_29": ["16_29"], "30_44": ["30_44"], "45_64": ["45_64"], "65p": ["65_79", "80p"] };

/** Multiple of the official migration variant: migScale, or the legacy switch (low = -1, high = +1). */
export const migrationScale = (L) => L.migScale || (L.migration === "low" ? -1 : L.migration === "high" ? 1 : 0);

/** Share of new mortgage volume above the chosen caps (independent LTV and LTI, a simplification the page states). */
export function bindingShare(P, ltvCap, ltiCap) {
  const ltv = { 90: P.hip_sobre_ltv90, 80: P.hip_sobre_ltv80, 70: P.hip_sobre_ltv70 }[ltvCap] ?? 0;
  const lti = { 6: P.hip_sobre_lti6, 4.5: P.hip_sobre_lti45 }[ltiCap] ?? 0;
  return 1 - (1 - ltv) * (1 - lti);
}

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

/** Central value of every parameter, with debate schools applied ({debateId: schoolIndex}). */
export function centralParams(model, debates = {}) {
  const out = {};
  for (const [name, p] of Object.entries(model.params)) {
    const school = p.debate && debates[p.debate.id] != null ? p.debate.schools[debates[p.debate.id]] : null;
    out[name] = school ? school.central : p.central;
  }
  return out;
}

/** Switch off every behavioural parameter whose layer is above `layer`. */
export function applyLayer(model, params, layer) {
  const keep = LAYERS.indexOf(layer);
  const out = { ...params };
  for (const [name, p] of Object.entries(model.params)) {
    if (LAYERS.indexOf(p.layer) > keep && name in NEUTRAL) out[name] = NEUTRAL[name];
  }
  return out;
}

const zeros = (n) => new Array(n).fill(0);

/**
 * One deterministic run. Returns arrays aligned with model.years (first year = last actual year, all deviations 0).
 * Units: % of baseline GDP for fiscal flows/stocks, fractions for pension/employment deviations, euros a month
 * (prices of the base year) for the typical cases.
 */
export function simulate(model, levers = DEFAULT_LEVERS, params = centralParams(model)) {
  const L = { ...DEFAULT_LEVERS, ...levers };
  const P = params;
  const C = model.constants;
  const B = model.baseline;
  const n = model.years.length;
  const start = model.policy_start;
  const es = C.employer_share;
  const sMig = migrationScale(L);
  const Lb = model.labour;
  // Behavioural offsets of the IRPF levers (elasticity of taxable income) and of the corporate tax base.
  const offAll = P.eti_general * (C.irpf_marginal_avg / (1 - C.irpf_marginal_avg));
  const offTop = P.eti_alta * (C.irpf_marginal_top / (1 - C.irpf_marginal_top)) * P.pareto_a_alto;
  const irpfUnit = P.recaudacion_por_punto_irpf * (1 - offAll); // revenue of 1 pp on every bracket, net of behaviour

  const keys = ["pension_dev", "pensioners_dev", "employment_dev", "employment_k", "gdp_dev", "pension_gross_pp",
    "other_benefits_pp", "irpf_back_pp", "labour_revenue_pp", "contrib_revenue_pp", "vat_revenue_pp", "vat_red_revenue_pp",
    "irpf_revenue_pp", "corp_revenue_pp", "cycle_revenue_pp", "migration_pp", "net_cost_pp", "primary_dev_pp",
    "interest_dev_pp", "debt_dev_pp", "closure_contrib_pp", "closure_vat_pp", "closure_irpf_pp", "price_level_dev",
    "labour_cost_dev", "wage_dev", "implicit_rate_dev", "debt_per_person_eur",
    // statutory (static) burdens of each instrument, % GDP: the quintile split uses them
    "s_irpf_all_pp", "s_irpf_top_pp", "s_vat_std_pp", "s_vat_red_pp", "s_contrib_pp", "s_corp_pp", "s_pension_net_pp",
    ...PERSONAS.map((p) => `${p}_month`), ...HOUSING_KEYS, ...LABOUR_KEYS];
  const out = Object.fromEntries(keys.map((k) => [k, zeros(n)]));
  out.years = model.years;
  out.pension_pct = [...B.pension_pct];
  out.debt_pct = [...B.debt_pct];
  out.deficit_pct = [...B.deficit_pct];

  let x = 0; // average pension deviation of the stock
  let z = 0; // persona 4 (existing pensioner) deviation
  let eSsc = 0; // employment deviation from labour cost, adjusts gradually
  let y = 0; // demand-side output deviation, % GDP
  let impulsePrev = 0;
  let dImp = 0; // implicit interest rate deviation, pp
  let D = 0; // debt deviation, % baseline GDP
  let pricePrev = 0;
  // Housing state (thousands of dwellings or households; rents, prices and credit as fractions)
  const Hs = model.housing;
  const hp = [0, 0]; // house price deviation history (for the two-year supply lag)
  let flowCum = 0;
  let pubStock = 0;
  let privCum = 0;
  let dHm = 0;
  let dHem = 0;
  let dCred = 0;
  let paidCov = 0;
  let paidUnc = 0;
  // Employment levers (slice 3) and the surgical waiting list (slice 4), as deviations
  let eSmi = 0;
  let eHours = 0;
  let eSelf = 0;
  let listDev = 0;
  let exitsPrev = model.labour?.health.exits_k ?? 1;

  for (let t = 1; t < n; t += 1) {
    const year = model.years[t];
    const on = year >= start;
    const k = year - start + 1; // years since the policy started
    const g = B.nominal_growth[t] / 100;
    const i = B.implicit_rate[t] / 100;
    const base = B.pension_pct[t];
    const lv = (key) => (on ? L[key] : 0);

    // Pensions: extra revaluation compounds on the stock; new pensions enter without it.
    const r = lv("reval") / 100;
    x = (1 - P.lambda_renovacion) * (x + r);
    z = on ? (1 + z) * (1 + r) - 1 : 0;
    const ageEff = on ? Math.sign(L.age) * Math.min(Math.abs(L.age), C.age_phase_in_per_year * k) : 0;
    // A later retirement removes about one retirement cohort per year of age; new pensions are above the average.
    const nDev = -P.kappa_cohorte * ageEff;
    const nSpend = nDev * C.new_pension_relative;
    const grossPp = base * ((1 + x) * (1 + nSpend) - 1);
    const otherPp = base * -nSpend * P.prestacion_alternativa;
    const irpfPp = P.tipo_marginal_irpf_pension * (grossPp + otherPp);

    // ---- Immigration (slice 3): population by stage from the official variant, scaled linearly; the extra residents
    // work at the employment rate of foreign citizens of their age, pay taxes and contributions at their relative wage,
    // and use health care, schooling, long-term care, pensions and other services. Amounts in % of baseline GDP; per-head
    // amounts grow with GDP per worker (revenue) or per person (services), as in the Ageing Report.
    let migPp = 0; // pensions of the extra residents
    let migCostPp = 0; // services other than health (health goes through the capacity block) minus revenue
    let migEmpFrac = 0;
    let migGdp = 0;
    let healthDem = 0;
    let lbRevPp = 0;
    let lbSupply = 0;
    let hlCostPp = 0;
    if (Lb) {
      const Cn = Lb.const;
      const a = Math.abs(sMig);
      const src = sMig > 0 ? Lb.mig_hi_k : Lb.mig_lo_k;
      const dPop = (st) => (on && a ? a * (src[st][t] - src[st][0]) : 0);
      const realIdx = B.real_index?.[t] ?? 1;
      const empIdx = B.employment_k[t] / B.employment_k[0];
      const gdp0 = model.start.gdp_meur;
      const popT = Lb.stages.reduce((acc, st) => acc + Lb.pop_k[st][t], 0);
      // Revenue of one extra worker at the relative wage: personal taxes and contributions (OECD schedule), employer
      // contributions and consumption taxes on what is left; euros of the base year -> % of GDP per thousand workers.
      const wRel = P.salario_relativo_inmigrante;
      const gross = Cn.aw_gross * wRel;
      const curve = Cn.personal_tax_curve;
      const at = (m) => {
        const pts = curve.filter(([x]) => x <= m).at(-1) ?? curve[0];
        const nx = curve.find(([x]) => x > m) ?? curve.at(-1);
        return nx[0] === pts[0] ? pts[1] : pts[1] + ((nx[1] - pts[1]) * (m - pts[0])) / (nx[0] - pts[0]);
      };
      const personal = at(wRel);
      const revWorker = gross * (personal + C.employer_rate) + gross * (1 - personal) * P.propension_consumo * P.tipo_implicito_consumo;
      const revPerK = ((revWorker / 1e3) / gdp0 / empIdx) * 100;
      const D = Lb.stages.reduce((acc, st) => acc + Lb.pop_k[st][t] * Lb.health.weights[st], 0);
      const follow = L.svcFunding !== "fixed";
      let dTot = 0;
      let dEmp = 0;
      let dDem = 0;
      const byGroup = {};
      for (const [g, members] of Object.entries(STAGE_GROUPS)) {
        let pop = 0;
        let emp = 0;
        let dem = 0;
        for (const st of members) {
          const d = dPop(st);
          pop += d;
          emp += d * (Lb.emp_rate.FOR[st] ?? 0) * P.ajuste_empleo_inmigrante;
          dem += d * Lb.health.weights[st] * P.uso_sanitario_relativo_inmigrante;
        }
        byGroup[g] = { pop, emp, dem };
        dTot += pop;
        dEmp += emp;
        dDem += dem;
      }
      healthDem = dDem / D;
      migEmpFrac = dEmp / B.employment_k[t];
      // Other revenue (corporate and property taxes, fees, other levies) grows with the output the extra workers add,
      // as other services grow with the residents: the two sides are treated alike.
      // Output of the extra workers: the short-run elasticity, rising to 1 as capital follows labour (the Commission's
      // «capital rule» for its long-run projections, reached over the years of the card).
      const migElast = C.labour_output_elasticity + (1 - C.labour_output_elasticity) * clamp(k / P.anios_ajuste_capital, 0, 1);
      migGdp = migElast * migEmpFrac;
      const otherRev = Cn.other_revenue_pct * migGdp;
      const revenue = dEmp * revPerK + otherRev;
      const d65 = dPop("65_79") + dPop("80p");
      const pop65 = Lb.pop_k["65_79"][t] + Lb.pop_k["80p"][t];
      // Pensions: extra residents of 65+ with a relative pension (shorter careers in Spain; assumption D), at the
      // baseline average pension in % of GDP.
      migPp = (d65 * P.pension_relativa_inmigrante * B.pension_pct[t]) / B.pensioners_k[t];
      const students = dPop("5_24") * Lb.education.enrol_ratio;
      const eduPp = follow ? (Lb.education.spend_pct[t] * students) / Lb.education.students_k[t] : 0;
      const ltcPp = follow && pop65 ? (Lb.health.ltc_pct[t] * d65) / pop65 : 0;
      const otherPp = follow ? (Lb.other_spending_pct * P.cuota_gasto_congestionable * dTot) / popT : 0;
      const healthPp = follow ? Lb.health.spend_pct[t] * healthDem : 0;
      migCostPp = migPp + eduPp + ltcPp + otherPp - revenue;
      // By age stage: revenue and the use of services (health, school, long-term care, pensions, other)
      const kids = dPop("0_15");
      const school015 = Math.max(0, Math.min(dPop("5_24"), (kids * 11) / 16));
      const eduShare015 = dPop("5_24") ? school015 / dPop("5_24") : 0;
      for (const [g, v] of Object.entries(byGroup)) {
        const use = (D ? (follow ? Lb.health.spend_pct[t] * (v.dem / D) : 0) : 0)
          + (g === "0_15" ? eduPp * eduShare015 : g === "16_29" ? eduPp * (1 - eduShare015) : 0)
          + (g === "65p" ? ltcPp + migPp : 0)
          + (dTot ? (otherPp * v.pop) / dTot : 0);
        out[`mig_pop_${g}`][t] = v.pop;
        out[`mig_rev_${g}`][t] = v.emp * revPerK + (dEmp ? (otherRev * v.emp) / dEmp : 0);
        out[`mig_use_${g}`][t] = use;
      }
      const set = {
        mig_pop_k: dTot, mig_emp_k: dEmp, mig_revenue_pp: revenue, mig_rev_other_pp: otherRev, mig_health_pp: healthPp, mig_edu_pp: eduPp, mig_ltc_pp: ltcPp,
        mig_other_pp: otherPp, mig_pension_pp: migPp, mig_spend_pp: healthPp + eduPp + ltcPp + otherPp + migPp,
        mig_net_pp: healthPp + eduPp + ltcPp + otherPp + migPp - revenue, mig_students_k: students,
        svc_per_person_pct: follow ? 0 : (-dTot / (popT + dTot)) * 100,
      };
      for (const [key, v] of Object.entries(set)) out[key][t] = v;

      // ---- Employment levers (slice 3): the affected group's jobs move with an elasticity and adjust halfway a year.
      const empBase = B.employment_k[t];
      const adj = C.employment_adjust_per_year;
      const smiPct = lv("smi");
      const cutH = Math.max(0, lv("hours"));
      const hoursPct = (cutH / 40) * 100;
      const affSmi = P.cuota_afectados_smi * Lb.employees_k;
      const affHours = P.cuota_afectados_jornada * Lb.employees_k;
      const quotaPct = (lv("selfQuota") / P.cuota_media_autonomos) * 100;
      if (on) {
        eSmi += ((P.elasticidad_empleo_smi * smiPct * affSmi) / 100 / empBase - eSmi) * adj;
        eHours += ((P.elasticidad_empleo_jornada * hoursPct * affHours) / 100 / empBase - eHours) * adj;
        eSelf += ((P.elasticidad_autonomos_cuota * quotaPct * P.autonomos_k) / 100 / empBase - eSelf) * adj;
      }
      // Revenue: contributions on the higher wages at the SMI (exempt from IRPF) and the quota on those who stay.
      const wageBill = (P.cuota_masa_afectados_smi * smiPct) / 100;
      const smiRev = wageBill * P.salarios_pib * Cn.smi_tax_rate;
      const quotaRev = (((lv("selfQuota") * 12 * (P.autonomos_k + eSelf * empBase)) / 1e3) / gdp0 / empIdx) * 100;
      lbRevPp = smiRev + quotaRev;
      // Hours: monthly pay is kept, so the hourly cost of the affected rises; part is offset by productivity.
      const hourCost = cutH ? (cutH / (40 - cutH)) * (1 - P.compensacion_productividad_jornada) : 0;
      lbSupply = -(hoursPct / 100) * (affHours / empBase) * (1 - P.compensacion_productividad_jornada);
      out.lb_smi_k[t] = eSmi * empBase;
      out.lb_hours_k[t] = eHours * empBase;
      out.lb_self_k[t] = eSelf * empBase;
      out.lb_wage_bill_pct[t] = wageBill * 100;
      out.lb_hour_cost_pct[t] = hourCost * 100;
      out.lb_revenue_pp[t] = lbRevPp;

      // ---- Healthcare capacity (slice 4): demand from the extra residents; money follows it (or not) plus the extra
      // budget; doctors come from extra training places after the lag, each with the average budget per doctor.
      // Money alone buys a share of the capacity (overtime, outsourcing, doctors from abroad); the rest needs doctors.
      const Hl = Lb.health;
      const lag = P.retardo_formacion_medico;
      const trainedK = on ? (L.mir * P.permanencia_sns_medicos * Math.max(0, k - lag)) / 1000 : 0;
      const docBase = Hl.doctors_k * Hl.demo_index[t];
      const doc = trainedK / docBase;
      const money = (follow ? healthDem : 0) + (on ? L.healthSpend / 100 : 0) + doc;
      const w = P.capacidad_por_gasto;
      const cap = w * money + (1 - w) * Math.min(money, doc);
      // Waiting list as a stock: entries grow with demand and fall when waits are longer (demand response to the
      // wait, which keeps the list from emptying or exploding); exits are the capacity while there is a list.
      const E0 = Hl.exits_k;
      const S0 = Hl.list_k;
      const exits = E0 * (1 + cap);
      const waitRel = Math.max(0.05, (S0 + listDev) / exitsPrev / (S0 / E0));
      const entries = E0 * (1 + healthDem) * waitRel ** P.elasticidad_demanda_espera;
      listDev = Math.max(-S0, listDev + entries - exits);
      exitsPrev = exits;
      out.hl_deterred_k[t] = E0 * (1 + healthDem) - entries; // patients who no longer enter the list (private care or none)
      const residents = on ? L.mir * Math.min(k, Math.min(lag, 5)) : 0;
      const trainPp = ((residents * P.coste_residente_anual) / 1e3 / gdp0 / empIdx) * 100;
      hlCostPp = Hl.spend_pct[t] * money + trainPp;
      out.hl_demand_pct[t] = healthDem * 100;
      out.hl_money_pct[t] = money * 100;
      out.hl_doctors_k[t] = trainedK;
      out.hl_capacity_pct[t] = cap * 100;
      out.hl_list_k[t] = listDev;
      out.hl_wait_days[t] = ((S0 + listDev) / exits) * 365;
      out.hl_wait_dev[t] = out.hl_wait_days[t] - (S0 / E0) * 365;
      out.hl_cost_pp[t] = hlCostPp;
      out.mig_gdp_pct[t] = migGdp * 100;
    }

    // ---- Housing (slice 2). Stock and households in thousands; rents, prices and credit as log deviations.
    let hsCostPp = 0;
    if (Hs) {
      const Lp = P.retardo_obra_publica;
      const Lq = P.retardo_obra_privada;
      const pubC = on ? L.pubHomes * ramp(k, Lp) : 0;
      pubStock += pubC;
      const landC = on ? L.land * P.absorcion_suelo * ramp(k, Lq + 1) : 0;
      const crowd = -P.desplazamiento_obra_privada * pubC;
      const privResp = P.elasticidad_oferta_privada * hp[hp.length - 2] * Hs.completions_free_k;
      const completions = pubC + landC + crowd + privResp;
      flowCum += completions;
      privCum += landC + crowd + privResp;
      const freed = on ? (L.tourCut / 100) * Hs.tourist_k * Math.min(1, k / 2) : 0;
      const tourist = P.conversion_turistica * freed;
      const dS = flowCum + tourist;
      // Migration: the official variant moves net migration by about ±46 % (a third more or less non-EU immigration);
      // each extra net migrant forms households.
      const dNet = Lb ? (sMig > 0 ? Lb.net_migration_k.hi[t] - Lb.net_migration_k.base[t] : Lb.net_migration_k.base[t] - Lb.net_migration_k.lo[t]) : Hs.net_migration_k[t] / 3;
      if (on) dHm += sMig * dNet * P.hogares_por_inmigrante;
      // Credit: caps remove part of the new lending above them; new lending follows prices (collateral, loop R2).
      const binding = on ? bindingShare(P, L.ltvCap, L.ltiCap) : 0;
      const cut = -P.perdida_credito_restringido * binding;
      const dNew = cut + P.elasticidad_credito_precio * hp[hp.length - 1];
      dCred = (1 - P.cuota_credito_nuevo) * dCred + P.cuota_credito_nuevo * dNew;
      // Market rent from dwellings per household, with latent households (loop B2) adjusting halfway each year.
      const Hb = Hs.households_k[t];
      const a = C.emancipation_adjust_per_year;
      const E = (P.elasticidad_emancipacion * Hs.at_home_k) / P.personas_por_hogar_nuevo;
      const beta = P.respuesta_alquiler_parque;
      const num = (-beta * (dS - dHm - (1 - a) * dHem)) / Hb + P.sustitucion_alquiler * -cut;
      const dR = num / (1 + (beta * a * E) / Hb);
      dHem = (1 - a) * dHem + a * -E * dR;
      const dP = dR + P.elasticidad_precio_credito * dCred;
      // Rent cap: covered contracts pay less, some landlords leave the market, uncovered rents absorb the shortage.
      const cov = on ? L.capCov / 100 : 0;
      const kappa = (L.capCut / 100) * P.cumplimiento_tope * (cov > 0 ? 1 : 0);
      const W = P.respuesta_oferta_tope * kappa * cov * Hs.renters_k * Math.min(1, k / 2);
      const spill = (P.traslado_escasez_alquiler * W) / Hs.renters_k;
      const rCov = dR - kappa;
      const rUnc = dR + spill;
      const rNew = cov * rCov + (1 - cov) * rUnc;
      const rho = P.renovacion_contratos;
      paidCov += rho * (rCov - paidCov);
      paidUnc += rho * (rUnc - paidUnc);
      const paid = cov * paidCov + (1 - cov) * paidUnc;
      // Public budget: each dwelling is paid in the two years before it is finished; social rents come back.
      const spend = on ? L.pubHomes * P.coste_vivienda_publica * P.cuota_financiacion_publica * (ramp(k + 1, Lp) + ramp(k + 2, Lp)) / 2 : 0;
      const rents = (P.renta_social_mes * 12 * pubStock * P.cuota_financiacion_publica) / 1000;
      hsCostPp = ((spend - rents) / (model.start.gdp_meur * (B.real_index?.[t] ?? 1))) * 100;
      hp.push(dP);
      const c1 = Hs.cases.p1;
      const c2 = Hs.cases.p2_renter;
      const b2 = Hs.cases.p2_buyer;
      const price = b2.home_price * (1 + dP);
      const ltvMax = Math.min(b2.ltv_pct / 100, L.ltvCap && on ? L.ltvCap / 100 : 1, L.ltiCap && on ? (L.ltiCap * c2.gross_year) / price : 1);
      const loan0 = b2.home_price * (b2.ltv_pct / 100);
      const loan = price * ltvMax;
      const set = {
        hs_stock_k: dS, hs_completions_k: completions, hs_public_k: pubStock, hs_private_k: privCum, hs_tourist_k: tourist,
        hs_households_k: dHm + dHem, hs_migration_hh_k: dHm, hs_emancipated_hh_k: dHem,
        hs_emancipated_k: dHem * P.personas_por_hogar_nuevo, hs_at_home_pp: (-dHem * P.personas_por_hogar_nuevo * 100) / Hs.pop_2534_k,
        hs_rent: dR, hs_rent_cov: cov ? rCov : 0, hs_rent_unc: rUnc, hs_rent_new: rNew, hs_rent_paid: paid, hs_price: dP,
        hs_credit: dCred, hs_new_credit: dNew, hs_credit_cut: cut, hs_rental_stock_k: -W, hs_cost_pp: hsCostPp, hs_binding: binding,
        p1_rent_cov_month: cov ? c1.rent_month * rCov : 0, p1_rent_unc_month: c1.rent_month * rUnc, p1_rent_paid_month: c1.rent_month * paid,
        p2r_rent_cov_month: cov ? c2.rent_month * rCov : 0, p2r_rent_unc_month: c2.rent_month * rUnc,
        p2b_payment_month: b2.cost_month * (loan / loan0 - 1),
        p2b_upfront_eur: price * (1 - ltvMax + b2.itp_pct / 100) - b2.home_price * (1 - b2.ltv_pct / 100 + b2.itp_pct / 100),
      };
      for (const [key, v] of Object.entries(set)) out[key][t] = v;
    }

    // Tax levers: statutory revenue and the behavioural response (taxable income, corporate base).
    // Cutting towards zero, the behavioural offset fades out (at no IRPF there is nothing to recoup), and no lever can
    // remove more than the tax raises today: what makes illustrative extremes such as «sin IRPF» add up.
    const abolishPp = C.irpf_revenue_pct ? C.irpf_revenue_pct / P.recaudacion_por_punto_irpf : Infinity;
    const taper = Math.max(0, 1 - Math.max(0, -lv("irpfAll")) / abolishPp);
    const irpfLeverPp = Math.max(
      -(C.irpf_revenue_pct ?? Infinity),
      P.recaudacion_por_punto_irpf * (1 - offAll * taper) * lv("irpfAll") + P.recaudacion_por_punto_irpf_alto * (1 - offTop) * lv("irpfTop"),
    );
    const vatRedPp = P.recaudacion_por_punto_iva_reducido * lv("vatRed");
    const corpStatic = P.recaudacion_por_punto_sociedades * lv("corp");
    const corpTaper = Math.max(0, 1 - Math.max(0, -lv("corp")) / 25); // the 25 % rate: at zero there is no base to shift
    const corpPp = Math.max(-C.corp_revenue_pct, corpStatic - (C.corp_revenue_pct * P.semielasticidad_base_sociedades * corpTaper * lv("corp")) / 100);
    // Part of the corporate tax ends up in lower wages (incidence), here as a fall of the wage bill.
    const wageCorp = (-P.traslado_sociedades_salarios * corpStatic) / P.salarios_pib;

    // Employment from a later retirement: the share of the delayed cohort that stays in work.
    const eAge = (P.permanencia_empleo * P.kappa_cohorte * ageEff * B.pensioners_k[t]) / B.employment_k[t];
    const contribLever = lv("contrib");
    const theta = P.traslado_cotizacion_salario * clamp(k / C.incidence_lag_years, 0, 1);
    const unit = { cotizaciones: P.base_cotizacion_pib, iva: P.recaudacion_por_punto_iva, irpf: irpfUnit }[L.closure];

    // The closure rate depends on the employment it destroys: solve the fixed point within the year.
    let close = 0;
    let parts = null;
    for (let iter = 0; iter < 40; iter += 1) {
      const closeC = L.closure === "cotizaciones" ? close : 0;
      const closeV = L.closure === "iva" ? close : 0;
      const closeI = L.closure === "irpf" ? close : 0;
      const extraRate = contribLever + closeC; // pp of base
      const dTauEr = (es * extraRate) / 100;
      const laborCost = ((1 - theta) * dTauEr) / (1 + C.employer_rate);
      const wageDev = (-theta * dTauEr) / (1 + C.employer_rate) + wageCorp;
      const eTarget = P.elasticidad_empleo_coste * laborCost;
      const eS = on ? eSsc + (eTarget - eSsc) * C.employment_adjust_per_year : 0;
      const e = eAge + eS + eSmi + eHours + eSelf;
      // Fewer jobs lose taxes, contributions and pay benefits; a lower gross wage loses the tax rate on wages.
      const labourPp = P.recaudacion_por_1pct_empleo * 100 * e + P.base_cotizacion_pib * 100 * C.wage_tax_rate * wageDev;
      const contribPp = P.base_cotizacion_pib * extraRate;
      const vatPp = P.recaudacion_por_punto_iva * (lv("vatStd") + closeV);
      const irpfRev = irpfLeverPp + irpfUnit * closeI;
      const taxes = contribPp + vatPp + vatRedPp + irpfRev + corpPp;
      const impulse = P.multiplicador_transferencias * (grossPp + otherPp - irpfPp) - P.multiplicador_impuestos * taxes;
      const yNow = P.persistencia_multiplicador * y + (impulse - impulsePrev);
      const cyclePp = P.semielasticidad_saldo * yNow;
      const leverTaxes = P.base_cotizacion_pib * contribLever + P.recaudacion_por_punto_iva * lv("vatStd") + vatRedPp + irpfLeverPp + corpPp;
      const costBefore = grossPp + otherPp - irpfPp + migCostPp + hlCostPp - lbRevPp + hsCostPp - labourPp - leverTaxes - cyclePp;
      const closureRevenue = unit ? unit * close : 0;
      parts = { e, eS, wageDev, laborCost, labourPp, contribPp, vatPp, irpfRev, impulse, yNow, cyclePp, costBefore, closureRevenue, closeC, closeV, closeI };
      if (!on || L.closure === "deuda") break;
      // Taxes are set to cover the cost before second-round effects, as a budget would; those go to the deficit.
      const gap = costBefore + cyclePp - closureRevenue;
      close += gap / unit;
      if (Math.abs(gap) < 1e-12) break;
    }
    const { e, eS, wageDev, laborCost, labourPp, contribPp, vatPp, irpfRev, impulse, yNow, cyclePp, costBefore, closureRevenue, closeC, closeV, closeI } = parts;
    eSsc = eS;
    y = yNow;
    impulsePrev = impulse;
    const primary = costBefore - closureRevenue;

    // VAT raises the price level with pass-through on the basket taxed at each rate.
    const price =
      (P.traslado_iva_precios *
        ((P.cuota_iva_general * (lv("vatStd") + closeV)) / (1 + C.vat_standard_rate) + (C.vat_reduced_basket_share * lv("vatRed")) / (1 + C.vat_reduced_rate))) /
      100;

    // Debt: interest on the extra debt, a risk premium on the extra debt, repricing at the refinancing share.
    const dMarket = (P.prima_por_deuda * D) / 100 + (on ? L.rateShock : 0);
    dImp = (1 - P.cuota_refinanciacion) * dImp + P.cuota_refinanciacion * dMarket;
    const debtPrev = B.debt_pct[t - 1] + D;
    const interestDev = (i * D + (dImp / 100) * debtPrev) / (1 + g);
    D = D / (1 + g) + primary + interestDev;

    const supply = (C.labour_output_elasticity * (e + lbSupply) + migGdp) * 100; // % GDP
    const gdpDev = supply + yNow;
    const denom = 1 + gdpDev / 100;

    out.pension_dev[t] = x;
    out.pensioners_dev[t] = nDev;
    out.employment_dev[t] = e;
    out.employment_k[t] = e * B.employment_k[t];
    out.gdp_dev[t] = gdpDev;
    out.pension_gross_pp[t] = grossPp;
    out.other_benefits_pp[t] = otherPp;
    out.irpf_back_pp[t] = irpfPp;
    out.labour_revenue_pp[t] = labourPp;
    out.contrib_revenue_pp[t] = contribPp;
    out.vat_revenue_pp[t] = vatPp;
    out.vat_red_revenue_pp[t] = vatRedPp;
    out.irpf_revenue_pp[t] = irpfRev;
    out.corp_revenue_pp[t] = corpPp;
    out.cycle_revenue_pp[t] = cyclePp;
    out.migration_pp[t] = migPp;
    out.net_cost_pp[t] = costBefore;
    out.primary_dev_pp[t] = primary;
    out.interest_dev_pp[t] = interestDev;
    out.debt_dev_pp[t] = D;
    out.closure_contrib_pp[t] = closeC;
    out.closure_vat_pp[t] = closeV;
    out.closure_irpf_pp[t] = closeI;
    out.price_level_dev[t] = price;
    out.labour_cost_dev[t] = laborCost;
    out.wage_dev[t] = wageDev;
    out.implicit_rate_dev[t] = dImp;
    out.pension_pct[t] = (base + grossPp + migPp) / denom;
    out.debt_pct[t] = (B.debt_pct[t] + D) / denom;
    out.deficit_pct[t] = (B.deficit_pct[t] + primary + interestDev) / denom;
    out.debt_per_person_eur[t] = ((D / 100) * model.start.gdp_meur * 1e6) / model.start.population;

    // Statutory burdens (before behaviour), what the quintile split distributes.
    const allPp = lv("irpfAll") + closeI;
    out.s_irpf_all_pp[t] = P.recaudacion_por_punto_irpf * allPp;
    out.s_irpf_top_pp[t] = P.recaudacion_por_punto_irpf_alto * lv("irpfTop");
    out.s_vat_std_pp[t] = P.recaudacion_por_punto_iva * (lv("vatStd") + closeV);
    out.s_vat_red_pp[t] = vatRedPp;
    out.s_contrib_pp[t] = contribPp;
    out.s_corp_pp[t] = corpStatic;
    out.s_pension_net_pp[t] = grossPp - P.tipo_marginal_irpf_pension * grossPp;

    // Typical cases, euros a month at base-year prices. Worker contributions are deductible in IRPF; a lower gross
    // wage loses the full personal marginal rate; prices hit what they spend (all their net income).
    const workerRate = ((1 - es) * (contribLever + closeC)) / 100;
    for (const id of PERSONAS) {
      const pc = model.personas[id];
      if (!pc) continue;
      let v = 0;
      if (pc.pension_gross) {
        v += pc.pension_gross * z * (1 - P.tipo_marginal_irpf_pension) - pc.net * (price - pricePrev);
      } else {
        // Nor can a contribution cut return more than the worker's own contributions.
        v += -pc.gross * Math.max(-pc.worker_ssc_rate, workerRate) * (1 - (pc.marginal_total - pc.worker_ssc_rate));
        v += pc.gross * wageDev * (1 - pc.marginal_total);
        v += -pc.net * (price - P.indiciacion_salarios * pricePrev);
      }
      // A tax cut cannot return more than the case pays today (illustrative extremes such as abolishing the IRPF).
      v += Math.min(pc.irpf_paid ?? Infinity, (-allPp / 100) * pc.irpf_liable - (lv("irpfTop") / 100) * pc.irpf_above_top);
      out[`${id}_month`][t] = v / 12;
    }
    pricePrev = price;
  }
  return out;
}

/**
 * Who bears the statutory change in year index t, by income quintile: euros a month per household (base-year
 * prices) and % of disposable income, per instrument. Shares from microdata (sistema.json `incidence`), totals from
 * the run. Positive = more income.
 */
export function quintileImpact(model, run, t, params = centralParams(model)) {
  const inc = model.incidence;
  const C = model.constants;
  const gdpEur = model.start.gdp_meur * 1e6 * (model.baseline.real_index?.[t] ?? 1);
  const es = C.employer_share;
  const theta = params.traslado_cotizacion_salario;
  const wc = params.traslado_sociedades_salarios;
  const parts = {
    irpf: (q) => -(run.s_irpf_all_pp[t] * q.share_base_all + run.s_irpf_top_pp[t] * q.share_base_top),
    iva: (q) => -(run.s_vat_std_pp[t] * inc.vat.by_rate["21"][q.q] + run.s_vat_red_pp[t] * inc.vat.by_rate["10"][q.q]),
    cotizaciones: (q) => -run.s_contrib_pp[t] * (1 - es + es * theta) * q.share_wages,
    sociedades: (q) => -run.s_corp_pp[t] * ((1 - wc) * q.share_capital + wc * q.share_wages),
    pensiones: (q) => run.s_pension_net_pp[t] * q.share_pensions,
  };
  return inc.ecv.quintiles.map((q) => {
    const byPart = Object.fromEntries(
      Object.entries(parts).map(([name, f]) => [name, (f(q) / 100) * gdpEur / q.households / 12]),
    );
    const total = Object.values(byPart).reduce((a, b) => a + b, 0);
    return { q: q.q, byPart, total, pctDisposable: ((total * 12) / q.disposable_per_household) * 100 };
  });
}

// Deterministic PRNG so a shared link reproduces the same bands.
function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function triangular(u, lo, mode, hi) {
  if (hi <= lo) return mode;
  const f = (mode - lo) / (hi - lo);
  return u < f ? lo + Math.sqrt(u * (hi - lo) * (mode - lo)) : hi - Math.sqrt((1 - u) * (hi - lo) * (hi - mode));
}

/** Latin-hypercube draws of every parameter (triangular on low/central/high; a chosen debate school sets the mode). */
export function drawParams(model, draws = 200, seed = 20261019, debates = {}) {
  const rand = mulberry32(seed);
  const names = Object.keys(model.params);
  const strata = names.map(() => {
    const idx = Array.from({ length: draws }, (_, j) => j);
    for (let j = draws - 1; j > 0; j -= 1) {
      const s = Math.floor(rand() * (j + 1));
      [idx[j], idx[s]] = [idx[s], idx[j]];
    }
    return idx;
  });
  const central = centralParams(model, debates);
  return Array.from({ length: draws }, (_, d) => {
    const p = {};
    names.forEach((name, k) => {
      const spec = model.params[name];
      const u = (strata[k][d] + rand()) / draws;
      const mode = clamp(central[name], spec.low, spec.high);
      p[name] = triangular(u, spec.low, mode, spec.high);
    });
    return p;
  });
}

const quantile = (sorted, q) => {
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
};

/**
 * Central run + bands (5th/95th percentile over the draws) + robustness of the sign at each year, and which
 * parameter moves each output most (rank correlation with the draw values).
 */
export function runEnsemble(model, levers, { draws = 200, seed = 20261019, debates = {}, layer = "segunda_ronda", keys } = {}) {
  const centralP = applyLayer(model, centralParams(model, debates), layer);
  const central = simulate(model, levers, centralP);
  const sample = drawParams(model, draws, seed, debates).map((p) => applyLayer(model, p, layer));
  const runs = sample.map((p) => simulate(model, levers, p));
  const fields = keys || Object.keys(central).filter((key) => Array.isArray(central[key]) && key !== "years");
  const bands = {};
  for (const key of fields) {
    const lo = [];
    const hi = [];
    const same = [];
    for (let t = 0; t < model.years.length; t += 1) {
      const values = runs.map((run) => run[key][t]).sort((a, b) => a - b);
      lo.push(quantile(values, 0.05));
      hi.push(quantile(values, 0.95));
      const c = central[key][t];
      const sign = Math.sign(c);
      same.push(sign === 0 ? 1 : values.filter((v) => Math.sign(v) === sign).length / values.length);
    }
    bands[key] = { lo, hi, sameSign: same };
  }
  return { central, bands, sample, runs };
}

/** Parameter whose draws are most correlated (Spearman) with `key` at year index t. */
export function mainDriver(model, ensemble, key, t) {
  const values = Array.isArray(key) ? key : ensemble.runs.map((run) => run[key][t]);
  const rank = (arr) => {
    const order = arr.map((v, j) => [v, j]).sort((a, b) => a[0] - b[0]);
    const r = new Array(arr.length);
    order.forEach(([, j], pos) => {
      r[j] = pos;
    });
    return r;
  };
  const ry = rank(values);
  const mean = (values.length - 1) / 2;
  let best = null;
  for (const name of Object.keys(model.params)) {
    const rx = rank(ensemble.sample.map((p) => p[name]));
    let num = 0;
    let dx = 0;
    let dy = 0;
    for (let j = 0; j < values.length; j += 1) {
      num += (rx[j] - mean) * (ry[j] - mean);
      dx += (rx[j] - mean) ** 2;
      dy += (ry[j] - mean) ** 2;
    }
    const rho = dx && dy ? num / Math.sqrt(dx * dy) : 0;
    if (!best || Math.abs(rho) > Math.abs(best.rho)) best = { name, rho };
  }
  return best;
}

/** Accounting cost of revaluing the whole stock by `rate` (fraction) on spending `meur`: used by the backtests. */
export function revaluationCost(rate, meur) {
  return rate * meur;
}

/** Cumulative real change of an existing pension when revalued by `nominal` (fractions) against `cpi` each year. */
export function realChange(nominal, cpi) {
  return nominal.reduce((acc, v, j) => (acc * (1 + v)) / (1 + cpi[j]), 1) - 1;
}

// URL fragment state: explicit, shareable, never in the query string.
export function encodeState(levers, debates = {}, extra = {}) {
  const parts = [];
  for (const [key, value] of Object.entries({ ...levers, ...extra })) {
    if (value !== DEFAULT_LEVERS[key]) parts.push(`${key}=${encodeURIComponent(value)}`);
  }
  for (const [key, value] of Object.entries(debates)) parts.push(`d.${key}=${value}`);
  return parts.join("&");
}

export function decodeState(hash) {
  const levers = { ...DEFAULT_LEVERS };
  const debates = {};
  const extra = {};
  for (const part of String(hash || "").replace(/^#/, "").split("&")) {
    const [key, raw] = part.split("=");
    if (!key || raw == null) continue;
    const value = decodeURIComponent(raw);
    if (key.startsWith("d.")) debates[key.slice(2)] = Number(value);
    else if (key in DEFAULT_LEVERS) levers[key] = typeof DEFAULT_LEVERS[key] === "number" ? Number(value) : value;
    else extra[key] = value;
  }
  return { levers, debates, extra };
}
