"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  formatMatch,
  groupDetails,
  linkPrompt,
  milestoneFor,
  nextQuestionId,
  partyReactions,
  pendingSubId,
  playOrder,
  podiumShareText,
  scoreParties,
  scorePercent,
  shareCodeFromHash,
} from "./votingAidModel.mjs";
import { formatReleased, otherVersions, versionById } from "./votingAidVersions.mjs";
import SidePanel from "./SidePanel";
import { DirectionBar, PoleLegend, VoteRow } from "./temas/VoteAtlasClient";
import { ATLAS_PATH, directionText, indexAtlas, votesForAxis } from "./voteAtlasModel.mjs";

const ANSWER_ORDER = ["agree", "neutral", "disagree"];
const EMPTY_STATE = { answers: {}, important: {}, skipped: {}, split: {}, history: [], seed: 0, streak: 0, bestStreak: 0, showReveal: true, excludeOmnibus: false };
const AGREEMENT_LABELS = { match: "Coincidís", partial: "A medias", clash: "Discrepáis", none: "Sin datos" };
const AGREEMENT_ICONS = { match: "✓", partial: "≈", clash: "✗", none: "–" };
const POOL_PATH = "/citizen/data/voting_aid_pool_v1.json";
const HIGHLIGHTS_PATH = "/citizen/data/voting_aid_highlights_v1.json";
const BULLETS_PATH = "/citizen/data/voting_aid_vote_bullets_v1.json";
const IMPACTS_PATH = "/citizen/data/voting_aid_vote_impacts_v1.json";

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
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

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
        <span aria-hidden="true">🗳️</span> Resume <strong>{question.votes_total} votaciones</strong> de {question.initiatives_total}{" "}
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
  if (failed) return <p className="votingAidNotice">No se pudieron cargar las votaciones. Inténtalo de nuevo más tarde.</p>;
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
        <button className="votingAidButton" onClick={() => setShown(shown + AXIS_PAGE)} type="button">
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

