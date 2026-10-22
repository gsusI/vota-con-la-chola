// Search and share copy for the /visualizaciones/ articles: title, finding, description, FAQ and share card.
// Every number is read from the same published JSON the page renders, never typed in, so the copy follows the data.
// Wording follows AGENTS.md «Public Data Visualizations»: findings carry their number, co-movement is not cause.

export const VIZ_SLUGS = ["carga-fiscal", "empleo", "vivienda", "educacion", "sanidad"];

// First commit of each page (git log); dateModified comes from the data file's generated_at.
const PUBLISHED = {
  "carga-fiscal": "2026-10-19T10:06:36+02:00",
  empleo: "2026-10-19T10:54:25+02:00",
  vivienda: "2026-10-19T11:00:37+02:00",
  educacion: "2026-10-19T11:02:06+02:00",
  sanidad: "2026-10-19T11:05:33+02:00",
};

export const num = (value, digits = 1) =>
  Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const pct = (value, digits = 1) => `${num(value, digits)} %`;
const count = (value) => Math.round(Number(value)).toLocaleString("es-ES", { useGrouping: "always" });
const howMany = (value, noun) =>
  Math.abs(Number(value)) >= 1e6 ? `${num(Number(value) / 1e6, 2)} millones de ${noun}` : `${count(value)} ${noun}`;
const at = (rows, year) => rows?.find((row) => row.year === year)?.value;
// «y» becomes «e» before an /i/ sound (Italia).
const listJoin = (items) =>
  items.length > 1 ? `${items.slice(0, -1).join(", ")} ${/^h?i(?![aeou])/i.test(items.at(-1)) ? "e" : "y"} ${items.at(-1)}` : items[0] || "";
const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
const cutLabel = (date) => `${MONTHS[Number(date.slice(5, 7)) - 1]} de ${date.slice(0, 4)}`;

export const SIMULATOR = { href: "/visualizaciones/sistema/", anchor: "Simulador de políticas: pensiones, impuestos y vivienda hasta 2050", note: "Cambia una palanca y mira qué pasa con la deuda y con cuatro hogares tipo." };
export const QUIZ = { href: "/citizen/vota/", anchor: "¿Con quién coincides? Compara tus respuestas con lo que votó cada partido", note: "Test sobre votaciones reales del Congreso." };

// Static per-article facts: keyword anchor for internal links, topic, related reading.
export const ARTICLES = {
  "carga-fiscal": {
    topic: "Impuestos",
    anchor: "presión fiscal en España",
    linkText: "Presión fiscal en España desde 1925: quién paga y a dónde va",
    about: ["Presión fiscal", "Impuestos en España", "Cotizaciones sociales", "Gasto público"],
    keywords: ["presión fiscal España", "impuestos en España", "presión fiscal OCDE", "recaudación por habitante", "quién paga impuestos", "gasto público España"],
    related: ["sanidad", "educacion", "empleo"],
    extra: [SIMULATOR],
  },
  empleo: {
    topic: "Empleo",
    anchor: "evolución del paro en España",
    linkText: "Evolución del paro en España frente a Europa desde 1960",
    about: ["Desempleo", "Paro en España", "Temporalidad", "Productividad"],
    keywords: ["paro en España", "evolución del paro en España", "tasa de paro", "paro estructural", "paro juvenil", "temporalidad", "productividad por hora"],
    related: ["vivienda", "educacion", "carga-fiscal"],
    extra: [SIMULATOR, QUIZ],
  },
  vivienda: {
    topic: "Vivienda",
    anchor: "precio de la vivienda en años de sueldo",
    linkText: "Precio de la vivienda en años de sueldo y viviendas por hogar nuevo",
    about: ["Vivienda", "Precio de la vivienda", "Alquiler", "Emancipación"],
    keywords: ["precio de la vivienda en años de sueldo", "vivienda España", "faltan viviendas", "edad de emancipación", "alquiler", "gasto público en vivienda"],
    related: ["empleo", "carga-fiscal", "sanidad"],
    extra: [SIMULATOR, QUIZ],
  },
  educacion: {
    topic: "Educación",
    anchor: "gasto en educación por alumno",
    linkText: "Gasto en educación por alumno, PISA y abandono escolar",
    about: ["Educación", "Gasto en educación", "PISA", "Abandono escolar temprano"],
    keywords: ["gasto en educación por alumno", "educación España", "PISA España", "abandono escolar temprano", "repetición de curso", "sobrecualificación"],
    related: ["empleo", "sanidad", "carga-fiscal"],
    extra: [QUIZ],
  },
  sanidad: {
    topic: "Sanidad",
    anchor: "esperanza de vida y listas de espera",
    linkText: "Esperanza de vida, gasto sanitario y listas de espera en España",
    about: ["Sanidad", "Esperanza de vida", "Listas de espera", "Gasto sanitario público"],
    keywords: ["esperanza de vida España", "listas de espera", "gasto sanitario", "sanidad pública", "médico de familia", "lista de espera quirúrgica"],
    related: ["carga-fiscal", "educacion", "vivienda"],
    extra: [SIMULATOR],
  },
};

