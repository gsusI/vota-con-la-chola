import { STANCE, VERDICT, dateEs, measureName, partiesIn } from "./model.mjs";

const SHORT = {
  psoe: "PSOE", sumar: "Sumar", up: "UP", podemos: "Pod.", erc: "ERC", bildu: "Bildu", pnv: "PNV", bng: "BNG", cc: "CC",
  junts: "Junts", plural: "Plural", mixto: "Mixto", cs: "Cs", pp: "PP", upn: "UPN", vox: "Vox",
};
const LETTER = { backed: "F", opposed: "C", abstained: "A", split: "D", absent: "" };

// Measures × parties: colour = the party's vote on the measure, ring = its votes decided the result.
export default function VoteMatrix({ measures, labels, numbering, caption }) {
  const parties = partiesIn(measures);
  return (
    <div className="decMatrix">
      <table>
        <caption className="decSr">{caption}</caption>
        <thead>
          <tr>
            <th scope="col" className="decMatrix__measure">Medida</th>
            {parties.map((p) => (
              <th scope="col" key={p} title={labels[p] || p}>
                <span className="decMatrix__party">{SHORT[p] || p}</span>
              </th>
            ))}
            <th scope="col" title="Resultado de la evaluación posterior">Evaluación</th>
          </tr>
        </thead>
        <tbody>
          {measures.map((m) => (
            <tr key={m.measure_id} className={m.took_effect ? "" : "decMatrix__cf"}>
              <th scope="row" className="decMatrix__measure">
                <a href={`#m-${m.measure_id}`}>
                  <span className="decMatrix__n">{numbering[m.measure_id]}</span> {measureName(m)}
                </a>
                <span className="decMatrix__meta">
                  {dateEs(m.date)} · {m.took_effect ? "salió adelante" : "no tuvo efecto"} · {m.totals.si}–{m.totals.no}
                  {m.totals.abst ? ` (${m.totals.abst} abst.)` : ""}
                </span>
              </th>
              {parties.map((p) => {
                const r = m.parties[p];
                const stance = r ? r.stance : "absent";
                const decisive = r?.decisive_if_absent;
                const title = r
                  ? `${labels[p] || p}: ${STANCE[stance].label} (Sí ${r.S}, No ${r.N}, Abst. ${r.A})${decisive ? ". Sin sus votos el resultado cambiaba" : ""}`
                  : `${labels[p] || p}: sin escaño en esa votación`;
                return (
                  <td key={p} title={title}>
                    <span
                      className={`decCell decCell--${stance}${decisive ? " decCell--decisive" : ""}`}
                      style={{ background: STANCE[stance].color }}
                      aria-label={title}
                    >
                      {LETTER[stance]}
                    </span>
                  </td>
                );
              })}
              <td className="decMatrix__verdict" title={VERDICT[m.verdict]?.label}>
                <span aria-hidden="true">{VERDICT[m.verdict]?.marker}</span> {VERDICT[m.verdict]?.short}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
