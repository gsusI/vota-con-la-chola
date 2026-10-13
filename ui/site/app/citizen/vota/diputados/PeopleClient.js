"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { withBasePath } from "../../../path-utils.mjs";
import { DirectionBar, PoleLegend } from "../temas/VoteAtlasClient";
import {
  ATLAS_PATH,
  CHOICE_LABELS,
  PEOPLE_PATH,
  classifiedById,
  directionText,
  filterPeople,
  formatCount,
  formatDate,
  groupLabel,
  groupShortLabel,
  indexAtlas,
  LEG_LABELS,
  officialVoteUrl,
  percent,
  personAxisRows,
  personChoice,
  pushOf,
  readHash,
  writeHash,
} from "../voteAtlasModel.mjs";

const PAGE = 20;

// Loyalty is usually 99-100 %: one decimal keeps the differences visible.
function percent1(value) {
  return Number.isFinite(value) ? `${(Math.floor(value * 1000) / 10).toLocaleString("es-ES")} %` : "—";
}
const SORTS = {
  name: { label: "Nombre", fn: (a, b) => a.name.localeCompare(b.name, "es") },
  loyalty: { label: "Más veces contra su partido", fn: (a, b) => (a.loyalty ?? 2) - (b.loyalty ?? 2) },
  participation: { label: "Menos participación", fn: (a, b) => (a.participation ?? 2) - (b.participation ?? 2) },
};

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

function partyLabel(person, partiesById) {
  if (person.party_id) return partiesById[person.party_id]?.label || person.party_id;
  const onlyEarlier = (person.legislatures || []).every((lg) => lg !== "15");
  if (onlyEarlier) return `${groupShortLabel(person.last_group)} (${(person.legislatures || []).map((lg) => LEG_LABELS[lg] || lg).join(", ")})`;
  return person.last_group === "GMx" ? "Grupo Mixto (sin partido de papeleta)" : groupLabel(person.last_group);
}

function VoteLine({ people, atlas, index, choice, partyCode, classified, axisFilter }) {
  const [id, path, date, kind, titleRef, subgroup, leg] = people.votes[index];
  const title = Number.isInteger(titleRef) ? people.titles?.[titleRef] || "" : titleRef;
  const v = classified[id];
  const { axisById } = indexAtlas(atlas);
  const axes = (v?.axes || []).filter((a) => !axisFilter || a[0] === axisFilter);
  return (
    <li className="atlasVote">
      <p className="atlasVote__meta">
        {formatDate(date)} · {atlas.kind_labels?.[kind] || kind}
        {leg && leg !== "15" ? ` · ${LEG_LABELS[leg] || leg} legislatura` : ""}
      </p>
      {v?.summary_yes ? <p className="atlasVote__summary">{v.summary_yes}</p> : null}
      <p className="atlasVote__title">
        {title}
        {subgroup ? <span className="votingAidMuted"> — {subgroup}</span> : null}
      </p>
      <p className="atlasVote__push">
        Votó <strong>{CHOICE_LABELS[choice] || choice}</strong>
        {partyCode ? (
          <>
            ; {leg && leg !== "15" ? "su grupo" : "su partido"}, <strong>{CHOICE_LABELS[partyCode] || partyCode}</strong>
          </>
        ) : null}
        {axes.map(([axisId, sign]) => {
          const push = pushOf(choice, sign);
          const axis = axisById[axisId];
          if (!axis || push === "none") return null;
          return (
            <span className="votingAidMuted" key={axisId}>
              {" "}
              · empujó hacia «{push === "pos" ? axis.pos_short : axis.neg_short}» ({axis.label})
            </span>
          );
        })}
      </p>
      <p className="atlasVote__links">
        <a href={officialVoteUrl(path)} rel="noopener noreferrer" target="_blank">
          Votación oficial
        </a>
        {v?.text_url ? (
          <>
            {" · "}
            <a href={v.text_url} rel="noopener noreferrer" target="_blank">
              Texto votado (BOCG)
            </a>
          </>
        ) : null}
      </p>
    </li>
  );
}

