"use client";

// Party map (/citizen/vota/mapa/): three views in one route, chosen by hash (#vista=mapa|brujula|adivina).
// Positions come from the vote atlas; «Tú» only appears when this browser holds answers to the current test
// (read from localStorage, never written to the URL).

import "./map.css";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { withBasePath } from "../../../path-utils.mjs";
import { ATLAS_PATH, formatCount } from "../voteAtlasModel.mjs";
import { CURRENT_VERSION } from "../votingAidVersions.mjs";
import {
  BEST_KEY,
  COMPASS_PRESETS,
  DEFAULT_PICKS,
  DEFAULT_X,
  DEFAULT_Y,
  DIANA,
  MAX_PICKS,
  MAX_PICKS_MOBILE,
  MIN_AXIS_VOTES,
  PARTY_ABBR,
  ROUNDS,
  axisInSentence,
  factLine,
  formatSigned,
  generateRounds,
  lanes,
  levelLine,
  mapAxes,
  mapHash,
  nearestParty,
  newSeed,
  parseMapHash,
  partyInSentence,
  partyPoint,
  placeLabels,
  planeX,
  planeY,
  rankByDistance,
  roundPoints,
  storedAnswers,
  streakOf,
  togglePick,
  userAxisValues,
  verdict,
} from "../mapModel.mjs";

const TEST_URL = "/citizen/vota/";
const METHOD_URL = "/citizen/vota/metodologia/";
const VIEW_TABS = [
  { id: "mapa", label: "Mapa" },
  { id: "brujula", label: "Brújula" },
  { id: "adivina", label: "Adivina" },
];
const SUBNAV = [
  { href: "/citizen/vota/explorar/", label: "Inicio" },
  { href: "/citizen/vota/mapa/", label: "Mapa", current: true },
  { href: "/citizen/vota/partidos/", label: "Partidos" },
  { href: "/citizen/vota/diputados/", label: "Diputados" },
  { href: "/citizen/vota/temas/", label: "Votaciones" },
];

function temasUrl(axis, partyId) {
  const parts = [`tema=${axis.topic_id}`, `eje=${axis.axis_id}`];
  if (partyId) parts.push(`partido=${partyId}`);
  return withBasePath(`/citizen/vota/temas/#${parts.join("&")}`);
}

// The test focuses one topic with ?p=jugar&tema=<topic label> (see readNav in VotingAidClient.js).
function testTopicUrl(topicLabel) {
  return withBasePath(topicLabel ? `${TEST_URL}?p=jugar&tema=${encodeURIComponent(topicLabel)}` : TEST_URL);
}

// ---------------------------------------------------------------------------
// Hooks

function useJson(path) {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("loading");
  useEffect(() => {
    let cancelled = false;
    fetch(withBasePath(path))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setStatus("ready");
        }
      })
      .catch(() => !cancelled && setStatus("error"));
    return () => {
      cancelled = true;
    };
  }, [path]);
  return [data, status];
}

