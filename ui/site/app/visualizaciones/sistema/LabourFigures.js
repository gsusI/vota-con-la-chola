// Slice 3 figures of /visualizaciones/sistema/, rendered at build time with the same engine as the simulator:
// the consolidated immigration figure (what extra residents pay and use by age, 2035 and 2050, and what happens to
// health capacity), the employment levers with their contested elasticities, and how many doctors keep waits stable.
import { DEFAULT_LEVERS, centralParams, runEnsemble, simulate } from "./engine.mjs";

const DRAWS = 200;
const STAGES = [
  ["0_15", "0–15 años"],
  ["16_29", "16–29"],
  ["30_44", "30–44"],
  ["45_64", "45–64"],
  ["65p", "65 o más"],
];
const n = (v, d = 0) => Number(v).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: "always" });
const sg = (v, d = 0) => {
  const r = Math.round(v * 10 ** d) / 10 ** d;
  return `${r > 0 ? "+" : r < 0 ? "−" : ""}${n(Math.abs(r), d)}`;
};
const bn = (meur) => n(meur / 1000, 1); // thousands of millions, one decimal

const cache = new WeakMap();

/** Every number the slice-3 figures and their copy use (memoised per model). */
export function labourFindings(model) {
  if (cache.has(model)) return cache.get(model);
  const T = { 2035: model.years.indexOf(2035), 2050: model.years.length - 1 };
  const meur = (pp, t) => (pp / 100) * model.start.gdp_meur * (model.baseline.real_index?.[t] ?? 1);
  const pick = (e, key, t, f = (v) => v) => {
    const a = f(e.bands[key].lo[t]);
    const b = f(e.bands[key].hi[t]);
    return { v: f(e.central[key][t]), lo: Math.min(a, b), hi: Math.max(a, b) };
  };
  const follow = runEnsemble(model, { ...DEFAULT_LEVERS, migScale: 1 }, { draws: DRAWS });
  const fixed = runEnsemble(model, { ...DEFAULT_LEVERS, migScale: 1, svcFunding: "fixed" }, { draws: DRAWS });
  const years = {};
  for (const [y, t] of Object.entries(T)) {
    const M = (v) => meur(v, t);
    years[y] = {
      stages: STAGES.map(([id, label]) => ({
        id, label, pop: follow.central[`mig_pop_${id}`][t], rev: pick(follow, `mig_rev_${id}`, t, M), use: pick(follow, `mig_use_${id}`, t, M),
      })),
      pop: follow.central.mig_pop_k[t],
      emp: pick(follow, "mig_emp_k", t),
      rev: pick(follow, "mig_revenue_pp", t, M),
      use: pick(follow, "mig_spend_pp", t, M),
      net: pick(follow, "mig_net_pp", t, (v) => -M(v)),
      parts: Object.fromEntries(["mig_health_pp", "mig_edu_pp", "mig_ltc_pp", "mig_other_pp", "mig_pension_pp"].map((k) => [k, pick(follow, k, t, M)])),
      wait: pick(follow, "hl_wait_days", t),
      waitFixed: pick(fixed, "hl_wait_days", t),
      deterredFixed: pick(fixed, "hl_deterred_k", t),
      perPersonFixed: fixed.central.svc_per_person_pct[t],
      netFixed: pick(fixed, "mig_net_pp", t, (v) => -M(v)),
      households: pick(follow, "hs_migration_hh_k", t),
      rent: pick(follow, "hs_rent", t, (v) => v * 100),
      debt: pick(follow, "debt_dev_pp", t),
      gdp: pick(follow, "mig_gdp_pct", t),
    };
    years[y].netPensionShare = (years[y].net.v / M(model.baseline.pension_pct[t])) * 100;
  }
  const waitBase = (model.labour.health.list_k / model.labour.health.exits_k) * 365;
  // The contested cost of «other services»: net balance under each school.
  const P = model.params.cuota_gasto_congestionable;
  const otherSchools = (P.debate?.schools || []).map((school, i) => {
    const run = simulate(model, { ...DEFAULT_LEVERS, migScale: 1 }, centralParams(model, { [P.debate.id]: i }));
    return { label: school.label, central: school.central, net35: -meur(run.mig_net_pp[T[2035]], T[2035]), net50: -meur(run.mig_net_pp[T[2050]], T[2050]) };
  });
  // Doctors: with the high variant, how many extra training places a year keep waits where they are.
  const mir = [0, 1000, 2000, 3000].map((places) => {
    const e = runEnsemble(model, { ...DEFAULT_LEVERS, migScale: 1, mir: places }, { draws: DRAWS, keys: ["hl_wait_days", "hl_doctors_k", "hl_cost_pp"] });
    return { places, wait35: pick(e, "hl_wait_days", T[2035]), wait50: pick(e, "hl_wait_days", T[2050]), doctors50: e.central.hl_doctors_k[T[2050]],
      cost50: meur(e.central.hl_cost_pp[T[2050]], T[2050]) };
  });
  // Employment levers in 2035: jobs and the net effect on the public accounts; schools of the contested elasticities.
  const LEVERS = [
    { key: "smi", value: 10, label: "Subir el SMI un 10 % real", param: "elasticidad_empleo_smi" },
    { key: "hours", value: 2.5, label: "Jornada máxima de 37,5 horas, con el mismo sueldo", param: "elasticidad_empleo_jornada" },
    { key: "selfQuota", value: 50, label: "Cuota de autónomos 50 € al mes más alta" },
    { key: "selfQuota", value: -50, label: "Cuota de autónomos 50 € al mes más baja" },
    { key: "contrib", value: 1, label: "Un punto más de cotizaciones sociales", param: "traslado_cotizacion_salario" },
  ];
  const t35 = T[2035];
  const employment = LEVERS.map((lv) => {
    const levers = { ...DEFAULT_LEVERS, [lv.key]: lv.value };
    const e = runEnsemble(model, levers, { draws: DRAWS, keys: ["employment_k", "net_cost_pp", "lb_wage_bill_pct", "lb_hour_cost_pct", "gdp_dev"] });
    const p = lv.param ? model.params[lv.param] : null;
    const schools = p?.debate ? p.debate.schools.map((school, i) => ({
      label: school.label, central: school.central,
      jobs: simulate(model, levers, centralParams(model, { [p.debate.id]: i })).employment_k[t35],
    })) : null;
    return { ...lv, jobs: pick(e, "employment_k", t35), net: pick(e, "net_cost_pp", t35, (v) => -meur(v, t35)), wageBill: e.central.lb_wage_bill_pct[t35],
      hourCost: pick(e, "lb_hour_cost_pct", t35), gdp: pick(e, "gdp_dev", t35), schools };
  });
  const out = { years, waitBase, otherSchools, mir, employment, variantPct: model.labour.variant_pct.hi,
    netMig: model.labour.net_migration_k, docLag: centralParams(model).retardo_formacion_medico };
  cache.set(model, out);
  return out;
}