function PersonView({ person, people, atlas, partiesById, onBack }) {
  const classified = useMemo(() => classifiedById(atlas), [atlas]);
  const rows = useMemo(() => personAxisRows(atlas, person), [atlas, person]);
  const { axisById } = useMemo(() => indexAtlas(atlas), [atlas]);
  const [shownRebels, setShownRebels] = useState(PAGE);
  const [axisFilter, setAxisFilter] = useState("");
  const [shownAxis, setShownAxis] = useState(PAGE);
  const indexById = useMemo(() => Object.fromEntries(people.votes.map((v, i) => [v[0], i])), [people]);
  const axisVotes = useMemo(() => {
    if (!axisFilter) return [];
    return (atlas.votes || [])
      .filter((v) => (v.axes || []).some((a) => a[0] === axisFilter))
      .map((v) => indexById[v.id])
      .filter((i) => Number.isInteger(i) && personChoice(person, i) !== ".")
      .sort((a, b) => b - a);
  }, [atlas, axisFilter, indexById, person]);
  const rebels = [...(person.rebels || [])].reverse();
  const first = people.votes[person.first]?.[2];
  const last = people.votes[person.first + String(person.votes || "").length - 1]?.[2];
  const party = partyLabel(person, partiesById);

  return (
    <section className="atlasPerson">
      <button className="votingAidLinkButton" onClick={onBack} type="button">
        ← Todos los diputados
      </button>
      <h2 className="atlasPerson__name">{person.name}</h2>
      <p className="votingAidLead">
        {party}
        {person.party_history?.length > 1 ? (
          <span className="votingAidMuted"> (antes: {person.party_history.slice(0, -1).map((p) => partiesById[p]?.label || p).join(", ")})</span>
        ) : null}
        <span className="votingAidMuted">
          {" "}
          · votaciones del {formatDate(first)} al {formatDate(last)}
        </span>
      </p>
      <p className="votingAidMuted">
        {(person.legislatures || []).map((lg, i) => (
          <span key={lg}>
            {i ? " · " : ""}
            {LEG_LABELS[lg] || lg} legislatura: {(person.groups_by_leg?.[lg] || []).map(groupLabel).join(", ")}
            {person.loyalty_by_leg?.[lg] ? ` (${percent1(person.loyalty_by_leg[lg][0])} igual que su ${lg === "15" ? "partido" : "grupo"})` : ""}
          </span>
        ))}
      </p>
      <ul className="votingAidFacts atlasFacts atlasFacts--grid">
        <li>
          <strong>{percent(person.participation)}</strong>
          <span className="votingAidMuted"> de participación ({formatCount(person.seated)} votaciones)</span>
        </li>
        <li>
          <strong>{percent1(person.loyalty)}</strong>
          <span className="votingAidMuted">
            {" "}
            {(person.legislatures || []).includes("15") ? (person.legislatures.length > 1 ? "igual que su partido o grupo" : "igual que su partido") : "igual que su grupo"}
            {!person.party_id && person.party_history?.length
              ? ` (mientras estuvo en ${person.party_history.map((p) => partiesById[p]?.label || p).join(", ")})`
              : ""}{" "}
            ({formatCount(person.loyalty_votes || 0)} votaciones)
          </span>
        </li>
        <li>
          <strong>{formatCount((person.rebels || []).length)}</strong>
          <span className="votingAidMuted"> votos distintos de su {(person.legislatures || []).includes("15") ? "partido" : "grupo"}</span>
        </li>
      </ul>

      <h3>Hacia dónde ha empujado, tema a tema</h3>
      {rows.length ? (
        <>
          <p className="votingAidMuted">
            La barra es su dirección personal; la marca vertical, la de su partido. Arriba, los ejes donde más se separa de su partido.
          </p>
          <div className="atlasPerson__axes">
            {rows.map((r) => (
              <div className="atlasPerson__axis" key={r.axis.axis_id}>
                <p className="atlasPerson__axisTitle">
                  <button className="votingAidLinkButton" onClick={() => setAxisFilter(r.axis.axis_id)} type="button">
                    {r.axis.label}
                  </button>
                </p>
                <PoleLegend axis={r.axis} />
                <DirectionBar label="" marker={r.partyScore} score={r.score} sub={`${directionText(r.axis, r.score)} · ${r.n} vot.`} />
              </div>
            ))}
          </div>
        </>
      ) : (
        <p className="votingAidMuted">No tiene suficientes votaciones clasificadas para calcular una dirección.</p>
      )}

      <h3 id="por-eje">Sus votaciones por tema</h3>
      <label className="atlasSelect">
        Eje{" "}
        <select
          onChange={(e) => {
            setAxisFilter(e.target.value);
            setShownAxis(PAGE);
          }}
          value={axisFilter}
        >
          <option value="">Elige un eje…</option>
          {Object.values(axisById)
            .filter((a) => a.votes > 0)
            .map((a) => (
              <option key={a.axis_id} value={a.axis_id}>
                {a.label}
              </option>
            ))}
        </select>
      </label>
      {axisFilter ? (
        <>
          <ul className="atlasVotes">
            {axisVotes.slice(0, shownAxis).map((i) => (
              <VoteLine atlas={atlas} axisFilter={axisFilter} choice={personChoice(person, i)} classified={classified} index={i} key={i} people={people} />
            ))}
          </ul>
          {axisVotes.length > shownAxis ? (
            <button className="votingAidButton" onClick={() => setShownAxis(shownAxis + PAGE)} type="button">
              Ver más ({axisVotes.length - shownAxis})
            </button>
          ) : null}
          {!axisVotes.length ? <p className="votingAidMuted">No votó en ninguna votación de este eje.</p> : null}
        </>
      ) : null}

      <h3>Cuando votó distinto de su partido</h3>
      {rebels.length ? (
        <>
          <ul className="atlasVotes">
            {rebels.slice(0, shownRebels).map(([i, partyCode]) => (
              <VoteLine atlas={atlas} choice={personChoice(person, i)} classified={classified} index={i} key={i} partyCode={partyCode} people={people} />
            ))}
          </ul>
          {rebels.length > shownRebels ? (
            <button className="votingAidButton" onClick={() => setShownRebels(shownRebels + PAGE)} type="button">
              Ver más ({rebels.length - shownRebels})
            </button>
          ) : null}
          <p className="votingAidMuted">
            Incluye enmiendas y trámites. Un voto distinto puede ser un error al votar (a veces se corrige en una votación repetida).
          </p>
        </>
      ) : (
        <p className="votingAidMuted">Siempre votó igual que la mayoría de su partido.</p>
      )}
    </section>
  );
}

