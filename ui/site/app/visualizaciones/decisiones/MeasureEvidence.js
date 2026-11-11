import { GRADE, STANCE, UNIT, VERDICT, dateEs, measureName, movedWith, partiesIn } from "./model.mjs";

function SourceList({ items, kind }) {
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
          {kind === "against" ? <span className="decMuted"> En contra de la lectura principal.</span> : null}
        </li>
      ))}
    </ul>
  );
}

function PartyVotes({ m, labels }) {
  const groups = { backed: [], opposed: [], abstained: [], split: [] };
  for (const p of partiesIn([m])) {
    const r = m.parties[p];
    if (groups[r.stance]) groups[r.stance].push(`${labels[p] || p}${r.decisive_if_absent ? " (decisivo)" : ""}`);
  }
  return (
    <p>
      {Object.entries(groups)
        .filter(([, list]) => list.length)
        .map(([stance, list]) => (
          <span key={stance} className="decVoteLine">
            <span className="decDot" style={{ background: STANCE[stance].color }} aria-hidden="true" />
            <strong>{STANCE[stance].short}:</strong> {list.join(", ")}.{" "}
          </span>
        ))}
    </p>
  );
}

// One measure, documented: what it changes, its stated goal, how parties voted and what the evidence says.
export default function MeasureEvidence({ m, n, labels }) {
  const verdict = VERDICT[m.verdict] || VERDICT.pendiente;
  return (
    <article className="decMeasure" id={`m-${m.measure_id}`} aria-labelledby={`m-${m.measure_id}-t`}>
      <h3 id={`m-${m.measure_id}-t`}>
        <span className="decMatrix__n">{n}</span> {measureName(m)}
      </h3>
      <p className="decMuted">
        {UNIT[m.unit]} · votada el {dateEs(m.date)} (legislatura {m.legislature === "14" ? "XIV" : "XV"}) · {m.totals.si} sí, {m.totals.no} no,{" "}
        {m.totals.abst} abstenciones{m.absolute_majority_required ? " (necesitaba 176 síes)" : ""} ·{" "}
        {m.yes_backs_measure ? "" : "votar Sí era devolver el proyecto al Gobierno · "}
        {m.lapsed
          ? "aprobada en el Congreso, pero caducó antes de publicarse: no llegó a tener efecto"
          : m.took_effect
            ? "salió adelante"
            : m.unit === "contrafactual"
              ? ""
              : "no llegó a tener efecto"}
        {m.legal_status ? ` · hoy: ${m.legal_status}` : ""}
      </p>
      {m.documented ? (
        <>
          <p>
            <strong>Qué cambia.</strong> {m.what_changes}
          </p>
          {m.in_force?.length ? (
            <p>
              <strong>En vigor.</strong>{" "}
              {m.in_force.map((f) => `${f.what}: ${dateEs(f.date)} (${f.provision})`).join("; ")}.
            </p>
          ) : null}
          <p>
            <strong>Objetivo que declara.</strong> {m.stated_goal}
            {m.stated_goal_url ? (
              <>
                {" "}
                <a href={m.stated_goal_url} rel="noopener noreferrer" target="_blank">
                  (texto)
                </a>
              </>
            ) : null}
          </p>
        </>
      ) : (
        <p className="decMuted">{m.title}</p>
      )}
      <PartyVotes m={m} labels={labels} />
      {m.documented ? (
        <>
          <p>
            <strong>Qué dice la evidencia: {verdict.short}.</strong> {m.verdict_reason}
          </p>
          {m.ex_ante?.length ? (
            <>
              <p className="decLabel">Estimación previa (oficial)</p>
              <SourceList items={m.ex_ante} />
            </>
          ) : null}
          {m.ex_post?.length ? (
            <>
              <p className="decLabel">Evaluaciones posteriores</p>
              <SourceList items={m.ex_post} />
            </>
          ) : null}
          {m.evidence_against?.length ? (
            <>
              <p className="decLabel">Evidencia en contra</p>
              <SourceList items={m.evidence_against} kind="against" />
            </>
          ) : null}
          {m.later_route ? (
            <p>
              <strong>Después:</strong>{" "}
              <a href={m.later_route.boe_url} rel="noopener noreferrer" target="_blank">
                {m.later_route.name}
              </a>{" "}
              ({dateEs(m.later_route.date)}).
            </p>
          ) : null}
        </>
      ) : null}
      {m.indicator_moves?.length || m.indicators?.length ? (
        <ul className="decMoves">
          {(m.indicator_moves || []).map((mv) => (
            <li key={`${mv.domain}-${mv.indicator}`}>{movedWith(mv)}</li>
          ))}
          {(m.indicators || []).map((ind) => (
            <li key={ind.label}>
              {ind.label}: {ind.before?.value?.toLocaleString("es-ES")} ({ind.before?.period}
              {ind.before?.url ? (
                <>
                  ,{" "}
                  <a href={ind.before.url} rel="noopener noreferrer" target="_blank">
                    fuente
                  </a>
                </>
              ) : null}
              ) → {ind.after?.value?.toLocaleString("es-ES")} ({ind.after?.period})
              {ind.unit ? ` ${ind.unit}` : ""}.{" "}
              <a href={ind.url} rel="noopener noreferrer" target="_blank">
                {ind.source}
              </a>
              . Se movió con la medida; no prueba efecto.
            </li>
          ))}
        </ul>
      ) : null}
      <p className="decLinks">
        {m.boe_url ? (
          <a href={m.boe_url} rel="noopener noreferrer" target="_blank">
            Texto oficial
          </a>
        ) : null}
        {m.boe_url ? " · " : ""}
        <a href={m.official_vote_url} rel="noopener noreferrer" target="_blank">
          Votación en el Congreso (datos abiertos)
        </a>
        {m.review?.status && m.review.status !== "pending" ? <span className="decMuted"> · revisión: {m.review.status === "pass" ? "verificada contra la fuente" : m.review.status === "corrected" ? "corregida tras revisión" : m.review.status}</span> : null}
      </p>
    </article>
  );
}