export const vizPath = (slug) => `/visualizaciones/${slug}/`;
export const cardPath = (slug) => `/visualizaciones/og/${slug}.png`;
export const downloadsOf = (slug) => [
  { path: `/visualizaciones/data/${slug}.csv`, format: "text/csv" },
  { path: `/visualizaciones/data/${slug}.json`, format: "application/json" },
];
export const sourcesOf = (data) =>
  Object.values(data.sources || {})
    .filter((s) => s?.page && s?.label)
    .map((s) => ({ name: s.label, url: s.page }));

function cargaFiscal(d) {
  const h = d.headline;
  const peers = d.peers_pct_gdp;
  const last = (area) => peers[area].at(-1);
  const eu = d.eu27_pct_gdp.at(-1);
  const payer = d.by_payer_pct_gdp.at(-1);
  const sp = d.spending.areas.find((row) => row.area === "ES");
  const sqEs = d.squeeze.areas.find((row) => row.area === "ES");
  const sqEu = d.squeeze.areas.find((row) => row.area === "EU27_2020");
  const NAMES = { DEU: "Alemania", FRA: "Francia", ITA: "Italia", PRT: "Portugal" };
  const countries = Object.keys(NAMES);
  const higher = countries.filter((a) => last(a).value > h.last_value).sort((a, b) => last(b).value - last(a).value);
  const lower = countries.filter((a) => last(a).value <= h.last_value);
  const named = (list) => listJoin(list.map((a) => `${NAMES[a]} (${pct(last(a).value)})`));
  const rise = (a) => last(a).value - peers[a][0].value;
  const esRise = h.last_value - h.oecd_first_value;
  const biggest = countries.every((a) => rise(a) < esRise);
  const oecd = last("OECD_REP");
  return {
    title: `Presión fiscal en España: ${pct(h.last_value)} del PIB`,
    headline: `La presión fiscal en España pasó del ${pct(h.oecd_first_value)} del PIB en ${h.oecd_first_year} al ${pct(h.last_value)} en ${h.last_year}`,
    description: `Impuestos y cotizaciones: ${pct(h.last_value)} del PIB en ${h.last_year} (media OCDE: ${pct(oecd.value)}; ${pct(h.oecd_first_value)} en ${h.oecd_first_year}). Quién paga, a dónde va y comparación con Europa.`,
    card: {
      big: pct(h.last_value),
      bigLabel: `del PIB en impuestos y cotizaciones (${h.last_year})`,
      line: `${pct(h.oecd_first_value)} en ${h.oecd_first_year}; media OCDE hoy: ${pct(oecd.value)}`,
      spark: { series: [{ points: d.long_run.oecd_tax_pct_gdp, main: true }], label: `% del PIB, ${h.oecd_first_year}–${h.last_year} (OCDE)` },
    },
    faqs: [
      {
        q: "¿Cuál es la presión fiscal en España?",
        a: `En ${h.last_year}, los impuestos y cotizaciones sociales de todas las administraciones sumaron el ${pct(h.last_value)} del PIB según la OCDE. Con la definición de Eurostat fue el ${pct(eu.es)}, frente al ${pct(eu.eu27)} de la UE-27 (${eu.year}).`,
      },
      {
        q: "¿Es alta la presión fiscal en España comparada con Europa?",
        a: `Está por debajo de la UE-27 (${pct(eu.es)} frente a ${pct(eu.eu27)} del PIB, Eurostat) y por encima de la media de la OCDE (${pct(h.last_value)} frente a ${pct(oecd.value)}). ${higher.length ? `${named(higher)} recaudan más en proporción a su PIB` : ""}${higher.length && lower.length ? "; " : ""}${lower.length ? `${named(lower)}, menos` : ""}.`,
      },
      {
        q: "¿Cuánto ha subido la presión fiscal en España?",
        a: `Del ${pct(h.oecd_first_value)} del PIB en ${h.oecd_first_year} al ${pct(h.last_value)} en ${h.last_year}: ${num(esRise)} puntos más${biggest ? ", la mayor subida frente a Alemania, Francia, Italia y Portugal" : ""}. Antes de ${h.oecd_first_year} solo hay datos del Estado central (${pct(h.first_value_imf)} del PIB en ${h.first_year}, FMI), que no se empalman con la serie de la OCDE.`,
      },
      {
        q: "¿Han subido los impuestos más que la renta de los hogares?",
        a: `Desde ${d.squeeze.base_year}, por habitante y descontada la inflación, la recaudación subió un ${pct(sqEs.real_tax_change_pct)} y la renta de los hogares un ${pct(sqEs.real_income_change_pct)}; en la UE, un ${pct(sqEu.real_tax_change_pct)} y un ${pct(sqEu.real_income_change_pct)}. La recaudación por habitante incluye lo que pagan las empresas, así que no es lo que paga cada persona.`,
      },
      {
        q: "¿Quién paga los impuestos en España?",
        a: `En ${payer.year}, los tributos sobre las personas (IRPF y cotizaciones del trabajador y de autónomos) sumaron el ${pct(payer.households)} del PIB; los de las empresas (Sociedades y cotizaciones empresariales), el ${pct(payer.companies)}; el consumo (IVA e impuestos especiales), el ${pct(payer.consumption)}, y la propiedad, el ${pct(payer.property)}. Se clasifica por quién ingresa legalmente cada tributo, no por quién lo soporta.`,
      },
      {
        q: "¿A dónde va el dinero de los impuestos?",
        a: `El gasto público fue el ${pct(sp.total)} del PIB en ${d.spending.year}: pensiones ${pct(sp.pensions)}, sanidad ${pct(sp.health)}, resto de protección social ${pct(sp.social)}, educación ${pct(sp.education)}, intereses de la deuda ${pct(sp.interest)} y todo lo demás ${pct(sp.rest)}. El gasto en pensiones ha subido ${num(sp.parts_change.pensions)} puntos del PIB desde ${sp.parts_base_year}.`,
      },
    ],
  };
}