const Range = ({ r, f = (v) => sg(v) }) => <span className="sim__muted"><br />{f(r.lo)} a {f(r.hi)}</span>;

export function MigrationFigure({ model, src }) {
  const F = labourFindings(model);
  const a = F.years[2035];
  const b = F.years[2050];
  const avgBase = F.netMig.base.slice(1).reduce((x, y) => x + y, 0) / (F.netMig.base.length - 1);
  const avgHi = F.netMig.hi.slice(1).reduce((x, y) => x + y, 0) / (F.netMig.hi.length - 1);
  return (
    <figure className="vizFigure" id="inmigracion">
      <h2>
        Con la variante alta oficial de inmigración, en 2035 viven en España {n(a.pop / 1000, 1)} millones de personas más que pagan unos {bn(a.rev.v)} mil
        millones al año y usan unos {bn(a.use.v)} mil millones en servicios y pensiones; la espera quirúrgica sube {n(a.wait.v - F.waitBase)} días si los servicios
        crecen con ellas y {n(a.waitFixed.v - F.waitBase)} si no
      </h2>
      <p className="vizFigure__dek">
        La variante alta del Ageing Report y de Eurostat supone un tercio más de inmigración de fuera de la UE: unas {n(avgHi - avgBase, 0)} mil personas netas
        más al año ({n(avgHi, 0)} mil en vez de {n(avgBase, 0)} mil de media hasta 2050, un {n(F.variantPct, 1)} % más). Cada fila es una edad de quienes llegan
        de más: cuántos son, cuánto pagan (cotizaciones, IRPF, impuestos al consumo y la parte de los demás impuestos que sale del PIB que añaden) y cuánto
        usan (sanidad, escuela, dependencia, pensiones y el resto de servicios), en millones de euros de {model.start.year} al año, con el rango del 5 % al 95 %
        de las simulaciones. Pone a prueba dos relatos. «Los inmigrantes pagan nuestras pensiones»: en estas décadas pagan más de lo que usan (un saldo de{" "}
        {sg(a.net.v / 1000, 1)} mil millones en 2035 y {sg(b.net.v / 1000, 1)} en 2050), porque llegan sobre todo en edad de trabajar; pero ese saldo es un{" "}
        {n(a.netPensionShare, 1)} % del gasto en pensiones de 2035, y quien cotiza hoy cobrará su pensión sobre todo después de 2050, fuera del horizonte del
        modelo. «Colapsan los servicios»: el dinero llega, pero un médico tarda unos{" "}
        {n(F.docLag, 0)} años en formarse; con el gasto creciendo con la población, la espera apenas sube; con el mismo dinero, cada persona recibe un{" "}
        {n(-a.perPersonFixed, 1)} % menos en 2035 y un {n(-b.perPersonFixed, 1)} % menos en 2050, y la lista crece. Lo que queda abierto: cuánto cuestan de
        verdad los demás servicios por persona ({F.otherSchools.map((sc) => `${sc.central >= 1 ? "si cada residente cuesta la media" : "si solo crecen los servicios que se congestionan"}, ${sg(sc.net35 / 1000, 1)} mil millones`).join("; ")}{" "}
        de saldo en 2035), cuánto usan la sanidad y cuánto tardan en encontrar empleo.
      </p>
      <div className="vizTable__scroll">
        <table className="sim__table sim__table--mig">
          <thead>
            <tr>
              <th scope="col" rowSpan={2}>Edad de quien llega de más</th>
              <th scope="col" colSpan={3}>2035</th>
              <th scope="col" colSpan={3}>2050</th>
            </tr>
            <tr>
              <th scope="col">Residentes</th>
              <th scope="col">Pagan (millones)</th>
              <th scope="col">Usan (millones)</th>
              <th scope="col">Residentes</th>
              <th scope="col">Pagan (millones)</th>
              <th scope="col">Usan (millones)</th>
            </tr>
          </thead>
          <tbody>
            {a.stages.map((s, i) => {
              const z = b.stages[i];
              return (
                <tr key={s.id}>
                  <th scope="row">{s.label}</th>
                  <td>{sg(s.pop)} mil</td>
                  <td>{sg(s.rev.v)}<Range r={s.rev} /></td>
                  <td>{sg(s.use.v)}<Range r={s.use} /></td>
                  <td>{sg(z.pop)} mil</td>
                  <td>{sg(z.rev.v)}<Range r={z.rev} /></td>
                  <td>{sg(z.use.v)}<Range r={z.use} /></td>
                </tr>
              );
            })}
            <tr className="svc__total">
              <th scope="row">Total</th>
              <td>{sg(a.pop)} mil<span className="sim__muted"><br />{n(a.emp.v)} mil trabajan</span></td>
              <td>{sg(a.rev.v)}<Range r={a.rev} /></td>
              <td>{sg(a.use.v)}<Range r={a.use} /></td>
              <td>{sg(b.pop)} mil<span className="sim__muted"><br />{n(b.emp.v)} mil trabajan</span></td>
              <td>{sg(b.rev.v)}<Range r={b.rev} /></td>
              <td>{sg(b.use.v)}<Range r={b.use} /></td>
            </tr>
          </tbody>
          <tbody className="sim__tbody--cap">
            <tr>
              <th scope="row">Saldo para las cuentas públicas, al año (servicios que crecen / mismo dinero)</th>
              <td colSpan={3}>{sg(a.net.v)} / {sg(a.netFixed.v)} millones<span className="sim__muted"><br />{sg(a.net.lo)} a {sg(a.net.hi)} con servicios que crecen</span></td>
              <td colSpan={3}>{sg(b.net.v)} / {sg(b.netFixed.v)} millones<span className="sim__muted"><br />{sg(b.net.lo)} a {sg(b.net.hi)} con servicios que crecen</span></td>
            </tr>
            <tr>
              <th scope="row">Espera quirúrgica media (hoy {n(F.waitBase)} días): servicios que crecen / mismo dinero</th>
              <td colSpan={3}>{n(a.wait.v)} / {n(a.waitFixed.v)} días<span className="sim__muted"><br />con el mismo dinero, {n(a.deterredFixed.v)} mil pacientes al año dejan de apuntarse</span></td>
              <td colSpan={3}>{n(b.wait.v)} / {n(b.waitFixed.v)} días<span className="sim__muted"><br />con el mismo dinero, {n(b.deterredFixed.v)} mil pacientes al año dejan de apuntarse</span></td>
            </tr>
            <tr>
              <th scope="row">Gasto en servicios por persona con el mismo dinero</th>
              <td colSpan={3}>{sg(a.perPersonFixed, 1)} %</td>
              <td colSpan={3}>{sg(b.perPersonFixed, 1)} %</td>
            </tr>
            <tr>
              <th scope="row">Hogares más y alquiler de un contrato nuevo</th>
              <td colSpan={3}>{sg(a.households.v)} mil hogares · alquiler {sg(a.rent.v, 1)} %<span className="sim__muted"> ({sg(a.rent.lo, 1)} a {sg(a.rent.hi, 1)})</span></td>
              <td colSpan={3}>{sg(b.households.v)} mil hogares · alquiler {sg(b.rent.v, 1)} %<span className="sim__muted"> ({sg(b.rent.lo, 1)} a {sg(b.rent.hi, 1)})</span></td>
            </tr>
            <tr>
              <th scope="row">Deuda pública, puntos de PIB (si el saldo va a deuda)</th>
              <td colSpan={3}>{sg(a.debt.v, 1)}<span className="sim__muted"> ({sg(a.debt.lo, 1)} a {sg(a.debt.hi, 1)})</span></td>
              <td colSpan={3}>{sg(b.debt.v, 1)}<span className="sim__muted"> ({sg(b.debt.lo, 1)} a {sg(b.debt.hi, 1)})</span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <figcaption className="vizFigure__caption">
        <span>
          Fuente: modelo de esta página sobre las proyecciones de población de{" "}
          <a href={src.europop.page} target="_blank" rel="noopener noreferrer">Eurostat (EUROPOP2023)</a>, las tasas de empleo por nacionalidad de la{" "}
          <a href={src.eurostat_lfs.page} target="_blank" rel="noopener noreferrer">EPA</a>, el gasto sanitario, educativo y de dependencia del Ageing Report 2024, el
          perfil de gasto sanitario por edad de Funcas y la lista de espera del Ministerio de Sanidad (página de <a href="/visualizaciones/sanidad/">sanidad</a>).
        </span>
        <span>
          «Usan» incluye, en 65 o más, las pensiones de quienes llegan de más y ya se jubilan antes de 2050 ({sg(b.parts.mig_pension_pp.v)} millones en 2050). En
          2050, de lo que usan: sanidad {sg(b.parts.mig_health_pp.v)}, escuela {sg(b.parts.mig_edu_pp.v)}, dependencia {sg(b.parts.mig_ltc_pp.v)} y el resto de
          servicios {sg(b.parts.mig_other_pp.v)} millones. El PIB que añaden sube un {n(b.gdp.v, 1)} % en 2050 frente a la ley actual.
        </span>
      </figcaption>
    </figure>
  );
}

