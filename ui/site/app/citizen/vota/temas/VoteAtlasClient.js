"use client";

import { useEffect, useMemo, useState } from "react";
import { withBasePath } from "../../../path-utils.mjs";
import "../explore.css";
import { ExploreNav, LoadState, PartySquares, ROUTES, ResultText, SquaresLegend, href, partyHref, useJson, voteHref } from "../explorar/ExploreClient";
import { barGeometry, leaningText, totalsText } from "../exploreModel.mjs";
import {
  ATLAS_PATH,
  CHOICE_LABELS,
  CONFIDENCE_LABELS,
  axisParties,
  directionText,
  formatCount,
  formatDate,
  indexAtlas,
  officialVoteUrl,
  partyChoices,
  pushOf,
  readHash,
  voteTitle,
  votesForAxis,
  writeHash,
} from "../voteAtlasModel.mjs";

const PAGE = 15;
const AMENDMENT_KINDS = new Set(["enmienda", "enmienda_senado", "voto_particular"]);

// ---------------------------------------------------------------------------
// Legacy pieces still used by the test (VotingAidClient): keep their props and class names.

export function DirectionBar({ score, label, sub, highlight = false, marker = null }) {
  const pct = Number.isFinite(score) ? Math.abs(score) * 50 : 0;
  const side = score >= 0 ? "pos" : "neg";
  return (
    <div className={`atlasBar${highlight ? " atlasBar--highlight" : ""}`}>
      <span className="atlasBar__label">{label}</span>
      <span aria-hidden="true" className="atlasBar__track">
        <span className="atlasBar__zero" />
        {Number.isFinite(score) ? (
          <span className={`atlasBar__fill atlasBar__fill--${side}`} style={side === "pos" ? { left: "50%", width: `${pct}%` } : { right: "50%", width: `${pct}%` }} />
        ) : null}
        {Number.isFinite(marker) ? <span className="atlasBar__marker" style={{ left: `${(marker + 1) * 50}%` }} title="Su partido" /> : null}
      </span>
      <span className="atlasBar__value">{Number.isFinite(score) ? (score > 0 ? "+" : "") + score.toFixed(2) : "—"}</span>
      {sub ? <span className="atlasBar__sub">{sub}</span> : null}
    </div>
  );
}

export function PoleLegend({ axis }) {
  return (
    <p className="atlasPoles">
      <span className="atlasPoles__neg" title={axis.neg}>← {axis.neg_short}</span>
      <span className="atlasPoles__pos" title={axis.pos}>{axis.pos_short} →</span>
    </p>
  );
}