function empleo(d) {
  const h = d.headline;
  const g = h.productivity_growth_pct;
  const u = d.unemployment.amecos;
  return {
    title: `Paro en España: ${pct(h.es_last)}, ${num(h.ratio_eu27_last, 2)} veces la UE`,
    headline: `Desde ${h.hypothesis_from}, el paro de España ha sido de media ${num(h.ratio_mean_since, 2)} veces el europeo; en ${h.last_year}, ${pct(h.es_last)} frente a ${pct(h.eu27_last)}`,
    description: `Evolución del paro en España desde ${h.first_year}: ${pct(h.es_last)} en ${h.last_year} (UE-27: ${pct(h.eu27_last)}), ${num(h.ratio_mean_since, 2)} veces el europeo de media desde ${h.hypothesis_from}. Causas, temporalidad y productividad.`,
    card: {
      big: `×${num(h.ratio_mean_since, 2)}`,
      bigLabel: `el paro europeo, de media desde ${h.hypothesis_from}`,
      line: `${pct(h.es_last)} en ${h.last_year} frente a ${pct(h.eu27_last)} en la UE-27`,
      spark: {
        series: [
          { points: u.DU15 },
          { points: u.EU15 },
          { points: u.ESP, main: true },
        ],
        label: `Tasa de paro, España (azul) y UE-15, ${h.first_year}–${h.last_year}`,
      },
    },
    faqs: [
      {
        q: "¿Cuál es la tasa de paro en España?",
        a: `El ${pct(h.es_last)} de la población activa en ${h.last_year} (media anual, Comisión Europea), frente al ${pct(h.eu27_last)} de la UE-27: ${num(h.ratio_eu27_last, 2)} veces. El mínimo reciente fue el ${pct(h.peaks.min_pre_crisis.value)} en ${h.peaks.min_pre_crisis.year} y el máximo, el ${pct(h.peaks.max_crisis.value)} en ${h.peaks.max_crisis.year}.`,
      },
      {
        q: "¿El paro en España es estructural o cíclico?",
        a: `Las dos cosas. Desde ${h.hypothesis_from} ha estado por encima de 1,5 veces el europeo en ${h.years_ratio_ge_1_5} de ${h.years_since} años, y la Comisión Europea estima su paro estructural (NAWRU) en el ${pct(h.nawru_last)}, frente al ${pct(h.nawru_eu15_last)} de la UE-15. El ciclo lo amplía: del ${pct(h.peaks.min_pre_crisis.value)} en ${h.peaks.min_pre_crisis.year} al ${pct(h.peaks.max_crisis.value)} en ${h.peaks.max_crisis.year}.`,
      },
      {
        q: "¿Por qué el paro en España es tan alto?",
        a: `Entre ${h.before_years[0]} y ${h.before_years[1]} era de media similar al europeo (${num(h.ratio_mean_before_gap)} veces); la brecha se abre desde ${h.gap_from_year}. La página contrasta con datos las explicaciones habituales (contratos temporales, peso de la construcción, nivel educativo, tamaño de las empresas, salario mínimo) y publica lo que no encaja: que dos cosas se muevan juntas no prueba la causa.`,
      },
      {
        q: "¿Cuál es el paro juvenil en España?",
        a: `El ${pct(h.youth_es_last)} de los jóvenes activos de 15 a 24 años en ${h.last_year}, frente al ${pct(h.youth_eu_last)} de la UE-27; llegó al ${pct(h.youth_es_max.value)} en ${h.youth_es_max.year}. Se calcula sobre los jóvenes que trabajan o buscan empleo, no sobre todos: muchos estudian.`,
      },
      {
        q: "¿Cuánta temporalidad hay en España?",
        a: `El ${pct(h.temp_es_last)} de los asalariados de 15 a 64 años tenía contrato temporal en ${h.temp_last_year} (UE: ${pct(h.temp_eu_last)}, Eurostat), frente al ${pct(h.temp_es_2021)} de 2021 y al ${pct(h.temp_es_max.value)} de ${h.temp_es_max.year}. Los fijos discontinuos pasaron de ${count(h.discont_k_2021)} mil a ${count(h.discont_k_last)} mil (EPA).`,
      },
      {
        q: "¿Cuánto ha crecido la productividad en España?",
        a: `La productividad por hora trabajada creció un ${pct(g.ESP)} entre ${h.productivity_base} y ${h.productivity_last}, frente al ${pct(g.EU27)} de la UE-27, el ${pct(g.DEU)} de Alemania, el ${pct(g.FRA)} de Francia y el ${pct(g.ITA)} de Italia.`,
      },
    ],
  };
}

