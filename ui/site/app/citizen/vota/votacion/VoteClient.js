"use client";

import { useMemo, useState } from "react";
import "../explore.css";
import { Crumbs, ExploreNav, LoadState, ROUTES, ResultText, VotePill, href, partyHref, personHref, useHashState, useJson } from "../explorar/ExploreClient";
import {
  XV,
  codeClass,
  countsText,
  organicMajority,
  relatedVotes,
  seatBlocks,
  shortLabel,
  totalsFromPeople,
  totalsText,
  voteDissenters,
  voteIndexById,
  votesWord,
} from "../exploreModel.mjs";
import { ATLAS_PATH, LEG_LABELS, PEOPLE_PATH, formatDate, groupShortLabel, officialVoteUrl, voteTitle } from "../voteAtlasModel.mjs";

const RELATED = 5;

function ResultCard({ vote, totals, organic, blocks, leg, partiesById }) {
  const [yes, no, abs] = totals;
  const cast = yes + no + abs;
  const pct = (x) => (cast ? (x / cast) * 100 : 0);
  const mark = organic && cast ? Math.min(100, (organic.needed / cast) * 100) : null;
  const aria = organic
    ? `${yes} sí, ${no} no y ${abs} abstenciones; la mayoría absoluta exigida a una ley orgánica es ${organic.needed}`
    : `${yes} sí, ${no} no y ${abs} abstenciones`;
  return (
    <section aria-labelledby="x-resultado" className="v-card x-result">
      <div className="x-result__top">
        <h2 className={vote.approved === true ? "x-res--ok" : vote.approved === false ? "x-res--ko" : ""} id="x-resultado">
          <ResultText vote={vote} />
        </h2>
        <p className="x-result__totals">
          <strong className="is-yes-ink">{yes} sí</strong> · <strong className="is-no-ink">{no} no</strong> · {abs} {abs === 1 ? "abstención" : "abstenciones"}
        </p>
      </div>
      {cast ? (
        <span aria-label={aria} className="x-bigbar" role="img">
          <span className="x-c-S" style={{ width: `${pct(yes)}%` }} />
          <span className="x-c-N" style={{ width: `${pct(no)}%` }} />
          <span className="x-c-A" style={{ width: `${pct(abs)}%` }} />
          {mark !== null ? <span aria-hidden="true" className="x-bigbar__mark" style={{ left: `${mark}%` }} /> : null}
        </span>
      ) : (
        <p className="v-muted">Sin datos del recuento.</p>
      )}
      {organic ? (
        <p className="v-muted">
          Línea blanca: {organic.needed} votos, la mayoría absoluta que exige una ley orgánica.{" "}
          {organic.reached ? (organic.margin === 0 ? "La alcanzó justo, sin votos de sobra." : `Salió por ${votesWord(organic.margin)}.`) : `Le faltaron ${votesWord(-organic.margin)}.`}
        </p>
      ) : null}

      {blocks ? (
        <div className="x-seats">
          <h3>Cada punto es un diputado</h3>
          {blocks.map((b) => (
            <div className="x-seat" key={b.key}>
              <span className="x-seat__label">
                {b.partyId ? <a href={partyHref(b.partyId)}>{partiesById[b.partyId]?.label || b.label}</a> : <span className="x-seat__name">{b.label}</span>}
                <span className="v-mono">{countsText(b.counts)}</span>
              </span>
              <span aria-label={`${b.label}: ${countsText(b.counts)}`} className="x-dots" role="img">
                {b.codes.map((c, i) => (
                  <span className={codeClass(c)} key={i} />
                ))}
              </span>
            </div>
          ))}
          <p className="v-legend">
            <span>
              <span className="v-swatch x-c-S" />
              Sí
            </span>
            <span>
              <span className="v-swatch x-c-N" />
              No
            </span>
            <span>
              <span className="v-swatch x-c-A" />
              Abstención
            </span>
            <span>
              <span className="v-swatch x-c-absent" />
              No votó
            </span>
          </p>
          <p className="v-muted">
            {leg === XV
              ? "Cada diputado aparece en su partido actual; «Otros» son quienes hoy no pertenecen a ninguno de los 12 partidos."
              : `Votación de la ${LEG_LABELS[leg] || leg} legislatura: cada diputado aparece en su grupo parlamentario de entonces.`}
          </p>
        </div>
      ) : null}
    </section>
  );
}

