import { C, num } from "./sections";

// Early leaving by mother's education and by country of birth: who the 12.8 % average is made of, and how much of the
// fall comes from the population changing (more mothers with degrees) rather than from each group improving.
const LEVEL_LABEL = {
  "E. Primaria e inferior": "Madre con Primaria o menos",
  "1ª etapa E. Secundaria": "Madre con ESO o equivalente",
  "2ª etapa E. Secundaria": "Madre con Bachillerato o FP",
  "E. Superior": "Madre con estudios superiores",
  "No consta": "Sin dato de la madre (por ejemplo, no vive en el mismo hogar)",
};
const MARK = 12;
const muted = { color: "var(--viz-muted)", fontWeight: 400 };
const minus = (text) => text.replace("-", "−");

function Dot({ value, max, hollow, color }) {
  return (
    <span
      aria-hidden="true"
      style={{
        position: "absolute",
        top: "50%",
        left: `max(0px, calc(${(value / max) * 100}% - ${MARK / 2}px))`,
        width: MARK,
        height: MARK,
        marginTop: -MARK / 2,
        borderRadius: "50%",
        boxSizing: "border-box",
        background: hollow ? "var(--viz-surface)" : color,
        border: hollow ? `2px solid ${C.ref}` : "none",
      }}
    />
  );
}

export function MotherDumbbell({ lm }) {
  const max = 50;
  const rows = [
    ...lm.rows.map((row) => ({ ...row, label: LEVEL_LABEL[row.level] || row.level })),
    { level: "TOTAL", label: "Todos los jóvenes de 18 a 24 años", rate_first: lm.total.first, rate_last: lm.total.last },
  ];
  return (
    <ul className="vizBars" style={{ width: "100%" }} aria-label={`Abandono temprano por estudios de la madre, ${lm.first_year} y ${lm.last_year}`}>
      {rows.map((row) => {
        const isTotal = row.level === "TOTAL";
        const color = isTotal ? C.ref : C.blue;
        return (
          <li key={row.level}>
            <span style={isTotal ? { fontWeight: 700 } : undefined}>
              {row.label}
              {isTotal ? null : (
                <span style={{ ...muted, display: "block", fontSize: "0.78rem" }}>
                  {num(row.share_last, 0)} % de los jóvenes en {lm.last_year}; {num(row.share_first, 0)} % en {lm.first_year}
                </span>
              )}
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
              <span style={{ position: "relative", flex: "1 1 auto", height: 22, minWidth: 120 }}>
                {[0, 10, 20, 30, 40, 50].map((t) => (
                  <span
                    key={t}
                    aria-hidden="true"
                    style={{ position: "absolute", left: `${(t / max) * 100}%`, top: 0, bottom: 0, width: 1, background: t ? "var(--viz-grid)" : "var(--viz-axis)" }}
                  />
                ))}
                <span
                  aria-hidden="true"
                  style={{
                    position: "absolute",
                    top: "50%",
                    height: 3,
                    marginTop: -1.5,
                    left: `${(Math.min(row.rate_first, row.rate_last) / max) * 100}%`,
                    width: `${(Math.abs(row.rate_first - row.rate_last) / max) * 100}%`,
                    background: "var(--viz-peer)",
                  }}
                />
                <Dot value={row.rate_first} max={max} hollow />
                <Dot value={row.rate_last} max={max} color={color} />
              </span>
              <span className="vizBars__value" style={{ minWidth: "8.5em" }}>
                {num(row.rate_last)} %<span style={muted}> ({num(row.rate_first)} %)</span>
              </span>
            </span>
          </li>
        );
      })}
      <li aria-hidden="true">
        <span />
        <span style={{ display: "flex", gap: 10 }}>
          <span style={{ position: "relative", flex: "1 1 auto", height: 16, minWidth: 120, fontSize: "0.74rem", color: "var(--viz-muted)" }}>
            {[0, 10, 20, 30, 40, 50].map((t) => (
              <span key={t} style={{ position: "absolute", whiteSpace: "nowrap", left: `${(t / max) * 100}%`, transform: t ? (t === max ? "translateX(-100%)" : "translateX(-50%)") : "none" }}>
                {t}
              </span>
            ))}
          </span>
          <span style={{ minWidth: "8.5em", fontSize: "0.74rem", color: "var(--viz-muted)" }}>% de 18-24 años</span>
        </span>
      </li>
    </ul>
  );
}

export function DecompositionBars({ lm }) {
  const max = Math.max(...lm.decomposition.map((d) => Math.abs(d.total_change)));
  return (
    <ul className="vizBars" style={{ width: "100%" }} aria-label="Bajada del abandono temprano: parte dentro de cada grupo y parte por composición">
      {lm.decomposition.map((d) => (
        <li key={d.from}>
          <span>
            Desde {d.from}: {minus(num(d.total_change))} puntos
            <span style={{ ...muted, display: "block", fontSize: "0.78rem" }}>
              {num(d.composition_pct, 0)} % por composición
            </span>
          </span>
          <span className="vizBars__track">
            <span style={{ display: "flex", width: `${(Math.abs(d.total_change) / max) * 100}%`, minWidth: 2 }}>
              <span className="vizBars__bar" style={{ width: `${(d.composition / d.total_change) * 100}%`, background: C.yellow, borderRadius: 0 }} />
              <span className="vizBars__bar" style={{ width: `${(d.within / d.total_change) * 100}%`, background: C.blue }} />
            </span>
            <span className="vizBars__value">
              {minus(num(d.composition))} <span style={muted}>·</span> {minus(num(d.within))}
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}

export function BirthBars({ birth }) {
  const last = (geo, cb) => birth[geo][cb].at(-1);
  const rows = [
    { label: "Nacidos en España", value: last("ES", "NAT"), color: C.blue },
    { label: "Nacidos en el extranjero", value: last("ES", "FOR"), color: C.orange },
    { label: "UE-27: nacidos en el país", value: last("EU27_2020", "NAT"), color: C.peer },
    { label: "UE-27: nacidos en el extranjero", value: last("EU27_2020", "FOR"), color: C.ref },
  ].filter((row) => row.value);
  const max = Math.max(...rows.map((row) => row.value.value));
  return (
    <ul className="vizBars" style={{ width: "100%" }} aria-label="Abandono temprano por país de nacimiento">
      {rows.map((row) => (
        <li key={row.label}>
          <span>{row.label}</span>
          <span className="vizBars__track">
            <span className="vizBars__bar" style={{ width: `${(row.value.value / max) * 100}%`, background: row.color }} />
            <span className="vizBars__value">
              {num(row.value.value)} %<span style={muted}> ({row.value.year})</span>
            </span>
          </span>
        </li>
      ))}
    </ul>
  );
}
