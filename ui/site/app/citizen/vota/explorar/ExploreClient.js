"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { withBasePath } from "../../../path-utils.mjs";
import "../explore.css";
import {
  CODE_WORDS,
  PARTY_ABBR,
  codeClass,
  codeOf,
  initials,
  isXvVote,
  latestVotes,
  partyCodesAria,
  percent1,
  personLegSummary,
  personPartyLabel,
  resultLabel,
  searchExplore,
  totalsText,
  xvPeople,
} from "../exploreModel.mjs";
import { ATLAS_PATH, PEOPLE_PATH, formatCount, formatDate, readHash, voteTitle } from "../voteAtlasModel.mjs";

// ---------------------------------------------------------------------------
// Shared pieces of the Explorar pages (hub, partidos, diputados, votacion, temas).

export const ROUTES = {
  hub: "/citizen/vota/explorar/",
  map: "/citizen/vota/mapa/",
  parties: "/citizen/vota/partidos/",
  people: "/citizen/vota/diputados/",
  vote: "/citizen/vota/votacion/",
  topics: "/citizen/vota/temas/",
  test: "/citizen/vota/",
  method: "/citizen/vota/metodologia/",
};

export const href = (path, hash = "") => `${withBasePath(path)}${hash}`;
export const voteHref = (id) => href(ROUTES.vote, `#v=${encodeURIComponent(id)}`);
export const partyHref = (id) => href(ROUTES.parties, `#p=${encodeURIComponent(id)}`);
export const personHref = (id) => href(ROUTES.people, `#p=${encodeURIComponent(id)}`);

// One fetch per file per page load, shared by every component that needs it.
const jsonCache = new Map();
export function loadJson(path) {
  if (!jsonCache.has(path)) {
    const p = fetch(withBasePath(path))
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .catch((err) => {
        jsonCache.delete(path);
        throw err;
      });
    jsonCache.set(path, p);
  }
  return jsonCache.get(path);
}

/** [data, status] with status "idle" (not asked yet) | "loading" | "ready" | "error". */
export function useJson(path, enabled = true) {
  const [state, setState] = useState({ data: null, status: enabled ? "loading" : "idle" });
  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;
    setState((s) => (s.data ? s : { data: null, status: "loading" }));
    loadJson(path).then(
      (data) => !cancelled && setState({ data, status: "ready" }),
      () => !cancelled && setState({ data: null, status: "error" }),
    );
    return () => {
      cancelled = true;
    };
  }, [path, enabled]);
  return [state.data, state.status];
}

