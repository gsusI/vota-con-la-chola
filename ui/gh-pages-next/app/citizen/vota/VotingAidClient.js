"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ANSWER_LABELS,
  POSITION_LABELS,
  STORAGE_KEY,
  decodeShareCode,
  encodeShareCode,
  formatMatch,
  sanitizeState,
  scoreParties,
  shareCodeFromHash,
} from "./votingAidModel.mjs";

const EMPTY_STATE = { answers: {}, important: {} };

function readStoredState(statements) {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? sanitizeState(statements, JSON.parse(raw)) : EMPTY_STATE;
  } catch {
    return EMPTY_STATE;
  }
}

function writeStoredState(state) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Private mode or blocked storage: answers simply are not remembered.
  }
}

function formatDate(value) {
  if (!value) return "—";
  const [y, m, d] = String(value).split("-");
  return d && m && y ? `${d}/${m}/${y}` : String(value);
}

function PositionBadge({ position }) {
  return <span className={`votingAidBadge votingAidBadge--${position}`}>{POSITION_LABELS[position] || position}</span>;
}

function VoteEvidence({ vote, parties }) {
  return (
    <li className="votingAidVote">
      <p className="votingAidVote__title">
        <strong>{formatDate(vote.vote_date)}</strong> · {vote.title}
        {vote.subgroup ? <span className="votingAidMuted"> · {vote.subgroup}</span> : null}
      </p>
      {vote.note ? <p className="votingAidMuted">{vote.note}</p> : null}
      <p className="votingAidMuted">
        Cuenta como «de acuerdo» votar <strong>{vote.agree_vote}</strong>.
        {vote.totals ? ` Resultado: ${vote.totals.yes} sí, ${vote.totals.no} no, ${vote.totals.abstain} abstenciones.` : ""}
      </p>
      <ul className="votingAidVote__parties">
        {parties.map((party) => {
          const pv = vote.party_votes?.[party.party_id];
          if (!pv) return null;
          return (
            <li key={party.party_id}>
              <span>{party.label}</span> <PositionBadge position={pv.position} />{" "}
              <span className="votingAidMuted">
                ({pv.yes} sí · {pv.no} no · {pv.abstain} abst.)
              </span>
            </li>
          );
        })}
      </ul>
      <p className="votingAidLinks">
        {vote.source_url ? (
          <a href={vote.source_url} rel="noopener noreferrer" target="_blank">
            Votación oficial (Congreso)
          </a>
        ) : null}
        {vote.text_url ? (
          <a href={vote.text_url} rel="noopener noreferrer" target="_blank">
            Texto votado (BOCG)
          </a>
        ) : null}
      </p>
    </li>
  );
}

function StatementCard({ statement, index, total, concernLabel, answer, important, parties, onAnswer, onImportant }) {
  const name = `answer-${statement.statement_id}`;
  return (
    <li className="votingAidStatement" id={`af-${statement.statement_id}`}>
      <fieldset>
        <legend>
          <span className="votingAidMuted">
            {index + 1}/{total}
            {concernLabel ? ` · ${concernLabel}` : ""}
          </span>
          <span className="votingAidStatement__text">{statement.text}</span>
        </legend>
        <div className="votingAidChoices">
          {Object.entries(ANSWER_LABELS).map(([value, label]) => (
            <label className={`votingAidChoice${answer === value ? " is-selected" : ""}`} key={value}>
              <input checked={answer === value} name={name} onChange={() => onAnswer(value)} type="radio" value={value} />
              {label}
            </label>
          ))}
          {answer ? (
            <button className="votingAidLinkButton" onClick={() => onAnswer(null)} type="button">
              Quitar respuesta
            </button>
          ) : null}
        </div>
        <label className="votingAidImportant">
          <input checked={Boolean(important)} disabled={!answer} onChange={(e) => onImportant(e.target.checked)} type="checkbox" />
          Es importante para mí (cuenta doble)
        </label>
      </fieldset>
      <details className="votingAidDetails">
        <summary>¿Qué se votó y cómo votó cada partido?</summary>
        {statement.context ? <p>{statement.context}</p> : null}
        <ul className="votingAidVotes">
          {statement.votes.map((vote) => (
            <VoteEvidence key={vote.vote_event_id} parties={parties} vote={vote} />
          ))}
        </ul>
      </details>
    </li>
  );
}

