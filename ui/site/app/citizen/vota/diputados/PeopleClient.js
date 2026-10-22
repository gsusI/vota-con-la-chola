"use client";

import { useEffect, useMemo, useState } from "react";
import "../explore.css";
import { Crumbs, ExploreNav, LoadState, PersonRow, ROUTES, VotePill, href, partyHref, useHashState, useJson, voteHref } from "../explorar/ExploreClient";
import {
  XV,
  axisPosition,
  codeClass,
  initials,
  legislaturesText,
  mainLeg,
  percent1,
  personDissents,
  personLegSummary,
  personPartyLabel,
  personVoteIndices,
  personVsPartyAxes,
  totalsText,
} from "../exploreModel.mjs";
import {
  ATLAS_PATH,
  LEG_LABELS,
  PEOPLE_PATH,
  classifiedById,
  filterPeople,
  formatCount,
  formatDate,
  groupLabel,
  personChoice,
  pushOf,
  writeHash,
} from "../voteAtlasModel.mjs";

const PAGE = 10;
const LIST_PAGE = 60;
const AXES_SHOWN = 6;
const SORTS = {
  name: { label: "Nombre", fn: (a, b) => a.name.localeCompare(b.name, "es") },
  loyalty: { label: "Más veces contra su partido", fn: (a, b) => (a.loyalty ?? 2) - (b.loyalty ?? 2) },
  participation: { label: "Menos participación", fn: (a, b) => (a.participation ?? 2) - (b.participation ?? 2) },
};

/** Everything a vote row needs, from the people file plus the atlas when the vote is classified. */
function voteInfo(people, atlas, classified, index) {
  const [id, , date, kind, titleRef, subgroup, leg] = people.votes[index];
  const v = classified[id];
  const title = Number.isInteger(titleRef) ? people.titles?.[titleRef] || "" : String(titleRef || "");
  const kindLabel = atlas.kind_labels?.[kind] || kind;
  const result = v ? `${v.approved ? "Aprobada" : "Rechazada"} · ${totalsText(v.totals)}` : "";
  return { id, date, kindLabel, title: v?.summary_yes || title, official: title, subgroup, leg: String(leg), v, result };
}

function DissentRow({ info, own, party, partyName }) {
  return (
    <li>
      <a className="x-drow" href={voteHref(info.id)}>
        <span className="x-drow__date">{formatDate(info.date)}</span>
        <span className="x-drow__text">
          <span className="x-drow__title">{info.title}</span>
          <span className="x-drow__sub">
            {info.kindLabel}
            {info.result ? ` · ${info.result}` : ""}
            {info.leg !== XV ? ` · ${LEG_LABELS[info.leg] || info.leg} legislatura` : ""}
          </span>
        </span>
        <span className="x-pills">
          <span>
            <span>Votó</span> <VotePill code={own} />
          </span>
          <span>
            <span className="x-pills__who--party">{partyName}</span> <VotePill code={party} />
          </span>
        </span>
      </a>
    </li>
  );
}

function OwnRow({ info, own, axisNote }) {
  return (
    <li>
      <a className="x-drow x-drow--own" href={voteHref(info.id)}>
        <span className="x-drow__date">{formatDate(info.date)}</span>
        <span className="x-drow__text">
          <span className="x-drow__title">{info.title}</span>
          <span className="x-drow__sub">
            {info.kindLabel}
            {info.result ? ` · ${info.result}` : ""}
            {info.leg !== XV ? ` · ${LEG_LABELS[info.leg] || info.leg} legislatura` : ""}
            {axisNote ? ` · ${axisNote}` : ""}
          </span>
        </span>
        <span>
          <span className="v-sr">Votó </span>
          <VotePill code={own} />
        </span>
      </a>
    </li>
  );
}

function MoreButton({ total, shown, onMore }) {
  if (total <= shown) return null;
  return (
    <button className="v-btn" onClick={onMore} type="button">
      Ver más ({formatCount(total - shown)})
    </button>
  );
}

