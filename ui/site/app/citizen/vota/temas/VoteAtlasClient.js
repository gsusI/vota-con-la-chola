"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { withBasePath } from "../../../path-utils.mjs";
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
      <p className="atlasVote__summary">{vote.summary_yes || voteTitle(atlas, vote)}</p>
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

function AxisCard({ atlas, axis, open, onToggle, highlight, kindLabels }) {
  const rows = useMemo(() => axisParties(atlas, axis.axis_id), [atlas, axis.axis_id]);
  const byParty = Object.fromEntries(rows.map((r) => [r.party_id, r]));
  const [onlyMain, setOnlyMain] = useState(false);
  const votes = useMemo(
    () => (open ? votesForAxis(atlas, axis.axis_id).filter((v) => !onlyMain || !AMENDMENT_KINDS.has(v.kind)) : []),
    [atlas, axis.axis_id, open, onlyMain],
  );
  const [shown, setShown] = useState(PAGE);
  return (
    <article className="atlasAxis votingAidCard" id={`eje-${axis.axis_id}`}>
      <h3 className="atlasAxis__title">{axis.label}</h3>
      <PoleLegend axis={axis} />
      <div className="atlasAxis__bars">
        {(atlas.parties || []).map((p) => {
          const r = byParty[p.party_id];
          return (
            <DirectionBar
              highlight={highlight === p.party_id}
              key={p.party_id}
              label={p.label}
              score={r ? r.score : NaN}
              sub={r ? `${directionText(axis, r.score)} · ${r.votes}\u00a0vot.` : "Sin votaciones"}
            />
          );
        })}
      </div>
      <p className="votingAidMuted atlasAxis__count">
        {axis.votes} votaciones de {axis.initiatives} iniciativas cuentan en este eje.{" "}
        <button aria-expanded={open} className="votingAidLinkButton" onClick={onToggle} type="button">
          {open ? "Ocultar votaciones" : "Ver las votaciones"}
        </button>
      </p>
      {open ? (
        <>
          <details className="atlasAxis__poles">
            <summary>Qué significa cada extremo</summary>
            <p>
              <strong>{axis.pos_short}:</strong> {axis.pos}
            </p>
            <p>
              <strong>{axis.neg_short}:</strong> {axis.neg}
            </p>
          </details>
          <label className="atlasSelect atlasToggle">
            <input checked={onlyMain} onChange={(e) => setOnlyMain(e.target.checked)} type="checkbox" /> Ocultar enmiendas (ver solo leyes,
            decretos, mociones y proposiciones)
          </label>
          <ul className="atlasVotes">
            {votes.slice(0, shown).map((v) => (
              <VoteRow atlas={atlas} axis={axis} key={`${v.id}-${axis.axis_id}`} kindLabels={kindLabels} vote={v} />
            ))}
          </ul>
          {votes.length > shown ? (
            <button className="votingAidButton" onClick={() => setShown(shown + PAGE)} type="button">
              Ver más ({votes.length - shown})
            </button>
          ) : null}
        </>
      ) : null}
    </article>
  );
}

