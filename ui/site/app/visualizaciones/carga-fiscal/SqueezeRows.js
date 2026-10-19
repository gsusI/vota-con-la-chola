import "./consolidated.css";

// «El dato mata el relato» for the taxpayer's pocket: per country, two panels on one row, each with its own single
// axis shared by every row. Left: taxes paid and household income left per person (PPS, same scale for both).
// Right: real change of each since the base year (%, same scale for every country). Colour = taxes vs income.
const nf = (v, digits = 0) =>
  Number(v).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits, useGrouping: "always" });
const signed = (v) => `${v >= 0 ? "+" : "−"}${nf(Math.abs(v), 1)} %`;

function ticks(min, max, step) {
  const out = [];
  for (let t = Math.ceil(min / step) * step; t <= max + 1e-9; t += step) out.push(Number(t.toFixed(6)));
  return out;
}

export default function SqueezeRows({ rows, year, baseYear, lastYear, taxColor, incomeColor, highlight }) {
  const levelMax = Math.ceil(Math.max(...rows.map((row) => row.income_pps)) / 10000) * 10000;
  const changes = rows.flatMap((row) => [row.real_tax_change_pct, row.real_income_change_pct]);
  const chMin = Math.min(0, Math.floor(Math.min(...changes) / 10) * 10);
  const chMax = Math.max(10, Math.ceil(Math.max(...changes) / 10) * 10);
  const lv = (v) => `${(v / levelMax) * 100}%`;
  const ch = (v) => `${((v - chMin) / (chMax - chMin)) * 100}%`;
  const bar = (from, to) => ({ left: ch(Math.min(from, to)), width: `${(Math.abs(to - from) / (chMax - chMin)) * 100}%` });
  const levelTicks = ticks(0, levelMax, 10000);
  const changeTicks = ticks(chMin, chMax, 10);

  return (
    <div className="sq" role="table" aria-label={`Impuestos y renta que queda por habitante en ${year}, y su cambio real desde ${baseYear}`}>
      <div className="sq__row sq__head" role="row">
        <span role="columnheader">País</span>
        <span role="columnheader">
          Por habitante en {year} <em>(estándar de poder adquisitivo)</em>
        </span>
        <span role="columnheader">
          Cambio real {baseYear}–{lastYear} <em>(%)</em>
        </span>
      </div>
      {rows.map((row) => (
        <div className="sq__row" role="row" key={row.area} data-highlight={row.area === highlight ? "true" : "false"}>
          <span className="sq__label" role="rowheader">
            {row.label}
          </span>
          <div className="sq__panel" role="cell">
            <div className="sq__track">
              {levelTicks.map((t) => (
                <span className="sq__tick" key={t} style={{ left: lv(t) }} aria-hidden="true" />
              ))}
              <span className="sq__bar sq__bar--top" style={{ left: 0, width: lv(row.tax_pps), background: taxColor }} />
              <span className="sq__bar sq__bar--bottom" style={{ left: 0, width: lv(row.income_pps), background: incomeColor }} />
            </div>
            <span className="sq__values">
              <span style={{ color: taxColor }}>paga {nf(row.tax_pps)}</span> ·{" "}
              <span style={{ color: incomeColor }}>le quedan {nf(row.income_pps)}</span> · {nf(row.tax_to_income_pct, 1)} %
            </span>
          </div>
          <div className="sq__panel" role="cell">
            <div className="sq__track">
              {changeTicks.map((t) => (
                <span className={`sq__tick${t === 0 ? " sq__tick--zero" : ""}`} key={t} style={{ left: ch(t) }} aria-hidden="true" />
              ))}
              <span className="sq__bar sq__bar--top" style={{ ...bar(0, row.real_tax_change_pct), background: taxColor }} />
              <span className="sq__bar sq__bar--bottom" style={{ ...bar(0, row.real_income_change_pct), background: incomeColor }} />
            </div>
            <span className="sq__values">
              <span style={{ color: taxColor }}>impuestos {signed(row.real_tax_change_pct)}</span> ·{" "}
              <span style={{ color: incomeColor }}>renta {signed(row.real_income_change_pct)}</span>
            </span>
          </div>
        </div>
      ))}
      <div className="sq__row sq__axis" aria-hidden="true">
        <span />
        <div className="sq__track sq__track--axis">
          {levelTicks.map((t) => (
            <span className="sq__tickLabel" key={t} style={{ left: lv(t) }}>
              {t ? `${nf(t / 1000)} mil` : "0"}
            </span>
          ))}
        </div>
        <div className="sq__track sq__track--axis">
          {changeTicks.map((t) => (
            <span className="sq__tickLabel" key={t} style={{ left: ch(t) }}>
              {t > 0 ? `+${t}` : t < 0 ? `−${Math.abs(t)}` : "0"}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