function ResultRow({ row, statementsById, expanded, onToggle }) {
  const pct = row.match === null ? 0 : Math.round(row.match * 100);
  return (
    <li className="votingAidResult">
      <button aria-expanded={expanded} className="votingAidResult__head" onClick={onToggle} type="button">
        <span className="votingAidResult__label">{row.label}</span>
        <span className="votingAidResult__bar" aria-hidden="true">
          <span style={{ width: `${pct}%` }} />
        </span>
        <span className="votingAidResult__pct">{formatMatch(row.match)}</span>
      </button>
      <p className="votingAidMuted">
        Comparado en {row.compared} de {row.answered} respuestas
        {row.compared < row.answered ? ` (${row.answered - row.compared} sin datos de este partido)` : ""}.
      </p>
      {expanded ? (
        <ul className="votingAidBreakdown">
          {row.details.map((d) => (
            <li key={d.statementId}>
              <a href={`#af-${d.statementId}`}>{statementsById[d.statementId]?.text}</a>
              <span>
                Tú: <strong>{ANSWER_LABELS[d.answer]}</strong>
                {d.weight > 1 ? " (importante)" : ""} · Partido: <PositionBadge position={d.position} />
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  );
}

export default function VotingAidClient({ snapshot, concernLabels = {} }) {
  const statements = useMemo(() => (Array.isArray(snapshot?.statements) ? snapshot.statements : []), [snapshot]);
  const parties = useMemo(() => (Array.isArray(snapshot?.parties) ? snapshot.parties : []), [snapshot]);
  const statementsById = useMemo(() => Object.fromEntries(statements.map((st) => [st.statement_id, st])), [statements]);
  const meta = snapshot?.meta || {};

  const [state, setState] = useState(EMPTY_STATE);
  const [loaded, setLoaded] = useState(false);
  const [fromShare, setFromShare] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [shareMessage, setShareMessage] = useState("");

  useEffect(() => {
    // A shared fragment wins over stored answers; nothing is written to the URL automatically.
    function load(initial) {
      const shared = decodeShareCode(statements, shareCodeFromHash(window.location.hash));
      if (shared) {
        setState(shared);
        setFromShare(true);
      } else if (initial) {
        setState(readStoredState(statements));
      }
      setLoaded(true);
    }
    // In-page anchors (#af-...) also fire hashchange; only a share code replaces the answers.
    const onHashChange = () => load(false);
    load(true);
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [statements]);

  useEffect(() => {
    if (loaded && !fromShare) writeStoredState(state);
  }, [state, loaded, fromShare]);

  const results = useMemo(() => scoreParties(snapshot, state.answers, state.important), [snapshot, state]);
  const answeredCount = Object.keys(state.answers).length;

  function update(next) {
    setFromShare(false);
    setState(next);
  }

  function setAnswer(id, value) {
    const answers = { ...state.answers };
    const important = { ...state.important };
    if (value) {
      answers[id] = value;
    } else {
      delete answers[id];
      delete important[id];
    }
    update({ answers, important });
  }

  function setImportant(id, value) {
    const important = { ...state.important };
    if (value) important[id] = true;
    else delete important[id];
    update({ answers: state.answers, important });
  }

  async function share() {
    const code = encodeShareCode(statements, state.answers, state.important);
    const url = `${window.location.origin}${window.location.pathname}#r=${code}`;
    try {
      await navigator.clipboard.writeText(url);
      setShareMessage("Enlace copiado. Contiene tus respuestas: compártelo solo si quieres.");
    } catch {
      setShareMessage(url);
    }
  }

  function reset() {
    update(EMPTY_STATE);
    setShareMessage("");
    if (window.location.hash) window.history.replaceState(null, "", window.location.pathname);
  }

  const draft = meta.review?.status !== "reviewed";

  return (
    <main className="shell staticRoute votingAid">
      <header className="votingAidHero">
        <p className="votingAidEyebrow">Elecciones generales · Congreso, legislatura {meta.legislature || "XV"}</p>
        <h1>¿Con quién coincides?</h1>
        <p>
          Responde a {statements.length} afirmaciones. Cada una está ligada a votaciones reales del Congreso: comparamos tus
          respuestas con <strong>cómo votó</strong> cada partido, no con lo que promete. Puedes abrir cada votación para comprobarlo.
        </p>
        <p className="votingAidMuted">
          Votaciones del {formatDate(meta.votes_first_date)} al {formatDate(meta.votes_last_date)}. Tus respuestas se quedan en
          este navegador.
        </p>
        {draft ? (
          <p className="votingAidNotice" role="note">
            <strong>Borrador sin revisión independiente.</strong> Las afirmaciones y el sentido de cada voto aún deben revisarlos
            otras personas. Úsalo para explorar, no como veredicto.
          </p>
        ) : null}
      </header>

      <div className="votingAidLayout">
        <section aria-label="Afirmaciones" className="votingAidQuestions">
          <ol className="votingAidStatements">
            {statements.map((st, i) => (
              <StatementCard
                answer={state.answers[st.statement_id]}
                concernLabel={st.concern_id ? concernLabels[st.concern_id] : null}
                important={state.important[st.statement_id]}
                index={i}
                key={st.statement_id}
                onAnswer={(value) => setAnswer(st.statement_id, value)}
                onImportant={(value) => setImportant(st.statement_id, value)}
                parties={parties}
                statement={st}
                total={statements.length}
              />
            ))}
          </ol>
        </section>

        <aside aria-label="Resultados" className="votingAidResults" id="tu-coincidencia">
          <h2>Tu coincidencia</h2>
          {answeredCount === 0 ? (
            <p className="votingAidMuted">Responde al menos una afirmación para ver resultados.</p>
          ) : (
            <>
              <p className="votingAidMuted">
                {answeredCount} de {statements.length} respondidas. El porcentaje mide cuánto se parecen tus respuestas a sus votos.
              </p>
              <ol className="votingAidResultList">
                {results.map((row) => (
                  <ResultRow
                    expanded={expanded === row.partyId}
                    key={row.partyId}
                    onToggle={() => setExpanded(expanded === row.partyId ? null : row.partyId)}
                    row={row}
                    statementsById={statementsById}
                  />
                ))}
              </ol>
              <div className="votingAidActions">
                <button onClick={share} type="button">
                  Copiar enlace con mis respuestas
                </button>
                <button onClick={reset} type="button">
                  Borrar respuestas
                </button>
              </div>
              {shareMessage ? <p className="votingAidMuted votingAidShare">{shareMessage}</p> : null}
            </>
          )}
          <details className="votingAidDetails">
            <summary>Cómo se calcula</summary>
            <ul>
              <li>La posición de un partido en una votación es lo que votó la mayoría de sus diputados.</li>
              <li>A favor cuenta +1, en contra −1, abstención o votos distintos 0. Tu respuesta: de acuerdo +1, neutral 0, en desacuerdo −1.</li>
              <li>Coincidencia por afirmación = 1 − |tú − partido| / 2; «importante» cuenta doble. Si no hay datos del partido, no cuenta.</li>
              {(meta.honesty || []).map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </details>
        </aside>
      </div>
      {answeredCount > 0 ? (
        <a className="votingAidJump" href="#tu-coincidencia">
          Ver resultados · {answeredCount}/{statements.length}
        </a>
      ) : null}
    </main>
  );
}