function PersonView({ person, people, atlas, partiesById }) {
  const classified = useMemo(() => classifiedById(atlas), [atlas]);
  const leg = mainLeg(person);
  const summary = useMemo(() => personLegSummary(people, person, leg), [people, person, leg]);
  const other = useMemo(
    () => (person.legislatures || []).map(String).filter((lg) => lg !== leg).map((lg) => personLegSummary(people, person, lg)),
    [people, person, leg],
  );
  const dissents = useMemo(() => personDissents(person), [person]);
  const allVotes = useMemo(() => personVoteIndices(person), [person]);
  const axes = useMemo(() => personVsPartyAxes(atlas, person), [atlas, person]);
  const indexById = useMemo(() => Object.fromEntries(people.votes.map((v, i) => [v[0], i])), [people]);
  const [shownDissent, setShownDissent] = useState(4);
  const [shownLatest, setShownLatest] = useState(PAGE);
  const [allAxes, setAllAxes] = useState(false);
  const [axisFilter, setAxisFilter] = useState("");
  const [shownAxis, setShownAxis] = useState(PAGE);
  const axisVotes = useMemo(() => {
    if (!axisFilter) return [];
    return (atlas.votes || [])
      .filter((v) => (v.axes || []).some((a) => a[0] === axisFilter))
      .map((v) => indexById[v.id])
      .filter((i) => Number.isInteger(i) && personChoice(person, i) !== ".")
      .sort((a, b) => b - a);
  }, [atlas, axisFilter, indexById, person]);
  const axisById = useMemo(() => Object.fromEntries((atlas.axes || []).map((a) => [a.axis_id, a])), [atlas]);

  const partyName = person.party_id ? partiesById[person.party_id]?.label || person.party_id : null;
  const unitName = leg === XV && partyName ? partyName : "su grupo";
  const legName = LEG_LABELS[leg] || leg;
  const groups = [...new Set((person.groups || []).map(groupLabel))];
  const { counts, seated } = summary;
  const pct = (x) => (seated ? (x / seated) * 100 : 0);
  const mixAria = `${counts.S} sí, ${counts.N} no, ${counts.A} abstenciones, ${counts["-"]} no votó`;

  function pickAxis(axisId) {
    setAxisFilter(axisId);
    setShownAxis(PAGE);
    requestAnimationFrame(() => document.getElementById("por-eje")?.scrollIntoView({ block: "start" }));
  }

  return (
    <>
      <Crumbs items={[{ label: "Explorar", href: href(ROUTES.hub) }, { label: "Diputados", href: "#" }, { label: person.name }]} />
      <div className="x-person-head">
        <span aria-hidden="true" className="x-avatar x-avatar--lg">
          {initials(person.name)}
        </span>
        <div className="x-head__text">
          <h1 className="v-h1">{person.name}</h1>
          <p className="v-lead">
            {person.party_id ? <a href={partyHref(person.party_id)}>{partyName}</a> : personPartyLabel(person, partiesById)}
            {person.party_history?.length > 1 ? (
              <span className="v-muted"> (antes: {person.party_history.slice(0, -1).map((p) => partiesById[p]?.label || p).join(", ")})</span>
            ) : null}
            {groups.length ? ` · ${groups.join(", ")}` : ""} · diputado/a en {legislaturesText(person)}
          </p>
        </div>
      </div>

      <ul aria-label={`Resumen de la ${legName} legislatura`} className="x-tiles">
        <li className="x-tile">
          <span className="x-tile__n">{formatCount(seated)}</span>
          <span className="x-tile__l">votaciones como diputado/a en la {legName} legislatura</span>
        </li>
        <li className="x-tile">
          <span className="x-tile__n">{percent1(summary.participation)}</span>
          <span className="x-tile__l">de ellas en las que votó</span>
        </li>
        <li className="x-tile">
          <span className="x-tile__n">{Number.isFinite(summary.loyalty) ? percent1(summary.loyalty, { floor: true }) : "sin datos"}</span>
          <span className="x-tile__l">igual que la mayoría de su {leg === XV ? "partido" : "grupo"}</span>
        </li>
        <li className="x-tile">
          <span className="x-tile__n">{formatCount(summary.rebels)}</span>
          <span className="x-tile__l">veces votó distinto a su {leg === XV ? "partido" : "grupo"}</span>
        </li>
      </ul>
      {other.length ? (
        <p className="v-muted">
          {other.map((o) => (
            <span key={o.leg}>
              {LEG_LABELS[o.leg] || o.leg} legislatura (desde oct. 2022): {formatCount(o.seated)} votaciones, votó en el {percent1(o.participation)}
              {Number.isFinite(o.loyalty) ? `, ${percent1(o.loyalty, { floor: true })} igual que su grupo` : ""}, {formatCount(o.rebels)} veces distinto.{" "}
            </span>
          ))}
        </p>
      ) : null}

      <div className="v-split">
        <div className="v-main">
          <section aria-labelledby="x-mix" className="v-card">
            <h2 className="x-card-title" id="x-mix">
              Qué votó en estas {formatCount(seated)} votaciones
            </h2>
            {seated ? (
              <>
                <span aria-label={mixAria} className="v-stack x-stack-lg" role="img" style={{ marginTop: 14 }}>
                  <span className="x-c-S" style={{ width: `${pct(counts.S)}%` }} />
                  <span className="x-c-N" style={{ width: `${pct(counts.N)}%` }} />
                  <span className="x-c-A" style={{ width: `${pct(counts.A)}%` }} />
                  <span className="x-c-absent" style={{ width: `${pct(counts["-"])}%` }} />
                </span>
                <p className="v-legend x-legend--counts">
                  {[
                    ["S", "Sí"],
                    ["N", "No"],
                    ["A", "Abstención"],
                    ["-", "No votó"],
                  ].map(([c, label]) => (
                    <span key={c}>
                      <span className={`v-swatch ${codeClass(c)}`} />
                      {label} <span className="v-mono">{formatCount(counts[c])}</span>
                    </span>
                  ))}
                </p>
              </>
            ) : (
              <p className="v-muted">Sin datos.</p>
            )}
          </section>

          <section aria-labelledby="x-distinto" className="v-card">
            <div className="x-sechead">
              <h2 className="v-h2" id="x-distinto">
                Cuando votó distinto a {person.party_id ? partyName : "su grupo"}
              </h2>
              {dissents.length ? <span className="v-muted">{formatCount(dissents.length)} en total</span> : null}
            </div>
            {dissents.length ? (
              <>
                <ul className="x-rows">
                  {dissents.slice(0, shownDissent).map(({ index, own, party }) => {
                    const info = voteInfo(people, atlas, classified, index);
                    return <DissentRow info={info} key={index} own={own} party={party} partyName={info.leg === XV && partyName ? partyName : "Su grupo"} />;
                  })}
                </ul>
                <div className="x-cardfoot">
                  <MoreButton onMore={() => setShownDissent(shownDissent + PAGE)} shown={shownDissent} total={dissents.length} />
                  <p className="v-muted">Incluye enmiendas y trámites. Un voto distinto puede ser un error al votar (a veces se corrige en una votación repetida).</p>
                </div>
              </>
            ) : (
              <p className="v-muted">Siempre votó igual que la mayoría de {unitName === "su grupo" ? "su grupo" : `su partido (${unitName})`}.</p>
            )}
          </section>

          <section aria-labelledby="x-ultimas" className="v-card">
            <h2 className="v-h2" id="x-ultimas">
              Últimas votaciones
            </h2>
            {allVotes.length ? (
              <>
                <ul className="x-rows">
                  {allVotes.slice(0, shownLatest).map((i) => (
                    <OwnRow info={voteInfo(people, atlas, classified, i)} key={i} own={personChoice(person, i)} />
                  ))}
                </ul>
                <div className="x-cardfoot">
                  <MoreButton onMore={() => setShownLatest(shownLatest + 20)} shown={shownLatest} total={allVotes.length} />
                </div>
              </>
            ) : (
              <p className="v-muted">Sin votaciones.</p>
            )}
          </section>

          <section aria-labelledby="por-eje" className="v-card">
            <h2 className="v-h2" id="por-eje">
              Sus votaciones por tema
            </h2>
            <label className="x-select" style={{ marginTop: 12 }}>
              Eje
              <select
                onChange={(e) => {
                  setAxisFilter(e.target.value);
                  setShownAxis(PAGE);
                }}
                value={axisFilter}
              >
                <option value="">Elige un eje…</option>
                {(atlas.axes || [])
                  .filter((a) => a.votes > 0)
                  .map((a) => (
                    <option key={a.axis_id} value={a.axis_id}>
                      {a.label}
                    </option>
                  ))}
              </select>
            </label>
            {axisFilter ? (
              axisVotes.length ? (
                <>
                  <ul className="x-rows">
                    {axisVotes.slice(0, shownAxis).map((i) => {
                      const info = voteInfo(people, atlas, classified, i);
                      const own = personChoice(person, i);
                      const hit = (info.v?.axes || []).find((a) => a[0] === axisFilter);
                      const push = hit ? pushOf(own, hit[1]) : "none";
                      const axis = axisById[axisFilter];
                      const note = axis && push !== "none" ? `empujó hacia «${push === "pos" ? axis.pos_short : axis.neg_short}»` : "";
                      return <OwnRow axisNote={note} info={info} key={i} own={own} />;
                    })}
                  </ul>
                  <div className="x-cardfoot">
                    <MoreButton onMore={() => setShownAxis(shownAxis + PAGE)} shown={shownAxis} total={axisVotes.length} />
                  </div>
                </>
              ) : (
                <p className="v-muted">No votó en ninguna votación de este eje.</p>
              )
            ) : null}
          </section>
        </div>

        <aside aria-labelledby="x-pos" className="v-side v-card">
          <h2 className="v-h2" id="x-pos">
            Sus posiciones y las de su partido
          </h2>
          {axes.length ? (
            <>
              <p className="v-legend x-legend" style={{ margin: "6px 0 4px" }}>
                <span>
                  <span className="x-dot" />
                  {person.name.split(" ")[0]}
                </span>
                {person.party_id ? (
                  <span>
                    <span className="x-ring" />
                    {partyName}
                  </span>
                ) : null}
              </p>
              <ul className="x-pos">
                {(allAxes ? axes : axes.slice(0, AXES_SHOWN)).map((r) => {
                  const me = axisPosition(r.score);
                  const pt = axisPosition(r.partyScore);
                  const aria = `${r.axis.label}: ${Math.round(r.score * 100)}${
                    r.partyScore !== null ? `, su partido ${Math.round(r.partyScore * 100)}` : ""
                  } (de −100 «${r.axis.neg_short}» a +100 «${r.axis.pos_short}»), ${r.n} votaciones`;
                  return (
                    <li key={r.axis.axis_id}>
                      <button className="v-link-btn x-pos__label" onClick={() => pickAxis(r.axis.axis_id)} type="button">
                        {r.axis.label}
                      </button>
                      <span aria-label={aria} className="x-dotline" role="img">
                        <span aria-hidden="true" className="x-dotline__track" />
                        <span aria-hidden="true" className="x-dotline__zero" />
                        {pt !== null ? <span className="x-ring" style={{ left: `${pt}%` }} /> : null}
                        {me !== null ? <span className="x-dot" style={{ left: `${me}%` }} /> : null}
                      </span>
                      <span className="x-poles x-poles--small">
                        <span>← {r.axis.neg_short}</span>
                        <span className="x-poles__n">{r.n} vot.</span>
                        <span>{r.axis.pos_short} →</span>
                      </span>
                    </li>
                  );
                })}
              </ul>
              {axes.length > AXES_SHOWN ? (
                <button aria-pressed={allAxes} className="v-link-btn x-toggle" onClick={() => setAllAxes(!allAxes)} type="button">
                  {allAxes ? "Ver menos ejes" : `Ver los ${axes.length} ejes`}
                </button>
              ) : null}
              <p className="v-muted">
                Calculado con sus votos en las votaciones clasificadas por tema, como el de los partidos. Toca un eje para ver sus votaciones.
              </p>
            </>
          ) : (
            <p className="v-muted">Sin datos: no tiene suficientes votaciones clasificadas para calcular una posición.</p>
          )}
        </aside>
      </div>
    </>
  );
}