function vivienda(d) {
  const h = d.headline;
  const s13 = h.since_2013;
  const boom = h.boom;
  const nms = d.capacity.years_net_median_sale_price;
  const nmsLast = nms.at(-1);
  const B = d.bases;
  const leave = d.leaving_home_age;
  const leaveEs = leave.ES.at(-1);
  const leaveEu = leave.EU27_2020.at(-1);
  const spend = d.public_spending_pct_gdp;
  const spEs = spend.ES.at(-1);
  const spEu = spend.EU27_2020.at(-1);
  const seg = d.segments;
  const segT = Object.fromEntries(seg.tenure.map((row) => [row.key, row]));
  const tenantsEu = d.capacity.peers.overburden_tenants.EU27_2020.at(-1);
  const ten = d.tenure;
  const ownPeak = ten.census.reduce((best, row) => (row.owner > best.owner ? row : best), ten.census[0]);
  const ownLast = ten.census.at(-1);
  return {
    title: `Un piso cuesta ${num(nmsLast.value)} años de sueldo neto`,
    headline: `Un piso de ${h.home_m2} m² cuesta ${num(nmsLast.value)} años de sueldo neto mediano (${nmsLast.year}); desde ${s13.from}, ${num(s13.ratio, 2)} viviendas por hogar nuevo`,
    description: `Precio de la vivienda en años de sueldo: ${num(nmsLast.value)} en ${nmsLast.year} (${num(at(nms, 2013))} en 2013). Desde ${s13.from}, ${num(s13.ratio, 2)} viviendas terminadas por hogar nuevo. Alquiler y emancipación.`,
    card: {
      big: num(nmsLast.value),
      bigLabel: `años de sueldo neto mediano por un piso de ${h.home_m2} m² (${nmsLast.year})`,
      line: `Desde ${s13.from}: ${howMany(s13.completed, "viviendas")} terminadas y ${howMany(s13.net_households, "hogares nuevos")}`,
      spark: { series: [{ points: nms, main: true }], label: `Años de sueldo neto mediano por un piso, ${nms[0].year}–${nmsLast.year}` },
    },
    faqs: [
      {
        q: "¿Cuántos años de sueldo cuesta una vivienda en España?",
        a: `Un piso de ${h.home_m2} m², al precio de compraventa del INE, costaba ${num(nmsLast.value)} años de sueldo neto mediano en ${nmsLast.year}: ${num(at(nms, 2019))} en 2019, ${num(at(nms, 2013))} en 2013 y ${num(nms[0].value)} en ${nms[0].year}. Con el salario bruto medio y el valor de tasación salen ${num(B.years_appraisal[String(B.last_year)])} años (${B.last_year}).`,
      },
      {
        q: "¿Faltan viviendas en España?",
        a: `Desde ${s13.from} se han terminado ${howMany(s13.completed, "viviendas")} y se han formado ${howMany(s13.net_households, "hogares nuevos")}: ${num(s13.ratio, 2)} viviendas por hogar nuevo. Entre ${boom.from} y ${boom.to} se terminaron ${num(boom.ratio, 2)} por hogar nuevo y a la vez el piso pasó de ${num(B.years_appraisal["2000"])} a ${num(B.years_appraisal["2007"])} años de salario bruto medio (2000 a 2007, a precio de tasación): la página publica también esa contraevidencia.`,
      },
      {
        q: "¿A qué edad se independizan los jóvenes en España?",
        a: `A los ${num(leaveEs.value)} años de media en ${leaveEs.year}, frente a ${num(leaveEu.value)} en la media de la UE (Eurostat). En 2008 era a los ${num(at(leave.ES, 2008))}.`,
      },
      {
        q: "¿Cuánto de su renta gastan en vivienda los que alquilan?",
        a: `El ${pct(segT.RENT_MKT.overburden_pct)} de quienes alquilan a precio de mercado dedica más del 40 % de su renta a la vivienda (UE: ${pct(tenantsEu.value)}), frente al ${pct(segT.OWN_NL.overburden_pct)} de quienes tienen la casa pagada y el ${pct(seg.overburden_total)} de toda la población (${seg.year}).`,
      },
      {
        q: "¿Cuántos hogares tienen la vivienda en propiedad?",
        a: `Según los censos del INE, la propiedad tocó techo en ${ownPeak.year} (${pct(ownPeak.owner)} de los hogares) y bajó al ${pct(ownLast.owner)} en ${ownLast.year}; el alquiler llegó al ${pct(ownLast.rent)}.`,
      },
      {
        q: "¿Cuánto gasta el Estado en vivienda?",
        a: `El gasto público directo en vivienda fue el ${num(spEs.total, 2)} % del PIB en ${spEs.year}, frente al ${num(spEu.total, 2)} % de media en la UE (Eurostat).`,
      },
    ],
  };
}

