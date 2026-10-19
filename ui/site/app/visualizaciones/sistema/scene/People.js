"use client";

import { Avatar, House, Icon, PAL } from "./art";

const eur = (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.round(Math.abs(v)).toLocaleString("es-ES", { useGrouping: "always" })} €`;
const mood = (v) => (v >= 0.5 ? "up" : v <= -0.5 ? "down" : "flat");

export const NEIGHBOURS = [
  { id: "p1", name: "Lucía", who: "25–34 años, asalariada, vive sola de alquiler en Madrid", case: 1 },
  { id: "p2", name: "Ana y Javi", who: "pareja de 30–44 con dos hijos y dos sueldos", case: 2 },
  { id: "p4", name: "Carmen", who: "jubilada de 65 años o más, vive sola, con la casa pagada", case: 4 },
  { id: "p5", name: "Laura", who: "45–54 años, universitaria, profesional en Madrid", case: 5 },
];

/** Four typical cases with a face that follows the change in their monthly income. */
export function Neighbours({ model, run, bands, t, levers = {} }) {
  const housing = ["pubHomes", "land", "capCov", "capCut", "tourCut", "ltvCap", "ltiCap"].some((key) => levers[key]) || levers.migration !== "base";
  // Rent of a new flat for the two renters: with and without the cap when there is one. Rent up = worse.
  const rentOf = (id) => {
    const key = id === "p1" ? "p1" : id === "p2" ? "p2r" : null;
    if (!key || !housing) return null;
    const unc = run[`${key}_rent_unc_month`]?.[t] ?? 0;
    const cov = run[`${key}_rent_cov_month`]?.[t] ?? 0;
    if (Math.abs(unc) < 0.5 && Math.abs(cov) < 0.5) return null;
    const capped = levers.capCov && levers.capCut;
    const vals = capped ? [cov, unc] : [unc];
    const m = vals.every((v) => v <= -0.5) ? "up" : vals.every((v) => v >= 0.5) ? "down" : "flat";
    const text = capped ? `${eur(cov)} con tope · ${eur(unc)} sin tope` : `${eur(unc)}`;
    return { text, mood: m };
  };
  return (
    <div className="nbrs">
      {NEIGHBOURS.map((n) => {
        const v = run[`${n.id}_month`][t];
        const b = bands[`${n.id}_month`];
        const p = model.personas[n.id];
        const income = (p.net || 0) / 12;
        const rent = rentOf(n.id);
        const face = Math.abs(v) >= 0.5 ? mood(v) : rent ? rent.mood : "flat";
        return (
          <figure className={`nbr nbr--${face}`} key={n.id}>
            <Avatar who={n.id} mood={face} size={104} />
            <figcaption>
              <span className="nbr__name">
                {n.name} <small>caso {n.case}</small>
              </span>
              <span className="nbr__who">{n.who}</span>
              <span className="nbr__bubble">
                {Math.abs(v) >= 0.5 ? `${eur(v)} al mes` : rent ? "Su renta no cambia" : "Sin cambio"}
                {Math.abs(v) >= 0.5 ? <small>entre {eur(b.lo[t])} y {eur(b.hi[t])}</small> : null}
              </span>
              {rent ? (
                <span className={`nbr__rent nbr__rent--${rent.mood}`}>
                  Alquiler de un piso nuevo: {rent.text} al mes
                </span>
              ) : null}
              <span className="nbr__base">hoy le quedan {eur(income).replace("+", "")} netos al mes</span>
            </figcaption>
          </figure>
        );
      })}
    </div>
  );
}

const PARTS = {
  irpf: { label: "IRPF", color: PAL.blue },
  iva: { label: "IVA", color: PAL.orange },
  cotizaciones: { label: "Cotizaciones", color: PAL.yellow },
  sociedades: { label: "Sociedades", color: PAL.purple },
  pensiones: { label: "Pensiones", color: PAL.green },
};

/** Income ladder: five houses on a staircase from the poorest fifth to the richest, with what each gains or loses. */
export function Ladder({ rows, cuts }) {
  const names = ["El 20 % con menos renta", "Segundo quinto", "Tercer quinto", "Cuarto quinto", "El 20 % con más renta"];
  const toneOf = (r) => (r.total >= 0.5 ? PAL.green : r.total <= -0.5 ? PAL.orange : PAL.muted);
  const total = (r) => (Math.abs(r.total) < 0.5 ? "Sin cambio" : `${eur(r.total)} al mes`);
  const pct = (r) =>
    Math.abs(r.total) < 0.5 ? "" : `${r.pctDisposable > 0 ? "+" : "−"}${Math.abs(r.pctDisposable).toLocaleString("es-ES", { maximumFractionDigits: 2, minimumFractionDigits: 2 })} % de su renta`;
  return (
    <div className="ladder">
      <div className="ladder__row ladder__totals">
        {rows.map((r) => (
          <span key={r.q} className={`ladder__total ladder__total--${mood(r.total)}`}>
            {total(r)}
            <small>{pct(r)}</small>
          </span>
        ))}
      </div>
      <svg className="ladder__stairs" viewBox="0 0 1000 200" width="100%" aria-hidden="true">
        {rows.map((r, i) => {
          const step = 20 + i * 26;
          return (
            <g key={r.q}>
              <rect x={i * 200} y={200 - step} width="200" height={step} fill="#ece9e0" />
              <rect x={i * 200} y={200 - step} width="200" height="6" fill="#dcd8cc" />
              <House x={i * 200 + 100} y={200 - step} w={56 + i * 10} h={44 + i * 8} color={toneOf(r)} />
            </g>
          );
        })}
      </svg>
      <div className="ladder__row">
        {rows.map((r, i) => {
          const parts = Object.entries(r.byPart).filter(([, v]) => Math.abs(v) >= 0.5);
          return (
            <div className="ladder__step" key={r.q}>
              <svg className="ladder__mini" viewBox="-40 -70 80 74" width="72" height="66" aria-hidden="true">
                <House w={40 + i * 5} h={30 + i * 4} color={toneOf(r)} />
              </svg>
              <span className={`ladder__total ladder__total--${mood(r.total)} ladder__total--mini`}>
                {total(r)}
                <small>{pct(r)}</small>
              </span>
              <span className="ladder__name">{names[i]}</span>
              <span className="ladder__cut">{i < 4 ? `hasta ${Math.round(cuts[i]).toLocaleString("es-ES", { useGrouping: "always" })} € al año por unidad de consumo` : "más de esa renta"}</span>
              <ul className="ladder__parts">
                {parts.map(([k, v]) => (
                  <li key={k} style={{ "--c": PARTS[k].color }}>
                    {PARTS[k].label} <b>{eur(v)}</b>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export { Icon };
