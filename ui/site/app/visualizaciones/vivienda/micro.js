import { num, thousands } from "./common";

// Inside each tenure column: what housing weighs for households by age of the reference person and territory, from the
// INE ECV microdata (scripts/housing_ecv_microdata.py). One block per tenure, one row per age, one track per territory
// (Madrid, Cataluña, rest of Spain, which together are Spain): dot = median share of housing in disposable income,
// whisker = 95 % interval, the number on the right = share of households above 40 %. Cells under the sample threshold
// stay empty with their sample size; they are never filled in.
export const MICRO_TERR = [
  ["ES30", "Madrid", "Comunidad de Madrid"],
  ["ES51", "Cataluña", "Cataluña"],
  ["ES_RESTO", "Resto", "Resto de España"],
];
export const MICRO_AGES = ["16-29", "30-44", "45-64", "65+", "TOTAL"];
export const ageLabel = (age) => (age === "TOTAL" ? "Todas las edades" : `${age.replace("-", "–")} años`);

export function microIndex(micro) {
  const idx = {};
  for (const c of micro?.cells || []) idx[`${c.geo}|${c.age}|${c.tenure}`] = c;
  return (geo, age, tenure) => idx[`${geo}|${age}|${tenure}`];
}

export function stat(cell, key) {
  const v = cell?.s?.[key];
  return v && v[0] != null ? { value: v[0], lo: v[1], hi: v[2] } : null;
}

export function ci(s, digits = 0, unit = " %") {
  return `${num(s.value, digits)}${unit} (${num(s.lo, digits)}–${num(s.hi, digits)})`;
}

export const eurCi = (s) => `${thousands(s.value)} € (${thousands(s.lo)}–${thousands(s.hi)})`;

export default function MicroGrid({ micro, order, tenure }) {
  const get = microIndex(micro);
  const highs = micro.cells.map((c) => stat(c, "burden_median")?.hi).filter((v) => v != null);
  const xMax = Math.min(100, Math.ceil(Math.max(45, ...highs) / 10) * 10);
  const x = (v) => `${(Math.max(0, Math.min(v, xMax)) / xMax) * 100}%`;
  const low = micro.low_n;
  return (
    <div>
      <h3 className="vizPanelTitle">
        Dentro de cada columna: lo que pesa la vivienda según la edad y el territorio
        <span>
          punto = peso mediano en la renta del hogar; raya = intervalo del 95 %; a la derecha, hogares que pasan del 40 % (ECV {micro.year}, microdatos)
        </span>
      </h3>
      <div className="hvMicro">
        {order.map((tk) => (
          <section key={tk} className="hvMicro__block" aria-label={tenure[tk].label}>
            <h4 className="hvMicro__head" title={tenure[tk].label}>
              <i style={{ background: tenure[tk].color }} aria-hidden="true" />
              {tenure[tk].short}
            </h4>
            {MICRO_AGES.map((age) => (
              <div key={age} className={`hvMicro__age${age === "TOTAL" ? " hvMicro__age--total" : ""}`}>
                <span className="hvMicro__ageLabel">{ageLabel(age)}</span>
                {MICRO_TERR.map(([geo, short, long]) => {
                  const cell = get(geo, age, tk);
                  const med = stat(cell, "burden_median");
                  const over = stat(cell, "overburden_pct");
                  const weak = cell && cell.n < low;
                  return (
                    <div key={geo} className="hvMicro__row" title={med ? `${long}, ${ageLabel(age)}: peso mediano ${ci(med, 1)}; sobrecarga ${ci(over, 1)}; ${cell.n} hogares en la muestra` : `${long}: ${cell?.n ?? 0} hogares en la muestra, por debajo del mínimo de ${micro.min_n}`}>
                      <span className="hvMicro__terr">{short}</span>
                      <span className="hvMicro__track">
                        <span className="hvMicro__limit" style={{ left: x(40) }} aria-hidden="true" />
                        {med ? (
                          <>
                            <span className="hvMicro__ci" style={{ left: x(med.lo), width: `calc(${x(med.hi)} - ${x(med.lo)})`, background: tenure[tk].color }} />
                            <span className={`hvMicro__dot${weak ? " hvMicro__dot--weak" : ""}`} style={{ left: x(med.value), borderColor: tenure[tk].color, background: weak ? "var(--viz-surface)" : tenure[tk].color }} />
                          </>
                        ) : (
                          <span className="hvMicro__empty">n = {cell?.n ?? 0}</span>
                        )}
                      </span>
                      <span className="hvMicro__value">
                        {med ? (
                          <>
                            {num(med.value, 0)} % · <b>{num(over.value, 0)} %</b>
                            {weak ? "*" : ""}
                          </>
                        ) : (
                          "—"
                        )}
                      </span>
                    </div>
                  );
                })}
              </div>
            ))}
          </section>
        ))}
      </div>
      <p className="hvMuted">
        Escala común de 0 a {xMax} %; la línea vertical marca el 40 %. Cifras: peso mediano · <b>hogares por encima del 40 %</b>. «n =»: hogares de la muestra cuando son menos de {micro.min_n} y la celda queda vacía; * entre {micro.min_n} y {low - 1} hogares, punto hueco: precisión baja. Hogares clasificados por la edad de su persona de referencia.
      </p>
    </div>
  );
}
