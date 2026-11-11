"use client";

import { Icon, PAL } from "./art";

// Slice 3 in the live simulator: what the employment levers do to jobs and the public accounts, what the extra residents
// pay and use by age stage, and what happens to the surgical waiting list. Central value and 5-95 % range of the draws.
const STAGE_LABEL = { "0_15": "0–15 años", "16_29": "16–29", "30_44": "30–44", "45_64": "45–64", "65p": "65 o más" };
const num = (v, d = 0) => Number(v).toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: "always" });
const sgn = (v, d = 0) => {
  const r = Math.round(v * 10 ** d) / 10 ** d;
  return `${r > 0 ? "+" : r < 0 ? "−" : ""}${num(Math.abs(r), d)}`;
};

export function hasServices(levers) {
  const mig = levers.migScale || (levers.migration !== "base" ? 1 : 0);
  return Boolean(mig || levers.mir || levers.healthSpend || levers.smi || levers.hours || levers.selfQuota);
}

export default function Services({ model, run, bands, t, levers }) {
  const year = model.years[t];
  const meur = (pp) => (pp / 100) * model.start.gdp_meur * (model.baseline.real_index?.[t] ?? 1);
  const Hl = model.labour.health;
  // Range after the display transform (a sign flip swaps the ends).
  const range = (key, f, g = (v) => v) => {
    if (!bands[key]) return "";
    const a = g(bands[key].lo[t]);
    const b = g(bands[key].hi[t]);
    return `${f(Math.min(a, b))} a ${f(Math.max(a, b))}`;
  };
  const mig = levers.migScale || (levers.migration === "low" ? -1 : levers.migration === "high" ? 1 : 0);
  const follow = levers.svcFunding !== "fixed";
  const jobs = [
    ["SMI", "lb_smi_k", levers.smi],
    ["Jornada", "lb_hours_k", levers.hours],
    ["Cuota de autónomos", "lb_self_k", levers.selfQuota],
  ].filter(([, , on]) => on);
  const waitBase = (Hl.list_k / Hl.exits_k) * 365;
  const stages = Object.keys(STAGE_LABEL);
  return (
    <div className="svc">
      {jobs.length ? (
        <div className="svc__block">
          <h3 className="vizPanelTitle">
            <Icon name="briefcase" size={20} /> Empleo en {year}
          </h3>
          <ul className="svc__list">
            {jobs.map(([label, key]) => (
              <li key={key}>
                {label}: <b>{sgn(run[key][t])} mil empleos</b> <span className="sim__muted">({range(key, (v) => sgn(v))} mil)</span>
              </li>
            ))}
            {levers.smi ? (
              <li>
                Masa salarial: <b>{sgn(run.lb_wage_bill_pct[t], 2)} %</b>; cotizaciones extra de los sueldos más altos y cuota:{" "}
                <b>{sgn(meur(run.lb_revenue_pp[t]))} millones</b> al año.
              </li>
            ) : null}
            {levers.hours ? (
              <li>
                Coste por hora de quien trabaja más de {num(40 - levers.hours, 1)} horas: <b>{sgn(run.lb_hour_cost_pct[t], 1)} %</b> tras lo que compensa la productividad
                ({range("lb_hour_cost_pct", (v) => sgn(v, 1))} %).
              </li>
            ) : null}
          </ul>
        </div>
      ) : null}

      {mig ? (
        <div className="svc__block">
          <h3 className="vizPanelTitle">
            <Icon name="people" size={20} /> Quién llega, qué paga y qué usa en {year}
          </h3>
          <p className="sim__muted">
            Millones de euros al año frente a la ley actual. «Usa»: sanidad, escuela, dependencia, pensiones y el resto de servicios
            {follow ? " (el gasto crece con la población)" : " (con el mismo dinero: no hay gasto extra, se reparte entre más gente)"}.
          </p>
          <div className="vizTable__scroll">
            <table className="sim__table">
              <thead>
                <tr>
                  <th scope="col">Edad</th>
                  <th scope="col">Residentes</th>
                  <th scope="col">Paga</th>
                  <th scope="col">Usa</th>
                </tr>
              </thead>
              <tbody>
                {stages.map((s) => (
                  <tr key={s}>
                    <th scope="row">{STAGE_LABEL[s]}</th>
                    <td>{sgn(run[`mig_pop_${s}`][t])} mil</td>
                    <td>{sgn(meur(run[`mig_rev_${s}`][t]))}</td>
                    <td>{sgn(meur(run[`mig_use_${s}`][t]))}</td>
                  </tr>
                ))}
                <tr className="svc__total">
                  <th scope="row">Total</th>
                  <td>{sgn(run.mig_pop_k[t])} mil</td>
                  <td>{sgn(meur(run.mig_revenue_pp[t]))}</td>
                  <td>{sgn(meur(run.mig_spend_pp[t]))}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p>
            Saldo para las cuentas públicas en {year}: <b>{sgn(-meur(run.mig_net_pp[t]))} millones</b>{" "}
            <span className="sim__muted">(del {range("mig_net_pp", (v) => sgn(v), (v) => -meur(v))}; positivo, pagan más de lo que usan)</span>.{" "}
            {follow ? null : <>Gasto en servicios por persona: <b>{sgn(run.svc_per_person_pct[t], 1)} %</b>.</>}
          </p>
        </div>
      ) : null}

      {mig || levers.mir || levers.healthSpend ? (
        <div className="svc__block">
          <h3 className="vizPanelTitle">
            <Icon name="hospital" size={20} /> Lista de espera quirúrgica en {year}
          </h3>
          <div className="svc__wait" style={{ "--fill": Math.min(1, run.hl_wait_days[t] / (2 * waitBase)), "--base": 0.5 }}>
            <span className="svc__bar" aria-hidden="true">
              <span className="svc__barFill" style={{ background: run.hl_wait_days[t] > waitBase + 0.5 ? PAL.orange : PAL.green }} />
              <span className="svc__barBase" />
            </span>
            <span>
              <b>{num(run.hl_wait_days[t])} días</b> de espera media frente a {num(waitBase)} con la ley actual{" "}
              <span className="sim__muted">({range("hl_wait_days", (v) => num(v))} días)</span>; {sgn(run.hl_list_k[t])} mil personas en lista.
            </span>
          </div>
          <ul className="svc__list">
            <li>
              {Math.abs(run.hl_deterred_k[t]) >= 0.5 ? (
                <>
                  {run.hl_deterred_k[t] > 0 ? "Pacientes que dejan de apuntarse en el año por la espera" : "Pacientes que se apuntan de más al bajar la espera"}:{" "}
                  <b>{num(Math.abs(run.hl_deterred_k[t]))} mil</b>.{" "}
                </>
              ) : null}
              Demanda: <b>{sgn(run.hl_demand_pct[t], 1)} %</b> · capacidad: <b>{sgn(run.hl_capacity_pct[t], 1)} %</b> · médicos formados de más:{" "}
              <b>{sgn(run.hl_doctors_k[t], 1)} mil</b>
            </li>
            <li className="sim__muted">
              Los médicos tardan en formarse (MIR más, si hacen falta, la carrera); sin ellos, el dinero solo compra una parte de la capacidad
              (horas extra, conciertos, médicos de fuera). Cuando la espera sube, parte de los pacientes deja de entrar en la lista: va a la privada o se
              queda sin atender, y el modelo no lo cuenta como resuelto.
            </li>
          </ul>
        </div>
      ) : null}
    </div>
  );
}
