import { withBasePath } from "../../path-utils.mjs";
import { formatDate, formatInt } from "../../static-snapshot.mjs";
import { actorDossierHref, formatRole, loadDossierPayload, safeArray, topPairs } from "../dossier-utils.mjs";

export const metadata = {
  title: "Actores de accountability | Vota Con La Chola",
  description: "Indice estatico de actores con historial auditable en el ledger de accountability.",
};

function ActorIndexCard({ actor }) {
  const topIssue = safeArray(actor.top_issues)[0];
  return (
    <article className="accountability-actor-index-card kpiCard">
      <p className="accountability-actor-index-card__eyebrow eyebrow">{actor.actor_kind || "actor"}</p>
      <h2 className="accountability-actor-index-card__title">
        <a className="accountability-actor-index-card__link" href={actorDossierHref(actor)}>
          {actor.actor_label || actor.actor_key || "Actor sin titulo"}
        </a>
      </h2>
      <dl className="accountability-actor-index-card__facts">
        <div className="accountability-actor-index-card__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(actor.entries_total)}</dd>
        </div>
        <div className="accountability-actor-index-card__fact">
          <dt>Temas</dt>
          <dd>{formatInt(actor.issues_total)}</dd>
        </div>
        <div className="accountability-actor-index-card__fact">
          <dt>Fechas</dt>
          <dd>
            {formatDate(actor.first_date)} / {formatDate(actor.last_date)}
          </dd>
        </div>
      </dl>
      {topIssue ? (
        <p className="accountability-actor-index-card__issue sub">
          Tema principal: {topIssue.issue_label || topIssue.issue_id}
        </p>
      ) : null}
      <div className="accountability-actor-index-card__roles chips" aria-label="Roles principales">
        {topPairs(actor.roles, 4).map((item) => (
          <span className="accountability-actor-index-card__role chip" key={item.label}>
            {formatRole(item.label)} · {formatInt(item.count)}
          </span>
        ))}
      </div>
    </article>
  );
}

export default function AccountabilityActorsIndexPage() {
  const payload = loadDossierPayload();
  const actors = safeArray(payload.actors);
  return (
    <main className="accountability-actor-index-page shell">
      <section className="accountability-actor-index-hero hero card">
        <p className="accountability-actor-index-hero__eyebrow eyebrow">Accountability · actores</p>
        <h1 className="accountability-actor-index-hero__title">Actores con historial</h1>
        <p className="accountability-actor-index-hero__summary sub">
          Indice de personas, grupos e instituciones con evidencia agregada por tema y rol.
        </p>
        <div className="accountability-actor-index-hero__actions chips">
          <a className="accountability-actor-index-hero__link chip" href={withBasePath("/accountability-dossiers/")}>
            Volver a dossiers
          </a>
          <a className="accountability-actor-index-hero__link chip" href={withBasePath("/accountability-dossiers/data/dossiers.json")}>
            Dossiers JSON
          </a>
        </div>
      </section>
      <section className="accountability-actor-index-list block">
        <div className="accountability-actor-index-list__head blockHead">
          <h2 className="accountability-actor-index-list__title">{formatInt(actors.length)} actores exportados</h2>
        </div>
        <div className="accountability-actor-index-list__grid grid">
          {actors.map((actor) => (
            <ActorIndexCard actor={actor} key={actor.actor_key || actor.actor_label} />
          ))}
        </div>
      </section>
    </main>
  );
}