export default function PeopleClient({ fallback = null }) {
  const [people, peopleStatus] = useJson(PEOPLE_PATH);
  const [atlas, atlasStatus] = useJson(ATLAS_PATH);
  const hash = useHashState();
  const [query, setQuery] = useState("");
  const [partyId, setPartyId] = useState("");
  const [sort, setSort] = useState("name");
  const [shown, setShown] = useState(LIST_PAGE);
  const personId = hash?.p || "";

  // List filters come from the hash (#partido=psoe&orden=loyalty) so party pages can link here.
  useEffect(() => {
    if (!hash || hash.p) return;
    setPartyId(hash.partido || "");
    setSort(SORTS[hash.orden] ? hash.orden : "name");
    setShown(LIST_PAGE);
  }, [hash]);

  function setFilters(next) {
    const state = { partido: partyId, orden: sort === "name" ? "" : sort, ...next };
    window.history.replaceState(null, "", `${window.location.pathname}${writeHash(state) || window.location.search}`);
  }

  const partiesById = useMemo(() => Object.fromEntries((people?.parties || []).map((p) => [p.party_id, p])), [people]);
  const list = useMemo(() => {
    const earlierOnly = partyId === "_earlier";
    const found = filterPeople(people?.people, { query, partyId: earlierOnly ? "" : partyId });
    return (earlierOnly ? found.filter((p) => !(p.legislatures || []).includes(XV)) : found).sort(SORTS[sort].fn);
  }, [people, query, partyId, sort]);
  const person = personId ? (people?.people || []).find((p) => p.id === personId) : null;
  const status = peopleStatus === "error" || atlasStatus === "error" ? "error" : people && atlas ? "ready" : "loading";

  return (
    <>
      <ExploreNav current="diputados" />
      <main className="v-page x-people-page">
        <LoadState status={status} what="los diputados" />
        {status === "ready" && hash ? null : fallback}
        {status === "ready" && hash && person ? <PersonView atlas={atlas} key={person.id} partiesById={partiesById} people={people} person={person} /> : null}
        {status === "ready" && hash && !person ? (
          <>
            <Crumbs items={[{ label: "Explorar", href: href(ROUTES.hub) }, { label: "Diputados" }]} />
            {personId ? (
              <p className="x-notice" role="alert">
                No encontramos a esa persona en los datos. Búscala en la lista.
              </p>
            ) : null}
            <div className="x-head__text">
              <h1 className="v-h1">Qué ha votado tu diputado/a</h1>
              <p className="v-lead">
                Cualquier diputado o diputada del Congreso desde octubre de 2022 (final de la XIV legislatura y toda la XV): cuántas veces votó
                distinto de su partido, hacia dónde empujó en cada tema y todas sus votaciones, enlazadas a la fuente oficial.
              </p>
            </div>
            <div className="x-controls">
              <label className="x-search__box">
                <span className="v-sr">Buscar por nombre</span>
                <svg aria-hidden="true" fill="none" height="20" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" viewBox="0 0 24 24" width="20">
                  <circle cx="11" cy="11" r="7" />
                  <path d="M20 20l-4-4" />
                </svg>
                <input
                  autoComplete="off"
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setShown(LIST_PAGE);
                  }}
                  placeholder="Buscar por nombre…"
                  type="search"
                  value={query}
                />
              </label>
              <div className="v-chips">
                <label className="x-select">
                  Partido
                  <select
                    onChange={(e) => {
                      setPartyId(e.target.value);
                      setShown(LIST_PAGE);
                      setFilters({ partido: e.target.value });
                    }}
                    value={partyId}
                  >
                    <option value="">Todos</option>
                    <option value="_earlier">Solo en la XIV (ya no son diputados)</option>
                    {(people.parties || []).map((p) => (
                      <option key={p.party_id} value={p.party_id}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="x-select">
                  Ordenar
                  <select
                    onChange={(e) => {
                      setSort(e.target.value);
                      setFilters({ orden: e.target.value === "name" ? "" : e.target.value });
                    }}
                    value={sort}
                  >
                    {Object.entries(SORTS).map(([k, s]) => (
                      <option key={k} value={k}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
            <p aria-live="polite" className="v-muted">
              {formatCount(list.length)} personas
              {partyId && partiesById[partyId] ? (
                <>
                  {" "}
                  de {partiesById[partyId].label} · <a href={partyHref(partyId)}>cómo vota {partiesById[partyId].label}</a>
                </>
              ) : null}
            </p>
            {list.length ? (
              <ul className="v-card v-list x-people">
                {list.slice(0, shown).map((p) => (
                  <PersonRow key={p.id} partiesById={partiesById} person={p} summary={{ participation: p.participation, loyalty: p.loyalty, rounded: true }} />
                ))}
              </ul>
            ) : (
              <p className="v-muted">Nadie coincide con esa búsqueda.</p>
            )}
            <MoreButton onMore={() => setShown(shown + LIST_PAGE)} shown={shown} total={list.length} />
            <p className="v-muted">
              «Con su partido»: votaciones en que votó igual que la mayoría de su partido o grupo (Sí, No o Abstención), en todas las legislaturas
              con datos.
            </p>
          </>
        ) : null}
      </main>
    </>
  );
}