export function VoteRow({ atlas, vote, axis, kindLabels }) {
  const choices = partyChoices(atlas, vote);
  const sign = vote.sign;
  return (
    <li className="atlasVote">
      <p className="atlasVote__meta">
        {formatDate(vote.date)} · {kindLabels?.[vote.kind] || vote.kind} ·{" "}
        <span className={`votingAidBadge votingAidBadge--${vote.approved ? "agree" : "disagree"}`}>{vote.approved ? "Aprobada" : "Rechazada"}</span>
        {vote.confidence === "baja" ? <span className="votingAidMuted"> · {CONFIDENCE_LABELS.baja}</span> : null}
      </p>
      <p className="atlasVote__summary">
        <a href={withBasePath(`/citizen/vota/votacion/#v=${encodeURIComponent(vote.id)}`)}>{vote.summary_yes || voteTitle(atlas, vote)}</a>
      </p>
      {axis && sign ? (
        <p className="atlasVote__push">
          Votar Sí empuja hacia <strong>«{sign === "+" ? axis.pos_short : axis.neg_short}»</strong>
        </p>
      ) : null}
      <p className="atlasVote__title">
        {voteTitle(atlas, vote)}
        {vote.subgroup ? <span className="votingAidMuted"> — {vote.subgroup}</span> : null}
      </p>
      <ul aria-label="Voto mayoritario de cada partido" className="atlasChips">
        {choices.map((c) => (
          <li className={`atlasChip atlasChip--${c.code === "S" ? "yes" : c.code === "N" ? "no" : "other"}${sign && pushOf(c.code, sign) !== "none" ? ` atlasChip--${pushOf(c.code, sign)}` : ""}`} key={c.party_id} title={`${c.label}: ${CHOICE_LABELS[c.code] || c.code}`}>
            {c.label} <strong>{CHOICE_LABELS[c.code] || c.code}</strong>
          </li>
        ))}
      </ul>
      <p className="atlasVote__links">
        <a href={officialVoteUrl(vote.path)} rel="noopener noreferrer" target="_blank">
          Votación oficial
        </a>
        {vote.text_url ? (
          <>
            {" · "}
            <a href={vote.text_url} rel="noopener noreferrer" target="_blank">
              Texto votado (BOCG)
            </a>
          </>
        ) : null}
      </p>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Votes by topic (/citizen/vota/temas/), Explorar design.

function PartyBar({ party, row, axis, highlight }) {
  const { left, width } = barGeometry(row ? row.score : NaN);
  return (
    <li className={`x-pbar${highlight ? " is-hl" : ""}`}>
      <a className="x-pbar__name" href={partyHref(party.party_id)}>
        {party.label}
      </a>
      <span aria-label={row ? `${party.label}: ${leaningText(axis, row.score)}` : `${party.label}: sin votaciones`} className={`x-dbar${highlight ? " x-dbar--hl" : ""}`} role="img">
        <span aria-hidden="true" className="x-dbar__zero" />
        {row ? <span className="x-dbar__fill" style={{ left: `${left}%`, width: `${width}%` }} /> : null}
      </span>
      <span className="x-pbar__sub">{row ? `${directionText(axis, row.score)} · ${row.votes} vot.` : "Sin votaciones"}</span>
    </li>
  );
}

function AtlasVote({ atlas, vote, axis }) {
  const sign = vote.sign;
  const title = voteTitle(atlas, vote);
  return (
    <li>
      <p className="x-vlist__meta">
        <span className="v-mono">{formatDate(vote.date)}</span>
        <span>{atlas.kind_labels?.[vote.kind] || vote.kind}</span>
        <ResultText vote={vote} />
        <span>{totalsText(vote.totals)}</span>
        {vote.confidence === "baja" ? <span>{CONFIDENCE_LABELS.baja}</span> : null}
      </p>
      <p className="x-vlist__summary">
        <a href={voteHref(vote.id)}>{vote.summary_yes || title}</a>
      </p>
      {axis && sign ? (
        <p className="x-vlist__push">
          Votar Sí empuja hacia <strong>«{sign === "+" ? axis.pos_short : axis.neg_short}»</strong>
        </p>
      ) : null}
      {title && title !== vote.summary_yes ? (
        <p className="x-vlist__title">
          {title}
          {vote.subgroup ? ` — ${vote.subgroup}` : ""}
        </p>
      ) : null}
      <PartySquares abbr="always" atlas={atlas} vote={vote} />
      <p className="x-vlist__links">
        <a href={voteHref(vote.id)}>Cómo votó cada diputado</a>
        {officialVoteUrl(vote.path) ? (
          <a href={officialVoteUrl(vote.path)} rel="noopener noreferrer" target="_blank">
            Votación oficial <span aria-hidden="true">↗</span>
          </a>
        ) : null}
        {vote.text_url ? (
          <a href={vote.text_url} rel="noopener noreferrer" target="_blank">
            Texto votado (BOCG) <span aria-hidden="true">↗</span>
          </a>
        ) : null}
      </p>
    </li>
  );
}

function AxisSection({ atlas, axis, open, onToggle, highlight }) {
  const rows = useMemo(() => axisParties(atlas, axis.axis_id), [atlas, axis.axis_id]);
  const byParty = Object.fromEntries(rows.map((r) => [r.party_id, r]));
  const [onlyMain, setOnlyMain] = useState(false);
  const [shown, setShown] = useState(PAGE);
  const votes = useMemo(
    () => (open ? votesForAxis(atlas, axis.axis_id).filter((v) => !onlyMain || !AMENDMENT_KINDS.has(v.kind)) : []),
    [atlas, axis.axis_id, open, onlyMain],
  );
  return (
    <article aria-labelledby={`t-${axis.axis_id}`} className="v-card x-axcard" id={`eje-${axis.axis_id}`}>
      <h3 id={`t-${axis.axis_id}`}>{axis.label}</h3>
      <p className="x-axcard__poles">
        <span title={axis.neg}>← {axis.neg_short}</span>
        <span title={axis.pos}>{axis.pos_short} →</span>
      </p>
      <ul className="x-pbars">
        {(atlas.parties || []).map((p) => (
          <PartyBar axis={axis} highlight={highlight === p.party_id} key={p.party_id} party={p} row={byParty[p.party_id]} />
        ))}
      </ul>
      <p className="x-axcard__foot">
        <span>
          {formatCount(axis.votes)} votaciones de {formatCount(axis.initiatives)} iniciativas cuentan en este eje.
        </span>
        <button aria-expanded={open} className="v-link-btn" onClick={onToggle} type="button">
          {open ? "Ocultar votaciones" : "Ver las votaciones"}
        </button>
      </p>
      {open ? (
        <>
          <details className="x-details">
            <summary>Qué significa cada extremo</summary>
            <p>
              <strong>{axis.pos_short}:</strong> {axis.pos}
            </p>
            <p>
              <strong>{axis.neg_short}:</strong> {axis.neg}
            </p>
          </details>
          <label className="x-check">
            <input checked={onlyMain} onChange={(e) => setOnlyMain(e.target.checked)} type="checkbox" /> Ocultar enmiendas (ver solo leyes, decretos,
            mociones y proposiciones)
          </label>
          {votes.length ? (
            <ul className="x-vlist">
              {votes.slice(0, shown).map((v) => (
                <AtlasVote atlas={atlas} axis={axis} key={`${v.id}-${axis.axis_id}`} vote={v} />
              ))}
            </ul>
          ) : (
            <p className="v-muted">Sin votaciones con este filtro.</p>
          )}
          {votes.length > shown ? (
            <button className="v-btn" onClick={() => setShown(shown + PAGE)} type="button">
              Ver más ({formatCount(votes.length - shown)})
            </button>
          ) : null}
          {votes.length ? <SquaresLegend /> : null}
        </>
      ) : null}
    </article>
  );
}

export default function VoteAtlasClient() {
  const [atlas, status] = useJson(ATLAS_PATH);
  const [view, setView] = useState({ tema: "", eje: "", partido: "" });

  useEffect(() => {
    const sync = () => setView({ tema: "", eje: "", partido: "", ...readHash(window.location.hash) });
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  useEffect(() => {
    if (status === "ready" && view.eje) document.getElementById(`eje-${view.eje}`)?.scrollIntoView({ block: "start" });
  }, [status, view.eje]);

  function go(next) {
    const merged = { ...view, ...next };
    setView(merged);
    window.history.replaceState(null, "", `${window.location.pathname}${writeHash(merged) || window.location.search}`);
  }

  const idx = useMemo(() => indexAtlas(atlas), [atlas]);
  const meta = atlas?.meta || {};
  const cov = meta.coverage || {};
  const axes = idx.axes.filter((a) => a.votes > 0 && (!view.tema || a.topic_id === view.tema));
  const topicsWithAxes = idx.topics.filter((t) => idx.axes.some((a) => a.topic_id === t.topic_id && a.votes > 0));
  const highlighted = idx.parties.find((p) => p.party_id === view.partido);

  return (
    <>
      <ExploreNav current="temas" />
      <main className="v-page x-topics">
        <div className="x-head__text">
          <p className="v-eyebrow">Congreso de los Diputados · XV legislatura</p>
          <h1 className="v-h1">¿Hacia dónde ha empujado cada partido?</h1>
          <p className="v-lead">
            Cada votación nominal del Pleno con partidos enfrentados, leída y colocada en ejes por tema. La barra de cada partido sale del centro
            hacia el extremo al que empujaron sus votos: más larga, más constante. El color no valora: solo marca el sentido.
          </p>
        </div>
        <LoadState status={status} what="las votaciones" />
        {atlas ? (
          <>
            <section aria-label="Sobre estos datos" className="v-card v-card--sunk">
              <ul className="x-facts">
                <li>
                  <strong>{formatCount(cov.events_total || 0)}</strong> votaciones nominales del Pleno entre {formatDate(meta.votes_first_date)} y{" "}
                  {formatDate(meta.votes_last_date)}; <strong>{formatCount(cov.scored_votes || 0)}</strong> cuentan en algún eje.
                </li>
                <li>
                  Las enmiendas también cuentan: su texto se buscó en el BOCG (
                  {formatCount((meta.amendments?.votes || 0) - (meta.amendments?.by_resolution?.sin_texto || 0))} de{" "}
                  {formatCount(meta.amendments?.votes || 0)} localizadas, XIV y XV) y todas las de una misma ley pesan como una sola iniciativa.
                  Puedes ocultarlas en la lista de votaciones de cada eje.
                </li>
                <li>
                  Clasificación con IA a partir del texto oficial, sin ver cómo votó nadie; cada votación enlaza al Congreso y al BOCG.{" "}
                  {meta.review?.agreement ? <>Acuerdo entre dos clasificadores independientes: {meta.review.agreement}. </> : null}
                  Falta la revisión humana. <a href={href(ROUTES.method, "#mapa")}>Cómo se hizo</a>.
                </li>
              </ul>
            </section>
            <div className="x-head__actions">
              <a className="v-btn v-btn--primary" href={href(ROUTES.test)}>
                Haz el test: ¿con quién coincides?
              </a>
              <a className="v-btn" href={href(ROUTES.people)}>
                Busca a tu diputado/a
              </a>
            </div>
            <div className="x-controls">
              <div aria-label="Temas" className="v-chips v-chips--scroll" role="group">
                <button aria-pressed={!view.tema} className="v-chip" onClick={() => go({ tema: "", eje: "" })} type="button">
                  Todos
                </button>
                {topicsWithAxes.map((t) => (
                  <button aria-pressed={view.tema === t.topic_id} className="v-chip" key={t.topic_id} onClick={() => go({ tema: t.topic_id, eje: "" })} type="button">
                    {t.label}
                  </button>
                ))}
              </div>
              <label className="x-select">
                Resaltar partido
                <select onChange={(e) => go({ partido: e.target.value })} value={view.partido}>
                  <option value="">—</option>
                  {idx.parties.map((p) => (
                    <option key={p.party_id} value={p.party_id}>
                      {p.label}
                    </option>
                  ))}
                </select>
                {highlighted ? <a href={partyHref(highlighted.party_id)}>Ficha de {highlighted.label} →</a> : null}
              </label>
            </div>
            {topicsWithAxes
              .filter((t) => !view.tema || t.topic_id === view.tema)
              .map((t) => (
                <section aria-labelledby={`tema-${t.topic_id}`} className="x-topic" key={t.topic_id}>
                  <h2 className="v-h2" id={`tema-${t.topic_id}`}>
                    {t.label}
                  </h2>
                  {axes
                    .filter((a) => a.topic_id === t.topic_id)
                    .map((a) => (
                      <AxisSection
                        atlas={atlas}
                        axis={a}
                        highlight={view.partido}
                        key={a.axis_id}
                        onToggle={() => go({ eje: view.eje === a.axis_id ? "" : a.axis_id })}
                        open={view.eje === a.axis_id}
                      />
                    ))}
                </section>
              ))}
            <section aria-labelledby="x-honesty" className="v-card v-card--sunk x-honesty">
              <h2 className="x-card-title" id="x-honesty">
                Antes de sacar conclusiones
              </h2>
              <ul>
                {(meta.honesty || []).map((h) => (
                  <li key={h}>{h}</li>
                ))}
              </ul>
            </section>
          </>
        ) : null}
      </main>
    </>
  );
}
