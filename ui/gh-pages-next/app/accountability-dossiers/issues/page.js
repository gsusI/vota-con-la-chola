import { withBasePath } from "../../path-utils.mjs";
import { formatDate, formatInt } from "../../static-snapshot.mjs";
import { formatRole, issueDossierHref, loadDossierPayload, safeArray, topPairs } from "../dossier-utils.mjs";

export const metadata = {
  title: "Temas de accountability | Vota Con La Chola",
  description: "Indice estatico de issues con actores, roles y evidencia trazable.",
};

function IssueIndexCard({ issue }) {
  return (
    <article className="accountability-issue-index-card kpiCard">
      <p className="accountability-issue-index-card__eyebrow eyebrow">{issue.scope || "tema"}</p>
      <h2 className="accountability-issue-index-card__title">
        <a className="accountability-issue-index-card__link" href={issueDossierHref(issue)}>
          {issue.label || issue.issue_id || "Tema sin titulo"}
        </a>
      </h2>
      <p className="accountability-issue-index-card__summary sub">{issue.summary || "Sin resumen disponible."}</p>
      <dl className="accountability-issue-index-card__facts">
        <div className="accountability-issue-index-card__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(issue.entries_total)}</dd>
        </div>
        <div className="accountability-issue-index-card__fact">
          <dt>Actores</dt>
          <dd>{formatInt(issue.actors_total)}</dd>
        </div>
        <div className="accountability-issue-index-card__fact">
          <dt>Fechas</dt>
          <dd>
            {formatDate(issue.first_date)} / {formatDate(issue.last_date)}
          </dd>
        </div>
      </dl>
      <div className="accountability-issue-index-card__roles chips" aria-label="Roles principales">
        {topPairs(issue.roles, 4).map((item) => (
          <span className="accountability-issue-index-card__role chip" key={item.label}>
            {formatRole(item.label)} · {formatInt(item.count)}
          </span>
        ))}
      </div>
    </article>
  );
}

export default function AccountabilityIssuesIndexPage() {
  const payload = loadDossierPayload();
  const issues = safeArray(payload.issues);
  return (
    <main className="accountability-issue-index-page shell">
      <section className="accountability-issue-index-hero hero card">
        <p className="accountability-issue-index-hero__eyebrow eyebrow">Accountability · temas</p>
        <h1 className="accountability-issue-index-hero__title">Temas con actores</h1>
        <p className="accountability-issue-index-hero__summary sub">
          Indice de issues con actores implicados, roles, fechas y evidencia primaria enlazada.
        </p>
        <div className="accountability-issue-index-hero__actions chips">
          <a className="accountability-issue-index-hero__link chip" href={withBasePath("/accountability-dossiers/")}>
            Volver a dossiers
          </a>
          <a className="accountability-issue-index-hero__link chip" href={withBasePath("/accountability-dossiers/data/dossiers.json")}>
            Dossiers JSON
          </a>
        </div>
      </section>
      <section className="accountability-issue-index-list block">
        <div className="accountability-issue-index-list__head blockHead">
          <h2 className="accountability-issue-index-list__title">{formatInt(issues.length)} temas exportados</h2>
        </div>
        <div className="accountability-issue-index-list__grid grid">
          {issues.map((issue) => (
            <IssueIndexCard issue={issue} key={issue.issue_id || issue.label} />
          ))}
        </div>
      </section>
    </main>
  );
}
