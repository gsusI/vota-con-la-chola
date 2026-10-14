"use client";

import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState } from "react";
import { withBasePath } from "../../path-utils.mjs";
import {
  ANSWER_LABELS,
  ANSWER_VALUES,
  MIN_ANSWERS_FOR_RANKING,
  POOL_ANSWER_LABELS,
  POSITION_LABELS,
  agreementKind,
  aiLinks,
  attachHighlights,
  buildAiPrompt,
  buildQuestions,
  decodeAnyShareCode,
  encodeShareCode,
  encodeShareCodeV2,
  groupDetails,
  impactShardKeys,
  linkPrompt,
  matchShare,
  mergeImpacts,
  nextInTopic,
  nextQuestionId,
  partyReactions,
  pendingSubId,
  playOrder,
  podiumShareText,
  questionTopic,
  resultsSpread,
  revealSummary,
  scoreParties,
  scorePercent,
  shareCodeFromHash,
  stepLists,
  stepNeighbors,
  topicGroups,
} from "./votingAidModel.mjs";
import { formatReleased, otherVersions, versionById } from "./votingAidVersions.mjs";
import SidePanel from "./SidePanel";
import { NAVIGATE_EVENT, VIEW_EVENT } from "./VotaShell";
import { DirectionBar, PoleLegend, VoteRow } from "./temas/VoteAtlasClient";
import { ATLAS_PATH, directionText, formatCount, indexAtlas, votesForAxis } from "./voteAtlasModel.mjs";

const ANSWER_ORDER = ["agree", "neutral", "disagree"];
const EMPTY_STATE = { answers: {}, important: {}, skipped: {}, split: {}, history: [], seed: 0, streak: 0, bestStreak: 0, showReveal: true, excludeOmnibus: false };
const AGREEMENT_LABELS = { match: "Coincidís", partial: "A medias", clash: "Discrepáis", none: "Sin datos" };
const AGREEMENT_ICONS = { match: "✓", partial: "≈", clash: "✗", none: "–" };
const POOL_PATH = "/citizen/data/voting_aid_pool_v1.json";
const HIGHLIGHTS_PATH = "/citizen/data/voting_aid_highlights_v1.json";
const BULLETS_PATH = "/citizen/data/voting_aid_vote_bullets_v1.json";
const IMPACTS_PATH = "/citizen/data/voting_aid_vote_impacts_v1.json";
const IMPACTS_SHARD_DIR = "/citizen/data/voting_aid_vote_impacts_v1";
// Asks for the per-vote «Ramificaciones» shards of a question when it is shown (the index only has statement figures).
const NeedImpactsContext = createContext(() => {});

// ---------------------------------------------------------------------------
// State persistence (local only; ids of questions the page has not loaded are kept, never dropped).

function cleanState(raw) {
  const out = { ...EMPTY_STATE, answers: {}, important: {}, skipped: {}, split: {} };
  if (!raw || typeof raw !== "object") return out;
  for (const [id, v] of Object.entries(raw.answers || {})) if (ANSWER_VALUES[v] !== undefined) out.answers[id] = v;
  for (const [id, v] of Object.entries(raw.important || {})) if (v === true && out.answers[id]) out.important[id] = true;
  for (const [id, v] of Object.entries(raw.skipped || {})) if (v === true) out.skipped[id] = true;
  // Multi-vote statements the user chose to answer "por partes" (their own answer is cleared).
  for (const [id, v] of Object.entries(raw.split || {})) if (v === true && !out.answers[id]) out.split[id] = true;
  out.history = Array.isArray(raw.history) ? raw.history.filter((id) => out.answers[id]).slice(-500) : Object.keys(out.answers);
  out.seed = Number.isInteger(raw.seed) && raw.seed > 0 ? raw.seed : 0;
  out.streak = Number.isInteger(raw.streak) ? raw.streak : 0;
  out.bestStreak = Number.isInteger(raw.bestStreak) ? raw.bestStreak : 0;
  out.showReveal = raw.showReveal !== false;
  out.excludeOmnibus = raw.excludeOmnibus === true;
  return out;
}

// Each test version keeps its own answers (see votingAidVersions.mjs).
function readStoredRaw(key) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function readStoredState(key) {
  return cleanState(readStoredRaw(key));
}

/**
 * First visit to a new version: start from the answers of the version it replaces, but only for questions both
 * share (the endless-mode votes). The old version's own storage is never touched.
 */
function initialState(version, questionIds) {
  const own = readStoredRaw(version.storageKey);
  if (own || !version.seedFrom) return cleanState(own);
  const prev = cleanState(readStoredRaw(versionById(version.seedFrom).storageKey));
  const out = cleanState(null);
  for (const [id, v] of Object.entries(prev.answers)) {
    if (!questionIds.has(id)) continue;
    out.answers[id] = v;
    if (prev.important[id]) out.important[id] = true;
  }
  out.history = prev.history.filter((id) => out.answers[id]);
  out.bestStreak = prev.bestStreak;
  out.showReveal = prev.showReveal;
  return out;
}

function writeStoredState(key, state) {
  try {
    window.localStorage.setItem(key, JSON.stringify(state));
  } catch {
    // Private mode or blocked storage: answers simply are not remembered.
  }
}

function newSeed() {
  return 1 + Math.floor(Math.random() * 2 ** 30);
}

function formatDate(value) {
  if (!value) return "—";
  const [y, m, d] = String(value).split("-");
  return d && m && y ? `${d}/${m}/${y}` : String(value);
}

function reducedMotion() {
  return mediaMatches("(prefers-reduced-motion: reduce)");
}

function mediaMatches(query) {
  try {
    return window.matchMedia(query).matches;
  } catch {
    return false;
  }
}

const FINE_POINTER_QUERY = "(hover: hover) and (pointer: fine)";

function answerLabel(question, answer) {
  return (question?.source === "pool" ? POOL_ANSWER_LABELS : ANSWER_LABELS)[answer] || "—";
}

// ---------------------------------------------------------------------------
// Small pieces

function PositionBadge({ position, score = null }) {
  const pct = scorePercent(score);
  return (
    <span
      className={`votingAidBadge votingAidBadge--${position}`}
      title={pct === null ? undefined : `En el ${pct} % de sus votos empujó en el sentido de la afirmación`}
    >
      {POSITION_LABELS[position] || position}
      {pct === null ? "" : ` · ${pct} %`}
    </span>
  );
}

function axisMapHref(question) {
  return withBasePath(`/citizen/vota/temas/#eje=${encodeURIComponent(question.axis_id)}`);
}

function EvidenceVote({ vote: v }) {
  return (
    <li>
      {v.agree_vote === "Sí" ? "A favor de: " : "En contra de: "}
      {v.summary_yes || v.title}{" "}
      <span className="votingAidVoted__loc">
        {formatDate(v.vote_date)} ·{" "}
        <a href={v.source_url} rel="noopener noreferrer" target="_blank">
          votación
        </a>
        {v.text_url ? (
          <>
            {" · "}
            <a href={v.text_url} rel="noopener noreferrer" target="_blank">
              texto
            </a>
          </>
        ) : null}
      </span>
    </li>
  );
}

/**
 * Evidence for a multi-vote statement, shown before answering: what kind of votes back it (plain summaries,
 * dates, official links), never how anyone voted. The full list with party votes lives in the topic map.
 */
function AxisEvidence({ question, parties }) {
  const [panelOpen, setPanelOpen] = useState(false);
  const closePanel = useCallback(() => setPanelOpen(false), []);
  const votes = question.votes || [];
  return (
    <section aria-label="Qué se votó" className="votingAidVoted votingAidAxisEvidence">
      <p className="votingAidVoted__title">
        Resume <strong>{question.votes_total} votaciones</strong> de {question.initiatives_total}{" "}
        {question.initiatives_total === 1 ? "iniciativa" : "iniciativas"} en el Congreso. Algunas:
      </p>
      <ul className="votingAidVoted__list">
        {votes.slice(0, 3).map((v) => (
          <EvidenceVote key={v.id} vote={v} />
        ))}
      </ul>
      {votes.length > 3 ? (
        <p className="votingAidVoted__actions">
          <button aria-expanded={panelOpen} className="votingAidLinkButton" onClick={() => setPanelOpen(true)} type="button">
            Ver más ejemplos ({votes.length})
          </button>
        </p>
      ) : null}
      <SidePanel onClose={closePanel} open={panelOpen} title="Ejemplos de lo que se votó">
        <p className="sidePanel__lead">«{question.text}»</p>
        <p className="votingAidMuted">
          {votes.length < question.votes_total ? `${votes.length} de las ${question.votes_total}` : `Las ${votes.length}`} votaciones que resume
          esta afirmación. Sin decir qué votó cada partido: lo verás al responder.
        </p>
        <ul className="votingAidVoted__list">
          {votes.map((v) => (
            <EvidenceVote key={v.id} vote={v} />
          ))}
        </ul>
      </SidePanel>
      <p className="votingAidMuted votingAidVoted__src">
        «A favor de» y «en contra de» indican qué voto cuenta como estar de acuerdo con la afirmación. Qué votación va a cada tema lo
        decidió una IA leyendo el texto oficial; falta la revisión humana.
      </p>
      <Ramifications question={question} />
      <AskAiToggle
        label="¿Quieres más detalle? Que te lo explique una IA"
        opts={{ mode: "explain" }}
        parties={parties}
        question={question}
        title="Pide una explicación sencilla de lo que se votó (sin decirte qué votó cada partido):"
      />
    </section>
  );
}

// The topic map (~1 MB) is fetched once, the first time someone opens an axis panel.
let atlasPromise = null;
function loadAtlas() {
  atlasPromise ||= fetch(withBasePath(ATLAS_PATH))
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
    .catch((err) => {
      atlasPromise = null;
      throw err;
    });
  return atlasPromise;
}

const AXIS_PAGE = 15;

/**
 * The votes behind an axis statement, with each party's choice: the same ones the test counts (this axis first,
 * confidence alta/media, current legislature), so the count and the party bars match the question.
 */