function educacion(d) {
  const h = d.headline;
  const el = d.early_leavers;
  return {
    title: `Gasto por alumno: ${h.spending_school_vs_oecd_pct} % de la media OCDE`,
    headline: `España gasta por alumno el ${h.spending_school_vs_oecd_pct} % de la media OCDE; en 2005 gastaba el ${h.spending_school_vs_oecd_2005_pct} %`,
    description: `Gasto en educación por alumno: ${h.spending_school_vs_oecd_pct} % de la media OCDE (${h.spending_school_last_year}). PISA matemáticas: ${h.math_2022}. Abandono escolar: ${pct(h.leavers_2008)} en 2008, ${pct(h.leavers_last)} en ${h.leavers_last_year}.`,
    card: {
      big: `${h.spending_school_vs_oecd_pct} %`,
      bigLabel: `de la media OCDE en gasto público por alumno (${h.spending_school_last_year})`,
      line: `Abandono escolar: del ${pct(h.leavers_2008)} en 2008 al ${pct(h.leavers_last)} en ${h.leavers_last_year} (UE-27: ${pct(h.leavers_eu_last)})`,
      spark: {
        series: [{ points: el.series.EU27_2020 }, { points: el.series.ES, main: true }],
        breaks: el.breaks,
        label: `Abandono escolar temprano, España (azul) y UE-27; rupturas de serie marcadas`,
      },
    },
    faqs: [
      {
        q: "¿Cuánto gasta España en educación por alumno?",
        a: `En ${h.spending_school_last_year}, el gasto público por alumno de Primaria a Bachillerato y FP fue el ${h.spending_school_vs_oecd_pct} % de la media de la OCDE (en 2005, el ${h.spending_school_vs_oecd_2005_pct} %). Con Eurostat, ${count(h.pps_es)} PPS por alumno en ${h.pps_last_year} frente a ${count(h.pps_eu)} en la UE-27. En términos reales es un ${h.spending_school_change_2000_pct} % mayor que en 2000, con el máximo en ${h.spending_school_peak.year}.`,
      },
      {
        q: "¿Cómo queda España en PISA?",
        a: `En matemáticas, ${h.math_2022} puntos en 2022 frente a ${h.math_2003} en 2003; la media de los mismos ${d.pisa.oecd_fixed_set.n} países de la OCDE cayó más, de ${num(h.oecd28_math_2003)} a ${num(h.oecd28_math_2022)}. En lectura, ${h.reading_2022} puntos (${h.reading_2000} en 2000) y en ciencias, ${h.science_2022} (${h.science_2006} en 2006).`,
      },
      {
        q: "¿Cuál es la tasa de abandono escolar en España?",
        a: `El ${pct(h.leavers_last)} de los jóvenes de 18 a 24 años en ${h.leavers_last_year} no tenía estudios más allá de la ESO ni seguía formándose, frente al ${pct(h.leavers_2008)} de 2008 y al ${pct(h.leavers_eu_last)} de la UE-27. Va del ${pct(h.leavers_mother_high)} de los jóvenes con madre universitaria al ${pct(h.leavers_mother_low)} de los que tienen madre con Primaria o menos.`,
      },
      {
        q: "¿Cuántos alumnos van retrasados de curso?",
        a: `A los 15 años, el ${pct(h.behind_last.value)} del alumnado iba retrasado de curso en ${h.behind_last.course}, frente al ${pct(h.behind_first.value)} de ${h.behind_first.course} y el ${pct(h.behind_peak.value)} del máximo de ${h.behind_peak.course}.`,
      },
      {
        q: "¿Cuántos universitarios trabajan en empleos que no requieren su título?",
        a: `El ${pct(h.overq_es)} de los titulados superiores ocupados en ${h.overq_year}, frente al ${pct(h.overq_eu)} de la UE-27 (Eurostat).`,
      },
    ],
  };
}