export default function VoteAtlasClient() {
  const [atlas, setAtlas] = useState(null);
  const [status, setStatus] = useState("loading");
  const [view, setView] = useState({ tema: "", eje: "", partido: "" });

  useEffect(() => {
    let cancelled = false;
    fetch(withBasePath(ATLAS_PATH))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => {
        if (!cancelled) {
          setAtlas(data);
          setStatus("ready");
        }
      })
      .catch(() => !cancelled && setStatus("error"));
    const sync = () => setView({ tema: "", eje: "", partido: "", ...readHash(window.location.hash) });
    sync();
    window.addEventListener("hashchange", sync);
    return () => {
      cancelled = true;
      window.removeEventListener("hashchange", sync);
    };
  }, []);

  useEffect(() => {
    if (status === "ready" && view.eje) document.getElementById(`eje-${view.eje}`)?.scrollIntoView({ block: "start" });
  }, [status, view.eje]);

  function go(next) {
    const merged = { ...view, ...next };
    setView(merged);
    window.history.replaceState(null, "", `${window.location.pathname}${writeHash(merged)}`);
  }

  const idx = useMemo(() => indexAtlas(atlas), [atlas]);
  const meta = atlas?.meta || {};
  const cov = meta.coverage || {};
  const axes = idx.axes.filter((a) => a.votes > 0 && (!view.tema || a.topic_id === view.tema));
  const topicsWithAxes = idx.topics.filter((t) => idx.axes.some((a) => a.topic_id === t.topic_id && a.votes > 0));

  return (
    <main className="votingAid atlas">
      <p className="votingAidEyebrow">Congreso de los Diputados · XV legislatura</p>
      <h1>¿Hacia dónde ha empujado cada partido?</h1>
      <p className="votingAidLead">
        Cada votación nominal del Pleno con partidos enfrentados, leída y colocada en ejes por tema. La barra de cada partido
        resume hacia qué extremo del eje empujaron sus diputados: de −1 (siempre hacia el extremo de la izquierda de la barra, en ocre) a +1 (siempre hacia el de la derecha, en azul). Los colores no valoran: solo marcan el sentido.
      </p>
      {status === "loading" ? <p className="votingAidMuted">Cargando votaciones…</p> : null}
      {status === "error" ? <p className="votingAidNotice">No se pudieron cargar los datos. Inténtalo de nuevo más tarde.</p> : null}
      {status === "ready" ? (
        <>
          <ul className="votingAidFacts atlasFacts">
            <li>
              <strong>{formatCount(cov.events_total || 0)}</strong> votaciones nominales del Pleno entre {formatDate(meta.votes_first_date)} y{" "}
              {formatDate(meta.votes_last_date)}; <strong>{formatCount(cov.scored_votes || 0)}</strong> cuentan en algún eje.
            </li>
            <li>
              Las enmiendas también cuentan: su texto se buscó en el BOCG (
              {formatCount((meta.amendments?.votes || 0) - (meta.amendments?.by_resolution?.sin_texto || 0))} de{" "}
              {formatCount(meta.amendments?.votes || 0)} localizadas, XIV y XV) y todas las de una misma ley pesan como una sola
              iniciativa. Puedes ocultarlas en la lista de votaciones de cada eje.
            </li>
            <li>
              Clasificación con IA a partir del texto oficial, sin ver cómo votó nadie; cada votación enlaza al Congreso y al BOCG.{" "}
              {meta.review?.agreement ? <>Acuerdo entre dos clasificadores independientes: {meta.review.agreement}. </> : null}
              Falta la revisión humana. <Link href="/citizen/vota/metodologia/#mapa">Cómo se hizo</Link>.
            </li>
          </ul>
          <p className="atlasNav">
            <Link className="votingAidButton votingAidButton--primary" href="/citizen/vota/">
              Haz el test: ¿con quién coincides?
            </Link>{" "}
            <Link className="votingAidButton" href="/citizen/vota/diputados/">
              Busca a tu diputado/a
            </Link>
          </p>
          <div className="atlasControls">
            <div aria-label="Temas" className="votingAidTabs atlasTopics" role="tablist">
              <button aria-selected={!view.tema} className="votingAidTab" onClick={() => go({ tema: "", eje: "" })} role="tab" type="button">
                Todos
              </button>
              {topicsWithAxes.map((t) => (
                <button aria-selected={view.tema === t.topic_id} className="votingAidTab" key={t.topic_id} onClick={() => go({ tema: t.topic_id, eje: "" })} role="tab" type="button">
                  {t.label}
                </button>
              ))}
            </div>
            <label className="atlasSelect">
              Resaltar partido{" "}
              <select onChange={(e) => go({ partido: e.target.value })} value={view.partido}>
                <option value="">—</option>
                {idx.parties.map((p) => (
                  <option key={p.party_id} value={p.party_id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {topicsWithAxes
            .filter((t) => !view.tema || t.topic_id === view.tema)
            .map((t) => (
              <section className="atlasTopic" key={t.topic_id}>
                <h2>{t.label}</h2>
                {axes
                  .filter((a) => a.topic_id === t.topic_id)
                  .map((a) => (
                    <AxisCard
                      atlas={atlas}
                      axis={a}
                      highlight={view.partido}
                      key={a.axis_id}
                      kindLabels={atlas.kind_labels}
                      onToggle={() => go({ eje: view.eje === a.axis_id ? "" : a.axis_id })}
                      open={view.eje === a.axis_id}
                    />
                  ))}
              </section>
            ))}
          <section className="votingAidNotice votingAidNotice--info atlasHonesty">
            <h2>Antes de sacar conclusiones</h2>
            <ul>
              {(meta.honesty || []).map((h) => (
                <li key={h}>{h}</li>
              ))}
            </ul>
          </section>
        </>
      ) : null}
    </main>
  );
}