/** Hash view state ("#p=psoe"); null until mounted. Scrolls to the top when the hash changes. */
export function useHashState() {
  const [state, setState] = useState(null);
  useEffect(() => {
    const read = () => setState(readHash(window.location.hash));
    const onChange = () => {
      read();
      window.scrollTo({ top: 0 });
    };
    read();
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return state;
}

const SUBNAV = [
  ["inicio", "Inicio", ROUTES.hub],
  ["mapa", "Mapa", ROUTES.map],
  ["partidos", "Partidos", ROUTES.parties],
  ["diputados", "Diputados", ROUTES.people],
  ["temas", "Votaciones", ROUTES.topics],
];

export function ExploreNav({ current }) {
  return (
    <nav aria-label="Explorar" className="v-subnav">
      <div className="v-subnav__inner">
        {SUBNAV.map(([id, label, path]) => (
          <a aria-current={current === id ? "page" : undefined} href={withBasePath(path)} key={id}>
            {label}
          </a>
        ))}
      </div>
    </nav>
  );
}

/** Breadcrumb: items [{label, href}], the last one is the current page. */
export function Crumbs({ items }) {
  return (
    <nav aria-label="Ruta" className="v-crumbs x-crumbs">
      {items.map((it, i) =>
        i < items.length - 1 ? (
          <span className="x-crumbs__item" key={it.label}>
            <a href={it.href}>{it.label}</a>
            <span aria-hidden="true">›</span>
          </span>
        ) : (
          <span aria-current="page" className="x-crumbs__current" key={it.label}>
            {it.label}
          </span>
        ),
      )}
    </nav>
  );
}

export function LoadState({ status, what = "los datos" }) {
  if (status === "error") {
    return (
      <p className="x-notice" role="alert">
        No se pudieron cargar {what}. Comprueba la conexión y vuelve a cargar la página.
      </p>
    );
  }
  if (status === "loading") {
    return (
      <p aria-live="polite" className="x-loading">
        Cargando {what}…
      </p>
    );
  }
  return null;
}

/** A vote as a pill with its word: Sí / No / Abstención / No votó. */
export function VotePill({ code }) {
  const cls = { S: "v-vote--yes", N: "v-vote--no", A: "v-vote--abs" }[code] || "x-pill--absent";
  return <span className={`v-vote ${cls}`}>{CODE_WORDS[code] || "sin dato"}</span>;
}

export function ResultText({ vote }) {
  const ok = vote?.approved;
  return <span className={`x-res ${ok === true ? "x-res--ok" : ok === false ? "x-res--ko" : ""}`}>{resultLabel(vote)}</span>;
}

/** The 12 parties' majority votes as coloured squares; text alternative names every party. */
export function PartySquares({ atlas, vote, abbr = "mobile" }) {
  const parties = atlas?.parties || [];
  return (
    <span aria-label={`Voto de cada partido: ${partyCodesAria(atlas, vote)}`} className={`x-sq x-sq--abbr-${abbr}`} role="img">
      {parties.map((p, i) => {
        const c = codeOf(vote, i);
        return (
          <span className="x-sq__cell" key={p.party_id} title={`${p.label}: ${CODE_WORDS[c] || "sin dato"}`}>
            <span className={`x-sq__box ${codeClass(c)}`} />
            <span aria-hidden="true" className="x-sq__abbr">
              {PARTY_ABBR[p.party_id] || p.label}
            </span>
          </span>
        );
      })}
    </span>
  );
}

export function PartyAbbrHeader({ atlas }) {
  return (
    <span aria-hidden="true" className="x-sq x-sq--head">
      {(atlas?.parties || []).map((p) => (
        <span key={p.party_id}>{PARTY_ABBR[p.party_id] || p.label}</span>
      ))}
    </span>
  );
}

export function SquaresLegend() {
  return (
    <p className="v-legend x-legend">
      <span>
        <span className="v-swatch x-sw x-c-S" />
        Sí
      </span>
      <span>
        <span className="v-swatch x-sw x-c-N" />
        No
      </span>
      <span>
        <span className="v-swatch x-sw x-c-A" />
        Abstención
      </span>
      <span>
        <span className="v-swatch x-sw x-c-q" />
        Sin dato
      </span>
    </p>
  );
}

/** A vote row: summary, result + totals + kind, and the 12 party squares. Links to the vote page. */
export function VoteItem({ atlas, vote }) {
  return (
    <li>
      <a className="x-vrow" href={voteHref(vote.id)}>
        <span className="x-vrow__text">
          <span className="x-vrow__title">{vote.summary_yes || voteTitle(atlas, vote)}</span>
          <span className="x-vrow__meta">
            <ResultText vote={vote} />
            <span>{totalsText(vote.totals)}</span>
            <span>{atlas?.kind_labels?.[vote.kind] || vote.kind}</span>
            <span className="v-mono">{formatDate(vote.date)}</span>
          </span>
        </span>
        <PartySquares atlas={atlas} vote={vote} />
      </a>
    </li>
  );
}

export function PersonRow({ person, partiesById, summary }) {
  return (
    <li>
      <a className="x-prow" href={personHref(person.id)}>
        <span aria-hidden="true" className="x-avatar">
          {initials(person.name)}
        </span>
        <span className="x-prow__text">
          <span className="x-prow__name">{person.name}</span>
          <span className="x-prow__meta">
            {personPartyLabel(person, partiesById)}
            {summary && Number.isFinite(summary.participation)
              ? ` · votó en el ${summary.rounded ? `${Math.round(summary.participation * 100)} %` : percent1(summary.participation)}`
              : ""}
          </span>
        </span>
        {summary && Number.isFinite(summary.loyalty) ? (
          <span className="x-prow__stat">
            <span className="v-mono">{percent1(summary.loyalty, { floor: true })}</span>
            <span>con su partido</span>
          </span>
        ) : (
          <span aria-hidden="true" className="x-prow__chev">
            ›
          </span>
        )}
      </a>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Hub: /citizen/vota/explorar/

// A fixed sample (official person ids); the 3.3 MB people file loads only when asked for.
const SAMPLE_PEOPLE = [
  { id: "p260", name: "Isabel Pozueta Fernández", party_id: "bildu", legislatures: ["14", "15"] },
  { id: "p302", name: "Gabriel Rufián Romero", party_id: "erc", legislatures: ["14", "15"] },
  { id: "p31", name: "Cayetana Álvarez de Toledo Peralta-Ramos", party_id: "pp", legislatures: ["14", "15"] },
];
const FILTERS = [
  ["todo", "Todo"],
  ["partidos", "Partidos"],
  ["diputados", "Diputados"],
  ["votaciones", "Votaciones"],
];
const STEP = { todo: 6, one: 30 };

function SectionHead({ id, title, children }) {
  return (
    <div className="x-sechead">
      <h2 className="v-h2" id={id}>
        {title}
      </h2>
      {children}
    </div>
  );
}

function PartyGrid({ parties }) {
  return (
    <ul className="x-partygrid">
      {parties.map((p) => (
        <li key={p.party_id}>
          <a className="x-partycard" href={partyHref(p.party_id)}>
            <span className="x-partycard__name">{p.label}</span>
            <span className="x-partycard__go">
              <span className="x-hide-mobile">Ver cómo vota </span>
              <span aria-hidden="true">→</span>
            </span>
          </a>
        </li>
      ))}
    </ul>
  );
}

function VotesCard({ atlas, votes, head = true }) {
  return (
    <div className="v-card x-votes">
      {head ? (
        <div aria-hidden="true" className="x-votes__head">
          <span />
          <PartyAbbrHeader atlas={atlas} />
        </div>
      ) : null}
      <ul className="v-list">
        {votes.map((v) => (
          <VoteItem atlas={atlas} key={v.id} vote={v} />
        ))}
      </ul>
      <SquaresLegend />
    </div>
  );
}

function MapCard() {
  return (
    <section aria-labelledby="x-mapa" className="v-card x-mapcard">
      <div className="x-mapcard__text">
        <p className="v-eyebrow">Mapa</p>
        <h2 className="v-h2" id="x-mapa">
          Mapa de partidos: dónde está cada uno, tema a tema
        </h2>
        <p className="v-muted">Los 12 partidos colocados según lo que votaron. Compara dos o tres, o pon a prueba lo que crees saber.</p>
      </div>
      <div className="x-mapcard__actions">
        <a className="v-btn v-btn--primary" href={href(ROUTES.map, "#vista=mapa")}>
          Ver el mapa
        </a>
        <a className="v-btn" href={href(ROUTES.map, "#vista=adivina")}>
          Juega a adivinar
        </a>
      </div>
    </section>
  );
}

export default function ExploreClient() {
  const [atlas, atlasStatus] = useJson(ATLAS_PATH);
  const [wantPeople, setWantPeople] = useState(false);
  const [people, peopleStatus] = useJson(PEOPLE_PATH, wantPeople);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("todo");
  const [limit, setLimit] = useState(STEP.todo);
  const deferredQuery = useDeferredValue(query);
  const searching = deferredQuery.trim().length > 0;

  // Opening the hub with "#q=…" (e.g. a shared search) runs that search.
  useEffect(() => {
    const q = readHash(window.location.hash).q;
    if (q) {
      setQuery(q);
      setWantPeople(true);
    }
  }, []);

  const results = useMemo(() => searchExplore({ atlas, people, query: deferredQuery }), [atlas, people, deferredQuery]);
  const partiesById = useMemo(() => Object.fromEntries((atlas?.parties || []).map((p) => [p.party_id, p])), [atlas]);
  const xvVotes = useMemo(() => (atlas?.votes || []).filter(isXvVote).length, [atlas]);
  const deputies = useMemo(() => (people ? xvPeople(people) : null), [people]);
  const latest = useMemo(() => latestVotes(atlas, 5, { onAxes: true }), [atlas]);
  const sample = useMemo(
    () =>
      SAMPLE_PEOPLE.map((s) => {
        const full = people?.people?.find((p) => p.id === s.id);
        return full ? { person: full, summary: personLegSummary(people, full) } : { person: s, summary: null };
      }),
    [people],
  );

  const counts = searching
    ? { partidos: results.parties.length, diputados: people ? results.people.length : null, votaciones: results.votes.length }
    : { partidos: atlas?.parties?.length ?? null, diputados: deputies ? deputies.length : null, votaciones: atlas ? xvVotes : null };

  function pick(id) {
    setFilter(id);
    setLimit(id === "todo" ? STEP.todo : STEP.one);
    if (id === "diputados") setWantPeople(true);
  }

  const show = (id) => filter === "todo" || filter === id;
  const cap = filter === "todo" ? STEP.todo : limit;

  return (
    <>
      <ExploreNav current="inicio" />
      <main className="v-page x-hub">
        <section aria-labelledby="x-title" className="x-hero">
          <h1 className="v-h1" id="x-title">
            Explora cómo vota el Congreso
          </h1>
          <p className="v-lead">
            Partidos, diputados y votaciones desde septiembre de 2023. No hace falta hacer el test: cada dato enlaza a la votación oficial.
          </p>
          <form
            className="x-search"
            onSubmit={(e) => {
              e.preventDefault();
              setWantPeople(true);
              document.getElementById("x-results")?.scrollIntoView({ block: "start" });
            }}
            role="search"
          >
            <label className="v-sr" htmlFor="x-q">
              Buscar un partido, un diputado o una votación
            </label>
            <span className="x-search__box">
              <svg aria-hidden="true" fill="none" height="20" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" viewBox="0 0 24 24" width="20">
                <circle cx="11" cy="11" r="7" />
                <path d="M20 20l-4-4" />
              </svg>
              <input
                autoComplete="off"
                id="x-q"
                onChange={(e) => {
                  setQuery(e.target.value);
                  setWantPeople(true);
                  if (filter !== "todo") setLimit(STEP.one);
                }}
                onFocus={() => setWantPeople(true)}
                placeholder="Un partido, un diputado o un tema: «alquiler», «Rufián», «amnistía»…"
                type="search"
                value={query}
              />
            </span>
            <button className="v-btn v-btn--primary x-search__btn" type="submit">
              Buscar
            </button>
          </form>
          <div aria-label="Qué mostrar" className="v-chips x-filters" role="group">
            {FILTERS.map(([id, label]) => (
              <button aria-pressed={filter === id} className="v-chip" key={id} onClick={() => pick(id)} type="button">
                {label}
                {id !== "todo" && counts[id] !== null ? <span className="x-count">{formatCount(counts[id])}</span> : null}
              </button>
            ))}
          </div>
        </section>

        <LoadState status={atlasStatus} what="las votaciones" />

        {searching && atlas ? (
          <section aria-labelledby="x-results-title" className="x-results" id="x-results">
            <h2 className="v-sr" id="x-results-title">
              Resultados de «{deferredQuery.trim()}»
            </h2>
            <p aria-live="polite" className="v-muted">
              {results.parties.length + results.people.length + results.votes.length
                ? `Resultados para «${deferredQuery.trim()}»`
                : people
                  ? `No hay resultados para «${deferredQuery.trim()}». Prueba con otra palabra o mira las votaciones por tema.`
                  : ""}
            </p>
            {show("partidos") && results.parties.length ? (
              <div className="x-group">
                <h3 className="v-kicker">Partidos</h3>
                <PartyGrid parties={results.parties} />
              </div>
            ) : null}
            {show("diputados") ? (
              <div className="x-group">
                <h3 className="v-kicker">Diputados</h3>
                {peopleStatus === "loading" || peopleStatus === "error" ? (
                  <LoadState status={peopleStatus} what="los diputados" />
                ) : results.people.length ? (
                  <ul className="v-card v-list x-people">
                    {results.people.slice(0, cap).map((p) => (
                      <PersonRow key={p.id} partiesById={partiesById} person={p} summary={personLegSummary(people, p)} />
                    ))}
                  </ul>
                ) : (
                  <p className="v-muted">Ningún diputado de la XV legislatura con ese nombre.</p>
                )}
                {results.people.length > cap ? (
                  filter === "todo" ? (
                    <button className="v-link-btn x-more" onClick={() => pick("diputados")} type="button">
                      Ver los {formatCount(results.people.length)} diputados →
                    </button>
                  ) : (
                    <button className="v-btn" onClick={() => setLimit(limit + STEP.one)} type="button">
                      Ver más ({formatCount(results.people.length - cap)})
                    </button>
                  )
                ) : null}
              </div>
            ) : null}
            {show("votaciones") ? (
              <div className="x-group">
                <h3 className="v-kicker">Votaciones</h3>
                {results.votes.length ? <VotesCard atlas={atlas} votes={results.votes.slice(0, cap)} /> : <p className="v-muted">Ninguna votación con esas palabras.</p>}
                {results.votes.length > cap ? (
                  filter === "todo" ? (
                    <button className="v-link-btn x-more" onClick={() => pick("votaciones")} type="button">
                      Ver las {formatCount(results.votes.length)} votaciones →
                    </button>
                  ) : (
                    <button className="v-btn" onClick={() => setLimit(limit + STEP.one)} type="button">
                      Ver más ({formatCount(results.votes.length - cap)})
                    </button>
                  )
                ) : null}
              </div>
            ) : null}
          </section>
        ) : null}

        {!searching ? (
          <>
            {show("partidos") ? (
              <section aria-labelledby="x-partidos" className="x-section">
                <SectionHead id="x-partidos" title="Partidos">
                  <p className="v-muted">Su postura en {atlas ? atlas.axes?.length : 33} ejes, sacada de sus votos</p>
                </SectionHead>
                {atlas ? <PartyGrid parties={atlas.parties || []} /> : null}
              </section>
            ) : null}

            {filter === "todo" ? <MapCard /> : null}

            <div className="v-split">
              {show("votaciones") ? (
                <section aria-labelledby="x-votaciones" className="v-main x-section">
                  <SectionHead id="x-votaciones" title="Últimas votaciones">
                    <a className="x-headlink" href={href(ROUTES.topics)}>
                      Todas, por tema →
                    </a>
                  </SectionHead>
                  <p className="v-muted x-note">Las más recientes con partidos enfrentados (sin ratificaciones de tratados ni trámites).</p>
                  {atlas ? <VotesCard atlas={atlas} votes={latest} /> : null}
                </section>
              ) : null}
              {show("diputados") ? (
                <section aria-labelledby="x-diputados" className={`${filter === "todo" ? "v-side" : "v-main"} x-section`}>
                  <SectionHead id="x-diputados" title="Diputados">
                    <a className="x-headlink" href={href(ROUTES.people)}>
                      {deputies ? `Los ${formatCount(deputies.length)} →` : "Todos →"}
                    </a>
                  </SectionHead>
                  {filter === "diputados" && peopleStatus !== "ready" ? <LoadState status={peopleStatus} what="los diputados" /> : null}
                  <ul className="v-card v-list x-people">
                    {(filter === "diputados" && deputies ? deputies.slice(0, limit).map((p) => ({ person: p, summary: personLegSummary(people, p) })) : sample).map(
                      ({ person, summary }) => (
                        <PersonRow key={person.id} partiesById={partiesById} person={person} summary={summary} />
                      ),
                    )}
                  </ul>
                  {filter === "diputados" && deputies && deputies.length > limit ? (
                    <button className="v-btn" onClick={() => setLimit(limit + STEP.one)} type="button">
                      Ver más ({formatCount(deputies.length - limit)})
                    </button>
                  ) : null}
                  <p className="v-muted">«Con su partido»: votaciones de la XV en que votó igual que la mayoría de su partido (Sí, No o Abstención).</p>
                </section>
              ) : null}
            </div>
          </>
        ) : null}
      </main>
    </>
  );
}