function sanidad(d) {
  const h = d.headline;
  const le = h.life_expectancy;
  const sp = h.spending;
  const w = h.waiting;
  const es1925 = d.life_expectancy.long_run.ESP[0];
  const ppsRatio = (sp.pps_es / sp.pps_eu27) * 100;
  const adjRatio = (ppsRatio * 100) / d.age_adjusted.spain_need;
  const change = (from, to) => ((to - from) / from) * 100;
  const gp = d.segments.gaps.find((row) => row.id === "cita_mf");
  const since = cutLabel(w.comparable_since);
  const lastCut = cutLabel(w.last_cut);
  return {
    title: `Esperanza de vida en España: ${num(le.es)} años`,
    headline: `En España se vive ${num(le.es - le.eu27)} años más que en la UE con un gasto sanitario público por habitante del ${num(ppsRatio, 0)} % de la media`,
    description: `Esperanza de vida: ${num(le.es)} años en ${le.year} (UE: ${num(le.eu27)}). Gasto público por habitante: ${num(ppsRatio, 0)} % de la UE. Listas de espera: ${num(w.selected_days[1], 0)} días en las operaciones más comunes.`,
    card: {
      big: `${num(le.es)} años`,
      bigLabel: `de esperanza de vida al nacer (${le.year}); UE-27: ${num(le.eu27)}`,
      line: `Gasto público por habitante: ${num(ppsRatio, 0)} % de la media de la UE`,
      spark: { series: [{ points: d.life_expectancy.long_run.ESP, main: true }], label: `Esperanza de vida en España, ${es1925.year}–${d.life_expectancy.long_run.ESP.at(-1).year}` },
    },
    faqs: [
      {
        q: "¿Cuál es la esperanza de vida en España?",
        a: `${num(le.es)} años al nacer en ${le.year}, ${num(le.es - le.eu27)} más que la media de la UE (${num(le.eu27)}). España ocupa el puesto ${le.world_rank.position} de ${le.world_rank.of} países y territorios y el ${le.oecd_rank.position} de ${le.oecd_rank.of} de la OCDE. En ${es1925.year} era de ${num(es1925.value, 0)} años.`,
      },
      {
        q: "¿Cuánto gasta España en sanidad pública?",
        a: `El ${pct(sp.pct_gdp_es)} del PIB en ${sp.year}, frente al ${pct(sp.pct_gdp_eu27)} de la UE. Por habitante y en poder de compra, ${count(sp.pps_es)} PPS frente a ${count(sp.pps_eu27)}: el ${num(ppsRatio, 0)} % de la media europea (${num(adjRatio, 0)} % si se descuenta que la población española es algo más joven).`,
      },
      {
        q: "¿Cuánto se tarda en operarse en la sanidad pública?",
        a: `En ${lastCut}, la espera media de toda la lista quirúrgica del SNS era de ${num(w.surgery_days[1], 0)} días (${num(w.surgery_days[0], 0)} en ${since}) y en las operaciones más comunes de ${num(w.selected_days[1], 0)} días (${num(w.selected_days[0], 0)}). Hay un ${num(change(w.surgery_rate[0], w.surgery_rate[1]), 0)} % más de pacientes en lista por habitante que en ${since}.`,
      },
      {
        q: "¿Cuánto se espera para ver al especialista?",
        a: `${num(w.consult_days[1], 0)} días de media para una primera consulta en ${lastCut}, frente a ${num(w.consult_days[0], 0)} en ${since}, con un ${num(change(w.consult_rate[0], w.consult_rate[1]), 0)} % más de pacientes esperando por habitante (Ministerio de Sanidad, SISLE-SNS).`,
      },
      {
        q: "¿Te atiende el médico de familia el mismo día?",
        a: `Al ${num(gp.national, 0)} % de quienes consultaron le atendió el mismo día o al siguiente (Barómetro Sanitario ${d.segments.barometro_year}): el ${num(gp.a.value, 0)} % en municipios de hasta 2.000 habitantes y el ${num(gp.b.value, 0)} % en los de más de un millón.`,
      },
    ],
  };
}

// Years actually covered by the published file (every numeric «year» field), for Dataset temporalCoverage.
function yearSpan(data) {
  let min = Infinity;
  let max = -Infinity;
  const walk = (node) => {
    if (Array.isArray(node)) node.forEach(walk);
    else if (node && typeof node === "object") {
      for (const [key, value] of Object.entries(node)) {
        if (key === "year" && Number.isInteger(value) && value > 1800 && value < 2100) {
          min = Math.min(min, value);
          max = Math.max(max, value);
        } else if (typeof value === "object") walk(value);
      }
    }
  };
  walk(data);
  return Number.isFinite(min) ? `${min}/${max}` : undefined;
}

const BUILDERS = { "carga-fiscal": cargaFiscal, empleo, vivienda, educacion, sanidad };

export function articleSeo(slug, data) {
  const built = BUILDERS[slug](data);
  return {
    slug,
    path: vizPath(slug),
    ...ARTICLES[slug],
    ...built,
    datePublished: PUBLISHED[slug],
    dateModified: data.generated_at || PUBLISHED[slug],
    temporalCoverage: yearSpan(data),
    sources: sourcesOf(data),
    downloads: downloadsOf(slug),
  };
}
