import { GRADE, STANCE, VERDICT, dateEs } from "./model.mjs";

const POS = { S: "backed", N: "opposed", A: "abstained" };

function Sources({ items }) {
  if (!items?.length) return null;
  return (
    <ul className="decSources">
      {items.map((s) => (
        <li key={`${s.url}-${s.finding}`}>
          {s.grade ? (
            <span className="decGrade" title={GRADE[s.grade]}>
              {s.grade}
            </span>
          ) : null}{" "}
          <a href={s.url} rel="noopener noreferrer" target="_blank">
            {s.authors_year || s.source}
          </a>
          {s.method ? <span className="decMuted"> ({s.method})</span> : null}: {s.finding}
          {s.locator ? <span className="decMuted"> [{s.locator}]</span> : null}
        </li>
      ))}
    </ul>
  );
}

// Decisions a government takes without a Congress vote (e.g. the yearly minimum-wage royal decree). Only whoever
// governs can take them, so they are attributed to the governing parties and never set against the opposition.
export default function GovernmentBlock({ government, labels }) {
  if (!government?.blocks?.length) return null;
  return (
    <>
      <section className="card vizProse" id="gobierno" aria-labelledby="gobierno-title">
        <h2 id="gobierno-title">Lo que decide el Gobierno sin votación del Congreso</h2>
        <p>
          <strong>Requiere gobernar.</strong> {government.note} Por eso este bloque va aparte: no hay una decisión equivalente que un partido de
          la oposición pudiera haber tomado.
        </p>
      </section>
      {government.blocks.map((b) => (
        <section key={b.rule} className="decMeasures" aria-labelledby={`gob-${b.rule}`}>
          <h2 id={`gob-${b.rule}`}>{b.label}</h2>
          <div className="vizTable__scroll decLedger">
            <table>
              <caption className="decSr">{b.label}: cada decisión, quién gobernaba y qué dice la evidencia</caption>
              <thead>
                <tr>
                  <th scope="col">Año</th>
                  <th scope="col">Norma</th>
                  <th scope="col">Gobierno</th>
                  <th scope="col">Evaluación</th>
                </tr>
              </thead>
              <tbody>
                {b.decisions.map((d) => (
                  <tr key={d.decision_id}>
                    <td>{d.year}</td>
                    <td>
                      <a href={d.boe_url} rel="noopener noreferrer" target="_blank">
                        {d.instrument}
                      </a>{" "}
                      <span className="decMuted">({dateEs(d.date)})</span>
                    </td>
                    <td>
                      {d.government}
                      <span className="decMuted"> · requiere gobernar</span>
                    </td>
                    <td>
                      {d.documented ? (
                        <a href={`#g-${d.decision_id}`}>
                          {VERDICT[d.verdict]?.marker} {VERDICT[d.verdict]?.short}
                        </a>
                      ) : (
                        <span className="decMuted">pendiente de documentar</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {b.decisions
            .filter((d) => d.documented)
            .map((d) => (
              <article key={d.decision_id} className="decMeasure" id={`g-${d.decision_id}`} aria-labelledby={`g-${d.decision_id}-t`}>
                <h3 id={`g-${d.decision_id}-t`}>{d.name || d.title}</h3>
                <p className="decMuted">
                  {d.instrument} · {dateEs(d.date)} · {d.government} · requiere gobernar, sin votación en el Congreso
                </p>
                <p>
                  <strong>Qué cambia.</strong> {d.what_changes}
                </p>
                <p>
                  <strong>Objetivo que declara.</strong> {d.stated_goal}
                </p>
                <p>
                  <strong>Qué dice la evidencia: {VERDICT[d.verdict]?.short}.</strong> {d.verdict_reason}
                </p>
                {d.ex_ante?.length ? (
                  <>
                    <p className="decLabel">Estimación previa (oficial)</p>
                    <Sources items={d.ex_ante} />
                  </>
                ) : null}
                {d.ex_post?.length ? (
                  <>
                    <p className="decLabel">Evaluaciones posteriores</p>
                    <Sources items={d.ex_post} />
                  </>
                ) : null}
                {d.evidence_against?.length ? (
                  <>
                    <p className="decLabel">Evidencia en contra</p>
                    <Sources items={d.evidence_against} />
                  </>
                ) : null}
              </article>
            ))}
          {b.positions?.length ? (
            <>
              <p className="decLabel">
                Posiciones en el Congreso sobre el mismo asunto (mociones y proposiciones no de ley, sin efecto legal): {b.positions.length}
              </p>
              <ul className="decMoves">
                {b.positions.map((p) => (
                  <li key={p.vote_id}>
                    {dateEs(p.date)}: {p.summary_yes} ({p.approved ? "aprobada" : "rechazada"}).{" "}
                    {["S", "N", "A"].map((c) => {
                      const who = Object.entries(p.parties)
                        .filter(([, ch]) => ch === c)
                        .map(([pid]) => labels[pid] || pid);
                      return who.length ? (
                        <span key={c}>
                          <strong>{STANCE[POS[c]].short}:</strong> {who.join(", ")}.{" "}
                        </span>
                      ) : null;
                    })}
                    <a href={p.official_vote_url} rel="noopener noreferrer" target="_blank">
                      Votación
                    </a>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </section>
      ))}
    </>
  );
}