export default function PeopleClient() {
  const [people, peopleStatus] = useJson(PEOPLE_PATH);
  const [atlas, atlasStatus] = useJson(ATLAS_PATH);
  const [query, setQuery] = useState("");
  const [partyId, setPartyId] = useState("");
  const [sort, setSort] = useState("name");
  const [shown, setShown] = useState(60);
  const [personId, setPersonId] = useState("");

  useEffect(() => {
    const sync = () => setPersonId(readHash(window.location.hash).p || "");
    sync();
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  function open(id) {
    setPersonId(id);
    window.history.pushState(null, "", `${window.location.pathname}${writeHash({ p: id })}`);
    window.scrollTo({ top: 0 });
  }

  const partiesById = useMemo(() => Object.fromEntries((people?.parties || []).map((p) => [p.party_id, p])), [people]);
  const list = useMemo(() => {
    const earlierOnly = partyId === "_earlier";
    const found = filterPeople(people?.people, { query, partyId: earlierOnly ? "" : partyId });
    return (earlierOnly ? found.filter((p) => !(p.legislatures || []).includes("15")) : found).sort(SORTS[sort].fn);
  }, [people, query, partyId, sort]);
  const person = personId ? (people?.people || []).find((p) => p.id === personId) : null;
  const ready = peopleStatus === "ready" && atlasStatus === "ready";

  return (
    <main className="votingAid atlas">
      <p className="votingAidEyebrow">Congreso de los Diputados · XIV (desde oct. 2022) y XV legislaturas</p>
      <h1>Qué ha votado tu diputado/a</h1>
      {!person ? (
        <p className="votingAidLead">
          Busca a cualquier diputado o diputada del Congreso desde octubre de 2022 (final de la XIV legislatura y toda la XV): hacia dónde ha
          empujado en cada tema, cuántas veces votó distinto de su partido o grupo y todas sus votaciones, enlazadas a la fuente oficial.{" "}
          <Link href="/citizen/vota/temas/">Ver el mapa por partidos</Link>.
        </p>
      ) : null}
      {peopleStatus === "error" || atlasStatus === "error" ? <p className="votingAidNotice">No se pudieron cargar los datos.</p> : null}
      {!ready && peopleStatus !== "error" && atlasStatus !== "error" ? <p className="votingAidMuted">Cargando votaciones…</p> : null}
      {ready && person ? (
        <PersonView atlas={atlas} onBack={() => open("")} partiesById={partiesById} people={people} person={person} />
      ) : null}
      {ready && personId && !person ? <p className="votingAidNotice">No encontramos a esa persona en los datos.</p> : null}
      {ready && !person ? (
        <>
          <div className="atlasControls">
            <label className="atlasSearch">
              <span className="votingAidSrOnly">Buscar por nombre</span>
              <input
                autoComplete="off"
                onChange={(e) => {
                  setQuery(e.target.value);
                  setShown(60);
                }}
                placeholder="Buscar por nombre…"
                type="search"
                value={query}
              />
            </label>
            <label className="atlasSelect">
              Partido{" "}
              <select onChange={(e) => setPartyId(e.target.value)} value={partyId}>
                <option value="">Todos</option>
                <option value="_earlier">Solo en la XIV (ya no son diputados)</option>
                {(people.parties || []).map((p) => (
                  <option key={p.party_id} value={p.party_id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="atlasSelect">
              Ordenar{" "}
              <select onChange={(e) => setSort(e.target.value)} value={sort}>
                {Object.entries(SORTS).map(([k, s]) => (
                  <option key={k} value={k}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="votingAidMuted">{list.length} personas</p>
          <ul className="atlasPeople">
            {list.slice(0, shown).map((p) => (
              <li key={p.id}>
                <a
                  className="atlasPeople__row"
                  href={writeHash({ p: p.id })}
                  onClick={(e) => {
                    e.preventDefault();
                    open(p.id);
                  }}
                >
                  <span className="atlasPeople__name">{p.name}</span>
                  <span className="atlasPeople__party">{partyLabel(p, partiesById)}</span>
                  <span className="atlasPeople__stat" title="Igual que su partido">
                    {percent1(p.loyalty)} con su partido
                  </span>
                  <span className="atlasPeople__stat" title="Participación">
                    {percent(p.participation)} participación
                  </span>
                </a>
              </li>
            ))}
          </ul>
          {list.length > shown ? (
            <button className="votingAidButton" onClick={() => setShown(shown + 60)} type="button">
              Ver más ({list.length - shown})
            </button>
          ) : null}
        </>
      ) : null}
    </main>
  );
}
