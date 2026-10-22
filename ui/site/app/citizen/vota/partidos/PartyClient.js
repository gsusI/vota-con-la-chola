"use client";

import { useMemo, useState } from "react";
import "../explore.css";
import { Crumbs, ExploreNav, LoadState, ROUTES, href, partyHref, useHashState, useJson } from "../explorar/ExploreClient";
import { leaningText, partyAxisGroups, partyVoteCount, sameVoteShares } from "../exploreModel.mjs";
import { ATLAS_PATH, formatCount, writeHash } from "../voteAtlasModel.mjs";
import { partyPagePath } from "../votaPaths.mjs";

const MIN_VOTES = 10;

function AxisRow({ row, topic, partyId }) {
  const { axis, score, votes, left, width } = row;
  const lean = score > 0 ? "pos" : score < 0 ? "neg" : "";
  return (
    <li className="x-axis">
      <span className="x-axis__label">
        <span className="x-axis__topic">{topic.label}</span>
        <a className="x-axis__name" href={href(ROUTES.topics, writeHash({ eje: axis.axis_id, partido: partyId }))}>
          {axis.label}
        </a>
      </span>
      <span className="x-axis__chart">
        <span aria-label={`${axis.label}: ${leaningText(axis, score)}, en ${votes} votaciones`} className="x-dbar" role="img">
          <span aria-hidden="true" className="x-dbar__zero" />
          <span className="x-dbar__fill" style={{ left: `${left}%`, width: `${width}%` }} />
        </span>
        <span className="x-poles">
          <span className={lean === "neg" ? "is-lean" : ""}>← {axis.neg_short}</span>
          <span className="x-poles__n">{formatCount(votes)} votaciones</span>
          <span className={lean === "pos" ? "is-lean" : ""}>{axis.pos_short} →</span>
        </span>
      </span>
    </li>
  );
}

function PartyList({ atlas }) {
  return (
    <>
      <Crumbs items={[{ label: "Explorar", href: href(ROUTES.hub) }, { label: "Partidos" }]} />
      <div className="x-head__text">
        <h1 className="v-h1">Partidos</h1>
        <p className="v-lead">Cómo ha votado cada uno de los 12 partidos con diputados en el Congreso, tema a tema, y con quién vota igual.</p>
      </div>
      <ul className="x-partygrid">
        {(atlas.parties || []).map((p) => (
          <li key={p.party_id}>
            <a className="x-partycard" href={partyHref(p.party_id)}>
              <span className="x-partycard__name">{p.label}</span>
              <span className="x-partycard__go">
                {formatCount(partyVoteCount(atlas, p.party_id))} votaciones <span aria-hidden="true">→</span>
              </span>
            </a>
          </li>
        ))}
      </ul>
    </>
  );
}

