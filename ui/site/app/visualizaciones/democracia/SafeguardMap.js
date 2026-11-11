import { CLASS_COLORS, CLASS_SHORT, PARTY_COLORS, num } from "./charts";

const POWER_LABELS = {
  obliga: "obliga",
  anula: "anula",
  sustituye: "sustituye",
  automatica: "consecuencia automática",
  declara: "solo declara",
  nadie: "nadie",
};
const PEERS = [
  ["DEU", "DE"],
  ["FRA", "FR"],
  ["ITA", "IT"],
  ["PRT", "PT"],
];
const T0 = 1978;
const W = 300;
const H = 26;

function yearFrac(day) {
  const [y, m, d] = day.split("-").map(Number);
  return y + (m - 1) / 12 + (d - 1) / 365;
}

export function partyOfEpisode(ep, governments) {
  const id = ep.power_holder?.government;
  return id ? governments.find((g) => g.id === id)?.party : null;
}

// The safeguard map: one row per safeguard with who enforces it, the sanction, the remedy delay, every episode
// since 1978 placed on a timeline and coloured by the party in government, and the peer panel (DE, FR, IT, PT).
export default function SafeguardMap({ safeguards, governments, snapshot, maxDelay }) {
  const T1 = yearFrac(snapshot);
  const sx = (day) => ((yearFrac(day) - T0) / (T1 - T0)) * W;
  return (
    <div className="demoMap" role="table" aria-label="Mapa de salvaguardas">
      <div className="demoMap__head" role="row">
        <span role="columnheader">Salvaguarda</span>
        <span role="columnheader">Clase</span>
        <span role="columnheader">Quién la hace cumplir · sanción</span>
        <span role="columnheader">Retraso del remedio</span>
        <span role="columnheader" className="demoMap__timeline">
          <svg viewBox={`0 0 ${W} 14`} aria-label={`Episodios ${T0}–${snapshot.slice(0, 4)}`}>
            {[1980, 1990, 2000, 2010, 2020].map((y) => (
              <text key={y} x={sx(`${y}-01-01`)} y="11" textAnchor="middle" className="demoChart__tick">
                {y}
              </text>
            ))}
          </svg>
        </span>
        <span role="columnheader">Pares</span>
      </div>
      {safeguards.map((sg) => {
        const delay = sg.remedy_delay?.days;
        return (
          <div className="demoMap__row" role="row" key={sg.id}>
            <span role="cell" className="demoMap__name">
              <a href={`#s-${sg.id}`}>{sg.name}</a>
              <span className="demoMap__art">{sg.rule.articles.join(" · ")}</span>
            </span>
            <span role="cell">
              <span className="demoPill" style={{ background: CLASS_COLORS[sg.classification] }}>
                {CLASS_SHORT[sg.classification]}
              </span>
            </span>
            <span role="cell" className="demoMap__enf">
              <strong>{sg.enforcer.short || sg.enforcer.who}</strong> ({POWER_LABELS[sg.enforcer.power]}). {sg.sanction_short || sg.sanction}
            </span>
            <span role="cell" className="demoMap__delay">
              {delay == null ? (
                <span className="demoMap__muted">sin remedio de tercero</span>
              ) : (
                <>
                  <span className="demoMap__delayBar" style={{ width: `${Math.max(2, (delay / maxDelay) * 100)}%` }} aria-hidden="true" />
                  <span>{num(delay)} días</span>
                </>
              )}
            </span>
            <span role="cell" className="demoMap__timeline">
              <svg viewBox={`0 0 ${W} ${H}`} aria-label={`${sg.episodes.length} episodios`}>
                <line x1="0" x2={W} y1={H / 2} y2={H / 2} className="demoMap__axis" />
                {[1980, 1990, 2000, 2010, 2020].map((y) => (
                  <line key={y} x1={sx(`${y}-01-01`)} x2={sx(`${y}-01-01`)} y1={H / 2 - 3} y2={H / 2 + 3} className="demoMap__axis" />
                ))}
                {sg.episodes.map((ep) => {
                  const party = partyOfEpisode(ep, governments);
                  const color = party ? PARTY_COLORS[party] : "#52514e";
                  const x = sx(ep.start);
                  const title = `${ep.start}${ep.end ? ` a ${ep.end}` : ""} · ${ep.summary}`;
                  if (ep.kind === "plazo_vencido") {
                    const x2 = sx(ep.end || snapshot);
                    return (
                      <rect key={ep.id} x={x} y={H / 2 - 4} width={Math.max(2.5, x2 - x)} height={8} fill={color} opacity={0.75}>
                        <title>{title}</title>
                      </rect>
                    );
                  }
                  if (ep.kind === "aval" || ep.kind === "remedio") {
                    return (
                      <path key={ep.id} d={`M${x - 4},${H / 2} L${x},${H / 2 - 5} L${x + 4},${H / 2} L${x},${H / 2 + 5} Z`} fill="none" stroke={color} strokeWidth="1.5">
                        <title>{title}</title>
                      </path>
                    );
                  }
                  return (
                    <circle
                      key={ep.id}
                      cx={x}
                      cy={H / 2}
                      r={4.5}
                      fill={ep.kind === "incumplimiento_declarado" ? color : "var(--demo-bg, #fff)"}
                      stroke={color}
                      strokeWidth="1.6"
                    >
                      <title>{title}</title>
                    </circle>
                  );
                })}
              </svg>
            </span>
            <span role="cell" className="demoMap__peers">
              {PEERS.map(([code, short]) => {
                const peer = sg.peers[code];
                return (
                  <span
                    key={code}
                    className="demoPeer"
                    style={{ background: CLASS_COLORS[peer?.classification] || "#d9d7cf" }}
                    title={`${short}: ${peer?.mechanism || ""}`}
                  >
                    {short}
                  </span>
                );
              })}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function MapLegend() {
  return (
    <ul className="vizLegend demoLegend" aria-label="Leyenda del mapa">
      {Object.entries(CLASS_SHORT)
        .filter(([k]) => k !== "no_aplica")
        .map(([k, label]) => (
          <li key={k}>
            <span className="vizLegend__key" style={{ background: CLASS_COLORS[k], width: 12, height: 12 }} aria-hidden="true" />
            {label}
          </li>
        ))}
      {Object.entries(PARTY_COLORS).map(([party, color]) => (
        <li key={party}>
          <span className="vizLegend__key" style={{ background: color, width: 10, height: 10, borderRadius: 6 }} aria-hidden="true" />
          Gobierno {party}
        </li>
      ))}
      <li>
        <span className="vizLegend__key" style={{ background: "#52514e", width: 10, height: 10, borderRadius: 6 }} aria-hidden="true" />
        Mayoría reforzada u otro órgano
      </li>
      <li>● incumplimiento declarado · ○ tensión · ▬ plazo vencido · ◇ aval o remedio</li>
    </ul>
  );
}
