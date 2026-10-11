"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ANSWER_LABELS,
  MIN_ANSWERS_FOR_RANKING,
  POSITION_LABELS,
  STORAGE_KEY,
  agreementKind,
  decodeShareCode,
  encodeShareCode,
  formatMatch,
  nextUnansweredIndex,
  sanitizeState,
  scoreParties,
  shareCodeFromHash,
  themeLabel,
} from "./votingAidModel.mjs";

const EMPTY_STATE = { answers: {}, important: {} };
const ANSWER_ORDER = ["agree", "neutral", "disagree"];
const AGREEMENT_LABELS = { match: "Coincidís", partial: "Coincidís en parte", clash: "Discrepáis", none: "Sin datos del partido" };
const AGREEMENT_ICONS = { match: "✓", partial: "≈", clash: "✗", none: "–" };

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

function prefersReducedMotion() {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

function PositionBadge({ position }) {
  return <span className={`votingAidBadge votingAidBadge--${position}`}>{POSITION_LABELS[position] || position}</span>;
}

function AgreementMark({ kind }) {
  return (
    <span className={`votingAidMark votingAidMark--${kind}`} title={AGREEMENT_LABELS[kind]}>
      <span aria-hidden="true">{AGREEMENT_ICONS[kind]}</span>
      <span className="votingAidSrOnly">{AGREEMENT_LABELS[kind]}</span>
    </span>
  );
}

function OfficialLinks({ vote }) {
  return (
    <span className="votingAidLinks">
      {vote.source_url ? (
        <a href={vote.source_url} rel="noopener noreferrer" target="_blank">
          Votación oficial
        </a>
      ) : null}
      {vote.text_url ? (
        <a href={vote.text_url} rel="noopener noreferrer" target="_blank">
          Texto votado (BOCG)
        </a>
      ) : null}
    </span>
  );
}

/** What was voted, without party positions (shown before answering, so it does not steer the answer). */
function VoteContext({ statement }) {
  return (
    <details className="votingAidDetails">
      <summary>¿Qué se votó en el Congreso?</summary>
      {statement.context ? <p>{statement.context}</p> : null}
      <ul className="votingAidVotes">
        {statement.votes.map((vote) => (
          <li className="votingAidVote" key={vote.vote_event_id}>
            <p className="votingAidVote__title">
              <strong>{formatDate(vote.vote_date)}</strong> · {vote.title}
            </p>
            {vote.note ? <p className="votingAidMuted">{vote.note}</p> : null}
            <OfficialLinks vote={vote} />
          </li>
        ))}
      </ul>
    </details>
  );
}

/** Full evidence for one vote, with every party's position and counts (results view). */
function VoteEvidence({ vote, parties, highlight }) {
  return (
    <li className="votingAidVote">
      <p className="votingAidVote__title">
        <strong>{formatDate(vote.vote_date)}</strong> · {vote.title}
      </p>
      <p className="votingAidMuted">
        {vote.note} Cuenta como «de acuerdo» votar <strong>{vote.agree_vote}</strong>.
      </p>
      <ul className="votingAidVote__parties">
        {parties.map((party) => {
          const pv = vote.party_votes?.[party.party_id];
          if (!pv) return null;
          return (
            <li className={party.party_id === highlight ? "is-highlight" : undefined} key={party.party_id}>
              <span>{party.label}</span> <PositionBadge position={pv.position} />
              <span className="votingAidMuted">
                {" "}
                {pv.yes} sí · {pv.no} no · {pv.abstain} abst.
              </span>
            </li>
          );
        })}
      </ul>
      <OfficialLinks vote={vote} />
    </li>
  );
}

function ProgressBar({ answered, total }) {
  const pct = total ? Math.round((answered / total) * 100) : 0;
  return (
    <div
      aria-label={`${answered} de ${total} respondidas`}
      aria-valuemax={total}
      aria-valuemin={0}
      aria-valuenow={answered}
      className="votingAidProgress"
      role="progressbar"
    >
      <span style={{ width: `${pct}%` }} />
    </div>
  );
}

function IntroView({ meta, statements, parties, answeredCount, onStart, onResults, draft }) {
  const resume = answeredCount > 0 && answeredCount < statements.length;
  return (
    <section className="votingAidIntro">
      <p className="votingAidEyebrow">Elecciones generales · Congreso de los Diputados</p>
      <h1>¿Con quién coincides?</h1>
      <p className="votingAidLead">
        Responde a {statements.length} afirmaciones sobre temas que se votaron en el Congreso y descubre qué partidos{" "}
        <strong>votaron</strong> como tú piensas.
      </p>
      <ul className="votingAidFacts">
        <li>
          <strong>Unos 5 minutos.</strong> Puedes saltar preguntas y volver cuando quieras.
        </li>
        <li>
          <strong>Hechos, no promesas.</strong> Cada afirmación está ligada a votaciones reales entre el{" "}
          {formatDate(meta.votes_first_date)} y el {formatDate(meta.votes_last_date)}, con enlace al registro oficial.
        </li>
        <li>
          <strong>Privado.</strong> Tus respuestas se guardan solo en este navegador.
        </li>
      </ul>
      {draft ? (
        <p className="votingAidNotice" role="note">
          <strong>Versión en revisión.</strong> Las afirmaciones y el sentido de cada voto aún deben revisarlos personas
          independientes. Úsalo para explorar, no como veredicto.
        </p>
      ) : null}
      <div className="votingAidActions votingAidActions--primary">
        <button className="votingAidButton votingAidButton--primary" onClick={onStart} type="button">
          {resume ? `Continuar (${answeredCount}/${statements.length})` : answeredCount ? "Revisar preguntas" : "Empezar"}
        </button>
        {answeredCount > 0 ? (
          <button className="votingAidButton" onClick={onResults} type="button">
            Ver mis resultados
          </button>
        ) : null}
      </div>
      <p className="votingAidMuted">Partidos comparados: {parties.map((p) => p.label).join(", ")}.</p>
    </section>
  );
}

function QuestionView({ statements, index, state, onAnswer, onSkip, onImportant, onGo, onResults }) {
  const statement = statements[index];
  const answer = state.answers[statement.statement_id];
  const important = Boolean(state.important[statement.statement_id]);
  const answeredCount = Object.keys(state.answers).length;
  const headingRef = useRef(null);

  useEffect(() => {
    // Move focus to the new statement so keyboard and screen-reader users follow the flow.
    headingRef.current?.focus({ preventScroll: true });
  }, [index]);

  return (
    <section className="votingAidQuestion" aria-label="Pregunta">
      <div className="votingAidQuestion__top">
        <span className="votingAidMuted">
          Pregunta {index + 1} de {statements.length}
        </span>
        <button className="votingAidLinkButton" onClick={onResults} type="button">
          Ver resultados ({answeredCount})
        </button>
      </div>
      <ProgressBar answered={answeredCount} total={statements.length} />

      <div className="votingAidCard">
        <p className="votingAidTheme">{themeLabel(statement)}</p>
        <h2 className="votingAidStatement__text" ref={headingRef} tabIndex={-1}>
          {statement.text}
        </h2>

        <div aria-label="Tu respuesta" className="votingAidAnswers" role="group">
          {ANSWER_ORDER.map((value, i) => (
            <button
              aria-keyshortcuts={String(i + 1)}
              aria-pressed={answer === value}
              className={`votingAidAnswer votingAidAnswer--${value}${answer === value ? " is-selected" : ""}`}
              key={value}
              onClick={() => onAnswer(value)}
              type="button"
            >
              {ANSWER_LABELS[value]}
            </button>
          ))}
        </div>

        <div className="votingAidQuestion__extras">
          <label className="votingAidImportant">
            <input checked={important} onChange={(e) => onImportant(e.target.checked)} type="checkbox" />
            <span>
              Esto es importante para mí <span className="votingAidMuted">(cuenta doble)</span>
            </span>
          </label>
          <button className="votingAidLinkButton" onClick={onSkip} type="button">
            {answer ? "Quitar respuesta" : "Saltar"}
          </button>
        </div>

        <VoteContext statement={statement} />
      </div>

      <nav aria-label="Navegación entre preguntas" className="votingAidPager">
        <button className="votingAidButton" disabled={index === 0} onClick={() => onGo(index - 1)} type="button">
          ← Anterior
        </button>
        <span className="votingAidMuted votingAidPager__hint">Atajos: 1 · 2 · 3 para responder, ← → para moverte</span>
        {index < statements.length - 1 ? (
          <button className="votingAidButton" onClick={() => onGo(index + 1)} type="button">
            Siguiente →
          </button>
        ) : (
          <button className="votingAidButton votingAidButton--primary" onClick={onResults} type="button">
            Ver resultados
          </button>
        )}
      </nav>
    </section>
  );
}

function PartyDetail({ row, statementsById, parties, onEdit }) {
  const [openId, setOpenId] = useState(null);
  const counts = row.details.reduce((acc, d) => {
    const kind = agreementKind(d.answer, d.position);
    acc[kind] = (acc[kind] || 0) + 1;
    return acc;
  }, {});
  const order = { clash: 0, partial: 1, match: 2, none: 3 };
  const details = [...row.details].sort(
    (a, b) => order[agreementKind(a.answer, a.position)] - order[agreementKind(b.answer, b.position)],
  );
  return (
    <div className="votingAidPartyDetail">
      <p className="votingAidMuted">
        Coincidís en {counts.match || 0}, en parte en {counts.partial || 0} y discrepáis en {counts.clash || 0}
        {counts.none ? `; sin datos en ${counts.none}` : ""}. Primero, las discrepancias.
      </p>
      <ul className="votingAidBreakdown">
        {details.map((d) => {
          const st = statementsById[d.statementId];
          const kind = agreementKind(d.answer, d.position);
          const open = openId === d.statementId;
          return (
            <li key={d.statementId}>
              <AgreementMark kind={kind} />
              <div className="votingAidBreakdown__body">
                <p className="votingAidBreakdown__text">{st?.text}</p>
                <p className="votingAidMuted">
                  Tú: <strong>{ANSWER_LABELS[d.answer]}</strong>
                  {d.weight > 1 ? " (importante)" : ""} · {row.label}: <PositionBadge position={d.position} />
                </p>
                <p className="votingAidBreakdown__actions">
                  <button
                    aria-expanded={open}
                    className="votingAidLinkButton"
                    onClick={() => setOpenId(open ? null : d.statementId)}
                    type="button"
                  >
                    {open ? "Ocultar votaciones" : "Ver votaciones"}
                  </button>
                  <button className="votingAidLinkButton" onClick={() => onEdit(d.statementId)} type="button">
                    Cambiar mi respuesta
                  </button>
                </p>
                {open ? (
                  <ul className="votingAidVotes">
                    {st.votes.map((vote) => (
                      <VoteEvidence highlight={row.partyId} key={vote.vote_event_id} parties={parties} vote={vote} />
                    ))}
                  </ul>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function ResultsView({ snapshot, statements, parties, state, fromShare, onEdit, onContinue, onReview, onShare, onReset, onOwn, shareMessage }) {
  const [expanded, setExpanded] = useState(null);
  const statementsById = useMemo(() => Object.fromEntries(statements.map((st) => [st.statement_id, st])), [statements]);
  const results = useMemo(() => scoreParties(snapshot, state.answers, state.important), [snapshot, state]);
  const answeredCount = Object.keys(state.answers).length;
  const provisional = answeredCount < MIN_ANSWERS_FOR_RANKING;
  const meta = snapshot?.meta || {};

  return (
    <section className="votingAidResultsView" aria-label="Resultados">
      {fromShare ? (
        <div className="votingAidNotice votingAidNotice--info" role="note">
          Estás viendo las respuestas de un enlace compartido; no se han guardado en tu navegador.{" "}
          <button className="votingAidLinkButton" onClick={onOwn} type="button">
            Hacer el test con mis respuestas
          </button>
        </div>
      ) : null}
      <h1>Tu coincidencia</h1>
      <p className="votingAidLead">
        Cuánto se parecen {fromShare ? "estas" : "tus"} {answeredCount} respuestas a cómo votó cada partido en el Congreso.
      </p>
      <ProgressBar answered={answeredCount} total={statements.length} />

      {answeredCount === 0 ? (
        <div className="votingAidEmpty">
          <p>Aún no has respondido ninguna afirmación.</p>
          <button className="votingAidButton votingAidButton--primary" onClick={onContinue} type="button">
            Empezar
          </button>
        </div>
      ) : (
        <>
          {provisional ? (
            <p className="votingAidNotice" role="note">
              <strong>Resultado provisional.</strong> Con menos de {MIN_ANSWERS_FOR_RANKING} respuestas el orden puede
              cambiar mucho.{" "}
              <button className="votingAidLinkButton" onClick={onContinue} type="button">
                Seguir respondiendo
              </button>
            </p>
          ) : null}
          <ol className="votingAidResultList">
            {results.map((row, i) => {
              const pct = row.match === null ? 0 : Math.round(row.match * 100);
              const open = expanded === row.partyId;
              return (
                <li className={`votingAidResult${open ? " is-open" : ""}`} key={row.partyId}>
                  <button
                    aria-controls={`detalle-${row.partyId}`}
                    aria-expanded={open}
                    className="votingAidResult__head"
                    onClick={() => setExpanded(open ? null : row.partyId)}
                    type="button"
                  >
                    <span className="votingAidResult__rank">{row.match === null ? "–" : i + 1}</span>
                    <span className="votingAidResult__label">{row.label}</span>
                    <span aria-hidden="true" className="votingAidResult__bar">
                      <span style={{ width: `${pct}%` }} />
                    </span>
                    <span className="votingAidResult__pct">{formatMatch(row.match)}</span>
                    <span aria-hidden="true" className="votingAidResult__chevron">
                      {open ? "▾" : "▸"}
                    </span>
                  </button>
                  <p className="votingAidMuted votingAidResult__coverage">
                    {row.compared === row.answered
                      ? `Comparado en ${row.answered} respuestas`
                      : `Comparado en ${row.compared} de ${row.answered} respuestas (sin datos en ${row.answered - row.compared})`}
                  </p>
                  {open ? (
                    <div id={`detalle-${row.partyId}`}>
                      <PartyDetail onEdit={onEdit} parties={parties} row={row} statementsById={statementsById} />
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ol>
          <div className="votingAidActions">
            {answeredCount < statements.length ? (
              <button className="votingAidButton votingAidButton--primary" onClick={onContinue} type="button">
                Responder las {statements.length - answeredCount} restantes
              </button>
            ) : null}
            <button className="votingAidButton" onClick={onReview} type="button">
              Revisar mis respuestas
            </button>
            <button className="votingAidButton" onClick={onShare} type="button">
              Copiar enlace con mis respuestas
            </button>
            <button className="votingAidButton votingAidButton--quiet" onClick={onReset} type="button">
              Borrar respuestas
            </button>
          </div>
          {shareMessage ? <p className="votingAidMuted votingAidShare">{shareMessage}</p> : null}
        </>
      )}

      <details className="votingAidDetails votingAidMethod">
        <summary>Cómo se calcula y qué no mide</summary>
        <ul>
          <li>La posición de un partido en cada votación es lo que votó la mayoría de sus diputados.</li>
          <li>
            Partido: a favor +1, en contra −1, abstención o votos distintos 0. Tú: de acuerdo +1, neutral 0, en desacuerdo −1.
          </li>
          <li>
            Coincidencia por afirmación = 1 − |tú − partido| / 2. «Importante» cuenta doble. Si el partido no votó, esa
            afirmación no cuenta para él.
          </li>
          {(meta.honesty || []).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </details>
    </section>
  );
}

function ReviewView({ statements, state, onAnswer, onEditQuestion, onResults }) {
  const groups = useMemo(() => {
    const out = [];
    statements.forEach((st, index) => {
      const label = themeLabel(st);
      const last = out[out.length - 1];
      if (last && last.label === label) last.items.push({ st, index });
      else out.push({ label, items: [{ st, index }] });
    });
    return out;
  }, [statements]);
  return (
    <section className="votingAidReview" aria-label="Tus respuestas">
      <h1>Tus respuestas</h1>
      <p className="votingAidLead">Cambia cualquier respuesta aquí; los resultados se actualizan al momento.</p>
      {groups.map((group) => (
        <div className="votingAidReview__group" key={group.label}>
          <h2 className="votingAidTheme">{group.label}</h2>
          <ul className="votingAidReview__list">
            {group.items.map(({ st, index }) => {
              const answer = state.answers[st.statement_id];
              return (
                <li key={st.statement_id}>
                  <button className="votingAidReview__text" onClick={() => onEditQuestion(index)} type="button">
                    {st.text}
                    {state.important[st.statement_id] ? <span className="votingAidStar"> ★ importante</span> : null}
                  </button>
                  <div aria-label="Tu respuesta" className="votingAidSegmented" role="group">
                    {ANSWER_ORDER.map((value) => (
                      <button
                        aria-pressed={answer === value}
                        className={answer === value ? "is-selected" : undefined}
                        key={value}
                        onClick={() => onAnswer(st.statement_id, answer === value ? null : value)}
                        type="button"
                      >
                        {ANSWER_LABELS[value]}
                      </button>
                    ))}
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      <div className="votingAidActions">
        <button className="votingAidButton votingAidButton--primary" onClick={onResults} type="button">
          Ver resultados
        </button>
      </div>
    </section>
  );
}

export default function VotingAidClient({ snapshot }) {
  const statements = useMemo(() => (Array.isArray(snapshot?.statements) ? snapshot.statements : []), [snapshot]);
  const parties = useMemo(() => (Array.isArray(snapshot?.parties) ? snapshot.parties : []), [snapshot]);
  const meta = snapshot?.meta || {};

  const [state, setState] = useState(EMPTY_STATE);
  const [loaded, setLoaded] = useState(false);
  const [fromShare, setFromShare] = useState(false);
  const [view, setView] = useState("intro");
  const [index, setIndex] = useState(0);
  const [shareMessage, setShareMessage] = useState("");
  const advanceTimer = useRef(null);
  const topRef = useRef(null);

  useEffect(() => {
    // A shared fragment wins over stored answers and opens the results; nothing is written to the URL automatically.
    function load(initial) {
      const shared = decodeShareCode(statements, shareCodeFromHash(window.location.hash));
      if (shared) {
        setState(shared);
        setFromShare(true);
        setView("results");
      } else if (initial) {
        setState(readStoredState(statements));
      }
      setLoaded(true);
    }
    const onHashChange = () => load(false);
    load(true);
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [statements]);

  useEffect(() => {
    if (loaded && !fromShare) writeStoredState(state);
  }, [state, loaded, fromShare]);

  useEffect(() => () => clearTimeout(advanceTimer.current), []);

  const answeredCount = Object.keys(state.answers).length;

  const show = useCallback((nextView, nextIndex) => {
    clearTimeout(advanceTimer.current);
    if (typeof nextIndex === "number") setIndex(nextIndex);
    setView(nextView);
    topRef.current?.scrollIntoView({ block: "start", behavior: prefersReducedMotion() ? "auto" : "smooth" });
  }, []);

  function update(next) {
    if (fromShare) {
      // Editing a shared result turns it into the visitor's own answers.
      setFromShare(false);
      if (window.location.hash) window.history.replaceState(null, "", window.location.pathname);
    }
    setState(next);
  }

  function setAnswer(id, value) {
    const answers = { ...state.answers };
    const important = { ...state.important };
    if (value) answers[id] = value;
    else {
      delete answers[id];
      delete important[id];
    }
    update({ answers, important });
    return answers;
  }

  function answerCurrent(value) {
    const id = statements[index].statement_id;
    const answers = setAnswer(id, value);
    clearTimeout(advanceTimer.current);
    // Brief pause so the selection is visible before moving on.
    advanceTimer.current = setTimeout(
      () => {
        const next = nextUnansweredIndex(statements, answers, index + 1);
        if (next === -1) show("results");
        else if (next > index) show("question", next);
        else if (index < statements.length - 1) show("question", index + 1);
        else show("results");
      },
      prefersReducedMotion() ? 0 : 280,
    );
  }

  function skipCurrent() {
    const id = statements[index].statement_id;
    if (state.answers[id]) {
      setAnswer(id, null);
      return;
    }
    if (index < statements.length - 1) show("question", index + 1);
    else show("results");
  }

  function setImportant(id, value) {
    const important = { ...state.important };
    if (value) important[id] = true;
    else delete important[id];
    update({ answers: state.answers, important });
  }

  function start() {
    const next = nextUnansweredIndex(statements, state.answers, 0);
    show("question", next === -1 ? 0 : next);
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
    if (answeredCount > 0 && !window.confirm("¿Borrar todas tus respuestas de este navegador?")) return;
    update(EMPTY_STATE);
    setShareMessage("");
    if (window.location.hash) window.history.replaceState(null, "", window.location.pathname);
    show("intro", 0);
  }

  function ownAnswers() {
    window.history.replaceState(null, "", window.location.pathname);
    setFromShare(false);
    setState(readStoredState(statements));
    show("intro", 0);
  }

  // Keyboard shortcuts while answering: 1/2/3 answer, ←/→ move.
  useEffect(() => {
    if (view !== "question") return undefined;
    function onKey(event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const tag = event.target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (event.key === "1" || event.key === "2" || event.key === "3") {
        event.preventDefault();
        answerCurrent(ANSWER_ORDER[Number(event.key) - 1]);
      } else if (event.key === "ArrowRight" && index < statements.length - 1) {
        event.preventDefault();
        show("question", index + 1);
      } else if (event.key === "ArrowLeft" && index > 0) {
        event.preventDefault();
        show("question", index - 1);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const draft = meta.review?.status !== "reviewed";

  return (
    <main className="shell staticRoute votingAid" ref={topRef}>
      {view !== "intro" ? (
        <nav aria-label="Secciones del test" className="votingAidTabs">
          <button aria-current={view === "question" ? "page" : undefined} onClick={start} type="button">
            Preguntas
          </button>
          <button aria-current={view === "review" ? "page" : undefined} onClick={() => show("review")} type="button">
            Respuestas <span className="votingAidMuted">{answeredCount}/{statements.length}</span>
          </button>
          <button aria-current={view === "results" ? "page" : undefined} onClick={() => show("results")} type="button">
            Resultados
          </button>
        </nav>
      ) : null}

      {view === "intro" ? (
        <IntroView
          answeredCount={answeredCount}
          draft={draft}
          meta={meta}
          onResults={() => show("results")}
          onStart={start}
          parties={parties}
          statements={statements}
        />
      ) : null}
      {view === "question" && statements[index] ? (
        <QuestionView
          index={index}
          onAnswer={answerCurrent}
          onGo={(i) => show("question", i)}
          onImportant={(value) => setImportant(statements[index].statement_id, value)}
          onResults={() => show("results")}
          onSkip={skipCurrent}
          state={state}
          statements={statements}
        />
      ) : null}
      {view === "results" ? (
        <ResultsView
          fromShare={fromShare}
          onContinue={start}
          onEdit={(id) => show("question", statements.findIndex((st) => st.statement_id === id))}
          onOwn={ownAnswers}
          onReset={reset}
          onReview={() => show("review")}
          onShare={share}
          parties={parties}
          shareMessage={shareMessage}
          snapshot={snapshot}
          state={state}
          statements={statements}
        />
      ) : null}
      {view === "review" ? (
        <ReviewView
          onAnswer={setAnswer}
          onEditQuestion={(i) => show("question", i)}
          onResults={() => show("results")}
          state={state}
          statements={statements}
        />
      ) : null}
    </main>
  );
}