function ProgressBar({ value, max, label }) {
  const pct = max ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div aria-label={label} aria-valuemax={max} aria-valuemin={0} aria-valuenow={value} className="votingAidProgress" role="progressbar">
      <span style={{ width: `${pct}%` }} />
    </div>
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
        <span aria-hidden="true">🤖</span> {title}
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
        <span aria-hidden="true">🤖</span> {label}
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
          <span aria-hidden="true">🧺</span> Votación ómnibus: mezcla {themes.length} temas
        </span>
      ) : null}
      {question.offtopic ? (
        <span className="votingAidScope__badge votingAidScope__badge--offtopic">
          <span aria-hidden="true">⚠️</span> También cambia leyes de otros temas
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
              <span aria-hidden="true">📋</span> {d.bullets_basis === "puntos" ? "Puntos literales" : "Índice literal"}
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
                <span aria-hidden="true">⚠️</span> En sus disposiciones finales también cambia: {d.offtopic_riders.join(" · ")}
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
 * «Ramificaciones»: who a vote affects and how many they are (official figures), and, folded, what changes
 * for each group and the knock-on effects someone expects or fears, each with its source. Shown before
 * answering, so it never names who argued what: the Diario de Sesiones link says it.
 */
function Ramifications({ question }) {
  const [open, setOpen] = useState(false);
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
            <span aria-hidden="true">🧭</span> A quién afecta
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
            {open ? "Ocultar consecuencias" : "Ver qué cambia para cada colectivo y posibles consecuencias"}
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
        {votes.length ? " Los efectos indirectos son previsiones con su fuente, no hechos; los del debate se resumen sin decir quién los dijo." : ""}
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
              <span aria-hidden="true">🗳️</span> Qué se votaba{many && w.vote_date ? ` (votación del ${formatDate(w.vote_date)})` : ""}
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
                <span aria-hidden="true">📭</span> Sin texto oficial enlazado: solo tenemos el título de la votación.
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

function RankBadge({ count }) {
  const { current, next } = milestoneFor(count);
  return (
    <span className="votingAidRank">
      <span aria-hidden="true">{current ? current.emoji : "🗳️"}</span> <strong>{current ? current.title : "Recién llegada/o"}</strong>
      {next ? (
        <span className="votingAidMuted">
          {" "}
          · {next.at - count} para «{next.title}»
        </span>
      ) : null}
    </span>
  );
}

function Toast({ toast }) {
  return (
    <div aria-live="polite" className={`votingAidToast${toast ? " is-visible" : ""}`} role="status">
      {toast ? (
        <>
          <span aria-hidden="true" className="votingAidToast__burst">
            {toast.emoji}
          </span>
          {toast.text}
        </>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Intro

function IntroView({ meta, questionsTotal, curatedTotal, poolStatus, parties, answeredCount, onStart, onResults }) {
  const keyVotes = meta?.quality?.votes_total;
  return (
    <section className="votingAidIntro">
      <p className="votingAidEyebrow">Elecciones generales · Congreso de los Diputados</p>
      <h1>¿Con quién coincides?</h1>
      <p className="votingAidPitch">Prometer no obliga. Votar queda registrado.</p>
      <p className="votingAidLead">
        Las promesas electorales no obligan a nada; lo que vota cada partido en el Congreso queda registrado. Responde qué habrías
        votado tú en votaciones reales y descubre quién votó como tú. Juega todo lo que quieras: hay{" "}
        {poolStatus === "ready" ? questionsTotal : "cientos de"} preguntas esperando.
      </p>
      <div className="votingAidActions votingAidActions--primary votingAidIntro__cta">
        <button className="votingAidButton votingAidButton--primary votingAidButton--big" onClick={onStart} type="button">
          {answeredCount ? `Seguir jugando (${answeredCount} respondidas)` : "¡Empezar!"}
        </button>
        {answeredCount > 0 ? (
          <button className="votingAidButton votingAidButton--big" onClick={onResults} type="button">
            Ver mis resultados
          </button>
        ) : null}
      </div>
      <ul className="votingAidFacts">
        <li>
          <span aria-hidden="true">🎯</span> <strong>Empieza con {curatedTotal} preguntas clave</strong>
          {keyVotes ? `, que resumen ${keyVotes.toLocaleString("es-ES")} votaciones del Congreso,` : ""} y sigue en modo infinito con
          votaciones reales una a una.
        </li>
        <li>
          <span aria-hidden="true">🗳️</span> <strong>Tras cada respuesta, la revelación:</strong> quién votó como tú, quién en
          contra y quién lo propuso.
        </li>
        <li>
          <span aria-hidden="true">🔍</span> <strong>Hechos, no promesas:</strong> votaciones del {formatDate(meta.votes_first_date)} en
          adelante, cada una con su enlace oficial.
        </li>
        <li>
          <span aria-hidden="true">🔒</span> <strong>Privado:</strong> tus respuestas se quedan en este navegador.
        </li>
      </ul>
      <p className="votingAidNotice" role="note">
        <strong>Versión en revisión.</strong> Qué votación va a cada pregunta lo decidió una IA leyendo el texto oficial y aún deben
        revisarlo personas independientes; las votaciones del modo infinito usan el título oficial tal cual. Úsalo para explorar, no
        como veredicto. <a href={withBasePath("/citizen/vota/temas/")}>Mapa por temas</a> ·{" "}
        <a href={withBasePath("/citizen/vota/diputados/")}>Tu diputado/a</a> ·{" "}
        <a href={withBasePath("/citizen/vota/metodologia/")}>Cómo se hizo (fuentes, IA y prompts)</a>
      </p>
      <p className="votingAidMuted">Partidos comparados: {parties.map((p) => p.label).join(", ")}.</p>
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
function VersionBanner({ version }) {
  const others = otherVersions(version.id);
  if (!others.length) return null;
  if (version.current) {
    return (
      <p className="votingAidVersion votingAidMuted">
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
    <p className="votingAidNotice votingAidNotice--info votingAidVersion" role="note">
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
    <section className="votingAidCard votingAidVersionCompare">
      <h2>Compara con {rows.length > 1 ? "las otras versiones" : version.current ? "la versión anterior" : "la versión actual"}</h2>
      {rows.map((r) => (
        <p key={r.version.id}>
          <a href={withBasePath(r.version.path)}>
            {r.version.label} ({formatReleased(r.version.released)})
          </a>
          : {r.answered} respuestas. Tu podio allí: {r.top.map((t, i) => `${i + 1}. ${t.label} ${formatMatch(t.match)}`).join(" · ") || "—"}.
        </p>
      ))}
    </section>
  );
}

function SplitOffer({ question, onSplit }) {
  const n = question.subIds?.length || 0;
  if (!n || !onSplit) return null;
  return (
    <div className="votingAidNotice votingAidNotice--info votingAidSplit votingAidSplit--prominent">
      <p>
        <strong>¿Te da igual o depende del caso?</strong> Esta pregunta resume {question.votes_total} votaciones. Responde {n} concretas, de
        iniciativas distintas, y afinamos tu resultado. Tu «neutral» aquí dejará de contar.
      </p>
      <button className="votingAidButton" onClick={onSplit} type="button">
        Responder por partes →
      </button>
    </div>
  );
}

function QuestionCard({ question, parties, answer, important, onAnswer, onSkip, onImportant, onSplit, showSwipeHint }) {
  const headingRef = useRef(null);
  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
  }, [question.statement_id]);
  const labels = question.source === "pool" ? POOL_ANSWER_LABELS : ANSWER_LABELS;
  const { dx, handlers } = useSwipe(onAnswer, question.statement_id);
  const tilt = Math.max(-1, Math.min(1, dx / SWIPE_THRESHOLD));
  const style = dx
    ? { transform: `translateX(${dx}px) rotate(${(dx / 24).toFixed(1)}deg)`, transition: "none" }
    : undefined;
  return (
    <div className="votingAidCard votingAidCard--question" key={question.statement_id} style={style} {...handlers}>
      {dx ? (
        <span
          aria-hidden="true"
          className={`votingAidSwipeStamp votingAidSwipeStamp--${tilt > 0 ? "agree" : "disagree"}`}
          style={{ opacity: Math.abs(tilt) }}
        >
          {tilt > 0 ? labels.agree : labels.disagree}
        </span>
      ) : null}
      <p className="votingAidTheme">
        {question.theme}
        {question.source === "pool" ? <span className="votingAidKind"> · {question.kind_label}</span> : null}
      </p>
      {question.source === "pool" ? (
        <>
          <h2 className="votingAidStatement__text" ref={headingRef} tabIndex={-1}>
            {question.question}
          </h2>
          <blockquote className="votingAidQuote">{question.text}</blockquote>
        </>
      ) : (
        <h2 className="votingAidStatement__text" ref={headingRef} tabIndex={-1}>
          {question.text}
        </h2>
      )}

      <WhatVoted parties={parties} question={question} />

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
            <span aria-hidden="true" className="votingAidAnswer__key">
              {i + 1}
            </span>
            {labels[value]}
          </button>
        ))}
        {question.subIds?.length ? (
          <button
            aria-keyshortcuts="4"
            className="votingAidAnswer votingAidAnswer--split"
            onClick={onSplit}
            type="button"
          >
            <span aria-hidden="true" className="votingAidAnswer__key">
              4
            </span>
            <span className="votingAidAnswer__body">
              Depende
              <span className="votingAidAnswer__hint">
                Responde por partes: {question.subIds.length} votaciones concretas en vez de esta pregunta resumen
              </span>
            </span>
          </button>
        ) : null}
      </div>

      {showSwipeHint ? (
        <p aria-hidden="true" className="votingAidSwipeHint">
          👈 {labels.disagree} · desliza · {labels.agree} 👉
        </p>
      ) : null}
      <div className="votingAidQuestion__extras">
        <button
          aria-pressed={Boolean(important)}
          className={`votingAidStarToggle${important ? " is-on" : ""}`}
          onClick={() => onImportant(!important)}
          type="button"
        >
          <span aria-hidden="true">{important ? "★" : "☆"}</span> Me importa mucho{" "}
          <span className="votingAidMuted votingAidHideMobile">(cuenta doble)</span>
        </button>
        <button className="votingAidLinkButton" onClick={onSkip} type="button">
          Saltar
        </button>
      </div>
      {question.parent && parentLabel(question) ? <p className="votingAidMuted votingAidSplit">{parentLabel(question)}</p> : null}
      {question.source === "curated" && question.context && !question.axis_id ? (
        <details className="votingAidDetails">
          <summary>¿Qué se votó en el Congreso?</summary>
          <p>{question.context}</p>
          <QuestionLinks question={question} />
        </details>
      ) : null}
      {question.source === "pool" ? (
        <p className="votingAidMuted votingAidQuestion__meta">
          Votada el {formatDate(question.vote_date)}. ¿Quieres leerla antes? <QuestionLinks question={question} />
        </p>
      ) : null}
    </div>
  );
}

function revealMessage(answer, reactions, topBefore) {
  const total = reactions.with.length + reactions.against.length + reactions.partial.length;
  if (answer === "neutral") return { emoji: "🤷", text: "Te da igual: esta no suma ni resta mucho con nadie." };
  if (topBefore && reactions.against.some((p) => p.party_id === topBefore.partyId)) {
    return { emoji: "😮", text: `Giro de guion: ${topBefore.label}, tu partido más afín hasta ahora, votó lo contrario.` };
  }
  if (reactions.with.length === 0) return { emoji: "🐺", text: "Lobo solitario: ningún partido votó como tú." };
  if (reactions.with.length <= 2 && total >= 6) return { emoji: "🐟", text: "A contracorriente: muy pocos partidos votaron como tú." };
  if (reactions.against.length <= 1 && total >= 6) return { emoji: "🤝", text: "Casi consenso: la mayoría de partidos votó como tú." };
  return { emoji: "⚖️", text: "Tema que divide: el Congreso se partió en dos." };
}

function ReactionGroup({ kind, label, parties }) {
  if (!parties.length) return null;
  return (
    <div className={`votingAidReactionGroup votingAidReactionGroup--${kind}`}>
      <p className="votingAidReactionGroup__label">
        <AgreementMark kind={kind} /> {label}
      </p>
      <ul className="votingAidChips">
        {parties.map((p) => (
          <li className="votingAidChip" key={p.party_id} title={scorePercent(p.score) === null ? undefined : "Porcentaje de su empuje en el sentido de la afirmación"}>
            {p.label}
            {scorePercent(p.score) === null ? "" : <span className="votingAidMuted"> {scorePercent(p.score)} %</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Challenge someone with this question: link to its hook page (own OG card), never the user's answer. */
function ShareQuestionButton({ question }) {
  const [note, setNote] = useState("");
  if (question.source !== "curated") return null;
  async function onShare() {
    const url = `${window.location.origin}${withBasePath(`/citizen/vota/t/${question.statement_id}/`)}`;
    const text = `«${question.text}» ¿De acuerdo? Adivina qué partidos votaron como tú en el Congreso:`;
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
      <button className="votingAidLinkButton" onClick={onShare} type="button">
        📣 Retar a alguien con esta pregunta
      </button>
      {note ? <span className="votingAidMuted">{note}</span> : null}
    </>
  );
}

function parentLabel(question) {
  return question.parentText ? `Parte de: «${question.parentText}»` : null;
}

const AUTO_NEXT_MS = 5000;

/**
 * Waze-style auto-advance: the «Siguiente» border fills up and then moves on by itself.
 * Any touch, scroll or key press stops it (the user wants to read); reduced motion never auto-advances.
 */
function useAutoNext(resetKey) {
  const [auto, setAuto] = useState(false);
  useEffect(() => {
    if (reducedMotion()) return undefined;
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

function RevealCard({ question, parties, answer, reactions, topBefore, onNext, onChange, onSplit }) {
  const msg = revealMessage(answer, reactions, topBefore);
  const nextRef = useRef(null);
  useEffect(() => {
    nextRef.current?.focus({ preventScroll: true });
  }, [question.statement_id]);
  const autoNext = useAutoNext(question.statement_id);
  const totals = question.source === "pool" ? question.totals : null;
  const margin = totals ? Math.abs((totals[0] || 0) - (totals[1] || 0)) : null;
  return (
    <div aria-live="polite" className="votingAidCard votingAidReveal">
      <p className="votingAidTheme">{question.theme}</p>
      <p className="votingAidReveal__q">{question.text}</p>
      <ScopeBadges question={question} />
      <p className="votingAidReveal__you">
        Tu respuesta: <strong>{answerLabel(question, answer)}</strong>
      </p>
      {answer === "neutral" ? <SplitOffer onSplit={onSplit} question={question} /> : null}
      <p className="votingAidReveal__msg">
        <span aria-hidden="true" className="votingAidReveal__emoji">
          {msg.emoji}
        </span>{" "}
        {msg.text}
      </p>
      {question.source === "pool" ? (
        <p className="votingAidMuted">
          {question.proposer ? (
            <>
              Propuesta por <strong>{question.proposer}</strong>.{" "}
            </>
          ) : null}
          El Congreso la {question.approved ? "aprobó" : "rechazó"} ({totals?.[0]} sí, {totals?.[1]} no, {totals?.[2]} abst.)
          {margin !== null && margin <= 6 ? <strong> ¡Por los pelos!</strong> : null}
        </p>
      ) : null}
      {question.axis_id ? (
        <p className="votingAidMuted">
          Según {question.votes_total} votaciones. El porcentaje es cuánto empujó cada partido hacia la afirmación (100 % = siempre a favor,
          0 % = siempre en contra).
        </p>
      ) : null}
      <div className="votingAidReactions">
        <ReactionGroup kind="match" label={question.axis_id ? "Votaron casi siempre como tú" : "Votaron como tú"} parties={reactions.with} />
        <ReactionGroup kind="partial" label={question.axis_id ? "A veces sí, a veces no (o abstención)" : "A medias (abstención o votos divididos)"} parties={reactions.partial} />
        <ReactionGroup kind="clash" label={question.axis_id ? "Votaron casi siempre lo contrario" : "Votaron lo contrario"} parties={reactions.against} />
        <ReactionGroup kind="none" label="Sin datos" parties={reactions.none} />
      </div>
      <p className="votingAidLinksRow">
        <QuestionLinks question={question} />
      </p>
      <AskAiToggle
        label="¿Por qué votaron así? Pregúntale a una IA"
        opts={{}}
        parties={parties}
        question={question}
        title="Pide que te expliquen qué se votó y los argumentos de cada partido:"
      />
      <p className="votingAidLinksRow">
        <ShareQuestionButton question={question} />
      </p>
      <div className="votingAidActions votingAidStickyBar">
        <button
          className={`votingAidButton votingAidButton--primary votingAidButton--big votingAidNext${autoNext ? " is-auto" : ""}`}
          onClick={onNext}
          ref={nextRef}
          title={autoNext ? "Pasa sola en unos segundos. Toca o desplázate para quedarte." : undefined}
          type="button"
        >
          {autoNext ? (
            <svg aria-hidden="true" className="votingAidNext__ring">
              <rect
                height="100%"
                onAnimationEnd={onNext}
                pathLength="100"
                rx="9"
                style={{ animationDuration: `${AUTO_NEXT_MS}ms` }}
                width="100%"
              />
            </svg>
          ) : null}
          Siguiente pregunta →
        </button>
        <button className="votingAidLinkButton" onClick={onChange} type="button">
          Cambiar mi respuesta
        </button>
      </div>
    </div>
  );
}

function MiniLeaderboard({ results, previousRanks, onOpen }) {
  const top = results.filter((r) => r.match !== null).slice(0, 5);
  return (
    <aside aria-label="Clasificación en directo" className="votingAidMini">
      <p className="votingAidMini__title">Tu podio en directo</p>
      {top.length === 0 ? (
        <p className="votingAidMuted">Responde para ver quién se acerca a ti.</p>
      ) : (
        <ol>
          {top.map((row, i) => {
            const before = previousRanks[row.partyId];
            const delta = before === undefined ? 0 : before - i;
            return (
              <li key={row.partyId}>
                <span className="votingAidMini__pos">{["🥇", "🥈", "🥉"][i] || i + 1}</span>
                <span className="votingAidMini__label">{row.label}</span>
                <span aria-hidden="true" className="votingAidMini__bar">
                  <span style={{ width: `${Math.round(row.match * 100)}%` }} />
                </span>
                <span className="votingAidMini__pct">{formatMatch(row.match)}</span>
                <span className={`votingAidMini__delta${delta > 0 ? " is-up" : delta < 0 ? " is-down" : ""}`}>
                  {delta > 0 ? `▲${delta}` : delta < 0 ? `▼${-delta}` : ""}
                </span>
              </li>
            );
          })}
        </ol>
      )}
      <button className="votingAidLinkButton" onClick={onOpen} type="button">
        Ver todos los partidos y por qué →
      </button>
    </aside>
  );
}

function PodiumStrip({ results, previousRanks, onOpen }) {
  const top = results.filter((r) => r.match !== null).slice(0, 3);
  if (!top.length) return null;
  return (
    <button aria-label="Ver clasificación completa" className="votingAidPodiumStrip" onClick={onOpen} type="button">
      {top.map((row, i) => {
        const before = previousRanks[row.partyId];
        const delta = before === undefined ? 0 : before - i;
        return (
          <span className="votingAidPodiumStrip__item" key={row.partyId}>
            <span aria-hidden="true">{["🥇", "🥈", "🥉"][i]}</span> <strong>{row.label}</strong> {formatMatch(row.match)}
            {delta > 0 ? <span className="votingAidMini__delta is-up"> ▲</span> : null}
          </span>
        );
      })}
      <span aria-hidden="true" className="votingAidPodiumStrip__more">
        ›
      </span>
    </button>
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
    <section aria-label={`Tú y ${row.label}`} className="votingAidPartyView">
      <button className="votingAidLinkButton" onClick={onBack} type="button">
        ← Todos los partidos
      </button>
      <h1>
        Tú y {row.label} <span className="votingAidPartyView__pct">{formatMatch(row.match)}</span>
      </h1>
      <div className="votingAidScoreStrip" aria-hidden="true">
        {["match", "partial", "clash"].map((k) =>
          groups[k].length ? <span className={`votingAidScoreStrip__${k}`} key={k} style={{ flexGrow: groups[k].length }} /> : null,
        )}
      </div>
      <p className="votingAidLead">
        <AgreementMark kind="match" /> {groups.match.length} coincidencias · <AgreementMark kind="partial" /> {groups.partial.length} a
        medias · <AgreementMark kind="clash" /> {groups.clash.length} discrepancias
        {groups.none.length ? ` · ${groups.none.length} sin datos` : ""}
      </p>
      {best.length ? (
        <div className="votingAidThemeInsights">
          <p>
            <span aria-hidden="true">💚</span> Donde más coincidís: {best.map((t) => `${t.theme} (${formatMatch(t.match)})`).join(" · ")}
          </p>
          {worst.length ? (
            <p>
              <span aria-hidden="true">💔</span> Donde menos: {worst.map((t) => `${t.theme} (${formatMatch(t.match)})`).join(" · ")}
            </p>
          ) : null}
        </div>
      ) : null}

      <div aria-label="Filtrar por resultado" className="votingAidTabs votingAidTabs--inner" role="tablist">
        {tabs.map(([key, label]) => (
          <button aria-selected={tab === key} key={key} onClick={() => setTab(key)} role="tab" type="button">
            <AgreementMark kind={key} /> {label} <span className="votingAidMuted">{groups[key].length}</span>
          </button>
        ))}
      </div>
      {themes.length > 1 ? (
        <div aria-label="Filtrar por tema" className="votingAidThemeFilter" role="group">
          <button aria-pressed={!theme} onClick={() => setTheme("")} type="button">
            Todos los temas
          </button>
          {themes.map((t) => (
            <button aria-pressed={theme === t.theme} key={t.theme} onClick={() => setTheme(theme === t.theme ? "" : t.theme)} type="button">
              {t.theme} <span className="votingAidMuted">{formatMatch(t.match)}</span>
            </button>
          ))}
        </div>
      ) : null}

      {list.length === 0 ? (
        <p className="votingAidMuted votingAidEmpty">Nada por aquí con este filtro.</p>
      ) : (
        <ul className="votingAidBreakdown" role="tabpanel">
          {list.map((d) => {
            const q = questionsById[d.statementId];
            if (!q) return null;
            const counts = q.source === "pool" ? q.counts?.[row.partyId] : null;
            return (
              <li key={d.statementId}>
                <AgreementMark kind={agreementKind(d.answer, d.position, d.score)} />
                <div className="votingAidBreakdown__body">
                  <p className="votingAidTheme votingAidTheme--small">{q.theme}</p>
                  <p className="votingAidBreakdown__text">{q.text}</p>
                  <ScopeBadges question={q} />
                  <p className="votingAidMuted">
                    Tú: <strong>{answerLabel(q, d.answer)}</strong>
                    {d.weight > 1 ? " ★" : ""} · {row.label}: <PositionBadge position={d.position} score={d.score} />
                    {counts ? ` (${counts[0]} sí · ${counts[1]} no · ${counts[2]} abst.)` : ""}
                  </p>
                  <p className="votingAidBreakdown__actions">
                    <QuestionLinks question={q} />
                    <button className="votingAidLinkButton" onClick={() => onEdit(d.statementId)} type="button">
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

function ResultsView({ results, answeredCount, fromShare, onParty, onPlay, onReview, onShare, onSharePodium, onReset, onOwn, shareMessage, method, bestStreak, excludeOmnibus, onExcludeOmnibus, omnibusAnswered }) {
  const provisional = answeredCount < MIN_ANSWERS_FOR_RANKING;
  return (
    <section aria-label="Resultados" className="votingAidResultsView">
      {fromShare ? (
        <div className="votingAidNotice votingAidNotice--info" role="note">
          Estás viendo respuestas de un enlace compartido; no se han guardado en tu navegador.{" "}
          <button className="votingAidLinkButton" onClick={onOwn} type="button">
            Jugar con mis respuestas
          </button>
        </div>
      ) : null}
      <h1>Tu coincidencia</h1>
      <p className="votingAidLead">
        Con {answeredCount} {answeredCount === 1 ? "respuesta" : "respuestas"}
        {bestStreak > 1 ? ` · mejor racha 🔥 ${bestStreak}` : ""}. Toca un partido para ver en qué coincidís y en qué no.
      </p>
      {answeredCount === 0 ? (
        <div className="votingAidEmpty">
          <p>Aún no has respondido nada.</p>
          <button className="votingAidButton votingAidButton--primary" onClick={onPlay} type="button">
            ¡Empezar!
          </button>
        </div>
      ) : (
        <>
          {provisional ? (
            <p className="votingAidNotice" role="note">
              <strong>Resultado provisional.</strong> Con menos de {MIN_ANSWERS_FOR_RANKING} respuestas el orden baila mucho.
            </p>
          ) : null}
          {omnibusAnswered > 0 ? (
            <label className="votingAidImportant votingAidOmnibusToggle">
              <input checked={excludeOmnibus} onChange={(e) => onExcludeOmnibus(e.target.checked)} type="checkbox" />
              <span>
                No contar las votaciones ómnibus <span className="votingAidMuted">({omnibusAnswered} respondidas): mezclan tantos temas que el voto de un partido puede deberse a cualquiera de ellos.</span>
              </span>
            </label>
          ) : null}
          <ol className="votingAidResultList">
            {results.map((row, i) => {
              const g = groupDetails(row.details);
              return (
                <li className="votingAidResult" key={row.partyId}>
                  <button className="votingAidResult__head" onClick={() => onParty(row.partyId)} type="button">
                    <span className="votingAidResult__rank">{row.match === null ? "–" : ["🥇", "🥈", "🥉"][i] || i + 1}</span>
                    <span className="votingAidResult__label">{row.label}</span>
                    <span aria-hidden="true" className="votingAidResult__bar">
                      <span style={{ width: `${row.match === null ? 0 : Math.round(row.match * 100)}%` }} />
                    </span>
                    <span className="votingAidResult__pct">{formatMatch(row.match)}</span>
                    <span aria-hidden="true" className="votingAidResult__chevron">
                      ›
                    </span>
                  </button>
                  <p className="votingAidMuted votingAidResult__coverage">
                    ✓ {g.match.length} coincidencias · ≈ {g.partial.length} · ✗ {g.clash.length} discrepancias
                    {g.none.length ? ` · sin datos ${g.none.length}` : ""}
                  </p>
                </li>
              );
            })}
          </ol>
          <div className="votingAidActions">
            <button className="votingAidButton votingAidButton--primary" onClick={onPlay} type="button">
              Seguir jugando
            </button>
            {answeredCount >= MIN_ANSWERS_FOR_RANKING ? (
              <button className="votingAidButton" onClick={onSharePodium} type="button">
                📣 Compartir mi podio
              </button>
            ) : null}
            <button className="votingAidButton" onClick={onReview} type="button">
              Revisar mis respuestas
            </button>
            <button className="votingAidButton" onClick={onShare} type="button">
              Copiar enlace con mis respuestas
            </button>
            <button className="votingAidButton votingAidButton--quiet" onClick={onReset} type="button">
              Borrar todo
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
            Partido: a favor +1, en contra −1, abstención o votos divididos 0. Tú: sí / de acuerdo +1, me da igual / neutral 0, no / en
            desacuerdo −1.
          </li>
          <li>Coincidencia por pregunta = 1 − |tú − partido| / 2. «Me importa mucho» cuenta doble. Sin datos del partido, no cuenta.</li>
          <li>
            En el modo infinito, «Sí» significa apoyar lo votado (tramitar la ley, convalidar el decreto, aprobar la moción). Se alternan
            votaciones donde el «sí» favorece a bloques distintos y se oculta quién lo propuso hasta que respondes.
          </li>
          {method.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <p>
          <a href={withBasePath("/citizen/vota/metodologia/")}>Cómo se hizo: fuentes, modelos de IA, prompts y limitaciones →</a>
        </p>
      </details>
    </section>
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
    <section aria-label="Tus respuestas" className="votingAidReview">
      <h1>Tus respuestas</h1>
      <p className="votingAidLead">Cambia lo que quieras; la clasificación se recalcula al momento.</p>
      <label className="votingAidImportant">
        <input checked={onlyImportant} onChange={(e) => setOnlyImportant(e.target.checked)} type="checkbox" />
        Solo las que me importan mucho ★
      </label>
      {groups.length === 0 ? <p className="votingAidMuted votingAidEmpty">Nada que revisar todavía.</p> : null}
      {groups.map(([theme, qs]) => (
        <details className="votingAidReview__group" key={theme} open={groups.length <= 4}>
          <summary>
            <span className="votingAidTheme">{theme}</span> <span className="votingAidMuted">{qs.length}</span>
          </summary>
          <ul className="votingAidReview__list">
            {qs.map((q) => {
              const answer = state.answers[q.statement_id];
              const labels = q.source === "pool" ? POOL_ANSWER_LABELS : ANSWER_LABELS;
              return (
                <li key={q.statement_id}>
                  <button className="votingAidReview__text" onClick={() => onOpen(q.statement_id)} type="button">
                    {q.text}
                    {state.important[q.statement_id] ? <span className="votingAidStar"> ★</span> : null}
                  </button>
                  <div aria-label="Tu respuesta" className="votingAidSegmented" role="group">
                    {ANSWER_ORDER.map((value) => (
                      <button
                        aria-pressed={answer === value}
                        className={answer === value ? "is-selected" : undefined}
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
// Page

export default function VotingAidClient({ snapshot, startStatementId = null, versionId = null }) {
  const version = versionById(versionId);
  const [staleShare, setStaleShare] = useState(false);
  const parties = useMemo(() => (Array.isArray(snapshot?.parties) ? snapshot.parties : []), [snapshot]);
  const meta = snapshot?.meta || {};
  const [pool, setPool] = useState(null);
  const [poolStatus, setPoolStatus] = useState("loading");
  const [highlights, setHighlights] = useState(null);
  const [voteBullets, setVoteBullets] = useState(null);
  const [voteImpacts, setVoteImpacts] = useState(null);
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
  const topRef = useRef(null);
  const toastTimer = useRef(null);
  const startedAt = useRef(false);

  const questions = useMemo(
    () => attachHighlights(buildQuestions(snapshot, pool), highlights, voteBullets, voteImpacts),
    [snapshot, pool, highlights, voteBullets, voteImpacts],
  );
  const scoredQuestions = useMemo(
    () => (state.excludeOmnibus ? questions.filter((q) => !q.omnibus) : questions),
    [questions, state.excludeOmnibus],
  );
  const questionsById = useMemo(() => Object.fromEntries(questions.map((q) => [q.statement_id, q])), [questions]);
  const curatedTotal = useMemo(() => questions.filter((q) => q.source === "curated").length, [questions]);
  const order = useMemo(() => playOrder(questions, state.seed || 1), [questions, state.seed]);
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
    if (poolStatus === "loading") return undefined;
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
        if (startStatementId && !startedAt.current && questions.some((q) => q.statement_id === startStatementId)) {
          startedAt.current = true;
          setCurrentId(startStatementId);
          setView("play");
        }
      }
      setLoaded(true);
    }
    const onHashChange = () => load(false);
    load(true);
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, [poolStatus, questions, startStatementId, version]);

  useEffect(() => {
    if (loaded && !fromShare) writeStoredState(version.storageKey, state);
  }, [state, loaded, fromShare, version.storageKey]);

  useEffect(() => () => clearTimeout(toastTimer.current), []);

  const scrollTop = useCallback(() => {
    topRef.current?.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" });
  }, []);

  function update(next) {
    if (fromShare) {
      setFromShare(false);
      if (window.location.hash) window.history.replaceState(null, "", window.location.pathname);
    }
    setState(next);
  }

  function showToast(emoji, text) {
    clearTimeout(toastTimer.current);
    setToast({ emoji, text });
    toastTimer.current = setTimeout(() => setToast(null), 3200);
  }

  function goPlay(nextId, answers = state.answers, skipped = state.skipped, split = state.split) {
    const id =
      nextId ||
      pendingSubId(questionsById, split, answers, skipped) ||
      nextQuestionId(
        order.filter((qid) => !split?.[qid]),
        answers,
        skipped,
      );
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
    const { current } = milestoneFor(count);
    if (!wasAnswered && current && current.at === count) showToast(current.emoji, `¡Nuevo rango: ${current.title}!`);
    else if (!wasAnswered && streak > 0 && streak % 10 === 0) showToast("🔥", `¡Racha de ${streak} sin saltarte ninguna!`);
    if (!wasAnswered && count === curatedTotal && Object.keys(answers).every((qid) => questionsById[qid]?.source === "curated")) {
      showToast("🎯", "¡Temas clave completados! Bienvenida/o al modo infinito.");
    }
    if (state.showReveal) setRevealId(id);
    else goPlay(nextQuestionId(order, answers, skipped), answers, skipped);
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
    goPlay(nextQuestionId(order, state.answers, skipped), state.answers, skipped);
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
      setShareMessage("Podio copiado (sin tus respuestas). ¡Pégalo donde quieras!");
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
    if (window.location.hash) window.history.replaceState(null, "", window.location.pathname);
    setView("intro");
    scrollTop();
  }

  function ownAnswers() {
    window.history.replaceState(null, "", window.location.pathname);
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

  // Keyboard: 1/2/3 answer, 4 «depende» (split), S skip, Enter next after the reveal.
  useEffect(() => {
    if (view !== "play") return undefined;
    function onKey(event) {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      const tag = event.target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
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

  const current = currentId ? questionsById[currentId] : null;
  const revealQuestion = revealId ? questionsById[revealId] : null;
  const partyRow = partyId ? results.find((r) => r.partyId === partyId) : null;
  const curatedLeft = questions.filter((q) => q.source === "curated" && !state.answers[q.statement_id] && !state.split?.[q.statement_id]).length;

  return (
    <main className="shell staticRoute votingAid" ref={topRef}>
      <Toast toast={toast} />
      <VersionBanner version={version} />
      {staleShare ? (
        <p className="votingAidNotice" role="note">
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
      {view !== "intro" ? (
        <nav aria-label="Secciones" className="votingAidTabs votingAidTabs--main">
          <button
            aria-current={view === "play" ? "page" : undefined}
            onClick={() => goPlay(currentId && !state.answers[currentId] ? currentId : null)}
            type="button"
          >
            <span aria-hidden="true" className="votingAidTabs__icon">🎮</span> Jugar
          </button>
          <button aria-current={view === "results" || view === "party" ? "page" : undefined} onClick={() => show("results")} type="button">
            <span aria-hidden="true" className="votingAidTabs__icon">🏆</span> Resultados
          </button>
          <button aria-current={view === "review" ? "page" : undefined} onClick={() => show("review")} type="button">
            <span aria-hidden="true" className="votingAidTabs__icon">📝</span> Respuestas{" "}
            {answeredCount ? <span className="votingAidTabs__count">{answeredCount}</span> : null}
          </button>
        </nav>
      ) : null}

      {view === "intro" ? (
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
      ) : null}

      {view === "play" ? (
        <section aria-label="Jugar" className="votingAidPlay">
          <div className="votingAidHud">
            <RankBadge count={answeredCount} />
            <span className="votingAidHud__stats">
              <span title="Respuestas seguidas sin saltar">🔥 {state.streak || 0}</span>
              <span className="votingAidMuted">
                {answeredCount}/{questions.length}
              </span>
            </span>
          </div>
          <ProgressBar
            label={curatedLeft ? `Temas clave: ${curatedTotal - curatedLeft} de ${curatedTotal}` : `${answeredCount} de ${questions.length}`}
            max={curatedLeft ? curatedTotal : questions.length}
            value={curatedLeft ? curatedTotal - curatedLeft : answeredCount}
          />
          <p className="votingAidMuted votingAidPhase">
            {curatedLeft
              ? `Fase 1 · Temas clave (quedan ${curatedLeft}). Después: modo infinito con votaciones reales.`
              : poolStatus === "ready"
                ? "♾️ Modo infinito · votaciones reales del Congreso. Para cuando quieras."
                : poolStatus === "error"
                  ? "No se pudieron cargar más votaciones ahora mismo."
                  : "Cargando votaciones…"}
          </p>
          <PodiumStrip onOpen={() => show("results")} previousRanks={previousRanks} results={results} />
          <div className="votingAidPlay__grid">
            <div>
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
                  important={state.important[current.statement_id]}
                  onAnswer={answer}
                  onImportant={(v) => setImportant(current.statement_id, v)}
                  onSkip={skip}
                  onSplit={() => splitStatement(current.statement_id)}
                  parties={parties}
                  question={current}
                  showSwipeHint={answeredCount < 3}
                />
              ) : (
                <div className="votingAidCard votingAidEmpty">
                  <p aria-hidden="true" className="votingAidReveal__emoji">
                    🏆
                  </p>
                  <h2>¡Lo has respondido todo!</h2>
                  <p>{answeredCount} preguntas. Eres oficialmente una enciclopedia andante del Congreso.</p>
                  <button className="votingAidButton votingAidButton--primary" onClick={() => show("results")} type="button">
                    Ver mis resultados
                  </button>
                </div>
              )}
              <label className="votingAidImportant votingAidRevealToggle">
                <input checked={state.showReveal !== false} onChange={(e) => update({ ...state, showReveal: e.target.checked })} type="checkbox" />
                Mostrar cómo votó cada partido después de responder
              </label>
              <p className="votingAidMuted votingAidShortcuts">Atajos: 1 · 2 · 3 para responder, 4 «depende», S para saltar, Intro para seguir.</p>
            </div>
            <MiniLeaderboard onOpen={() => show("results")} previousRanks={previousRanks} results={results} />
          </div>
        </section>
      ) : null}

      {view === "results" ? (
        <ResultsView
          answeredCount={answeredCount}
          bestStreak={state.bestStreak || 0}
          fromShare={fromShare}
          method={meta.honesty || []}
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
          excludeOmnibus={state.excludeOmnibus}
          onExcludeOmnibus={(v) => update({ ...state, excludeOmnibus: v })}
          omnibusAnswered={omnibusAnswered}
          results={results}
          shareMessage={shareMessage}
        />
      ) : null}
      {view === "results" && !fromShare && pool ? <OtherVersionResults pool={pool} version={version} /> : null}

      {view === "party" && partyRow ? (
        <PartyView key={partyRow.partyId} parties={parties} onBack={() => show("results")} onEdit={(id) => goPlay(id)} questionsById={questionsById} row={partyRow} />
      ) : null}

      {view === "review" ? <ReviewView onAnswer={setAnswer} onOpen={(id) => goPlay(id)} questions={questions} state={state} /> : null}
    </main>
  );
}