function PartyView({ atlas, party }) {
  const [all, setAll] = useState(false);
  const n = useMemo(() => partyVoteCount(atlas, party.party_id), [atlas, party.party_id]);
  const shares = useMemo(() => sameVoteShares(atlas, party.party_id), [atlas, party.party_id]);
  const { groups, shown, total } = useMemo(() => partyAxisGroups(atlas, party.party_id, { minVotes: all ? 1 : MIN_VOTES }), [atlas, party.party_id, all]);
  const hidden = total - shown;

  return (
    <>
      <Crumbs items={[{ label: "Explorar", href: href(ROUTES.hub) }, { label: "Partidos", href: "#" }, { label: party.label }]} />
      <div className="x-head">
        <div className="x-head__text">
          <h1 className="v-h1">{party.label}</h1>
          <p className="v-lead">Cómo ha votado en {formatCount(n)} votaciones de la XV legislatura, resumidas en los temas del test.</p>
        </div>
        <div className="x-head__actions">
          <a className="v-btn" href={href(ROUTES.people, writeHash({ partido: party.party_id }))}>
            Sus diputados
          </a>
          <a className="v-btn" href={href(partyPagePath(party.party_id))}>
            Resumen y votaciones clave
          </a>
          <a className="v-btn v-btn--primary" href={href(ROUTES.test)}>
            ¿Coincides? Haz el test
          </a>
        </div>
      </div>

      <div className="v-split">
        <section aria-labelledby="x-ejes" className="v-main v-card">
          <div className="x-sechead">
            <h2 className="v-h2" id="x-ejes">
              Dónde se sitúa, tema a tema
            </h2>
          </div>
          <p className="x-card-lead">
            Cada barra sale del centro hacia el lado al que empujaron sus votos; más larga, más constante. Toca un eje para ver sus votaciones.
          </p>
          {groups.length ? (
            <ul className="x-axes">
              {groups.flatMap((g) => g.rows.map((r) => <AxisRow key={r.axis.axis_id} partyId={party.party_id} row={r} topic={g.topic} />))}
            </ul>
          ) : (
            <p className="v-muted">Sin datos: este partido no tiene votaciones suficientes en ningún eje.</p>
          )}
          {total > 0 && (all || hidden > 0) ? (
            <button aria-pressed={all} className="v-link-btn x-toggle" onClick={() => setAll(!all)} type="button">
              {all ? `Ver solo los ejes con ${MIN_VOTES} votaciones o más` : `Ver los ${total} ejes (${hidden} con menos de ${MIN_VOTES} votaciones)`}
            </button>
          ) : null}
        </section>

        <aside className="v-side">
          <section aria-labelledby="x-afines" className="v-card">
            <h2 className="v-h2" id="x-afines">
              Con quién vota igual
            </h2>
            <p className="x-card-lead">Votaciones de la XV en que la mayoría de ambos partidos votó lo mismo (Sí, No o Abstención).</p>
            <ol className="x-meters">
              {shares.map((r) => (
                <li key={r.party_id}>
                  <span className="x-meters__row">
                    <a href={partyHref(r.party_id)}>{r.label}</a>
                    <span className="v-mono">{r.share === null ? "sin datos" : `${Math.round(r.share * 100)} %`}</span>
                  </span>
                  <span aria-hidden="true" className="v-meter">
                    <span style={{ width: `${r.share === null ? 0 : Math.round(r.share * 100)}%` }} />
                  </span>
                  <span className="v-sr">
                    {r.share === null ? "" : `${formatCount(r.same)} de ${formatCount(r.n)} votaciones`}
                  </span>
                </li>
              ))}
            </ol>
          </section>
          <section className="v-card v-card--sunk x-trail">
            <h2>Sigue el rastro</h2>
            <a href={href(ROUTES.topics, writeHash({ partido: party.party_id }))}>
              Todas sus votaciones, por tema <span aria-hidden="true">→</span>
            </a>
            <a href={href(ROUTES.people, writeHash({ partido: party.party_id, orden: "loyalty" }))}>
              Sus diputados que más votaron distinto <span aria-hidden="true">→</span>
            </a>
            <a href={href(ROUTES.method, "#mapa")}>
              Cómo se calcula cada eje <span aria-hidden="true">→</span>
            </a>
          </section>
        </aside>
      </div>
    </>
  );
}

export default function PartyClient({ fallback = null }) {
  const [atlas, status] = useJson(ATLAS_PATH);
  const hash = useHashState();
  const partyId = hash?.p || "";
  const party = atlas && partyId ? (atlas.parties || []).find((p) => p.party_id === partyId) : null;

  return (
    <>
      <ExploreNav current="partidos" />
      <main className="v-page x-party">
        <LoadState status={status} what="las votaciones" />
        {atlas && hash ? (
          party ? (
            <PartyView atlas={atlas} key={party.party_id} party={party} />
          ) : (
            <>
              {partyId ? (
                <p className="x-notice" role="alert">
                  No encontramos el partido «{partyId}». Estos son los 12 partidos con datos.
                </p>
              ) : null}
              <PartyList atlas={atlas} />
            </>
          )
        ) : (
          fallback
        )}
      </main>
    </>
  );
}