function Discipline({ dissenters, blocks, leg, partiesById }) {
  const others = leg === XV ? blocks?.find((b) => b.key === "otros") : null;
  const unit = leg === XV ? "partido" : "grupo";
  return (
    <section aria-labelledby="x-disciplina" className="v-card x-side-card">
      <h2 id="x-disciplina">Disciplina de voto</h2>
      {dissenters.length ? (
        <>
          <p>
            {dissenters.length === 1 ? "Un diputado votó" : `${dissenters.length} diputados votaron`} distinto a su {unit}:
          </p>
          <ul className="x-dissent">
            {dissenters.map(({ person, own, party }) => (
              <li key={person.id}>
                <a href={personHref(person.id)}>{person.name}</a>
                <span className="x-pills">
                  <span>
                    <VotePill code={own} />
                  </span>
                  <span className="x-pills__who--party">
                    {leg === XV ? partiesById[person.party_id]?.label || "su partido" : groupShortLabel((person.groups_by_leg?.[leg] || []).slice(-1)[0])}{" "}
                    <VotePill code={party} />
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p>Ningún diputado votó distinto a su {unit}.</p>
      )}
      {others && others.codes.length ? (
        <p className="v-muted">
          {others.codes.length === 1 ? "Un diputado que hoy no pertenece" : `${others.codes.length} diputados que hoy no pertenecen`} a ninguno de los 12 partidos:{" "}
          {countsText(others.counts)}.
        </p>
      ) : null}
    </section>
  );
}

function Sources({ atlas, vote, path, textUrl }) {
  const [all, setAll] = useState(false);
  const related = useMemo(() => (vote ? relatedVotes(atlas, vote) : []), [atlas, vote]);
  const shown = all ? related : related.slice(0, RELATED);
  const official = officialVoteUrl(path);
  return (
    <section aria-labelledby="x-fuentes" className="v-card v-card--sunk x-trail">
      <h2 id="x-fuentes">Fuentes y contexto</h2>
      {official ? (
        <a href={official} rel="noopener noreferrer" target="_blank">
          Votación oficial en congreso.es <span aria-hidden="true">↗</span>
        </a>
      ) : (
        <p className="v-muted">Sin enlace a la votación oficial.</p>
      )}
      {textUrl ? (
        <a href={textUrl} rel="noopener noreferrer" target="_blank">
          Texto que se votó (BOCG) <span aria-hidden="true">↗</span>
        </a>
      ) : null}
      {related.length ? <p className="x-trail__sub">Otras votaciones de la misma iniciativa</p> : null}
      {shown.map((r) => (
        <a className="x-trail__vote" href={`#v=${encodeURIComponent(r.id)}`} key={r.id}>
          <span>
            {String(r.date) < String(vote.date) ? "Antes" : String(r.date) > String(vote.date) ? "Después" : "El mismo día"}: {r.summary_yes || atlas.kind_labels?.[r.kind] || r.kind}
          </span>
          <span className="x-trail__sub">
            {formatDate(r.date)} · {atlas.kind_labels?.[r.kind] || r.kind} · {r.approved ? "aprobada" : "rechazada"} · {totalsText(r.totals)}
          </span>
        </a>
      ))}
      {related.length > RELATED ? (
        <button aria-expanded={all} className="v-link-btn x-toggle" onClick={() => setAll(!all)} type="button">
          {all ? "Ver menos" : `Ver las ${related.length} votaciones de esta iniciativa`}
        </button>
      ) : null}
    </section>
  );
}

function VoteView({ atlas, people, voteId }) {
  const index = useMemo(() => voteIndexById(people)[voteId], [people, voteId]);
  const atlasVote = useMemo(() => (atlas.votes || []).find((v) => v.id === voteId) || null, [atlas, voteId]);
  const row = Number.isInteger(index) ? people.votes[index] : null;
  const blocks = useMemo(() => (Number.isInteger(index) ? seatBlocks(people, index, people.parties || atlas.parties) : null), [people, atlas, index]);
  const dissenters = useMemo(() => (Number.isInteger(index) ? voteDissenters(people, index) : []), [people, index]);
  const partiesById = useMemo(() => Object.fromEntries((atlas.parties || []).map((p) => [p.party_id, p])), [atlas]);

  if (!atlasVote && !row) {
    return (
      <>
        <Crumbs items={[{ label: "Explorar", href: href(ROUTES.hub) }, { label: "Votaciones", href: href(ROUTES.topics) }, { label: "No encontrada" }]} />
        <p className="x-notice" role="alert">
          No encontramos la votación «{voteId}» en los datos. Búscala en <a href={href(ROUTES.hub)}>Explorar</a> o en las <a href={href(ROUTES.topics)}>votaciones por tema</a>.
        </p>
      </>
    );
  }

  const vote = atlasVote || { id: voteId, path: row[1], date: row[2], kind: row[3], t: null, subgroup: row[5], leg: row[6] };
  const title = atlasVote ? voteTitle(atlas, atlasVote) : Number.isInteger(row[4]) ? people.titles?.[row[4]] || "" : String(row[4] || "");
  const leg = String(atlasVote?.leg || row?.[6] || XV);
  const totals = Array.isArray(atlasVote?.totals) ? atlasVote.totals : Number.isInteger(index) ? totalsFromPeople(people, index) : [0, 0, 0];
  const organic = organicMajority({ ...vote, totals }, title);
  const firstAxis = atlasVote?.axes?.[0];
  const axis = firstAxis ? (atlas.axes || []).find((a) => a.axis_id === firstAxis[0]) : null;
  const topic = axis ? (atlas.topics || []).find((t) => t.topic_id === axis.topic_id) : null;
  const kind = atlas.kind_labels?.[vote.kind] || vote.kind || "Votación";
  const heading = atlasVote?.summary_yes || title || "Votación sin título";

  return (
    <>
      <Crumbs items={[{ label: "Explorar", href: href(ROUTES.hub) }, { label: "Votaciones", href: href(ROUTES.topics) }, { label: shortLabel(heading) }]} />
      <div className="x-vote-head">
        <p className="v-eyebrow">
          {axis ? (
            <a href={href(ROUTES.topics, `#eje=${encodeURIComponent(axis.axis_id)}`)}>
              {topic ? `${topic.label} · ` : ""}
              {axis.label}
            </a>
          ) : (
            `${kind}${leg !== XV ? ` · ${LEG_LABELS[leg] || leg} legislatura` : ""}`
          )}
        </p>
        <h1 className="v-h1">{heading}</h1>
        <p className="v-lead">
          {kind} · Pleno del {formatDate(vote.date)}
          {title && title !== heading ? <> · «{title.replace(/\.$/u, "")}»</> : null}
          {vote.subgroup ? <span className="v-muted"> — {vote.subgroup}</span> : null}
        </p>
      </div>
      <div className="v-split">
        <div className="v-main">
          <ResultCard blocks={blocks} leg={leg} organic={organic} partiesById={partiesById} totals={totals} vote={vote} />
          {!atlasVote ? (
            <p className="v-muted">
              Esta votación no está clasificada por temas (trámite o votación sin partidos enfrentados): el recuento sale del voto de cada diputado.
            </p>
          ) : null}
        </div>
        <aside className="v-side">
          {blocks ? <Discipline blocks={blocks} dissenters={dissenters} leg={leg} partiesById={partiesById} /> : null}
          <Sources atlas={atlas} path={vote.path} textUrl={atlasVote?.text_url} vote={vote} />
        </aside>
      </div>
    </>
  );
}

export default function VoteClient() {
  const [atlas, atlasStatus] = useJson(ATLAS_PATH);
  const [people, peopleStatus] = useJson(PEOPLE_PATH);
  const hash = useHashState();
  const voteId = hash?.v || "";
  const status = atlasStatus === "error" || peopleStatus === "error" ? "error" : atlas && people ? "ready" : "loading";

  return (
    <>
      <ExploreNav current="temas" />
      <main className="v-page x-vote">
        <LoadState status={status} what="la votación" />
        {status === "ready" && hash ? (
          voteId ? (
            <VoteView atlas={atlas} key={voteId} people={people} voteId={voteId} />
          ) : (
            <>
              <Crumbs items={[{ label: "Explorar", href: href(ROUTES.hub) }, { label: "Votación" }]} />
              <h1 className="v-h1">Elige una votación</h1>
              <p className="v-lead">
                Busca una votación en <a href={href(ROUTES.hub)}>Explorar</a> o recórrelas por <a href={href(ROUTES.topics)}>temas</a>.
              </p>
            </>
          )
        ) : null}
      </main>
    </>
  );
}