export function DoctorsTable({ model }) {
  const F = labourFindings(model);
  return (
    <div className="vizTable__scroll">
      <table className="sim__table">
        <thead>
          <tr>
            <th scope="col">Plazas de especialista (MIR) más al año, desde 2026</th>
            <th scope="col">Espera media en 2035</th>
            <th scope="col">Espera media en 2050</th>
            <th scope="col">Médicos más en 2050</th>
            <th scope="col">Coste en 2050 (millones al año)</th>
          </tr>
        </thead>
        <tbody>
          {F.mir.map((r) => (
            <tr key={r.places}>
              <th scope="row">{r.places ? `+${n(r.places)}` : "Ninguna"}</th>
              <td>{n(r.wait35.v)} días <span className="sim__muted">({n(r.wait35.lo)} a {n(r.wait35.hi)})</span></td>
              <td>{n(r.wait50.v)} días <span className="sim__muted">({n(r.wait50.lo)} a {n(r.wait50.hi)})</span></td>
              <td>{r.doctors50 ? `+${n(r.doctors50 * 1000)}` : "0"}</td>
              <td>{n(r.cost50)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EmploymentFigure({ model }) {
  const F = labourFindings(model);
  const [smi, hours] = F.employment;
  return (
    <figure className="vizFigure" id="empleo">
      <h2>
        En el modelo, subir el SMI un 10 % va con {n(-smi.jobs.v)} mil empleos menos en 2035 ({n(-smi.jobs.hi)} a {n(-smi.jobs.lo)} mil); la jornada de 37,5
        horas, entre {n(-hours.schools[0].jobs)} mil empleos menos y {n(hours.schools.at(-1).jobs)} mil más según el estudio que se tome
      </h2>
      <p className="vizFigure__dek">
        Cinco cambios del mercado de trabajo desde {model.policy_start}, en 2035, con todo lo demás igual. El empleo responde con una elasticidad medida en otros
        episodios (con su rango), las cuentas públicas cambian por los sueldos, las cotizaciones y la cuota de quienes siguen, y por los impuestos que dejan de
        pagar quienes pierden el empleo. Pone a prueba dos relatos. «Subir el SMI destruye empleo»: los estudios de la subida de 2019 van de ningún efecto
        a uno negativo, y el simulador muestra los dos. «Trabajar menos crea empleo»: ningún estudio de Francia, Portugal o Alemania encuentra un reparto
        grande; el debate es si se pierde empleo o no cambia. Lo que queda abierto: la respuesta del empleo a cada medida (ver las escuelas).
      </p>
      <div className="vizTable__scroll">
        <table className="sim__table">
          <thead>
            <tr>
              <th scope="col">Medida</th>
              <th scope="col">Empleo en 2035 (miles)</th>
              <th scope="col">Cuentas públicas en 2035 (millones al año)</th>
              <th scope="col">Además</th>
            </tr>
          </thead>
          <tbody>
            {F.employment.map((r) => (
              <tr key={r.label}>
                <th scope="row">{r.label}</th>
                <td>{sg(r.jobs.v)}<Range r={r.jobs} /></td>
                <td>{sg(r.net.v)}<Range r={r.net} /></td>
                <td>
                  {r.key === "smi" ? `Masa salarial ${sg(r.wageBill, 2)} %` : null}
                  {r.key === "hours" ? `Coste por hora de los afectados ${sg(r.hourCost.v, 1)} %; PIB ${sg(r.gdp.v, 1)} % (${sg(r.gdp.lo, 1)} a ${sg(r.gdp.hi, 1)})` : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="vizTable__scroll">
        <table className="sim__table">
          <thead>
            <tr>
              <th scope="col">Escuela (elasticidad del empleo de los afectados)</th>
              <th scope="col">Empleo en 2035 (miles)</th>
            </tr>
          </thead>
          <tbody>
            {[smi, hours].flatMap((r) => r.schools.map((sc) => (
              <tr key={r.key + sc.label}>
                <th scope="row">{r.key === "smi" ? "SMI +10 %" : "37,5 horas"} · {sc.label} <span className="sim__muted">({sg(sc.central, 2)})</span></th>
                <td>{sg(sc.jobs)}</td>
              </tr>
            )))}
          </tbody>
        </table>
      </div>
      <figcaption className="vizFigure__caption">
        <span>
          Cuentas públicas: positivo, ingresan más de lo que pierden. Ninguno de los casos tipo cobra el SMI (todos ganan más), así que la subida no cambia sus euros
          al mes; afecta a uno de cada ocho asalariados. La jornada no cambia los sueldos mensuales: el coste por hora sube y, si la productividad no lo compensa,
          baja el PIB; el modelo no reparte ese coste entre beneficios, precios y salarios futuros.
        </span>
      </figcaption>
    </figure>
  );
}