/** The user's position per axis from the current test's answers in this browser (empty when there are none). */
function useUserValues() {
  const [values, setValues] = useState({});
  useEffect(() => {
    let raw = null;
    try {
      raw = JSON.parse(window.localStorage.getItem(CURRENT_VERSION.storageKey) || "null");
    } catch {
      raw = null;
    }
    const answers = storedAnswers(raw);
    if (!Object.keys(answers).length) return undefined;
    let cancelled = false;
    fetch(withBasePath(`/${CURRENT_VERSION.snapshot}`))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((snapshot) => {
        if (!cancelled) setValues(userAxisValues(snapshot, answers));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return values;
}

function useMedia(query) {
  const [matches, setMatches] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setMatches(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return matches;
}

/** Width of an element, kept up to date with a ResizeObserver. */
function useWidth(fallback) {
  const [width, setWidth] = useState(fallback);
  const observer = useRef(null);
  const ref = useCallback((el) => {
    observer.current?.disconnect();
    observer.current = null;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = Math.round(entries[0]?.contentRect?.width || 0);
      if (w > 0) setWidth(w);
    });
    ro.observe(el);
    observer.current = ro;
  }, []);
  return [ref, width];
}

// ---------------------------------------------------------------------------
// Page

export default function MapClient({ fallback = null }) {
  const [atlas, status] = useJson(ATLAS_PATH);
  const userValues = useUserValues();
  const isMobile = useMedia("(max-width: 767px)");
  const [state, setState] = useState({ view: "mapa", picks: DEFAULT_PICKS, x: DEFAULT_X, y: DEFAULT_Y, game: 0 });

  const axisIds = useMemo(() => (atlas ? mapAxes(atlas).map((a) => a.axis_id) : []), [atlas]);
  const partyIds = useMemo(() => (atlas?.parties || []).map((p) => p.party_id), [atlas]);

  useEffect(() => {
    const sync = () => {
      const parsed = parseMapHash(window.location.hash, { partyIds, axisIds });
      setState((s) => ({ ...s, ...parsed }));
    };
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, [partyIds, axisIds]);

  const stateRef = useRef(state);
  stateRef.current = state;
  const update = useCallback((patch) => {
    const next = { ...stateRef.current, ...patch };
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${mapHash(next)}`);
    setState(next);
  }, []);

  const maxPicks = isMobile ? MAX_PICKS_MOBILE : MAX_PICKS;
  const picks = state.picks.slice(-maxPicks);

  return (
    <>
      <nav aria-label="Explorar" className="v-subnav">
        <div className="v-subnav__inner">
          {SUBNAV.map((l) => (
            <a aria-current={l.current ? "page" : undefined} href={withBasePath(l.href)} key={l.href}>
              {l.label}
            </a>
          ))}
        </div>
      </nav>
      <main className="v-page vm">
        <nav aria-label="Vistas del mapa" className="v-chips vm-views">
          {VIEW_TABS.map((t) => (
            <a aria-current={state.view === t.id ? "page" : undefined} className="v-chip" href={mapHash({ ...state, picks, view: t.id })} key={t.id}>
              {t.label}
            </a>
          ))}
        </nav>
        {status === "loading" ? <p className="v-muted">Cargando las posiciones de los partidos…</p> : null}
        {atlas ? null : fallback}
        {status === "error" ? <p className="v-card">No se pudieron cargar los datos. Recarga la página para intentarlo de nuevo.</p> : null}
        {atlas && state.view === "mapa" ? (
          <MapView atlas={atlas} isMobile={isMobile} maxPicks={maxPicks} onPicks={(p) => update({ picks: p })} picks={picks} userValues={userValues} />
        ) : null}
        {atlas && state.view === "brujula" ? (
          <CompassView atlas={atlas} onAxes={(x, y) => update({ x, y })} userValues={userValues} x={state.x} y={state.y} />
        ) : null}
        {atlas && state.view === "adivina" ? <GuessView atlas={atlas} onSeed={(game) => update({ game })} seed={state.game} /> : null}
      </main>
    </>
  );
}

// ---------------------------------------------------------------------------
// Mapa

function MapView({ atlas, picks, maxPicks, isMobile, onPicks, userValues }) {
  const hasMe = Object.keys(userValues).length > 0;
  const [meOn, setMeOn] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const [trackRef, trackW] = useWidth(isMobile ? 260 : 720);
  const topicById = useMemo(() => Object.fromEntries((atlas.topics || []).map((t) => [t.topic_id, t])), [atlas]);
  const mainAxes = useMemo(() => mapAxes(atlas), [atlas]);
  const allAxes = useMemo(() => mapAxes(atlas, { all: true }), [atlas]);
  const axes = showAll ? allAxes : mainAxes;
  const showMe = hasMe && meOn;

  const rows = useMemo(() => {
    const px = (n) => (n / trackW) * 100;
    const charW = isMobile ? 6.1 : 6.7;
    const pillPad = isMobile ? 18 : 20;
    const lane = isMobile ? 26 : 28;
    const dotLane = isMobile ? 12 : 13;
    return axes.map((a) => {
      const toks = [];
      const dots = [];
      const missing = [];
      for (const p of atlas.parties) {
        const s = partyPoint(atlas, p.party_id, a.axis_id);
        const k = picks.indexOf(p.party_id);
        if (s === null) {
          missing.push({ p, picked: k >= 0 });
          continue;
        }
        const abbr = PARTY_ABBR[p.party_id] || p.label;
        const title = `${p.label}: ${formatSigned(s)}`;
        if (k >= 0) toks.push({ id: p.party_id, x: 50 + s / 2, abbr, title, cls: `vm-pill--pick${k + 1}`, w: px(abbr.length * charW + pillPad) });
        else dots.push({ id: p.party_id, x: 50 + s / 2, title });
      }
      const me = userValues[a.axis_id];
      const meScore = Number.isFinite(me) ? Math.round(me * 100) : null;
      if (showMe && meScore !== null) toks.push({ id: "tu", x: 50 + meScore / 2, abbr: "TÚ", title: `Tú: ${formatSigned(meScore)}`, cls: "vm-pill--me", w: px(2 * charW + pillPad) });
      const tl = toks.length ? lanes(toks, px(8)) : 0;
      const dl = lanes(dots, px(12));
      const tokH = tl * lane;
      for (const t of toks) t.top = t.lane * lane;
      for (const d of dots) d.top = tokH + 6 + d.lane * dotLane;
      const h = tokH + 6 + dl * dotLane + 2;
      const scores = atlas.parties.map((p) => {
        const s = partyPoint(atlas, p.party_id, a.axis_id);
        return `${p.label} ${s === null ? "sin datos" : formatSigned(s)}`;
      });
      const meText = meScore !== null ? `; tú ${formatSigned(meScore)}` : "";
      return {
        axis: a,
        topic: topicById[a.topic_id]?.label || "",
        toks,
        dots,
        missing,
        h,
        lineTop: tokH + 6 + 5 - 1,
        near: meScore !== null ? nearestParty(atlas, a.axis_id, me) : null,
        aria: `${a.label}, de «${a.neg_short}» (−100) a «${a.pos_short}» (+100): ${scores.join(", ")}${meText}`,
      };
    });
  }, [atlas, axes, picks, showMe, userValues, trackW, isMobile, topicById]);

  return (
    <>
      <header className="vm-intro">
        <div className="vm-intro__text">
          <h1 className="v-h1">Dónde está cada partido, tema a tema</h1>
          <p className="v-lead">
            Cada posición sale de cómo votó en el Congreso, no de lo que promete. Elige hasta {maxPicks === 3 ? "tres" : "cuatro"} partidos para
            seguirlos de un tema a otro.
          </p>
        </div>
        <a className="v-btn v-btn--primary vm-cta" href={mapHash({ view: "adivina" })}>
          <TargetIcon />
          ¿Te lo sabes? Juega a adivinar
        </a>
      </header>

      <section aria-label="Elige partidos" className="v-card vm-picker">
        <div className="vm-picker__row">
          <span className="vm-picker__label" id="vm-compare">
            Comparar
          </span>
          <div aria-labelledby="vm-compare" className="v-chips vm-picker__chips" role="group">
            {hasMe ? (
              <button aria-pressed={meOn ? "true" : "false"} className="v-chip vm-chip-me" onClick={() => setMeOn(!meOn)} type="button">
                Tú
              </button>
            ) : null}
            {atlas.parties.map((p) => {
              const k = picks.indexOf(p.party_id);
              return (
                <button
                  aria-pressed={k >= 0 ? "true" : "false"}
                  className={`v-chip${k >= 0 ? ` vm-chip--pick${k + 1}` : ""}`}
                  key={p.party_id}
                  onClick={() => onPicks(togglePick(picks, p.party_id, maxPicks))}
                  type="button"
                >
                  {p.label}
                </button>
              );
            })}
          </div>
        </div>
        <p className="v-legend">
          <span>
            <span aria-hidden="true" className="vm-key vm-key--pick" />
            Partido elegido
          </span>
          <span>
            <span aria-hidden="true" className="vm-key vm-key--dot" />
            Los demás (pasa el ratón para ver cuál)
          </span>
          {hasMe ? (
            <span>
              <span aria-hidden="true" className="vm-key vm-key--me" />
              Tú, con tus respuestas al test
            </span>
          ) : (
            <span>
              <a href={withBasePath("/citizen/vota/")}>Haz el test</a> y aparecerás tú en cada tema.
            </span>
          )}
        </p>
      </section>

      <section aria-label="Mapa por temas" className="v-card vm-map">
        <ul className="v-list">
          {rows.map((r, ri) => (
            <li className="vm-row" key={r.axis.axis_id}>
              <div className="vm-row__head">
                <span className="vm-row__topic">{r.topic}</span>
                <a className="vm-row__label" href={temasUrl(r.axis)}>
                  {r.axis.label}
                </a>
                <span className="vm-row__votes">
                  {formatCount(r.axis.votes)} votaciones{r.axis.votes < MIN_AXIS_VOTES ? " · pocas, tómalo con cautela" : ""}
                </span>
              </div>
              <div className="vm-row__chart">
                <div aria-label={r.aria} className="vm-track" ref={ri === 0 ? trackRef : undefined} role="img" style={{ height: `${r.h}px` }}>
                  <span aria-hidden="true" className="vm-track__line" style={{ top: `${r.lineTop}px` }} />
                  <span aria-hidden="true" className="vm-track__mid" />
                  {r.dots.map((d) => (
                    <span className="vm-dot" key={d.id} style={{ left: `${d.x}%`, top: `${d.top}px` }} title={d.title} />
                  ))}
                  {r.toks.map((t) => (
                    <span className={`vm-pill ${t.cls}`} key={t.id} style={{ left: `${t.x}%`, top: `${t.top}px` }} title={t.title}>
                      {t.abbr}
                    </span>
                  ))}
                </div>
                <p className="vm-poles">
                  <span>← {r.axis.neg_short}</span>
                  <span>{r.axis.pos_short} →</span>
                </p>
                {r.missing.length ? <p className="vm-row__missing">Sin datos: {r.missing.map((m) => m.p.label).join(", ")}</p> : null}
              </div>
              <div className="vm-row__near">
                {r.near ? (
                  <>
                    <span className="vm-row__near-k">Más cerca de ti</span> <strong>{r.near.party.label}</strong>
                  </>
                ) : hasMe ? (
                  <a className="vm-quiet" href={testTopicUrl(r.topic)}>
                    Responde este tema para aparecer
                  </a>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      </section>
      {allAxes.length > mainAxes.length ? (
        <button aria-expanded={showAll ? "true" : "false"} className="v-btn vm-more" onClick={() => setShowAll(!showAll)} type="button">
          {showAll ? `Ver solo los ${mainAxes.length} ejes con ${MIN_AXIS_VOTES} votaciones o más` : `Ver los ${allAxes.length} ejes`}
        </button>
      ) : null}
      <p className="v-muted vm-foot">
        Posición = hacia dónde empujaron sus votos en cada eje, de −100 a +100. En el centro: votos repartidos o abstenciones. Solo se muestran
        por defecto los ejes con {MIN_AXIS_VOTES} votaciones o más. <a href={withBasePath(METHOD_URL)}>Metodología</a>
      </p>
    </>
  );
}

function TargetIcon() {
  return (
    <svg aria-hidden="true" fill="none" height="20" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" viewBox="0 0 24 24" width="20">
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="5" />
      <circle cx="12" cy="12" r="1" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Brújula

function CompassView({ atlas, x, y, onAxes, userValues }) {
  const [planeRef, size] = useWidth(600);
  const axes = useMemo(() => mapAxes(atlas), [atlas]);
  const axisById = useMemo(() => Object.fromEntries((atlas.axes || []).map((a) => [a.axis_id, a])), [atlas]);
  const topics = atlas.topics || [];
  const topicById = useMemo(() => Object.fromEntries(topics.map((t) => [t.topic_id, t])), [topics]);
  const X = axisById[x] || axisById[DEFAULT_X];
  const Y = axisById[y] || axisById[DEFAULT_Y];
  const small = size < 480;
  const pad = small ? 20 : 28;
  const labelW = small ? 84 : 120;
  const ux = userValues[X?.axis_id];
  const uy = userValues[Y?.axis_id];
  const meShown = Number.isFinite(ux) && Number.isFinite(uy);

  const points = useMemo(() => {
    if (!X || !Y) return [];
    const pts = [];
    for (const p of atlas.parties) {
      const sx = partyPoint(atlas, p.party_id, X.axis_id);
      const sy = partyPoint(atlas, p.party_id, Y.axis_id);
      if (sx === null || sy === null) continue;
      const label = small && p.label.length > 8 ? PARTY_ABBR[p.party_id] : p.label;
      pts.push({ id: p.party_id, label, name: p.label, sx, sy, x: planeX(sx, size, pad), y: planeY(sy, size, pad) });
    }
    if (meShown) {
      const sx = Math.round(ux * 100);
      const sy = Math.round(uy * 100);
      pts.push({ id: "tu", me: true, label: "Tú", name: "Tú", sx, sy, x: planeX(sx, size, pad), y: planeY(sy, size, pad) });
    }
    return placeLabels(pts, size, { labelW, lineH: small ? 15 : 16 }).map((p) => ({ ...p, ty: Math.min(Math.max(p.ty, 8), size - 8) }));
  }, [atlas, X, Y, size, pad, small, labelW, meShown, ux, uy]);

  if (!X || !Y) return <p className="v-card">Sin datos para estos ejes.</p>;
  const missingCount = atlas.parties.length - points.filter((p) => !p.me).length;
  const ranked = meShown ? rankByDistance(atlas, X.axis_id, Y.axis_id, ux, uy).slice(0, 3) : [];
  const missing = [X, Y].filter((a) => !Number.isFinite(userValues[a.axis_id]));
  const uniqueMissing = missing.filter((a, i) => missing.findIndex((b) => b.axis_id === a.axis_id) === i);
  const aria = `Partidos según ${X.label} (horizontal, de «${X.neg_short}» a «${X.pos_short}») y ${Y.label} (vertical, de «${Y.neg_short}» abajo a «${Y.pos_short}» arriba): ${points
    .map((p) => `${p.name} ${formatSigned(p.sx)} / ${formatSigned(p.sy)}`)
    .join("; ")}`;

  const options = topics.map((t) => ({ topic: t, axes: axes.filter((a) => a.topic_id === t.topic_id) })).filter((g) => g.axes.length);
  const select = (id, value, onChange, label) => (
    <label className="vm-select" htmlFor={id}>
      {label}
      <select id={id} onChange={(e) => onChange(e.target.value)} value={value}>
        {options.map((g) => (
          <optgroup key={g.topic.topic_id} label={g.topic.label}>
            {g.axes.map((a) => (
              <option key={a.axis_id} value={a.axis_id}>
                {a.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );

  return (
    <div className="v-split">
      <section aria-labelledby="vm-compass-title" className="v-main">
        <div className="vm-head">
          <h1 className="v-h1" id="vm-compass-title">
            Brújula: cruza dos temas
          </h1>
          <p className="v-lead">Cada punto es un partido, colocado por cómo votó en los dos ejes que elijas.</p>
        </div>
        <div className="vm-selects">
          {select("vm-x", X.axis_id, (v) => onAxes(v, Y.axis_id), "Horizontal")}
          {select("vm-y", Y.axis_id, (v) => onAxes(X.axis_id, v), "Vertical")}
        </div>
        <div className="vm-compass">
          <p aria-hidden="true" className="vm-compass__y">
            <span>← {Y.neg_short}</span>
            <span>{Y.pos_short} →</span>
          </p>
          <div aria-label={aria} className="vm-plane" ref={planeRef} role="img">
            <span aria-hidden="true" className="vm-plane__v" />
            <span aria-hidden="true" className="vm-plane__h" />
            <span aria-hidden="true" className="vm-corner vm-corner--tl">
              {X.neg_short} · {Y.pos_short}
            </span>
            <span aria-hidden="true" className="vm-corner vm-corner--tr">
              {X.pos_short} · {Y.pos_short}
            </span>
            <span aria-hidden="true" className="vm-corner vm-corner--bl">
              {X.neg_short} · {Y.neg_short}
            </span>
            <span aria-hidden="true" className="vm-corner vm-corner--br">
              {X.pos_short} · {Y.neg_short}
            </span>
            {points.map((p) => (
              <span key={p.id}>
                {p.lead ? (
                  <span aria-hidden="true" className="vm-lead" style={{ left: `${p.align === "left" ? p.x + 7 : p.x - 14}px`, top: `${p.ty}px` }} />
                ) : null}
                <span
                  className={`vm-pt${p.me ? " vm-pt--me" : ""}`}
                  style={{ left: `${p.x}px`, top: `${p.y}px` }}
                  title={`${p.name}: ${formatSigned(p.sx)} / ${formatSigned(p.sy)}`}
                />
                <span
                  className={`vm-pt__label${p.me ? " vm-pt__label--me" : ""}${p.align === "right" ? " is-right" : ""}`}
                  style={{ left: `${p.tx}px`, top: `${p.ty}px`, width: `${labelW}px` }}
                >
                  {p.label}
                </span>
              </span>
            ))}
          </div>
          <span />
          <p aria-hidden="true" className="vm-compass__x">
            <span>← {X.neg_short}</span>
            <span>{X.pos_short} →</span>
          </p>
        </div>
        <p className="v-muted">
          Cada eje va de −100 a +100 según hacia dónde empujaron sus votos.
          {missingCount > 0 ? ` ${missingCount === 1 ? "Un partido no aparece" : `${missingCount} partidos no aparecen`}: sin datos en alguno de los dos ejes.` : ""}{" "}
          <a href={temasUrl(X)}>Votaciones de {axisInSentence(X.label)}</a> · <a href={temasUrl(Y)}>de {axisInSentence(Y.label)}</a>
        </p>
      </section>

      <aside className="v-side vm-side">
        {meShown ? (
          <section className="v-card vm-me-card">
            <p className="vm-me-card__k">En estos dos temas</p>
            <h2 className="v-h2">Tu vecino más cercano: {ranked[0]?.party.label || "sin datos"}</h2>
            <ol className="vm-ranked">
              {ranked.map((r, i) => (
                <li key={r.party.party_id}>
                  <span>
                    {i + 1}. {r.party.label}
                  </span>
                  <span className="v-mono">a {r.d} pts</span>
                </li>
              ))}
            </ol>
          </section>
        ) : (
          <section className="v-card vm-invite">
            <h2 className="v-h2">Aparece tú en la brújula</h2>
            <p>
              Te falta responder {uniqueMissing.map((a) => `«${a.label}»`).join(" y ")}. {uniqueMissing.length === 1 ? "Una pregunta" : "Dos preguntas"} y verás qué
              partido tienes más cerca.
            </p>
            <a className="v-btn v-btn--primary v-btn--block" href={testTopicUrl(topicById[uniqueMissing[0]?.topic_id]?.label)}>
              Responder ahora
            </a>
          </section>
        )}
        <section className="v-card v-card--sunk vm-presets">
          <h2 className="vm-presets__title">Prueba estos cruces</h2>
          {COMPASS_PRESETS.filter((s) => axisById[s.x] && axisById[s.y]).map((s) => (
            <button
              aria-pressed={s.x === X.axis_id && s.y === Y.axis_id ? "true" : "false"}
              className="vm-preset"
              key={s.label}
              onClick={() => onAxes(s.x, s.y)}
              type="button"
            >
              {s.label} <span aria-hidden="true">→</span>
            </button>
          ))}
        </section>
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Adivina

function readBest() {
  try {
    const v = Number(window.localStorage.getItem(BEST_KEY));
    return Number.isFinite(v) && v > 0 ? v : 0;
  } catch {
    return 0;
  }
}

function writeBest(v) {
  try {
    window.localStorage.setItem(BEST_KEY, String(v));
  } catch {
    // Private mode: the record just is not kept.
  }
}

function GuessView({ atlas, seed, onSeed }) {
  const axisById = useMemo(() => Object.fromEntries((atlas.axes || []).map((a) => [a.axis_id, a])), [atlas]);
  const partyById = useMemo(() => Object.fromEntries((atlas.parties || []).map((p) => [p.party_id, p])), [atlas]);
  const topicById = useMemo(() => Object.fromEntries((atlas.topics || []).map((t) => [t.topic_id, t])), [atlas]);
  const rounds = useMemo(() => (seed ? generateRounds(atlas, seed) : []), [atlas, seed]);
  const [game, setGame] = useState({ i: 0, g: 0, rev: false, h: [] });
  const [best, setBest] = useState(0);
  const [record, setRecord] = useState(false);
  const [shareMsg, setShareMsg] = useState("");
  const rangeRef = useRef(null);
  const nextRef = useRef(null);
  const focusNext = useRef(null);

  // A game without a seed in the URL gets a fresh one (shareable: the same link plays the same rounds).
  useEffect(() => {
    if (!seed) onSeed(newSeed());
  }, [seed, onSeed]);

  useEffect(() => {
    setGame({ i: 0, g: 0, rev: false, h: [] });
    setRecord(false);
    setShareMsg("");
  }, [seed]);

  useEffect(() => {
    setBest(readBest());
  }, []);

  const total = rounds.length || ROUNDS;
  const done = rounds.length > 0 && game.i >= rounds.length;
  const r = rounds[Math.min(game.i, rounds.length - 1)];
  const axis = r ? axisById[r.axis_id] : null;
  const party = r ? partyById[r.party_id] : null;
  const score = game.h.reduce((s, x) => s + x, 0);
  const streak = streakOf(game.h);
  const off = r ? Math.abs(game.g - r.real) : 0;
  const pts = r ? roundPoints(game.g, r.real) : 0;

  const check = () => {
    if (game.rev || !r) return;
    setGame({ ...game, rev: true, h: [...game.h, roundPoints(game.g, r.real)] });
    focusNext.current = "next";
  };

  const next = () => {
    if (!game.rev) return;
    const i = game.i + 1;
    if (i >= rounds.length) {
      const prev = readBest();
      if (score > prev) {
        writeBest(score);
        setBest(score);
        setRecord(true);
      } else setBest(prev);
    }
    setGame({ ...game, i, g: 0, rev: false });
    focusNext.current = "range";
  };

  useEffect(() => {
    if (focusNext.current === "next" && game.rev) nextRef.current?.focus();
    if (focusNext.current === "range" && !game.rev) (rangeRef.current || nextRef.current)?.focus();
    focusNext.current = null;
  }, [game.rev, game.i]);

  // Enter checks / goes to the next round (buttons and links keep their own Enter).
  const keys = useRef({ check, next, rev: game.rev, done });
  keys.current = { check, next, rev: game.rev, done };
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== "Enter" || e.defaultPrevented) return;
      const t = e.target;
      if (t?.closest?.("button, a, select, textarea, summary")) return;
      if (t?.tagName === "INPUT" && t.type !== "range") return;
      const k = keys.current;
      if (k.done) return;
      e.preventDefault();
      if (k.rev) k.next();
      else k.check();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const restart = () => onSeed(newSeed());

  const share = async () => {
    const url = `${window.location.origin}${window.location.pathname}${mapHash({ view: "adivina", game: seed })}`;
    const text = `He sacado ${formatCount(score)} de 1.000 adivinando dónde está cada partido según sus votos en el Congreso. ¿Me superas con las mismas ${total} rondas?`;
    try {
      if (navigator.share) {
        await navigator.share({ title: "Adivina dónde está cada partido", text, url });
        return;
      }
      await navigator.clipboard.writeText(`${text} ${url}`);
      setShareMsg("Enlace copiado. Pégalo donde quieras.");
    } catch (err) {
      if (err?.name === "AbortError") return;
      setShareMsg(`No se pudo copiar. Este es el enlace: ${url}`);
    }
  };

  if (!rounds.length) return <p className="v-muted">Preparando la partida…</p>;

  const pipClass = (n) => {
    if (n < game.h.length) return game.h[n] >= 100 - DIANA ? "is-diana" : game.h[n] >= 50 ? "is-near" : "is-far";
    return n === game.i ? "is-now" : "";
  };

  return (
    <div className="v-split vm-game">
      <section aria-label="Juego" className="v-main">
        <div className="vm-game__bar">
          <p className="vm-game__round">{done ? "Resultado" : `Ronda ${game.i + 1} de ${total}`}</p>
          <p aria-live="polite" className="vm-game__score">
            <span className="vm-score">{formatCount(score)} pts</span>
            <span className="vm-streak">Racha {streak}</span>
          </p>
        </div>

        {!done && r && axis && party ? (
          <div className="v-card vm-round">
            <div className="vm-round__q">
              <p className="v-eyebrow">{topicById[axis.topic_id]?.label || ""}</p>
              <h1 className="vm-round__title">
                ¿Dónde está <strong>{partyInSentence(party)}</strong> en {axisInSentence(axis.label)}?
              </h1>
              <p className="v-muted">
                Mueve el marcador según cómo crees que ha votado. Luego lo comprobamos con {formatCount(r.votes)} votaciones reales.
              </p>
            </div>

            <div className="vm-guess">
              <div className="vm-guess__track">
                <span aria-hidden="true" className="vm-guess__line" />
                <span aria-hidden="true" className="vm-guess__mid" />
                {game.rev ? (
                  <>
                    <span
                      aria-hidden="true"
                      className="vm-guess__gap"
                      style={{ left: `${50 + Math.min(game.g, r.real) / 2}%`, width: `${off / 2}%` }}
                    />
                    <span aria-hidden="true" className="vm-guess__tick vm-guess__tick--real" style={{ left: `${50 + r.real / 2}%` }} />
                    <span className="vm-marker vm-marker--real" style={{ left: `${50 + r.real / 2}%`, transform: `translateX(-${50 + r.real / 2}%)` }}>
                      {PARTY_ABBR[party.party_id]} {formatSigned(r.real)}
                    </span>
                  </>
                ) : null}
                <span aria-hidden="true" className="vm-guess__tick vm-guess__tick--me" style={{ left: `${50 + game.g / 2}%` }} />
                <span
                  aria-hidden="true"
                  className="vm-marker vm-marker--me"
                  style={{ left: `${50 + game.g / 2}%`, transform: `translateX(-${50 + game.g / 2}%)` }}
                >
                  TÚ {formatSigned(game.g)}
                </span>
              </div>
              <label className="v-sr" htmlFor="vm-guess">
                Tu apuesta para {party.label}, de «{axis.neg_short}» (−100) a «{axis.pos_short}» (+100)
              </label>
              <input
                aria-valuetext={`${formatSigned(game.g)}: ${game.g < 0 ? axis.neg_short : game.g > 0 ? axis.pos_short : "centro"}`}
                className="vm-range"
                disabled={game.rev}
                id="vm-guess"
                max="100"
                min="-100"
                onChange={(e) => setGame((s) => (s.rev ? s : { ...s, g: Number(e.target.value) }))}
                ref={rangeRef}
                step="5"
                type="range"
                value={game.g}
              />
              <p className="vm-guess__poles">
                <span>← {axis.neg_short}</span>
                <span>{axis.pos_short} →</span>
              </p>
            </div>

            {game.rev ? (
              <div aria-live="polite" className="vm-result">
                <div className="vm-result__head">
                  <h2 className="vm-result__verdict">{verdict(off)}</h2>
                  <p className="vm-result__pts">+{pts} pts</p>
                </div>
                <p className="vm-result__text">
                  {party.label} está en <strong>{formatSigned(r.real)}</strong> y tú dijiste <strong>{formatSigned(game.g)}</strong>. {factLine(r.real, axis)}
                </p>
                <div className="vm-result__actions">
                  <button className="v-btn v-btn--primary" onClick={next} ref={nextRef} type="button">
                    {game.i + 1 >= total ? "Ver resultado" : "Siguiente ronda"}
                  </button>
                  <a className="v-btn" href={temasUrl(axis, party.party_id)}>
                    Ver sus votaciones
                  </a>
                </div>
              </div>
            ) : (
              <button className="v-btn v-btn--primary v-btn--block vm-check" onClick={check} type="button">
                Comprobar
              </button>
            )}
            <div aria-hidden="true" className="vm-pips">
              {rounds.map((_, n) => (
                <span className={pipClass(n)} key={n} />
              ))}
            </div>
          </div>
        ) : null}

        {done ? (
          <div className="v-card vm-round vm-final">
            <p className="v-kicker">Partida terminada</p>
            <h1 className="v-h1">{formatCount(score)} de 1.000 puntos</h1>
            <p className="v-lead">{levelLine(score)}</p>
            <p className="v-muted">
              {record ? "¡Nuevo récord en este navegador!" : best ? `Tu mejor partida en este navegador: ${formatCount(best)} puntos.` : ""}
            </p>
            <div className="vm-result__actions">
              <button className="v-btn v-btn--primary" onClick={restart} type="button">
                Jugar otra vez
              </button>
              <button className="v-btn" onClick={share} type="button">
                Retar a alguien
              </button>
              <a className="v-btn" href={withBasePath(TEST_URL)}>
                Ahora, el test
              </a>
            </div>
            {shareMsg ? (
              <p aria-live="polite" className="v-muted vm-share-msg">
                {shareMsg}
              </p>
            ) : null}
          </div>
        ) : null}
      </section>

      <aside className="v-side">
        <section aria-labelledby="vm-rounds" className="v-card vm-log">
          <h2 className="vm-side-title" id="vm-rounds">
            Tus rondas
          </h2>
          <ol className="vm-log__list">
            {rounds.map((x, n) => {
              const played = n < game.h.length;
              const a = axisById[x.axis_id];
              return (
                <li className={played || n === game.i ? "is-on" : ""} key={`${x.party_id}-${x.axis_id}`}>
                  <span className="v-mono">{n + 1}</span>
                  <span className="vm-log__label">
                    {PARTY_ABBR[x.party_id]} · {axisInSentence(a?.label)}
                  </span>
                  <span className={`v-mono vm-log__pts${played && game.h[n] >= 100 - DIANA ? " is-diana" : ""}`}>
                    {played ? `+${game.h[n]}` : n === game.i && !done ? "…" : ""}
                  </span>
                </li>
              );
            })}
          </ol>
        </section>
        <section className="v-card v-card--sunk vm-rules">
          <h2 className="vm-side-title">Cómo se puntúa</h2>
          <p>100 puntos menos lo que te alejes. A {DIANA} o menos: diana. Cada diana seguida alarga tu racha.</p>
          <p>Las posiciones salen de votos reales del Congreso, así que algunas sorprenden.</p>
          {best ? <p>Tu mejor partida: {formatCount(best)} de 1.000.</p> : null}
        </section>
      </aside>
    </div>
  );
}
