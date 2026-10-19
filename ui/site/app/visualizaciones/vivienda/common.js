import HousingChart from "./HousingChart";

export const C = {
  blue: "#2a78d6",
  orange: "#eb6834",
  aqua: "#1baf7a",
  yellow: "#eda100",
  ref: "#52514e",
  peer: "#b4b2a9",
};

export const NAMES = {
  ES: "España",
  ESP: "España",
  EU27_2020: "Media UE-27",
  EU: "Media UE",
  OECD: "OCDE",
  DE: "Alemania",
  DEU: "Alemania",
  FR: "Francia",
  FRA: "Francia",
  IT: "Italia",
  ITA: "Italia",
  PT: "Portugal",
  PRT: "Portugal",
};

export const num = (value, digits = 1) =>
  Number(value).toLocaleString("es-ES", { minimumFractionDigits: digits, maximumFractionDigits: digits });
export const thousands = (value) => Math.round(Number(value)).toLocaleString("es-ES", { useGrouping: "always" });
export const millions = (value, digits = 2) =>
  Math.abs(Number(value)) >= 1e6 ? `${num(Number(value) / 1e6, digits)} millones` : thousands(value);
// «1,67 millones de hogares» but «957.674 viviendas».
export const howMany = (value, noun) => (Math.abs(Number(value)) >= 1e6 ? `${millions(value)} de ${noun}` : `${thousands(value)} ${noun}`);
export const day = (iso) => (iso ? String(iso).slice(0, 10) : null);
export const at = (rows, year) => rows?.find((p) => p.year === year)?.value;
export const pct = (value, digits = 1) => `${num(value, digits)} %`;
// «A, B y C».
export const joinEs = (items) => (items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}`);

// Bars use at most 70 % of the track so the value label always fits beside them, also on phones.
export function Bars({ rows, max, label }) {
  return (
    <ul className="vizBars hvBars" aria-label={label}>
      {rows.map((row) => (
        <li key={row.id}>
          <span>{row.label}</span>
          <span className="vizBars__track">
            <span className="vizBars__bar" style={{ width: `${(Math.max(0, row.value) / max) * 70}%`, background: row.color }} />
            <span className="vizBars__value">{row.text}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

// Spain against each peer, one panel per peer with a shared scale (as in /visualizaciones/carga-fiscal/).
export function PeerPanels({ data, spain, peers, unit, digits = 1, xMin, xMax, yMax, panelNote }) {
  return (
    <div className="vizMultiples">
      {peers.map((geo) => {
        const other = data[geo] || [];
        if (!other.length) return null;
        return (
          <div key={geo}>
            <h3 className="vizPanelTitle">
              España frente a {NAMES[geo]}
              <span>{panelNote(other, geo)}</span>
            </h3>
            <HousingChart
              series={[
                { id: geo, label: NAMES[geo], color: geo === "EU27_2020" || geo === "OECD" ? C.ref : C.peer, points: other },
                { id: spain, label: "España", color: C.blue, emphasis: true, points: data[spain] },
              ]}
              unit={unit}
              digits={digits}
              xMin={xMin}
              xMax={xMax}
              yMax={yMax}
              height={210}
              ariaLabel={`España frente a ${NAMES[geo]}`}
            />
          </div>
        );
      })}
    </div>
  );
}

export const PEER_LEGEND = [
  { id: "ES", label: "España", color: C.blue },
  { id: "other", label: "País o media de comparación", color: C.ref },
];

// «menos que» / «más que» / «al ritmo de»: compares a change with two others, within one point counts as the same pace.
export function paceWord(value, ...others) {
  if (others.every((o) => value < o - 1)) return "menos que";
  if (others.every((o) => value > o + 1)) return "más que";
  return "al ritmo de";
}