function AxisVotesPanel({ question }) {
  const [atlas, setAtlas] = useState(null);
  const [failed, setFailed] = useState(false);
  const [shown, setShown] = useState(AXIS_PAGE);
  useEffect(() => {
    let cancelled = false;
    loadAtlas()
      .then((data) => !cancelled && setAtlas(data))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);
  const axis = useMemo(() => (atlas ? indexAtlas(atlas).axisById[question.axis_id] : null), [atlas, question.axis_id]);
  const votes = useMemo(
    () => (axis ? votesForAxis(atlas, axis.axis_id).filter((v) => v.primary && v.confidence !== "baja") : []),
    [atlas, axis],
  );
  // Party scores come from the question (towards the statement); flip them onto the axis poles.
  const toAxis = question.pole === "-" ? -1 : 1;
  if (failed) return <p className="va-note">No se pudieron cargar las votaciones. Inténtalo de nuevo más tarde.</p>;
  if (!atlas) return <p className="votingAidMuted">Cargando votaciones…</p>;
  if (!axis) return <p className="votingAidMuted">Este tema ya no está en el mapa de temas.</p>;
  return (
    <>
      <p className="sidePanel__lead">{axis.label}</p>
      <PoleLegend axis={axis} />
      <div className="atlasAxis__bars">
        {(atlas.parties || []).map((p) => {
          const cell = question.cells?.[p.party_id];
          const score = Number.isFinite(cell?.score) ? cell.score * toAxis : NaN;
          return (
            <DirectionBar
              key={p.party_id}
              label={p.label}
              score={score}
              sub={Number.isFinite(score) ? `${directionText(axis, score)} · ${cell.votes_with_data} vot.` : "Sin votaciones"}
            />
          );
        })}
      </div>
      <p className="votingAidMuted">
        Las {votes.length} votaciones que cuentan en esta pregunta, de la más reciente a la más antigua.{" "}
        <a href={axisMapHref(question)}>Abrir en el mapa de temas</a>
      </p>
      <ul className="atlasVotes">
        {votes.slice(0, shown).map((v) => (
          <VoteRow atlas={atlas} axis={axis} key={v.id} kindLabels={atlas.kind_labels} vote={v} />
        ))}
      </ul>
      {votes.length > shown ? (
        <button className="v-btn" onClick={() => setShown(shown + AXIS_PAGE)} type="button">
          Ver más ({votes.length - shown})
        </button>
      ) : null}
    </>
  );
}

function AgreementMark({ kind }) {
  return (
    <span className={`votingAidMark votingAidMark--${kind}`} title={AGREEMENT_LABELS[kind]}>
      <span aria-hidden="true">{AGREEMENT_ICONS[kind]}</span>
      <span className="votingAidSrOnly">{AGREEMENT_LABELS[kind]}</span>
    </span>
  );
}

function QuestionLinks({ question }) {
  const [panelOpen, setPanelOpen] = useState(false);
  const closePanel = useCallback(() => setPanelOpen(false), []);
  const links = [];
  if (question.axis_id) {
    links.push({ href: axisMapHref(question), label: `Ver las ${question.votes_total} votaciones y cómo votó cada partido`, internal: true });
  } else if (question.source === "pool") {
    if (question.source_url) links.push({ href: question.source_url, label: "Votación oficial" });
    if (question.text_url) links.push({ href: question.text_url, label: "Texto (BOCG)" });
  } else {
    for (const v of question.votes || []) {
      if (v.source_url) links.push({ href: v.source_url, label: `Votación ${formatDate(v.vote_date)}` });
      if (v.text_url) links.push({ href: v.text_url, label: "Texto (BOCG)" });
    }
  }
  if (!links.length) return null;
  return (
    <span className="votingAidLinks">
      {links.map((l) =>
        l.internal ? (
          <a
            aria-expanded={panelOpen}
            href={l.href}
            key={l.href + l.label}
            onClick={(e) => {
              if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
              e.preventDefault();
              setPanelOpen(true);
            }}
          >
            {l.label}
          </a>
        ) : (
          <a href={l.href} key={l.href + l.label} rel="noopener noreferrer" target="_blank">
            {l.label}
          </a>
        ),
      )}
      {question.axis_id ? (
        <SidePanel onClose={closePanel} open={panelOpen} title="Cómo votó cada partido">
          <AxisVotesPanel question={question} />
        </SidePanel>
      ) : null}
    </span>
  );
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/**
 * Links that open ChatGPT / Claude with the question already written, and Gemini after copying it.
 * The prompt holds exactly what was voted (official title, date, result, party votes, official links),
 * never the user's answers; it is shown in full before sending.
 */
function AskAi({ prompt, linkText, title }) {
  const [note, setNote] = useState("");
  const links = useMemo(() => aiLinks(linkText || prompt), [linkText, prompt]);
  async function onOpen(link) {
    const copied = await copyText(prompt);
    if (!link.prefill) setNote(copied ? `Pregunta copiada: pégala en ${link.label}.` : `Copia la pregunta de abajo y pégala en ${link.label}.`);
    else setNote("");
  }
  return (
    <div className="votingAidAskAi">
      <p className="votingAidAskAi__title">
        {title}
      </p>
      <div className="votingAidAskAi__links">
        {links.map((link) => (
          <a
            className="votingAidAskAi__link"
            href={link.href}
            key={link.id}
            onClick={() => onOpen(link)}
            rel="noopener noreferrer"
            target="_blank"
          >
            {link.label}
            {!link.prefill ? <span className="votingAidMuted"> (copia y pega)</span> : null}
          </a>
        ))}
        <button
          className="votingAidAskAi__link"
          onClick={async () => setNote((await copyText(prompt)) ? "Pregunta copiada." : "No se pudo copiar: selecciónala abajo.")}
          type="button"
        >
          Copiar pregunta
        </button>
      </div>
      {note ? (
        <p aria-live="polite" className="votingAidMuted votingAidAskAi__note">
          {note}
        </p>
      ) : null}
      <details className="votingAidAskAi__prompt">
        <summary>Ver la pregunta que se envía</summary>
        <pre>{prompt}</pre>
      </details>
      <p className="votingAidMuted votingAidAskAi__disclaimer">
        Se abre en otra web con esta pregunta, sin tus respuestas. Las IA se equivocan: contrasta con los enlaces oficiales.
      </p>
    </div>
  );
}

function AskAiToggle({ label, question, parties, opts, title }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="votingAidAskAiToggle">
      <button aria-expanded={open} className="votingAidLinkButton" onClick={() => setOpen(!open)} type="button">
        {label}
      </button>
      {open ? (
        <AskAi linkText={linkPrompt(question, parties, opts)} prompt={buildAiPrompt(question, parties, opts)} title={title} />
      ) : null}
    </div>
  );
}

function ScopeBadges({ question }) {
  if (!question.omnibus && !question.offtopic) return null;
  const themes = [...new Set((question.highlights || []).flatMap((h) => h.doc.themes || []))];
  return (
    <p className="votingAidScope">
      {question.omnibus ? (
        <span className="votingAidScope__badge votingAidScope__badge--omnibus" title={themes.join(", ")}>
          Votación ómnibus: mezcla {themes.length} temas
        </span>
      ) : null}
      {question.offtopic ? (
        <span className="votingAidScope__badge votingAidScope__badge--offtopic">
          También cambia leyes de otros temas
        </span>
      ) : null}
    </p>
  );
}

/** What the voted text really contains: literal headings from the official text, with its source. */
function WhatsInside({ question, only = null, embedded = false }) {
  const [open, setOpen] = useState(false);
  const items = only ? (question.highlights || []).filter((h) => h.doc === only) : question.highlights || [];
  if (!items.length) return null;
  const many = items.length > 1;
  return (
    <section aria-label="Qué incluye según el texto oficial" className={`votingAidInside${embedded ? " votingAidInside--embedded" : ""}`}>
      {embedded ? null : <ScopeBadges question={question} />}
      {items.map((h) => {
        const d = h.doc;
        // Motions carry their literal points in full; other texts their (clipped) literal headings.
        const lines = d.points?.length ? d.points.map((p) => `${p.n}. ${p.text}`) : d.bullets;
        const shown = open ? lines : lines.slice(0, 3);
        const hidden = (d.points?.length ? lines.length : d.bullets_total || lines.length) - shown.length;
        return (
          <div className="votingAidInside__doc" key={d.url}>
            <p className="votingAidInside__title">
              {d.bullets_basis === "puntos" ? "Puntos literales" : "Índice literal"}
              {many && h.vote_date ? ` (votación del ${formatDate(h.vote_date)})` : ""}
              <span className="votingAidMuted"> · texto oficial ({d.source})</span>
            </p>
            <ul className="votingAidInside__list">
              {shown.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
            {open && d.modified_norms?.length && d.bullets_basis !== "normas" ? (
              <p className="votingAidMuted votingAidInside__norms">
                Modifica {d.modified_norms_total} {d.modified_norms_total === 1 ? "norma" : "normas"}: {d.modified_norms.join(" · ")}
                {d.modified_norms_total > d.modified_norms.length ? " …" : ""}
              </p>
            ) : null}
            {open && d.offtopic_riders?.length ? (
              <p className="votingAidInside__offtopic">
                En sus disposiciones finales también cambia: {d.offtopic_riders.join(" · ")}
              </p>
            ) : null}
            <p className="votingAidInside__actions">
              {hidden > 0 || (!open && (d.modified_norms?.length || d.offtopic_riders?.length)) ? (
                <button aria-expanded={open} className="votingAidLinkButton" onClick={() => setOpen(!open)} type="button">
                  {open ? "Ver menos" : hidden > 0 ? `Ver todo (${hidden} más)` : "Ver normas que modifica"}
                </button>
              ) : null}
              {embedded ? null : (
                <a href={d.url} rel="noopener noreferrer" target="_blank">
                  Texto completo ({d.source})
                </a>
              )}
            </p>
          </div>
        );
      })}
    </section>
  );
}

const EVIDENCE_LABELS = { organismo_publico: "Organismo público", estudio: "Estudio", debate: "Debate en el Congreso" };

function SourceLink({ href, children }) {
  return (
    <a href={href} rel="noopener noreferrer" target="_blank">
      {children}
    </a>
  );
}

/**
 * «Ramificaciones»: who a vote affects and how many they are (official figures), and, open by default (as
 * important as who it affects), what changes for each group and the knock-on effects someone expects or fears, each with its source. Shown before
 * answering, so it never names who argued what: the Diario de Sesiones link says it.
 */
function Ramifications({ question }) {
  const [open, setOpen] = useState(true);
  const needImpacts = useContext(NeedImpactsContext);
  useEffect(() => needImpacts(question), [needImpacts, question.statement_id]);
  const r = question.ramifications;
  if (!r) return null;
  const votes = r.votes.filter((v) => v.direct.length || v.indirect.length || v.gaps);
  const many = votes.length > 1;
  // Figures come from official sources; only the effects carry a review status.
  const review = !votes.length ? "" : votes.some((v) => v.review === "draft") ? " · Efectos: borrador sin revisión humana" : " · Efectos: verificados con IA, sin revisión humana";
  return (
    <div className="votingAidRamif">
      {r.facts.length ? (
        <>
          <p className="votingAidVoted__title">
            A quién afecta
          </p>
          <ul className="votingAidRamif__facts">
            {r.facts.map((f) => (
              <li key={f.id}>
                {f.text}{" "}
                <span className="votingAidVoted__loc">
                  <SourceLink href={f.url}>{f.source}</SourceLink>, {f.period}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {votes.length ? (
        <p className="votingAidVoted__actions">
          <button aria-expanded={open} className="votingAidLinkButton" onClick={() => setOpen((o) => !o)} type="button">
            {open ? "Ocultar" : votes.some((v) => v.indirect.length) ? "Ver qué cambia para cada colectivo y posibles consecuencias" : "Ver qué cambia para cada colectivo"}
          </button>
        </p>
      ) : null}
      {open
        ? votes.map((v) => {
            const benefits = v.indirect.filter((e) => e.kind === "beneficio_esperado");
            const risks = v.indirect.filter((e) => e.kind === "riesgo_senalado");
            return (
              <div className="votingAidRamif__vote" key={v.vote_event_id}>
                {many && v.vote_date ? <p className="votingAidRamif__when">Votación del {formatDate(v.vote_date)}</p> : null}
                {v.direct.length ? (
                  <>
                    <p className="votingAidRamif__head">Qué cambiaría para cada colectivo</p>
                    <ul className="votingAidVoted__list">
                      {v.direct.map((d) => (
                        <li key={d.actor}>
                          <strong>{d.actor}:</strong> {d.text} <span className="votingAidVoted__loc">{d.locator}</span>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : null}
                {[
                  ["Lo que se espera que mejore", benefits, "plus"],
                  ["Riesgos que se han señalado", risks, "minus"],
                ].map(([title, list, tone]) =>
                  list.length ? (
                    <div className={`votingAidRamif__side votingAidRamif__side--${tone}`} key={tone}>
                      <p className="votingAidRamif__head">{title}</p>
                      <ul className="votingAidVoted__list">
                        {list.map((e) => (
                          <li key={e.text}>
                            {e.text}{" "}
                            <span className="votingAidVoted__loc">
                              <span className="votingAidRamif__evidence">{EVIDENCE_LABELS[e.evidence] || e.evidence}</span>{" "}
                              <SourceLink href={e.url}>{e.source}</SourceLink>, {e.locator}
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null,
                )}
                {v.gaps ? (
                  <p className="votingAidMuted votingAidRamif__gaps">
                    <strong>Lo que no se sabe:</strong> {v.gaps}
                  </p>
                ) : null}
              </div>
            );
          })
        : null}
      <p className="votingAidMuted votingAidVoted__src">
        Cifras de fuentes oficiales.
        {votes.some((v) => v.indirect.length) ? " Los efectos indirectos son previsiones con su fuente, no hechos; los del debate se resumen sin decir quién los dijo." : ""}
        {review}
      </p>
    </div>
  );
}

/**
 * «Qué se votaba»: plain-language bullets written from the official text (draft until reviewed), with a link
 * to the full text, the literal headings/points as evidence and the AI explanation for more detail.
 * Shown before answering, so it never names the proposer nor says how anyone voted.
 */
function WhatVoted({ question, parties }) {
  const [literalFor, setLiteralFor] = useState(null);
  const [expanded, setExpanded] = useState({});
  const items = question.whatVoted || [];
  if (question.axis_id) return <AxisEvidence parties={parties} question={question} />;
  const many = items.length > 1;
  // Several votes behind one question: 3 bullets each until expanded, so the answers stay in reach.
  const fold = many ? 3 : 6;
  if (!items.length) return null;
  return (
    <section aria-label="Qué se votaba" className="votingAidVoted">
      <ScopeBadges question={question} />
      {items.map((w, i) => {
        const doc = w.doc || null;
        const url = w.url || doc?.url;
        const label = w.text_status_label || doc?.text_status_label;
        if (w.status === "pending" && !doc) return null; // bullets still loading, or not drafted yet
        return (
          <div className="votingAidVoted__doc" key={`${w.vote_event_id}-${i}`}>
            <p className="votingAidVoted__title">
              Qué se votaba{many && w.vote_date ? ` (votación del ${formatDate(w.vote_date)})` : ""}
            </p>
            {w.status === "ok" && w.simple ? (
              <p className="votingAidVoted__simple">
                <span className="votingAidVoted__simpleLabel">En pocas palabras:</span> {w.simple}
              </p>
            ) : null}
            {w.status === "ok" && (!w.simple || expanded[i]) ? (
              <ul className="votingAidVoted__list">
                {(expanded[i] || w.simple ? w.bullets : w.bullets.slice(0, fold)).map((b) => (
                  <li key={b.text}>
                    {b.text} <span className="votingAidVoted__loc">{b.locator}</span>
                  </li>
                ))}
              </ul>
            ) : doc ? null : (
              <p className="votingAidMuted votingAidVoted__none">
                Sin texto oficial enlazado: solo tenemos el título de la votación.
              </p>
            )}
            {w.status === "ok" && (!w.simple || expanded[i]) ? (
              <p className="votingAidMuted votingAidVoted__src">
                Resumen del texto oficial ({w.source || doc?.source}){label ? ` · ${label}` : ""}
                {w.review === "draft" ? " · borrador sin revisar" : w.review === "agent_reviewed" ? " · verificado con IA contra el texto, sin revisión humana" : ""}
              </p>
            ) : null}
            {doc && (w.status !== "ok" || literalFor === i) ? <WhatsInside embedded only={doc} question={question} /> : null}
            {url || doc || (w.status === "ok" && (w.simple || w.bullets.length > fold)) ? (
              <p className="votingAidVoted__actions">
                {w.status === "ok" && w.simple ? (
                  <button aria-expanded={Boolean(expanded[i])} className="votingAidLinkButton" onClick={() => setExpanded((e) => ({ ...e, [i]: !e[i] }))} type="button">
                    {expanded[i] ? "Ocultar detalle" : `Ver en detalle (${w.bullets.length} ${w.bullets.length === 1 ? "punto" : "puntos"})`}
                  </button>
                ) : w.status === "ok" && w.bullets.length > fold ? (
                  <button aria-expanded={Boolean(expanded[i])} className="votingAidLinkButton" onClick={() => setExpanded((e) => ({ ...e, [i]: !e[i] }))} type="button">
                    {expanded[i] ? "Ver menos" : `Ver ${w.bullets.length - fold} más`}
                  </button>
                ) : null}
                {url ? (
                  <a href={url} rel="noopener noreferrer" target="_blank">
                    Ver texto completo ({w.source || doc?.source || "oficial"})
                  </a>
                ) : null}
                {doc && w.status === "ok" ? (
                  <button aria-expanded={literalFor === i} className="votingAidLinkButton" onClick={() => setLiteralFor(literalFor === i ? null : i)} type="button">
                    {literalFor === i ? "Ocultar texto literal" : doc.bullets_basis === "puntos" ? "Ver puntos literales" : "Ver índice literal"}
                  </button>
                ) : null}
              </p>
            ) : null}
          </div>
        );
      })}
      <Ramifications question={question} />
      <AskAiToggle
        label="¿Quieres más detalle? Que te lo explique una IA"
        opts={{ mode: "explain" }}
        parties={parties}
        question={question}
        title="Pide una explicación sencilla de lo que se vota (sin decirte qué votó cada partido):"
      />
    </section>
  );
}

// Percent with the Spanish thin space convention used across the test ("64 %").
function pctText(value) {
  return Number.isFinite(value) ? `${Math.round(value * 100)} %` : "sin datos";
}

const pad2 = (n) => String(n).padStart(2, "0");

const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

function monthYear(value) {
  const [y, m] = String(value || "").split("-");
  const name = MONTHS[Number(m) - 1];
  return name && y ? `${name} de ${y}` : "";
}

function svgProps(size) {
  return { "aria-hidden": true, width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round", strokeLinejoin: "round" };
}

function StarIcon({ filled = false, size = 18 }) {
  return (
    <svg {...svgProps(size)} fill={filled ? "currentColor" : "none"}>
      <path d="M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" />
    </svg>
  );
}

function SplitIcon({ size = 18 }) {
  return (
    <svg {...svgProps(size)}>
      <path d="M6 4v6a4 4 0 004 4h8M6 4v16M14 10l4 4-4 4" />
    </svg>
  );
}

function ChevronIcon({ dir = "down", size = 18 }) {
  return (
    <svg {...svgProps(size)} className="va-chevron">
      <path d={dir === "right" ? "M9 6l6 6-6 6" : "M6 9l6 6 6-6"} />
    </svg>
  );
}

function ShareIcon({ size = 18 }) {
  return (
    <svg {...svgProps(size)}>
      <path d="M12 15V3M7 8l5-5 5 5M5 13v6a2 2 0 002 2h10a2 2 0 002-2v-6" />
    </svg>
  );
}

function ListIcon({ size = 22 }) {
  return (
    <svg {...svgProps(size)}>
      <path d="M4 6h16M4 12h16M4 18h10" />
    </svg>
  );
}

function Toast({ toast }) {
  return (
    <div aria-live="polite" className={`va-toast${toast ? " is-visible" : ""}`} role="status">
      {toast ? toast.text : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Intro

function IntroView({ meta, questionsTotal, curatedTotal, poolStatus, parties, answeredCount, onStart, onResults }) {
  const keyVotes = meta?.quality?.votes_total;
  return (
    <section aria-labelledby="va-intro-title" className="va-intro">
      <p className="v-kicker">Elecciones generales · Congreso de los Diputados</p>
      <h1 className="v-h1" id="va-intro-title">
        ¿Con quién coincides?
      </h1>
      <p className="va-intro__pitch">Prometer no obliga. Votar queda registrado.</p>
      <p className="v-lead">
        Las promesas electorales no obligan a nada; lo que vota cada partido en el Congreso queda registrado. Responde qué habrías
        votado tú en votaciones reales y compara con lo que votó cada partido. Responde todo lo que quieras: hay{" "}
        {poolStatus === "ready" ? questionsTotal : "cientos de"} preguntas.
      </p>
      <div className="va-intro__cta">
        <button className="v-btn v-btn--primary" onClick={onStart} type="button">
          {answeredCount ? `Seguir respondiendo (${answeredCount} respondidas)` : "Empezar el test"}
        </button>
        {answeredCount > 0 ? (
          <button className="v-btn" onClick={onResults} type="button">
            Ver mis resultados
          </button>
        ) : null}
      </div>
      <ul className="va-intro__facts">
        <li>
          <strong>Empieza con {curatedTotal} preguntas clave</strong>
          {keyVotes ? `, que resumen ${formatCount(keyVotes)} votaciones del Congreso,` : ""} y sigue con votaciones concretas una a
          una, sin límite.
        </li>
        <li>
          <strong>Tras cada respuesta ves cómo votó cada partido:</strong> quién votó como tú, quién a medias y quién lo contrario.
        </li>
        <li>
          <strong>Hechos, no promesas:</strong> votaciones del {formatDate(meta.votes_first_date)} en adelante, cada una con su enlace
          oficial.
        </li>
        <li>
          <strong>Privado:</strong> tus respuestas se quedan en este navegador.
        </li>
      </ul>
      <p className="va-note" role="note">
        <strong>Versión en revisión.</strong> Qué votación va a cada pregunta lo decidió una IA leyendo el texto oficial y aún deben
        revisarlo personas independientes; las votaciones concretas usan el título oficial tal cual. Úsalo para explorar, no como
        veredicto. <a href={withBasePath("/citizen/vota/explorar/")}>Explorar votaciones, partidos y diputados</a> ·{" "}
        <a href={withBasePath("/citizen/vota/metodologia/")}>Cómo se hizo (fuentes, IA y prompts)</a>
      </p>
      <p className="v-muted">Partidos comparados: {parties.map((p) => p.label).join(", ")}.</p>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Play: one question, then the reveal

const SWIPE_THRESHOLD = 90;

/** Horizontal swipe on touch screens: right = agree, left = disagree. Vertical scrolling is untouched. */
function useSwipe(onSwipe, resetKey) {
  const start = useRef(null);
  const [dx, setDx] = useState(0);
  const dragging = useRef(false);
  useEffect(() => {
    setDx(0);
    start.current = null;
    dragging.current = false;
  }, [resetKey]);
  const handlers = {
    onPointerDown(e) {
      if (e.pointerType === "mouse") return;
      start.current = { x: e.clientX, y: e.clientY, id: e.pointerId };
      dragging.current = false;
    },
    onPointerMove(e) {
      const s = start.current;
      if (!s || s.id !== e.pointerId) return;
      const mx = e.clientX - s.x;
      const my = e.clientY - s.y;
      if (!dragging.current) {
        if (Math.abs(mx) < 12 || Math.abs(mx) < Math.abs(my) * 1.3) return;
        dragging.current = true;
      }
      setDx(mx);
    },
    onPointerUp(e) {
      const s = start.current;
      start.current = null;
      if (!s || !dragging.current) return;
      const mx = e.clientX - s.x;
      if (mx > SWIPE_THRESHOLD) onSwipe("agree");
      else if (mx < -SWIPE_THRESHOLD) onSwipe("disagree");
      setDx(0);
    },
    onPointerCancel() {
      start.current = null;
      dragging.current = false;
      setDx(0);
    },
    onClickCapture(e) {
      // A drag that ended over a button must not also count as a tap.
      if (dragging.current) {
        e.preventDefault();
        e.stopPropagation();
        dragging.current = false;
      }
    },
  };
  return { dx, handlers };
}

/** Which version of the test this is, with links to the others (they all stay online). */
function VersionBanner({ version, onIntro }) {
  const others = otherVersions(version.id);
  if (!others.length) return null;
  if (version.current) {
    // The pointer to older versions belongs on the start page, not above every question.
    if (!onIntro) return null;
    return (
      <p className="v-muted va-version">
        Versión actual del test ({formatReleased(version.released)}). ¿Hiciste una anterior? Tus respuestas siguen ahí:{" "}
        {others.map((v, i) => (
          <span key={v.id}>
            {i ? " · " : ""}
            <a href={withBasePath(v.path)}>
              {v.label} ({formatReleased(v.released)})
            </a>
          </span>
        ))}
        .
      </p>
    );
  }
  const current = others.find((v) => v.current) || others[0];
  return (
    <p className="va-note va-note--info va-version" role="note">
      <strong>Versión anterior del test</strong> ({version.label}, {formatReleased(version.released)}): {version.summary}. Se mantiene para
      que puedas revisar tus respuestas y compararlas. <a href={withBasePath(current.path)}>Ir a la versión actual</a> ({current.summary}).
    </p>
  );
}

/** Your top parties in the other versions of the test, computed from the answers saved for each one. */
function OtherVersionResults({ version, pool }) {
  const [rows, setRows] = useState([]);
  useEffect(() => {
    let cancelled = false;
    const others = otherVersions(version.id).filter((v) => Object.keys(readStoredState(v.storageKey).answers).length);
    Promise.all(
      others.map((v) =>
        fetch(withBasePath(`/${v.snapshot}`))
          .then((r) => (r.ok ? r.json() : null))
          .then((snap) => {
            if (!snap) return null;
            const qs = buildQuestions(snap, pool);
            const ids = new Set(qs.map((q) => q.statement_id));
            const st = readStoredState(v.storageKey);
            const answered = Object.keys(st.answers).filter((id) => ids.has(id)).length;
            const top = scoreParties({ parties: snap.parties || [], statements: qs }, st.answers, st.important).filter((r) => r.match !== null).slice(0, 3);
            return answered ? { version: v, answered, top } : null;
          })
          .catch(() => null),
      ),
    ).then((list) => !cancelled && setRows(list.filter(Boolean)));
    return () => {
      cancelled = true;
    };
  }, [version.id, pool]);
  if (!rows.length) return null;
  return (
    <section aria-label="Compara con otras versiones del test" className="va-compare">
      {rows.map((r) => (
        <p className="v-muted" key={r.version.id}>
          ¿Hiciste la {r.version.current ? "versión actual" : r.version.label} ({formatReleased(r.version.released)})? Con {r.answered} respuestas,
          tu podio allí: {r.top.map((t, i) => `${i + 1}. ${t.label} ${pctText(t.match)}`).join(" · ") || "—"}.{" "}
          <a href={withBasePath(r.version.path)}>Compara tus resultados</a>
        </p>
      ))}
    </section>
  );
}

function SplitOffer({ question, onSplit }) {
  const n = question.subIds?.length || 0;
  if (!n || !onSplit) return null;
  return (
    <div className="va-note va-note--info va-splitOffer">
      <p>
        <strong>¿Te da igual o depende del caso?</strong> Esta pregunta resume {question.votes_total} votaciones. Responde {n} concretas, de
        iniciativas distintas, y afinamos tu resultado. Tu «neutral» aquí dejará de contar.
      </p>
      <button className="v-btn" onClick={onSplit} type="button">
        <SplitIcon /> Responder por partes
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Topic rail: jump to another topic (and stay in it) or to any question of the current one.

// Key questions and concrete votes are counted apart everywhere, so the topic rail, its question list and the
// progress line add up. A split key question counts as done (its votes are then counted as votes).
function topicCounts(ids, questionsById, answers, split) {
  const counts = { keys: 0, keysDone: 0, votes: 0, votesDone: 0 };
  for (const id of ids) {
    const done = answers[id] !== undefined || Boolean(split?.[id]);
    if (questionsById[id]?.source === "curated") {
      counts.keys += 1;
      if (done) counts.keysDone += 1;
    } else {
      counts.votes += 1;
      if (done) counts.votesDone += 1;
    }
  }
  return counts;
}

function topicLeftLabel(topics, topic, questionsById, answers, split) {
  const group = topics.find((g) => g.topic === topic);
  if (!group) return "";
  const c = topicCounts(group.ids, questionsById, answers, split);
  const parts = [];
  if (c.keys - c.keysDone) parts.push(`${c.keys - c.keysDone} ${c.keys - c.keysDone === 1 ? "pregunta clave" : "preguntas clave"}`);
  if (c.votes - c.votesDone) parts.push(`${c.votes - c.votesDone} ${c.votes - c.votesDone === 1 ? "votación" : "votaciones"}`);
  const left = c.keys - c.keysDone + c.votes - c.votesDone;
  return left ? `${left === 1 ? "te queda" : "te quedan"} ${parts.join(" y ")}` : "todas respondidas";
}

// ---------------------------------------------------------------------------
// Progress: one segment per step of the current list (key questions, or concrete votes when they are few).

const MAX_TICKS = 60;

function StepProgress({ ids, currentId, answers, split, label }) {
  const done = ids.filter((id) => answers[id] !== undefined || Boolean(split?.[id])).length;
  const common = { "aria-label": label, "aria-valuemax": ids.length, "aria-valuemin": 0, "aria-valuenow": done, role: "progressbar" };
  if (ids.length && ids.length <= MAX_TICKS) {
    return (
      <div {...common} className="va-ticks" style={{ "--n": ids.length }}>
        {ids.map((id) => (
          <span
            className={id === currentId ? "is-current" : answers[id] !== undefined || split?.[id] ? "is-done" : undefined}
            key={id}
          />
        ))}
      </div>
    );
  }
  return (
    <div {...common} className="v-meter va-meter">
      <span style={{ width: `${ids.length ? Math.round((done / ids.length) * 100) : 0}%` }} />
    </div>
  );
}

function ProgressHead({ stepLists: lists, questionsById, hereId, answers, split, answeredCount, phase, onStep, onRail }) {
  const { isKey, ids, pos, prev, next } = stepNeighbors(lists, questionsById, hereId);
  const kind = isKey ? "Pregunta clave" : "Votación";
  const where = pos >= 0 ? `${kind} ${pos + 1} de ${ids.length} · ` : "";
  return (
    <div className="va-progress">
      <div className="va-progress__row">
        <p className="v-kicker va-progress__label">
          {where}
          {answeredCount} {answeredCount === 1 ? "respondida" : "respondidas"}
        </p>
        {phase ? <p className="va-progress__phase">{phase}</p> : null}
        <span className="va-progress__nav">
          <button aria-label="Temas y preguntas" className="va-iconBtn va-railToggle" onClick={onRail} type="button">
            <ListIcon />
          </button>
          <button aria-label={isKey ? "Pregunta clave anterior" : "Votación anterior"} className="va-iconBtn" disabled={!prev} onClick={() => onStep(prev)} type="button">
            <span aria-hidden="true">‹</span>
          </button>
          <button aria-label={isKey ? "Pregunta clave siguiente" : "Votación siguiente"} className="va-iconBtn" disabled={!next} onClick={() => onStep(next)} type="button">
            <span aria-hidden="true">›</span>
          </button>
        </span>
      </div>
      <StepProgress
        answers={answers}
        currentId={hereId}
        ids={pos >= 0 ? ids : lists.keys}
        label={isKey ? "Preguntas clave respondidas" : "Votaciones respondidas"}
        split={split}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Topic rail: every topic with one dot per key question; the current topic lists its questions.

const STATUS_NOTES = { current: "Estás aquí", answered: null, split: "Respondida por partes", skipped: "Saltada", open: "Sin responder" };

function TopicDots({ counts, showVotes }) {
  const c = counts;
  return (
    <span className="va-rail__progress">
      {c.keys && c.keys <= 8 ? (
        <span aria-label={`${c.keysDone} de ${c.keys} ${c.keys === 1 ? "pregunta clave respondida" : "preguntas clave respondidas"}`} className="va-dots" role="img">
          {Array.from({ length: c.keys }, (_, i) => (
            <span className={i < c.keysDone ? "is-done" : undefined} key={i} />
          ))}
        </span>
      ) : c.keys ? (
        <span className="va-rail__count">
          {c.keysDone}/{c.keys}
          <span className="v-sr"> preguntas clave respondidas</span>
        </span>
      ) : null}
      {showVotes && c.votes ? (
        <span className="va-rail__count">
          {c.votesDone}/{c.votes}
          <span className="v-sr"> votaciones respondidas</span>
        </span>
      ) : null}
    </span>
  );
}

function TopicRail({ topics, questionsById, currentId, focusTopic, answers, skipped, split, onTopic, onQuestion, showVotes }) {
  const currentTopic = questionTopic(questionsById[currentId]);

  function questionItem(id) {
    const q = questionsById[id];
    const status =
      id === currentId ? "current" : answers[id] !== undefined ? "answered" : split?.[id] ? "split" : skipped?.[id] ? "skipped" : "open";
    const note = status === "answered" ? `Tu respuesta: ${answerLabel(q, answers[id])}` : status === "open" && q.source === "pool" && q.vote_date ? `Votada el ${formatDate(q.vote_date)}` : STATUS_NOTES[status];
    return (
      <li key={id}>
        <button
          aria-current={status === "current" ? "step" : undefined}
          className={`va-rail__q${q.parent && split?.[q.parent] ? " is-sub" : ""}`}
          onClick={() => onQuestion(id)}
          type="button"
        >
          <span aria-hidden="true" className={`va-mark va-mark--${status}`} />
          <span className="va-rail__qtext">
            <span className="va-clamp">{q.text}</span>
            <span className="va-rail__note">{note}</span>
          </span>
        </button>
      </li>
    );
  }

  return (
    <nav aria-label="Temas" className="va-rail">
      <p className="v-kicker">Temas</p>
      <ul className="va-rail__list">
        <li>
          <button aria-pressed={!focusTopic} className="va-rail__topic" onClick={() => onTopic(null)} type="button">
            <span>Todos los temas, mezclados</span>
          </button>
        </li>
        {topics.map((g) => {
          const c = topicCounts(g.ids, questionsById, answers, split);
          const here = g.topic === currentTopic;
          const keyIds = here ? g.ids.filter((id) => questionsById[id]?.source === "curated") : [];
          const voteIds = here ? g.ids.filter((id) => questionsById[id]?.source !== "curated") : [];
          return (
            <li key={g.topic}>
              <button
                aria-pressed={focusTopic === g.topic}
                className={`va-rail__topic${here ? " is-here" : ""}`}
                onClick={() => onTopic(g.topic)}
                title={focusTopic === g.topic ? "Sigues solo con este tema" : "Seguir solo con este tema"}
                type="button"
              >
                <span>{g.topic}</span>
                <TopicDots counts={c} showVotes={showVotes} />
              </button>
              {here ? (
                <div className="va-rail__questions">
                  {keyIds.length ? <ul className="va-rail__qlist">{keyIds.map(questionItem)}</ul> : null}
                  {voteIds.length ? (
                    <details className="va-rail__votes" open={keyIds.length === 0 || questionsById[currentId]?.source !== "curated"}>
                      <summary>
                        Votaciones concretas{" "}
                        <span className="va-rail__count">
                          {c.votesDone}/{c.votes}
                        </span>
                      </summary>
                      <ul className="va-rail__qlist">{voteIds.map(questionItem)}</ul>
                    </details>
                  ) : null}
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Question

function questionMeta(question) {
  if (question.axis_id) {
    const dates = (question.votes || []).map((v) => v.vote_date).filter(Boolean).sort();
    const range = dates.length > 1 ? `, entre ${monthYear(dates[0])} y ${monthYear(dates[dates.length - 1])}` : "";
    return `Resume ${question.votes_total} votaciones del Congreso sobre ${question.initiatives_total} ${question.initiatives_total === 1 ? "iniciativa" : "iniciativas"}${range}.`;
  }
  if (question.source === "pool") return question.vote_date ? `Votada en el Congreso el ${formatDate(question.vote_date)}.` : null;
  const n = question.votes?.length || 0;
  return n ? `Basada en ${n} ${n === 1 ? "votación" : "votaciones"} del Congreso.` : null;
}

/** «¿Qué se votó?»: the evidence behind the question, folded under the card (open state kept between questions). */
function Evidence({ question, parties, open, onToggle }) {
  const shown = Math.min(3, question.votes?.length || 0);
  const summary = question.axis_id && shown ? `¿Qué se votó? ${shown === 3 ? "Tres" : shown} de las ${question.votes_total} votaciones` : "¿Qué se votó?";
  return (
    <details className="va-evidence" onToggle={(e) => onToggle(e.currentTarget.open)} open={open}>
      <summary>
        <span>{summary}</span>
        <ChevronIcon />
      </summary>
      <div className="va-evidence__body">
        <WhatVoted parties={parties} question={question} />
        {question.source === "curated" && question.context && !question.axis_id ? (
          <>
            <p>{question.context}</p>
            <QuestionLinks question={question} />
          </>
        ) : null}
        {question.source === "pool" ? (
          <p className="v-muted">
            Fuentes oficiales: <QuestionLinks question={question} />
          </p>
        ) : null}
      </div>
    </details>
  );
}

function QuestionCard({ question, parties, answer, important, onAnswer, onSkip, onImportant, onSplit, showSwipeHint, evidenceOpen, onEvidence }) {
  const headingRef = useRef(null);
  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
  }, [question.statement_id]);
  const labels = question.source === "pool" ? POOL_ANSWER_LABELS : ANSWER_LABELS;
  const { dx, handlers } = useSwipe(onAnswer, question.statement_id);
  const tilt = Math.max(-1, Math.min(1, dx / SWIPE_THRESHOLD));
  // Only the statement moves with the finger: the answers sheet is fixed on phones and must not follow a transform.
  const style = dx ? { transform: `translateX(${dx}px) rotate(${(dx / 24).toFixed(1)}deg)`, transition: "none" } : undefined;
  const pool = question.source === "pool";
  const subCount = question.subIds?.length || 0;
  const meta = questionMeta(question);
  const headingId = `va-q-${question.statement_id}`.replace(/[^\w-]/gu, "_");
  return (
    <section aria-labelledby={headingId} className="va-q" key={question.statement_id}>
      <div className="va-qcard" {...handlers}>
        <div className="va-qcard__head" style={style}>
          {dx ? (
            <span aria-hidden="true" className={`va-stamp va-stamp--${tilt > 0 ? "agree" : "disagree"}`} style={{ opacity: Math.abs(tilt) }}>
              {tilt > 0 ? labels.agree : labels.disagree}
            </span>
          ) : null}
          <p className="v-eyebrow">
            {question.theme}
            {pool && question.kind_label ? <span className="va-kind"> · {question.kind_label}</span> : null}
          </p>
          <h1 className="va-statement" id={headingId} ref={headingRef} tabIndex={-1}>
            {pool ? question.question : question.text}
          </h1>
          {pool ? <blockquote className="va-quote">{question.text}</blockquote> : null}
          {meta ? <p className="va-qmeta">{meta}</p> : null}
          {parentLabel(question) ? <p className="va-qmeta">{parentLabel(question)}</p> : null}
        </div>
        <div aria-label="Tu respuesta" className="va-sheet" role="group">
          {showSwipeHint ? (
            <p aria-hidden="true" className="va-swipeHint">
              ← {labels.disagree} · desliza · {labels.agree} →
            </p>
          ) : null}
          <div className="va-answers">
            {ANSWER_ORDER.map((value, i) => (
              <button
                aria-keyshortcuts={String(i + 1)}
                aria-pressed={answer === value}
                className="va-answer"
                key={value}
                onClick={() => onAnswer(value)}
                type="button"
              >
                <span aria-hidden="true" className="va-key">
                  {i + 1}
                </span>
                {labels[value]}
              </button>
            ))}
          </div>
          <div className={`va-extras${subCount ? "" : " va-extras--two"}`}>
            <button aria-pressed={Boolean(important)} className={`va-extra${important ? " is-on" : ""}`} onClick={() => onImportant(!important)} type="button">
              <StarIcon filled={Boolean(important)} />
              Me importa
              <span className="va-wide">
                {" "}
                mucho <span className="va-soft">· cuenta doble</span>
              </span>
            </button>
            {subCount ? (
              <button
                aria-keyshortcuts="4"
                className="va-extra"
                onClick={onSplit}
                title={`Responde por partes: ${subCount} votaciones concretas en vez de esta pregunta resumen`}
                type="button"
              >
                <SplitIcon />
                Depende<span className="va-wide">: responder votación a votación</span>
              </button>
            ) : null}
            <button aria-keyshortcuts="S" className="va-extra va-extra--skip" onClick={onSkip} type="button">
              <span className="va-wide">No lo sé · saltar</span>
              <span className="va-narrow">Saltar</span>
            </button>
          </div>
        </div>
      </div>
      <Evidence onToggle={onEvidence} open={evidenceOpen} parties={parties} question={question} />
    </section>
  );
}

/** Challenge someone with this question: link to its hook page (own OG card), never the user's answer. */
function ShareQuestionButton({ question }) {
  const [note, setNote] = useState("");
  if (question.source !== "curated") return null;
  async function onShare() {
    const url = `${window.location.origin}${withBasePath(`/citizen/vota/t/${question.statement_id}/`)}`;
    const text = `«${question.text}» ¿De acuerdo? Mira qué partidos votaron como tú en el Congreso:`;
    try {
      if (navigator.share) {
        await navigator.share({ text, url });
        return;
      }
    } catch (error) {
      if (error?.name === "AbortError") return;
    }
    setNote((await copyText(`${text} ${url}`)) ? "Pregunta copiada (sin tu respuesta)." : url);
  }
  return (
    <>
      <button className="v-link-btn va-linkish" onClick={onShare} type="button">
        <ShareIcon /> Compartir esta pregunta (sin tu respuesta)
      </button>
      {note ? <span className="v-muted">{note}</span> : null}
    </>
  );
}

function parentLabel(question) {
  return question.parentText ? `Parte de: «${question.parentText}»` : null;
}

const AUTO_NEXT_MS = 5000;

/**
 * Waze-style auto-advance: the «Siguiente» border fills up and then moves on by itself.
 * Any touch, scroll or key press stops it (the user wants to read). Never with reduced motion, nor with a mouse:
 * on desktop people read the reveal without touching anything, and «Siguiente» already has focus (Intro).
 */
function useAutoNext(resetKey) {
  const [auto, setAuto] = useState(false);
  useEffect(() => {
    if (reducedMotion() || mediaMatches(FINE_POINTER_QUERY)) return undefined;
    setAuto(true);
    const stop = () => setAuto(false);
    const events = ["pointerdown", "wheel", "touchmove", "keydown"];
    // Listen from the next tick so the click that answered does not cancel its own reveal.
    const t = setTimeout(() => events.forEach((e) => window.addEventListener(e, stop, { passive: true })), 0);
    return () => {
      clearTimeout(t);
      events.forEach((e) => window.removeEventListener(e, stop));
      setAuto(false);
    };
  }, [resetKey]);
  return auto;
}

/** Swatches for the vote bars; the share that matches the user's answer says so in words, not by colour alone. */
function MixLegend({ matching, pool }) {
  const items = [
    ["yes", pool ? "Sí (a favor)" : "A favor de la afirmación", "is-yes"],
    ["abstain", "Abstención", "is-abs"],
    ["no", pool ? "No (en contra)" : "En contra de la afirmación", "is-no"],
  ];
  return (
    <p className="v-legend va-legend">
      <span className="v-sr">Leyenda: </span>
      {items.map(([key, label, cls]) => (
        <span key={key}>
          <span aria-hidden="true" className={`v-swatch va-swatch ${cls}`} />
          {label}
          {key === matching ? <strong className="va-legend__you"> · como tú</strong> : null}
        </span>
      ))}
    </p>
  );
}

/** One party: a 100 % stacked bar of how it voted (for / abstention / against) and the share that matches you. */
function MixRow({ party, answer }) {
  const mix = party.mix;
  const share = matchShare(mix, answer);
  const pct = (f) => Math.round(f * 100);
  return (
    <li className="va-mixRow">
      <span className="va-mixRow__label">{party.label}</span>
      {mix ? (
        <span
          aria-label={`${party.label}: ${pct(mix.yes)} % a favor, ${pct(mix.abstain)} % abstención, ${pct(mix.no)} % en contra`}
          className="v-stack va-mixRow__bar"
          role="img"
        >
          <span className="is-yes" style={{ width: `${mix.yes * 100}%` }} />
          <span className="is-abs" style={{ width: `${mix.abstain * 100}%` }} />
          <span className="is-no" style={{ width: `${mix.no * 100}%` }} />
        </span>
      ) : (
        <span className="va-mixRow__bar va-mixRow__empty">Sin votos registrados</span>
      )}
      <span className="va-mixRow__pct">{share === null ? "sin datos" : `${pct(share)} % como tú`}</span>
    </li>
  );
}

/** «Ver las N votaciones»: the votes behind the question with each party's choice (panel), or the official vote. */
function VotesLink({ question }) {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  if (question.axis_id) {
    return (
      <>
        <a
          aria-expanded={open}
          className="va-votesLink"
          href={axisMapHref(question)}
          onClick={(e) => {
            if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
            e.preventDefault();
            setOpen(true);
          }}
        >
          Ver las {question.votes_total} votaciones →
        </a>
        <SidePanel onClose={close} open={open} title="Cómo votó cada partido">
          <AxisVotesPanel question={question} />
        </SidePanel>
      </>
    );
  }
  const url = question.source_url || (question.votes?.length === 1 ? question.votes[0].source_url : null);
  return url ? (
    <a className="va-votesLink" href={url} rel="noopener noreferrer" target="_blank">
      Ver la votación oficial →
    </a>
  ) : null;
}

function RevealCard({ question, parties, answer, reactions, topBefore, onNext, onChange, onSplit }) {
  const nextRef = useRef(null);
  const titleId = useId();
  useEffect(() => {
    nextRef.current?.focus({ preventScroll: true });
  }, [question.statement_id]);
  const autoNext = useAutoNext(question.statement_id);
  const multi = Boolean(question.axis_id);
  const pool = question.source === "pool";
  const summary = revealSummary(answer, reactions, { multi });
  const totals = pool ? question.totals : null;
  const margin = totals ? Math.abs((totals[0] || 0) - (totals[1] || 0)) : null;
  // Fact, not drama: the party you matched most so far voted the other way here.
  const twist = topBefore && answer !== "neutral" && reactions.against.some((p) => p.party_id === topBefore.partyId) ? topBefore.label : null;
  const groups = [
    ["with", multi ? "Votaron casi siempre como tú" : "Votaron como tú", reactions.with],
    ["partial", "A medias", reactions.partial],
    ["against", multi ? "Casi siempre al contrario" : "Al contrario", reactions.against],
    ["none", "Sin datos", reactions.none],
  ];
  return (
    <section aria-labelledby={titleId} className="va-reveal">
      <div className="va-reveal__q">
        <p className="v-eyebrow">{question.theme}</p>
        <p className="va-reveal__statement">{question.text}</p>
        <p className="va-you">
          Tu respuesta <span className="va-pill">{answerLabel(question, answer)}</span>
        </p>
        <ScopeBadges question={question} />
      </div>
      {answer === "neutral" ? <SplitOffer onSplit={onSplit} question={question} /> : null}
      <div aria-live="polite" className="va-reveal__head">
        <h2 className="va-reveal__title" id={titleId}>
          {summary.total ? `${summary.withCount} de ${summary.total} partidos votaron como tú` : "No hay datos de cómo votaron los partidos"}
        </h2>
        {summary.sentence ? <p className="va-reveal__sentence">{summary.sentence}</p> : null}
        {twist ? <p className="va-reveal__sentence">{twist}, el partido más afín a ti hasta ahora, votó lo contrario.</p> : null}
        {pool ? (
          <p className="v-muted">
            {question.proposer ? (
              <>
                Propuesta por <strong>{question.proposer}</strong>.{" "}
              </>
            ) : null}
            El Congreso la {question.approved ? "aprobó" : "rechazó"} ({totals?.[0]} sí, {totals?.[1]} no, {totals?.[2]} abst.)
            {margin !== null && margin <= 6 ? `: se decidió por ${margin} ${margin === 1 ? "voto" : "votos"}.` : "."}
          </p>
        ) : null}
        {multi ? (
          <p className="v-muted">
            Según {question.votes_total} votaciones: cada barra reparte las del partido entre a favor, abstención y en contra de la afirmación.
          </p>
        ) : null}
      </div>
      <MixLegend matching={summary.matching} pool={pool} />
      <div className="va-groups">
        {groups.map(([kind, label, list]) =>
          list.length ? (
            <div className={`va-group va-group--${kind}`} key={kind}>
              <h3 className="va-group__title">
                {label} <span className="va-group__count">{list.length}</span>
              </h3>
              <ul className="va-mixList">
                {list.map((p) => (
                  <MixRow answer={answer} key={p.party_id} party={p} />
                ))}
              </ul>
            </div>
          ) : null,
        )}
      </div>
      <div className="va-reveal__actions">
        <div className="va-reveal__bar">
          <button
            className={`v-btn v-btn--primary va-next${autoNext ? " is-auto" : ""}`}
            onClick={onNext}
            ref={nextRef}
            title={autoNext ? "Pasa sola en unos segundos. Toca o desplázate para quedarte." : undefined}
            type="button"
          >
            {autoNext ? (
              <svg aria-hidden="true" className="va-next__ring">
                <rect height="100%" onAnimationEnd={onNext} pathLength="100" rx="11" style={{ animationDuration: `${AUTO_NEXT_MS}ms` }} width="100%" />
              </svg>
            ) : null}
            Siguiente pregunta
            <span aria-hidden="true" className="va-key va-key--dark">
              Intro
            </span>
          </button>
          <button className="v-btn" onClick={onChange} type="button">
            Cambiar<span className="va-wide"> respuesta</span>
          </button>
        </div>
        <VotesLink question={question} />
      </div>
      <details className="va-more">
        <summary>
          <span>Qué se votó, a quién afecta y por qué votaron así</span>
          <ChevronIcon />
        </summary>
        <div className="va-more__body">
          <WhatVoted parties={parties} question={question} />
          <p className="va-linksRow">
            <QuestionLinks question={question} />
          </p>
          <AskAiToggle
            label="¿Por qué votaron así? Pregúntale a una IA"
            opts={{}}
            parties={parties}
            question={question}
            title="Pide que te expliquen qué se votó y los argumentos de cada partido:"
          />
          <p className="va-linksRow">
            <ShareQuestionButton question={question} />
          </p>
        </div>
      </details>
    </section>
  );
}

/** «Tu afinidad»: top five while answering; the whole ranking with ▲/▼ moves right after an answer. */
function AffinityPanel({ results, previousRanks, revealing, onOpen }) {
  const titleId = useId();
  const scored = results.filter((r) => r.match !== null);
  const rows = revealing ? scored : scored.slice(0, 5);
  return (
    <aside aria-labelledby={titleId} className="va-aff">
      <div className="va-aff__card">
        <h2 className="v-kicker" id={titleId}>
          {revealing ? "Tu afinidad · tras esta respuesta" : "Tu afinidad hasta ahora"}
        </h2>
        {rows.length === 0 ? (
          <p className="v-muted">Responde para ver con qué partidos coincides.</p>
        ) : (
          <ol className="va-aff__list">
            {rows.map((row, i) => {
              const before = previousRanks[row.partyId];
              const delta = revealing && before !== undefined ? before - i : 0;
              return (
                <li key={row.partyId}>
                  <span className="va-aff__line">
                    <span className="va-aff__name">
                      <span className="va-pos">{pad2(i + 1)}</span> {row.label}
                      {delta ? (
                        <span className={`va-move ${delta > 0 ? "is-up" : "is-down"}`}>
                          <span aria-hidden="true"> {delta > 0 ? `▲${delta}` : `▼${-delta}`}</span>
                          <span className="v-sr">
                            {" "}
                            ({delta > 0 ? "sube" : "baja"} {Math.abs(delta)} {Math.abs(delta) === 1 ? "puesto" : "puestos"})
                          </span>
                        </span>
                      ) : null}
                    </span>
                    <span className="va-aff__pct">{pctText(row.match)}</span>
                  </span>
                  <span aria-hidden="true" className="v-meter">
                    <span style={{ width: `${Math.round(row.match * 100)}%` }} />
                  </span>
                </li>
              );
            })}
          </ol>
        )}
        <button className="v-link-btn va-aff__more" onClick={onOpen} type="button">
          Ver los {results.length} partidos →
        </button>
      </div>
      {revealing && rows.length ? <p className="v-muted va-aff__note">Las flechas marcan cuántos puestos ha subido o bajado cada partido con esta respuesta.</p> : null}
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Results and per-party breakdown

function themeStats(details, questionsById) {
  const stats = {};
  for (const d of details) {
    if (d.similarity === null) continue;
    const theme = questionsById[d.statementId]?.theme || "Otros";
    stats[theme] = stats[theme] || { sum: 0, w: 0, n: 0 };
    stats[theme].sum += d.similarity * d.weight;
    stats[theme].w += d.weight;
    stats[theme].n += 1;
  }
  return Object.entries(stats)
    .map(([theme, s]) => ({ theme, match: s.sum / s.w, n: s.n }))
    .sort((a, b) => b.match - a.match || b.n - a.n);
}

function PartyView({ row, parties, questionsById, onBack, onEdit }) {
  const groups = useMemo(() => groupDetails(row.details), [row]);
  const [tab, setTab] = useState(groups.clash.length ? "clash" : "match");
  const [theme, setTheme] = useState("");
  const themes = useMemo(() => themeStats(row.details, questionsById), [row, questionsById]);
  const ranked = themes.filter((t) => t.n >= 2 && t.theme !== "Otros");
  const best = ranked.slice(0, 2);
  // Worst themes come only from those not already listed as best.
  const worst = ranked.slice(best.length).slice(-2).reverse();
  const list = groups[tab].filter((d) => !theme || questionsById[d.statementId]?.theme === theme);
  const tabs = [
    ["match", "Coincidís"],
    ["partial", "A medias"],
    ["clash", "Discrepáis"],
    ["none", "Sin datos"],
  ];
  return (
    <section aria-labelledby="va-party-title" className="va-party">
      <button className="v-link-btn va-back" onClick={onBack} type="button">
        ← Todos los partidos
      </button>
      <div className="va-party__head">
        <h1 className="v-h1" id="va-party-title">
          Tú y {row.label} <span className="va-party__pct">{pctText(row.match)}</span>
        </h1>
        <a className="va-votesLink" href={withBasePath(`/citizen/vota/partidos/#p=${encodeURIComponent(row.partyId)}`)}>
          Cómo vota {row.label} en todos los temas →
        </a>
      </div>
      <div className="va-scoreStrip" aria-hidden="true">
        {["match", "partial", "clash"].map((k) =>
          groups[k].length ? <span className={`va-scoreStrip__${k}`} key={k} style={{ flexGrow: groups[k].length }} /> : null,
        )}
      </div>
      <p className="v-lead">
        <AgreementMark kind="match" /> {groups.match.length} coincidencias · <AgreementMark kind="partial" /> {groups.partial.length} a
        medias · <AgreementMark kind="clash" /> {groups.clash.length} discrepancias
        {groups.none.length ? ` · ${groups.none.length} sin datos` : ""}
      </p>
      {best.length ? (
        <div className="v-card v-card--sunk va-insights">
          <p>
            <strong>Donde más coincidís:</strong> {best.map((t) => `${t.theme} (${pctText(t.match)})`).join(" · ")}
          </p>
          {worst.length ? (
            <p>
              <strong>Donde menos:</strong> {worst.map((t) => `${t.theme} (${pctText(t.match)})`).join(" · ")}
            </p>
          ) : null}
        </div>
      ) : null}

      <div aria-label="Filtrar por resultado" className="v-chips va-tabs" role="tablist">
        {tabs.map(([key, label]) => (
          <button aria-selected={tab === key} className="v-chip" key={key} onClick={() => setTab(key)} role="tab" type="button">
            <AgreementMark kind={key} /> {label} <span className="va-chipCount">{groups[key].length}</span>
          </button>
        ))}
      </div>
      {themes.length > 1 ? (
        <div aria-label="Filtrar por tema" className="v-chips va-chipsRow" role="group">
          <button aria-pressed={!theme} className="v-chip" onClick={() => setTheme("")} type="button">
            Todos los temas
          </button>
          {themes.map((t) => (
            <button aria-pressed={theme === t.theme} className="v-chip" key={t.theme} onClick={() => setTheme(theme === t.theme ? "" : t.theme)} type="button">
              {t.theme} <span className="va-chipCount">{pctText(t.match)}</span>
            </button>
          ))}
        </div>
      ) : null}

      {list.length === 0 ? (
        <p className="v-muted va-empty">Nada por aquí con este filtro.</p>
      ) : (
        <ul className="va-breakdown" role="tabpanel">
          {list.map((d) => {
            const q = questionsById[d.statementId];
            if (!q) return null;
            const counts = q.source === "pool" ? q.counts?.[row.partyId] : null;
            return (
              <li key={d.statementId}>
                <AgreementMark kind={agreementKind(d.answer, d.position, d.score)} />
                <div className="va-breakdown__body">
                  <p className="v-eyebrow">{q.theme}</p>
                  <p className="va-breakdown__text">{q.text}</p>
                  <ScopeBadges question={q} />
                  <p className="v-muted">
                    Tú: <strong>{answerLabel(q, d.answer)}</strong>
                    {d.weight > 1 ? " (te importa mucho)" : ""} · {row.label}: <PositionBadge position={d.position} score={d.score} />
                    {counts ? ` (${counts[0]} sí · ${counts[1]} no · ${counts[2]} abst.)` : ""}
                  </p>
                  <p className="va-breakdown__actions">
                    <QuestionLinks question={q} />
                    <button className="v-link-btn va-linkish" onClick={() => onEdit(d.statementId)} type="button">
                      Cambiar mi respuesta
                    </button>
                  </p>
                  <AskAiToggle
                    label={`¿Por qué ${row.label} votó así?`}
                    opts={{ partyId: row.partyId }}
                    parties={parties}
                    question={q}
                    title={`Pide que te expliquen qué se votó y los argumentos de ${row.label}:`}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

const TIE_MARGIN = 0.05;
// Topic chips shown before «+ N temas» on the results page.
const RESULT_TOPICS_SHOWN = 4;

function listJoin(items) {
  return items.length > 1 ? `${items.slice(0, -1).join(", ")} y ${items[items.length - 1]}` : items.join("");
}

function ResultsView({
  results,
  parties,
  scoredQuestions,
  answers,
  important,
  answeredCount,
  curatedTotal,
  curatedDone,
  votesAnswered,
  fromShare,
  onParty,
  onPlay,
  onReview,
  onShare,
  onSharePodium,
  onReset,
  onOwn,
  shareMessage,
  method,
  excludeOmnibus,
  onExcludeOmnibus,
  omnibusAnswered,
  compare,
}) {
  const [topic, setTopic] = useState("");
  const [allTopics, setAllTopics] = useState(false);
  const topicList = useMemo(() => {
    const counts = new Map();
    for (const q of scoredQuestions) {
      if (!answers[q.statement_id]) continue;
      const t = questionTopic(q);
      counts.set(t, (counts.get(t) || 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "es")).map(([t, n]) => ({ topic: t, n }));
  }, [scoredQuestions, answers]);
  const rows = useMemo(
    () => (topic ? scoreParties({ parties, statements: scoredQuestions.filter((q) => questionTopic(q) === topic) }, answers, important) : results),
    [topic, parties, scoredQuestions, answers, important, results],
  );
  const provisional = answeredCount < MIN_ANSWERS_FOR_RANKING;
  const spread = resultsSpread(rows);
  // Parties within a few points of the leader are a statistical tie: say so instead of letting the order decide.
  const scored = rows.filter((r) => r.match !== null);
  const tied = scored.filter((r) => scored[0].match - r.match < TIE_MARGIN);
  const curatedLeft = Math.max(0, curatedTotal - curatedDone);
  const hidden = topicList.length - RESULT_TOPICS_SHOWN;
  const shownTopics = allTopics || hidden <= 1 ? topicList : topicList.slice(0, RESULT_TOPICS_SHOWN).concat(topicList.filter((t, i) => i >= RESULT_TOPICS_SHOWN && t.topic === topic));
  return (
    <div className="v-split va-results">
      <section aria-labelledby="va-results-title" className="v-main">
        {fromShare ? (
          <div className="va-note va-note--info" role="note">
            Estás viendo respuestas de un enlace compartido; no se han guardado en tu navegador.{" "}
            <button className="v-link-btn va-linkish" onClick={onOwn} type="button">
              Responder con mis respuestas
            </button>
          </div>
        ) : null}
        <div className="va-results__head">
          <p className="v-kicker">
            {curatedDone} de {curatedTotal} preguntas clave
            {votesAnswered ? ` · ${votesAnswered} ${votesAnswered === 1 ? "votación" : "votaciones"}` : ""}
          </p>
          <h1 className="v-h1" id="va-results-title">
            Con quién coincides
          </h1>
          <p className="v-lead">
            Comparamos tus respuestas con cómo votó cada partido en el Congreso.
            {spread && scored.length > 1 ? (
              <>
                {" "}
                {topic ? `En ${topic}, todos` : "Todos"} quedan entre el {pctText(spread.min)} y el {pctText(spread.max)}
                {spread.narrow ? (
                  <>
                    : <strong>ninguno destaca con claridad todavía</strong>.
                  </>
                ) : (
                  "."
                )}
              </>
            ) : null}
            {curatedLeft && answeredCount ? ` Responder las ${curatedLeft} preguntas clave que faltan afinará el orden.` : ""}
          </p>
        </div>
        {answeredCount === 0 ? (
          <div className="v-card va-empty">
            <p>Aún no has respondido nada.</p>
            <button className="v-btn v-btn--primary" onClick={onPlay} type="button">
              Empezar el test
            </button>
          </div>
        ) : (
          <>
            {provisional ? (
              <p className="va-note" role="note">
                <strong>Resultado provisional.</strong> Con menos de {MIN_ANSWERS_FOR_RANKING} respuestas el orden cambia mucho con cada
                respuesta.
              </p>
            ) : tied.length > 1 && !spread?.narrow ? (
              <p className="va-note va-note--info" role="note">
                <strong>Empate técnico.</strong> {listJoin(tied.map((r) => r.label))} quedan a menos de {Math.round(TIE_MARGIN * 100)} puntos
                del primero: con {answeredCount} respuestas esa diferencia no dice mucho.
              </p>
            ) : null}
            {topicList.length > 1 ? (
              <div aria-label="Filtrar por tema" className="v-chips va-chipsRow" role="group">
                <button aria-pressed={!topic} className="v-chip" onClick={() => setTopic("")} type="button">
                  Todos los temas
                </button>
                {shownTopics.map((t) => (
                  <button aria-pressed={topic === t.topic} className="v-chip" key={t.topic} onClick={() => setTopic(topic === t.topic ? "" : t.topic)} type="button">
                    {t.topic} <span className="va-chipCount">{t.n}</span>
                  </button>
                ))}
                {!allTopics && hidden > 1 ? (
                  <button aria-expanded="false" className="v-chip" onClick={() => setAllTopics(true)} type="button">
                    + {hidden} temas
                  </button>
                ) : null}
              </div>
            ) : null}
            {omnibusAnswered > 0 ? (
              <label className="va-check">
                <input checked={excludeOmnibus} onChange={(e) => onExcludeOmnibus(e.target.checked)} type="checkbox" />
                <span>
                  No contar las votaciones ómnibus{" "}
                  <span className="v-muted">
                    ({omnibusAnswered} respondidas): mezclan tantos temas que el voto de un partido puede deberse a cualquiera de ellos.
                  </span>
                </span>
              </label>
            ) : null}
            <ol className="va-rank">
              {rows.map((row, i) => {
                const g = groupDetails(row.details);
                const top = row.match !== null && i < 3;
                return (
                  <li key={row.partyId}>
                    <button className={`va-rank__btn${top ? " is-top" : ""}`} onClick={() => onParty(row.partyId)} type="button">
                      <span className="va-rank__pos">{row.match === null ? "–" : pad2(i + 1)}</span>
                      <span className="va-rank__label">{row.label}</span>
                      <span aria-hidden="true" className="va-rank__bar">
                        <span className="va-rank__fill" style={{ width: `${row.match === null ? 0 : Math.round(row.match * 100)}%` }} />
                        <span className="va-rank__mid" />
                      </span>
                      <span className="va-rank__pct">{pctText(row.match)}</span>
                      <span className="v-sr">
                        : {g.match.length} coincidencias, {g.partial.length} a medias, {g.clash.length} discrepancias
                        {g.none.length ? `, ${g.none.length} sin datos` : ""}.
                      </span>
                      <span className="va-rank__more">
                        En qué coincidís <span aria-hidden="true">→</span>
                      </span>
                      <span className="va-rank__chev">
                        <ChevronIcon dir="right" size={16} />
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
            <p className="v-muted">La línea vertical marca el 50 %: lo que obtendría un partido que votase al azar respecto a ti.</p>
          </>
        )}
      </section>

      <aside aria-label="Afina el resultado y cómo se calcula" className="v-side">
        <div className="v-card va-refine">
          <h2 className="v-h2">Afina el resultado</h2>
          <p className="v-muted">
            {curatedLeft
              ? `Quedan ${curatedLeft} preguntas clave. Después puedes seguir con votaciones concretas sin límite.`
              : "Ya respondiste las preguntas clave. Puedes seguir con votaciones concretas sin límite."}
          </p>
          <button className="v-btn v-btn--primary v-btn--block" onClick={onPlay} type="button">
            Seguir respondiendo
          </button>
          <div className="va-refine__grid">
            <button className="v-btn" onClick={answeredCount >= MIN_ANSWERS_FOR_RANKING ? onSharePodium : onShare} type="button">
              <ShareIcon /> Compartir
            </button>
            <button className="v-btn" onClick={onReview} type="button">
              Tus respuestas
            </button>
          </div>
          <p className="va-refine__more">
            {answeredCount >= MIN_ANSWERS_FOR_RANKING ? (
              <button className="v-link-btn va-linkish" onClick={onShare} type="button">
                Copiar enlace con tus respuestas
              </button>
            ) : null}
            <button className="v-link-btn va-linkish va-linkish--quiet" onClick={onReset} type="button">
              Borrar todo
            </button>
          </p>
          {answeredCount >= MIN_ANSWERS_FOR_RANKING ? (
            <p className="v-muted va-refine__hint">«Compartir» envía solo tu podio; el enlace con respuestas las incluye todas.</p>
          ) : null}
          {shareMessage ? (
            <p aria-live="polite" className="v-muted va-shareMsg">
              {shareMessage}
            </p>
          ) : null}
        </div>

        <div className="v-card v-card--sunk va-method" id="metodo">
          <h2 className="va-method__title">Cómo se calcula</h2>
          <ul>
            <li>Cada postura sale de votaciones reales del Congreso, enlazadas una a una. La de un partido es lo que votó la mayoría de sus diputados.</li>
            <li>«Neutral» coincide con quien se abstuvo. Una pregunta saltada no cuenta.</li>
            <li>«Me importa mucho» cuenta doble.</li>
            <li>Nunca rellenamos huecos: sin votos, sin dato.</li>
          </ul>
          <details className="va-method__more">
            <summary>La fórmula y qué no mide</summary>
            <ul>
              <li>
                Partido: a favor +1, en contra −1, abstención o votos divididos 0. Tú: sí / de acuerdo +1, me da igual / neutral 0, no / en
                desacuerdo −1.
              </li>
              <li>Coincidencia por pregunta = 1 − |tú − partido| / 2. Sin datos del partido, no cuenta.</li>
              <li>
                En las votaciones concretas, «Sí» significa apoyar lo votado (tramitar la ley, convalidar el decreto, aprobar la moción). Se
                alternan votaciones donde el «sí» favorece a bloques distintos y se oculta quién lo propuso hasta que respondes.
              </li>
              {method.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </details>
          <a className="va-votesLink" href={withBasePath("/citizen/vota/metodologia/")}>
            Metodología completa →
          </a>
        </div>
        {compare}
      </aside>
    </div>
  );
}

function ReviewView({ questions, state, onAnswer, onOpen }) {
  const [onlyImportant, setOnlyImportant] = useState(false);
  const groups = useMemo(() => {
    const out = new Map();
    for (const q of questions) {
      if (!state.answers[q.statement_id] || (onlyImportant && !state.important[q.statement_id])) continue;
      if (!out.has(q.theme)) out.set(q.theme, []);
      out.get(q.theme).push(q);
    }
    return [...out.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [questions, state.answers, state.important, onlyImportant]);
  return (
    <section aria-labelledby="va-review-title" className="va-review">
      <h1 className="v-h1" id="va-review-title">
        Tus respuestas
      </h1>
      <p className="v-lead">Cambia lo que quieras; la clasificación se recalcula al momento.</p>
      <label className="va-check">
        <input checked={onlyImportant} onChange={(e) => setOnlyImportant(e.target.checked)} type="checkbox" />
        Solo las que me importan mucho
      </label>
      {groups.length === 0 ? <p className="v-muted va-empty">Nada que revisar todavía.</p> : null}
      {groups.map(([theme, qs]) => (
        <details className="v-card va-review__group" key={theme} open={groups.length <= 4}>
          <summary>
            <span className="v-eyebrow">{theme}</span> <span className="va-chipCount">{qs.length}</span>
          </summary>
          <ul className="va-review__list">
            {qs.map((q) => {
              const answer = state.answers[q.statement_id];
              const labels = q.source === "pool" ? POOL_ANSWER_LABELS : ANSWER_LABELS;
              return (
                <li key={q.statement_id}>
                  <button className="va-review__text" onClick={() => onOpen(q.statement_id)} type="button">
                    {q.text}
                    {state.important[q.statement_id] ? (
                      <span className="va-review__star">
                        {" "}
                        <StarIcon filled size={14} />
                        <span className="v-sr">(me importa mucho)</span>
                      </span>
                    ) : null}
                  </button>
                  <div aria-label="Tu respuesta" className="va-segmented" role="group">
                    {ANSWER_ORDER.map((value) => (
                      <button
                        aria-pressed={answer === value}
                        key={value}
                        onClick={() => onAnswer(q.statement_id, answer === value ? null : value)}
                        type="button"
                      >
                        {labels[value]}
                      </button>
                    ))}
                  </div>
                </li>
              );
            })}
          </ul>
        </details>
      ))}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Where you are lives in the URL (?p=jugar&q=…&tema=…), so refresh and the back button keep it. Never the answers:
// those stay in localStorage (and in the explicit #r= share link).

const VIEW_PARAM = { play: "jugar", results: "resultados", party: "partido", review: "respuestas" };
const PARAM_VIEW = Object.fromEntries(Object.entries(VIEW_PARAM).map(([view, param]) => [param, view]));

function navUrl({ view, questionId, focusTopic, partyId }) {
  const params = new URLSearchParams();
  if (VIEW_PARAM[view]) params.set("p", VIEW_PARAM[view]);
  if (view === "play" && questionId) params.set("q", questionId);
  if (view === "play" && focusTopic) params.set("tema", focusTopic);
  if (view === "party" && partyId) params.set("partido", partyId);
  const query = params.toString();
  return `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`;
}

function readNav() {
  const params = new URLSearchParams(window.location.search);
  return { view: PARAM_VIEW[params.get("p")] || "intro", questionId: params.get("q"), focusTopic: params.get("tema"), partyId: params.get("partido") };
}

/** Back to the saved scroll position once the page is tall enough (data and impacts load after the first render). */
function restoreScroll(y) {
  if (!Number.isFinite(y) || y <= 0) return;
  let cancelled = false;
  const stop = () => {
    cancelled = true;
  };
  const events = ["wheel", "touchstart", "keydown", "mousedown"];
  for (const e of events) window.addEventListener(e, stop, { once: true, passive: true });
  [0, 150, 400, 900, 1600].forEach((ms, i, all) =>
    setTimeout(() => {
      if (!cancelled && Math.abs(window.scrollY - y) > 2) window.scrollTo(0, y);
      if (i === all.length - 1) for (const e of events) window.removeEventListener(e, stop);
    }, ms),
  );
}

// ---------------------------------------------------------------------------
// Page

export default function VotingAidClient({ snapshot: pageSnapshot, startStatementId = null, versionId = null }) {
  const version = versionById(versionId);
  // The page inlines the snapshot without its vote lists (fast first paint); the full file loads with the pool.
  const [fullSnapshot, setFullSnapshot] = useState(pageSnapshot?.slim ? null : pageSnapshot);
  const snapshot = fullSnapshot || pageSnapshot;
  const [staleShare, setStaleShare] = useState(false);
  const parties = useMemo(() => (Array.isArray(snapshot?.parties) ? snapshot.parties : []), [snapshot]);
  const meta = snapshot?.meta || {};
  const [pool, setPool] = useState(null);
  const [poolStatus, setPoolStatus] = useState("loading");
  const [highlights, setHighlights] = useState(null);
  const [voteBullets, setVoteBullets] = useState(null);
  const [voteImpacts, setVoteImpacts] = useState(null);
  const [impactShards, setImpactShards] = useState({});
  const requestedShards = useRef(new Set());
  const needImpacts = useCallback((question) => {
    for (const key of impactShardKeys(question)) {
      if (requestedShards.current.has(key)) continue;
      requestedShards.current.add(key);
      fetch(withBasePath(`${IMPACTS_SHARD_DIR}/${key}.json`))
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then((data) => setImpactShards((prev) => ({ ...prev, [key]: data })))
        .catch(() => requestedShards.current.delete(key));
    }
  }, []);
  const impacts = useMemo(() => mergeImpacts(voteImpacts, Object.values(impactShards)), [voteImpacts, impactShards]);
  const [state, setState] = useState(() => cleanState(null));
  const [loaded, setLoaded] = useState(false);
  const [fromShare, setFromShare] = useState(false);
  const [view, setView] = useState("intro");
  const [currentId, setCurrentId] = useState(null);
  const [revealId, setRevealId] = useState(null);
  const [partyId, setPartyId] = useState(null);
  const [toast, setToast] = useState(null);
  const [shareMessage, setShareMessage] = useState("");
  const [previousRanks, setPreviousRanks] = useState({});
  const [topBefore, setTopBefore] = useState(null);
  // Topic the user chose to stay in (null: all topics, mixed in play order).
  const [focusTopic, setFocusTopic] = useState(null);
  // «¿Qué se votó?» stays as the user left it from one question to the next; the topic drawer is for narrow screens.
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [railOpen, setRailOpen] = useState(false);
  const closeRail = useCallback(() => setRailOpen(false), []);
  const topRef = useRef(null);
  const toastTimer = useRef(null);
  const startedAt = useRef(false);
  const navRestored = useRef(false);
  const lastUrl = useRef(null);

  const questions = useMemo(
    () => attachHighlights(buildQuestions(snapshot, pool), highlights, voteBullets, impacts),
    [snapshot, pool, highlights, voteBullets, impacts],
  );
  const scoredQuestions = useMemo(
    () => (state.excludeOmnibus ? questions.filter((q) => !q.omnibus) : questions),
    [questions, state.excludeOmnibus],
  );
  const questionsById = useMemo(() => Object.fromEntries(questions.map((q) => [q.statement_id, q])), [questions]);
  const curatedTotal = useMemo(() => questions.filter((q) => q.source === "curated").length, [questions]);
  const order = useMemo(() => playOrder(questions, state.seed || 1), [questions, state.seed]);
  const topics = useMemo(() => topicGroups(order, questionsById, state.split), [order, questionsById, state.split]);
  const steps = useMemo(() => stepLists(topics, questionsById), [topics, questionsById]);
  const results = useMemo(
    () => scoreParties({ parties, statements: scoredQuestions }, state.answers, state.important),
    [parties, scoredQuestions, state.answers, state.important],
  );
  const omnibusAnswered = useMemo(
    () => questions.filter((q) => q.omnibus && state.answers[q.statement_id]).length,
    [questions, state.answers],
  );
  const answeredCount = useMemo(() => Object.keys(state.answers).filter((id) => questionsById[id]).length, [state.answers, questionsById]);

  // Official-text highlights, «Qué se votaba» bullets and «Ramificaciones» are optional: questions work without them.
  useEffect(() => {
    let cancelled = false;
    fetch(withBasePath(HIGHLIGHTS_PATH))
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data) setHighlights(data);
      })
      .catch(() => {});
    fetch(withBasePath(BULLETS_PATH))
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data) setVoteBullets(data);
      })
      .catch(() => {});
    fetch(withBasePath(IMPACTS_PATH))
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data) setVoteImpacts(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (fullSnapshot) return undefined;
    let cancelled = false;
    fetch(withBasePath(`/${version.snapshot}`))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      // Without the vote lists the test still works: no evidence lists or «por partes» sub-questions.
      .catch(() => pageSnapshot)
      .then((data) => {
        if (!cancelled) setFullSnapshot(data);
      });
    return () => {
      cancelled = true;
    };
  }, [fullSnapshot, pageSnapshot, version.snapshot]);

  // Load the pool of real votes (endless mode). The curated statements work even if this fails.
  useEffect(() => {
    let cancelled = false;
    fetch(withBasePath(POOL_PATH))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (!cancelled) {
          setPool(data);
          setPoolStatus("ready");
        }
      })
      .catch(() => {
        if (!cancelled) setPoolStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Restore answers (or a shared link) once the question set is final.
  useEffect(() => {
    if (poolStatus === "loading" || !fullSnapshot) return undefined;
    function load(initial) {
      const code = shareCodeFromHash(window.location.hash);
      const shared = decodeAnyShareCode(questions, code);
      // A share link made with another version of the test: offer to open it there.
      setStaleShare(Boolean(code && !shared));
      if (shared) {
        setState({ ...cleanState(null), answers: shared.answers, important: shared.important, history: Object.keys(shared.answers) });
        setFromShare(true);
        setView("results");
      } else if (initial) {
        const stored = initialState(version, new Set(questions.map((q) => q.statement_id)));
        if (!stored.seed) stored.seed = newSeed();
        setState(stored);
        const nav = readNav();
        if (!navRestored.current && nav.view !== "intro") {
          navRestored.current = true;
          startedAt.current = true;
          applyNav(nav, stored, playOrder(questions, stored.seed));
          restoreScroll(window.history.state?.y);
        } else if (startStatementId && !startedAt.current && questions.some((q) => q.statement_id === startStatementId)) {
          startedAt.current = true;
          setCurrentId(startStatementId);
          setView("play");
        }
        navRestored.current = true;
      }
      setLoaded(true);
    }
    const onHashChange = () => load(false);
    load(true);
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [poolStatus, fullSnapshot, questions, startStatementId, version]);

  useEffect(() => {
    if (loaded && !fromShare) writeStoredState(version.storageKey, state);
  }, [state, loaded, fromShare, version.storageKey]);

  // Each move (question, topic, tab, party) is one history entry; the first one only replaces the landing URL.
  useEffect(() => {
    if (!loaded) return;
    const url = navUrl({ view, questionId: revealId || currentId, focusTopic, partyId });
    const here = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (url !== here) {
      if (lastUrl.current === null) window.history.replaceState({ ...window.history.state, y: window.scrollY }, "", url);
      else window.history.pushState({ y: 0 }, "", url);
    }
    lastUrl.current = url;
  }, [loaded, view, currentId, revealId, focusTopic, partyId]);

  // Back / forward: show the URL's place and its scroll position.
  useEffect(() => {
    function onPop(event) {
      if (shareCodeFromHash(window.location.hash)) return; // the hashchange handler restores shared results
      applyNav(readNav(), state, order);
      restoreScroll(event.state?.y);
    }
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  });

  // Remember the scroll position in the current history entry (we restore it ourselves: content loads late).
  useEffect(() => {
    if ("scrollRestoration" in window.history) window.history.scrollRestoration = "manual";
    let timer = null;
    function onScroll() {
      clearTimeout(timer);
      timer = setTimeout(() => {
        try {
          window.history.replaceState({ ...window.history.state, y: window.scrollY }, "");
        } catch {
          // Some browsers rate-limit history updates; losing one position is fine.
        }
      }, 200);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      clearTimeout(timer);
    };
  }, []);

  useEffect(() => () => clearTimeout(toastTimer.current), []);

  const scrollTop = useCallback(() => {
    topRef.current?.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" });
  }, []);

  function update(next) {
    if (fromShare) {
      setFromShare(false);
      if (window.location.hash) window.history.replaceState(window.history.state, "", `${window.location.pathname}${window.location.search}`);
    }
    setState(next);
  }

  function showToast(text) {
    clearTimeout(toastTimer.current);
    setToast({ text });
    toastTimer.current = setTimeout(() => setToast(null), 3200);
  }

  /** Next question to play (inside `topic` when one is chosen); `topicDone` when that topic has nothing left. */
  function pickNext({ answers, skipped, split, topic, playIds = order }) {
    let topicNext = null;
    if (topic) {
      const group = topicGroups(playIds, questionsById, split).find((g) => g.topic === topic);
      topicNext = group ? nextInTopic(group.ids, questionsById, answers, skipped, split) : null;
    }
    const id =
      topicNext ||
      pendingSubId(questionsById, split, answers, skipped) ||
      nextQuestionId(
        playIds.filter((qid) => !split?.[qid]),
        answers,
        skipped,
      );
    return { id, topicDone: Boolean(topic && !topicNext) };
  }

  /** Show what a URL describes (on load and on the back/forward buttons), without adding history. */
  function applyNav(nav, st, playIds) {
    const topic = nav.focusTopic && questions.some((q) => questionTopic(q) === nav.focusTopic) ? nav.focusTopic : null;
    if (nav.view === "play") {
      const id = nav.questionId && questionsById[nav.questionId] ? nav.questionId : pickNext({ ...st, topic, playIds }).id;
      setFocusTopic(topic);
      setCurrentId(id);
      setRevealId(id && st.answers[id] !== undefined && st.showReveal !== false ? id : null);
      setView("play");
    } else if (nav.view === "party") {
      setPartyId(nav.partyId);
      setView(nav.partyId && parties.some((p) => p.party_id === nav.partyId) ? "party" : "results");
    } else {
      setView(nav.view);
    }
  }

  function goPlay(nextId, answers = state.answers, skipped = state.skipped, split = state.split, topic = focusTopic) {
    let id = nextId;
    if (!id) {
      const next = pickNext({ answers, skipped, split, topic });
      id = next.id;
      if (next.topicDone) {
        setFocusTopic(null);
        showToast(`Tema completado: ${topic}. Seguimos con todos los temas.`);
      }
    }
    setRevealId(null);
    setCurrentId(id);
    setView("play");
    scrollTop();
  }

  function answer(value) {
    const id = currentId;
    if (!id) return;
    try {
      if (window.matchMedia("(pointer: coarse)").matches && !reducedMotion()) navigator.vibrate?.(8);
    } catch {
      // Vibration is optional.
    }
    const before = results;
    setPreviousRanks(Object.fromEntries(before.filter((r) => r.match !== null).map((r, i) => [r.partyId, i])));
    setTopBefore(before.find((r) => r.match !== null) || null);
    const wasAnswered = Boolean(state.answers[id]);
    const answers = { ...state.answers, [id]: value };
    const skipped = { ...state.skipped };
    delete skipped[id];
    const streak = wasAnswered ? state.streak || 0 : (state.streak || 0) + 1;
    update({
      ...state,
      answers,
      skipped,
      history: wasAnswered ? state.history : [...state.history, id],
      streak,
      bestStreak: Math.max(state.bestStreak || 0, streak),
    });
    const count = Object.keys(answers).filter((qid) => questionsById[qid]).length;
    if (!wasAnswered && count === curatedTotal && Object.keys(answers).every((qid) => questionsById[qid]?.source === "curated")) {
      showToast("Preguntas clave completadas. Ahora siguen votaciones concretas, una a una.");
    }
    if (state.showReveal) setRevealId(id);
    else goPlay(null, answers, skipped);
  }

  /** Answer a multi-vote statement "por partes": clear its own answer and play its concrete votes next. */
  function splitStatement(id) {
    const q = questionsById[id];
    if (!q?.subIds?.length) return;
    const answers = { ...state.answers };
    delete answers[id];
    const important = { ...state.important };
    delete important[id];
    const skipped = { ...state.skipped };
    delete skipped[id];
    const split = { ...(state.split || {}), [id]: true };
    update({ ...state, answers, important, skipped, split, history: state.history.filter((h) => h !== id) });
    goPlay(null, answers, skipped, split);
  }

  function skip() {
    const id = currentId;
    if (!id) return;
    const skipped = { ...state.skipped, [id]: true };
    update({ ...state, skipped, streak: 0 });
    goPlay(null, state.answers, skipped);
  }

  /** Stay in one topic (its next open question; its first one if all are answered), or null to mix them all again. */
  function chooseTopic(topic) {
    setFocusTopic(topic);
    if (!topic) return;
    const group = topics.find((g) => g.topic === topic);
    if (!group) return;
    goPlay(nextInTopic(group.ids, questionsById, state.answers, state.skipped, state.split) || group.ids[0], undefined, undefined, undefined, topic);
  }

  function setImportant(id, value) {
    const important = { ...state.important };
    if (value) important[id] = true;
    else delete important[id];
    update({ ...state, important });
  }

  function setAnswer(id, value) {
    const answers = { ...state.answers };
    const important = { ...state.important };
    if (value) answers[id] = value;
    else {
      delete answers[id];
      delete important[id];
    }
    update({ ...state, answers, important, history: value ? state.history : state.history.filter((h) => h !== id) });
  }

  async function share() {
    const code =
      poolStatus === "ready"
        ? encodeShareCodeV2(questions, state.answers, state.important)
        : encodeShareCode(
            questions.filter((q) => q.source === "curated"),
            state.answers,
            state.important,
          );
    const url = `${window.location.origin}${window.location.pathname}#r=${code}`;
    try {
      await navigator.clipboard.writeText(url);
      setShareMessage("Enlace copiado. Contiene tus respuestas: compártelo solo si quieres.");
    } catch {
      setShareMessage(url);
    }
  }

  async function sharePodium() {
    const url = `${window.location.origin}${window.location.pathname}`;
    const text = podiumShareText(results, answeredCount, url);
    try {
      if (navigator.share) {
        await navigator.share({ text });
        return;
      }
      await navigator.clipboard.writeText(text);
      setShareMessage("Podio copiado, sin tus respuestas.");
    } catch {
      setShareMessage(text);
    }
  }

  function reset() {
    if (answeredCount > 0 && !window.confirm("¿Borrar todas tus respuestas de este navegador?")) return;
    update({ ...cleanState(null), seed: newSeed() });
    setShareMessage("");
    setCurrentId(null);
    setRevealId(null);
    if (window.location.hash) window.history.replaceState(window.history.state, "", `${window.location.pathname}${window.location.search}`);
    setView("intro");
    scrollTop();
  }

  function ownAnswers() {
    window.history.replaceState(window.history.state, "", `${window.location.pathname}${window.location.search}`);
    setFromShare(false);
    const stored = readStoredState(version.storageKey);
    if (!stored.seed) stored.seed = newSeed();
    setState(stored);
    setView("intro");
  }

  function show(nextView) {
    setView(nextView);
    scrollTop();
  }

  // Keyboard: 1/2/3 answer, 4 «depende» (split), S skip, Enter next after the reveal, ← → previous/next question.
  useEffect(() => {
    if (view !== "play") return undefined;
    function onKey(event) {
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
      const tag = event.target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        const here = revealId || currentId;
        if (!here) return;
        const { prev, next } = stepNeighbors(steps, questionsById, here);
        const target = event.key === "ArrowLeft" ? prev : next;
        if (target) {
          event.preventDefault();
          goPlay(target);
        }
        return;
      }
      if (event.target?.closest?.(".va-rail")) return; // keys typed while browsing the topic list do not answer
      if (revealId) {
        if (event.key === "Enter" && tag !== "BUTTON" && tag !== "A") {
          event.preventDefault();
          goPlay();
        }
        return;
      }
      if (["1", "2", "3"].includes(event.key)) {
        event.preventDefault();
        answer(ANSWER_ORDER[Number(event.key) - 1]);
      } else if (event.key === "4" && current?.subIds?.length) {
        event.preventDefault();
        splitStatement(current.statement_id);
      } else if (event.key === "s" || event.key === "S") {
        event.preventDefault();
        skip();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // Shell contract (VotaShell): its Test / Resultados / Respuestas tabs ask for a view instead of reloading the page,
  // and the shell lights the tab of whatever view is showing (after a click here, a share link or back/forward).
  const navigateRef = useRef(null);
  navigateRef.current = (target) => {
    if (target === "play") goPlay(currentId && !state.answers[currentId] ? currentId : null);
    else if (target === "results" || target === "review") show(target);
  };
  useEffect(() => {
    const onNavigate = (event) => navigateRef.current?.(event.detail?.view);
    window.addEventListener(NAVIGATE_EVENT, onNavigate);
    return () => window.removeEventListener(NAVIGATE_EVENT, onNavigate);
  }, []);
  useEffect(() => {
    window.dispatchEvent(new CustomEvent(VIEW_EVENT, { detail: { view } }));
  }, [view]);

  const current = currentId ? questionsById[currentId] : null;
  const revealQuestion = revealId ? questionsById[revealId] : null;
  const shown = revealQuestion || current;
  const partyRow = partyId ? results.find((r) => r.partyId === partyId) : null;
  const curatedLeft = questions.filter((q) => q.source === "curated" && !state.answers[q.statement_id] && !state.split?.[q.statement_id]).length;
  const votesAnswered = Object.keys(state.answers).filter((id) => questionsById[id] && questionsById[id].source !== "curated").length;

  function pickQuestion(id) {
    setRailOpen(false);
    goPlay(id);
  }

  function pickTopic(topic) {
    setRailOpen(false);
    chooseTopic(topic);
  }

  const phase = focusTopic ? (
    <>
      Solo <strong>{focusTopic}</strong>: {topicLeftLabel(topics, focusTopic, questionsById, state.answers, state.split)}.{" "}
      <button className="v-link-btn va-linkish" onClick={() => chooseTopic(null)} type="button">
        Mezclar todos los temas
      </button>
    </>
  ) : curatedLeft ? (
    answeredCount < MIN_ANSWERS_FOR_RANKING ? (
      `Con ${MIN_ANSWERS_FOR_RANKING} respuestas o más el resultado deja de ser provisional`
    ) : (
      `Quedan ${curatedLeft} preguntas clave; después siguen votaciones concretas`
    )
  ) : poolStatus === "ready" ? (
    "Votaciones concretas del Congreso, una a una, sin límite"
  ) : poolStatus === "error" ? (
    "No se pudieron cargar más votaciones ahora mismo"
  ) : (
    "Cargando votaciones…"
  );

  const rail = (
    <TopicRail
      answers={state.answers}
      currentId={shown?.statement_id}
      focusTopic={focusTopic}
      onQuestion={pickQuestion}
      onTopic={pickTopic}
      questionsById={questionsById}
      showVotes={!curatedLeft}
      skipped={state.skipped}
      split={state.split}
      topics={topics}
    />
  );

  return (
    <NeedImpactsContext.Provider value={needImpacts}>
      <main className={`va${view === "play" ? ` va--play${revealQuestion ? " is-reveal" : ""}` : ""}`} ref={topRef}>
        <Toast toast={toast} />
        {view === "intro" || !version.current || staleShare ? (
          <div className="va-top">
            <VersionBanner onIntro={view === "intro"} version={version} />
            {staleShare ? (
              <p className="va-note" role="note">
                Este enlace compartido es de otra versión del test. Ábrelo en:{" "}
                {otherVersions(version.id).map((v, i) => (
                  <span key={v.id}>
                    {i ? " · " : ""}
                    <a href={`${withBasePath(v.path)}${typeof window !== "undefined" ? window.location.hash : ""}`}>
                      {v.label} ({formatReleased(v.released)})
                    </a>
                  </span>
                ))}
              </p>
            ) : null}
          </div>
        ) : null}

        {view === "intro" ? (
          <div className="v-page">
            <IntroView
              answeredCount={answeredCount}
              curatedTotal={curatedTotal}
              meta={meta}
              onResults={() => show("results")}
              onStart={() => goPlay()}
              parties={parties}
              poolStatus={poolStatus}
              questionsTotal={questions.length}
            />
          </div>
        ) : null}

        {view === "play" ? (
          <div className="va-play">
            {shown ? (
              <ProgressHead
                answeredCount={answeredCount}
                answers={state.answers}
                hereId={shown.statement_id}
                onRail={() => setRailOpen(true)}
                onStep={(id) => id && goPlay(id)}
                phase={phase}
                questionsById={questionsById}
                split={state.split}
                stepLists={steps}
              />
            ) : null}
            <div className="va-play__grid">
              {shown ? <div className="va-play__rail">{rail}</div> : null}
              <div className="va-play__main">
                {revealQuestion ? (
                  <RevealCard
                    answer={state.answers[revealQuestion.statement_id]}
                    onChange={() => {
                      setCurrentId(revealQuestion.statement_id);
                      setRevealId(null);
                    }}
                    onNext={() => goPlay()}
                    onSplit={() => splitStatement(revealQuestion.statement_id)}
                    parties={parties}
                    question={revealQuestion}
                    reactions={partyReactions(revealQuestion, state.answers[revealQuestion.statement_id], parties)}
                    topBefore={topBefore}
                  />
                ) : current ? (
                  <QuestionCard
                    answer={state.answers[current.statement_id]}
                    evidenceOpen={evidenceOpen}
                    important={state.important[current.statement_id]}
                    key={current.statement_id}
                    onAnswer={answer}
                    onEvidence={setEvidenceOpen}
                    onImportant={(v) => setImportant(current.statement_id, v)}
                    onSkip={skip}
                    onSplit={() => splitStatement(current.statement_id)}
                    parties={parties}
                    question={current}
                    showSwipeHint={answeredCount < 3}
                  />
                ) : (
                  <div className="v-card va-empty">
                    <h1 className="v-h2">Has respondido todas las preguntas</h1>
                    <p className="v-muted">{answeredCount} respuestas. Puedes revisarlas o ver con quién coincides.</p>
                    <button className="v-btn v-btn--primary" onClick={() => show("results")} type="button">
                      Ver mis resultados
                    </button>
                  </div>
                )}
                <div className="va-play__foot">
                  <label className="va-check">
                    <input checked={state.showReveal !== false} onChange={(e) => update({ ...state, showReveal: e.target.checked })} type="checkbox" />
                    Mostrar cómo votó cada partido después de responder
                  </label>
                  <p className="va-shortcuts">Teclado: 1 · 2 · 3 responder · 4 depende · S saltar · Intro seguir · ← → moverse</p>
                </div>
              </div>
              <AffinityPanel onOpen={() => show("results")} previousRanks={previousRanks} results={results} revealing={Boolean(revealQuestion)} />
            </div>
            <SidePanel onClose={closeRail} open={railOpen} title="Temas y preguntas">
              {rail}
            </SidePanel>
          </div>
        ) : null}

        {view === "results" ? (
          <div className="v-page">
            <ResultsView
              answeredCount={answeredCount}
              answers={state.answers}
              compare={!fromShare && pool ? <OtherVersionResults pool={pool} version={version} /> : null}
              curatedDone={curatedTotal - curatedLeft}
              curatedTotal={curatedTotal}
              excludeOmnibus={state.excludeOmnibus}
              fromShare={fromShare}
              important={state.important}
              method={meta.honesty || []}
              omnibusAnswered={omnibusAnswered}
              onExcludeOmnibus={(v) => update({ ...state, excludeOmnibus: v })}
              onOwn={ownAnswers}
              onParty={(id) => {
                setPartyId(id);
                show("party");
              }}
              onPlay={() => goPlay()}
              onReset={reset}
              onReview={() => show("review")}
              onShare={share}
              onSharePodium={sharePodium}
              parties={parties}
              results={results}
              scoredQuestions={scoredQuestions}
              shareMessage={shareMessage}
              votesAnswered={votesAnswered}
            />
          </div>
        ) : null}

        {view === "party" && partyRow ? (
          <div className="v-page">
            <PartyView key={partyRow.partyId} onBack={() => show("results")} onEdit={(id) => goPlay(id)} parties={parties} questionsById={questionsById} row={partyRow} />
          </div>
        ) : null}

        {view === "review" ? (
          <div className="v-page">
            <ReviewView onAnswer={setAnswer} onOpen={(id) => goPlay(id)} questions={questions} state={state} />
          </div>
        ) : null}
      </main>
    </NeedImpactsContext.Provider>
  );
}
