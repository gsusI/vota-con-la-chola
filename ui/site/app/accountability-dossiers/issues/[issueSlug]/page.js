import { notFound } from "next/navigation";
import { withBasePath } from "../../../path-utils.mjs";
import { formatDate, formatInt } from "../../../static-snapshot.mjs";
import {
  actorDossierHref,
  findIssueBySlug,
  formatRole,
  issueSlug,
  loadDossierPayload,
  loadLedgerPayload,
  safeArray,
  topPairs,
} from "../../dossier-utils.mjs";

const EMPTY_ISSUE_SLUG = "no-issues-exported";

export const dynamicParams = false;

export async function generateStaticParams() {
  const payload = loadDossierPayload();
  const params = safeArray(payload.issues).map((issue) => ({ issueSlug: issueSlug(issue) }));
  return params.length ? params : [{ issueSlug: EMPTY_ISSUE_SLUG }];
}

export async function generateMetadata({ params }) {
  const { issueSlug: currentSlug } = await params;
  const issue = findIssueBySlug(loadDossierPayload(), currentSlug);
  if (!issue && currentSlug === EMPTY_ISSUE_SLUG) {
    return {
      title: "Sin temas exportados | Vota Con La Chola",
      description: "El corte publico actual no contiene temas de accountability exportados.",
    };
  }
  if (!issue) {
    return {
      title: "Tema no encontrado | Vota Con La Chola",
      description: "No encontramos ese tema en el corte publico actual.",
    };
  }
  return {
    title: `${issue.label || issue.issue_id || "Tema"} | Dossier de accountability`,
    description: issue.summary || "Historial auditable de actores, roles y evidencia para un tema.",
  };
}

function RolePills({ roles }) {
  const pairs = topPairs(roles, 6);
  if (!pairs.length) {
    return <span className="accountability-issue-detail-role-pill pill pill-muted">sin rol</span>;
  }
  return (
    <div className="accountability-issue-detail-role-list chips" aria-label="Roles del tema">
      {pairs.map((item) => (
        <span className="accountability-issue-detail-role-pill chip" key={item.label}>
          {formatRole(item.label)} · {formatInt(item.count)}
        </span>
      ))}
    </div>
  );
}

function IssueMetric({ label, value, note }) {
  return (
    <article className="accountability-issue-detail-metric kpiCard">
      <span className="accountability-issue-detail-metric__label kpiLabel">{label}</span>
      <strong className="accountability-issue-detail-metric__value kpiValue">{value}</strong>
      {note ? <span className="accountability-issue-detail-metric__note kpiLabel">{note}</span> : null}
    </article>
  );
}

function ActorRow({ actor }) {
  return (
    <article className="accountability-issue-actor-row kpiCard">
      <p className="accountability-issue-actor-row__eyebrow eyebrow">{actor.actor_kind || "actor"}</p>
      <h3 className="accountability-issue-actor-row__title">
        <a className="accountability-issue-actor-row__link" href={actorDossierHref(actor)}>
          {actor.actor_label || actor.actor_key || "Actor sin titulo"}
        </a>
      </h3>
      <dl className="accountability-issue-actor-row__facts">
        <div className="accountability-issue-actor-row__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(actor.entries_total)}</dd>
        </div>
        <div className="accountability-issue-actor-row__fact">
          <dt>Fechas</dt>
          <dd>
            {formatDate(actor.first_date)} / {formatDate(actor.last_date)}
          </dd>
        </div>
      </dl>
      <RolePills roles={actor.roles} />
    </article>
  );
}

function EvidenceRow({ entry }) {
  const sourceUrl = String(entry.source_url || "").trim();
  const hasSourceLink = sourceUrl.startsWith("http://") || sourceUrl.startsWith("https://");
  return (
    <article className="accountability-issue-evidence-row kpiCard">
      <div className="accountability-issue-evidence-row__head">
        <p className="accountability-issue-evidence-row__eyebrow eyebrow">tier {entry.evidence_tier || "sin tier"}</p>
        <span className="accountability-issue-evidence-row__role chip">{formatRole(entry.accountability_role)}</span>
      </div>
      <h3 className="accountability-issue-evidence-row__title">{entry.actor_label || "Actor sin etiqueta"}</h3>
      <p className="accountability-issue-evidence-row__summary sub">{entry.summary || entry.title || "Sin resumen."}</p>
      <dl className="accountability-issue-evidence-row__facts">
        <div className="accountability-issue-evidence-row__fact">
          <dt>Fecha</dt>
          <dd>{formatDate(entry.event_date || entry.published_date)}</dd>
        </div>
        <div className="accountability-issue-evidence-row__fact">
          <dt>Fuente</dt>
          <dd>
            {hasSourceLink ? (
              <a className="accountability-issue-evidence-row__source-link" href={sourceUrl}>
                {entry.source_title || entry.source_id || "fuente"}
              </a>
            ) : (
              entry.source_title || entry.source_id || "sin fuente"
            )}
          </dd>
        </div>
        <div className="accountability-issue-evidence-row__fact">
          <dt>Localizador</dt>
          <dd>{entry.source_locator || entry.linked_object_id || entry.entry_id || "sin localizador"}</dd>
        </div>
        <div className="accountability-issue-evidence-row__fact">
          <dt>Cita</dt>
          <dd>{entry.evidence_quote || "sin cita"}</dd>
        </div>
      </dl>
    </article>
  );
}

function EmptyIssueDossierPage() {
  return (
    <main className="accountability-issue-empty-page shell">
      <section className="accountability-issue-empty-hero hero card">
        <p className="accountability-issue-empty-hero__eyebrow eyebrow">Dossier de tema</p>
        <h1 className="accountability-issue-empty-hero__title">Sin temas exportados</h1>
        <p className="accountability-issue-empty-hero__summary sub">
          Este snapshot no contiene filas de accountability con temas. El catalogo de fuentes y el ledger JSON siguen disponibles para auditoria.
        </p>
        <div className="accountability-issue-empty-hero__actions chips">
          <a className="accountability-issue-empty-hero__link chip" href={withBasePath("/accountability-dossiers/")}>
            Volver a dossiers
          </a>
          <a className="accountability-issue-empty-hero__link chip" href={withBasePath("/accountability-dossiers/data/ledger.json")}>
            Ledger JSON
          </a>
        </div>
      </section>
    </main>
  );
}

export default async function AccountabilityIssueDossierPage({ params }) {
  const { issueSlug: currentSlug } = await params;
  const payload = loadDossierPayload();
  const issue = findIssueBySlug(payload, currentSlug);
  if (!issue) {
    if (currentSlug === EMPTY_ISSUE_SLUG) {
      return <EmptyIssueDossierPage />;
    }
    return notFound();
  }

  const ledger = loadLedgerPayload();
  const ledgerIssue = safeArray(ledger.issues).find((item) => item.issue_id === issue.issue_id) || {};
  const evidenceEntries = safeArray(ledgerIssue.entries).slice(0, 80);
  const topActors = safeArray(issue.top_actors);

  return (
    <main className="accountability-issue-detail-page shell">
      <section className="accountability-issue-detail-hero hero card">
        <p className="accountability-issue-detail-hero__eyebrow eyebrow">Dossier de tema · {issue.scope || "sin ambito"}</p>
        <h1 className="accountability-issue-detail-hero__title">{issue.label || issue.issue_id || "Tema sin titulo"}</h1>
        <p className="accountability-issue-detail-hero__summary sub">{issue.summary || "Sin resumen disponible."}</p>
        <div className="accountability-issue-detail-hero__actions chips">
          <a className="accountability-issue-detail-hero__link chip" href={withBasePath("/accountability-dossiers/")}>
            Volver a dossiers
          </a>
          <a className="accountability-issue-detail-hero__link chip" href={withBasePath("/accountability-dossiers/data/ledger.json")}>
            Ledger JSON
          </a>
          <a className="accountability-issue-detail-hero__link chip" href={withBasePath("/explorer/")}>
            Auditar en SQL
          </a>
        </div>
      </section>

      <section className="accountability-issue-detail-metrics kpiGrid" aria-label="Cobertura del tema">
        <IssueMetric label="Entradas" value={formatInt(issue.entries_total)} note="filas vinculadas" />
        <IssueMetric label="Actores" value={formatInt(issue.actors_total)} note="actores distintos" />
        <IssueMetric label="Desde" value={formatDate(issue.first_date)} note="primera evidencia" />
        <IssueMetric label="Hasta" value={formatDate(issue.last_date)} note="ultima evidencia" />
      </section>

      <section className="accountability-issue-roles block">
        <div className="accountability-issue-roles__head blockHead">
          <h2 className="accountability-issue-roles__title">Roles y tipos</h2>
        </div>
        <RolePills roles={issue.roles} />
      </section>

      <section className="accountability-issue-actors block">
        <div className="accountability-issue-actors__head blockHead">
          <h2 className="accountability-issue-actors__title">Actores implicados</h2>
        </div>
        <div className="accountability-issue-actors__grid grid">
          {topActors.length ? (
            topActors.map((actor) => <ActorRow actor={actor} key={actor.actor_key || actor.actor_label} />)
          ) : (
            <p className="accountability-issue-actors__empty sub">Sin actores exportados para este tema.</p>
          )}
        </div>
      </section>

      <section className="accountability-issue-evidence block">
        <div className="accountability-issue-evidence__head blockHead">
          <h2 className="accountability-issue-evidence__title">Evidencia del tema</h2>
        </div>
        <div className="accountability-issue-evidence__grid grid">
          {evidenceEntries.length ? (
            evidenceEntries.map((entry) => <EvidenceRow entry={entry} key={entry.entry_id} />)
          ) : (
            <p className="accountability-issue-evidence__empty sub">Sin filas de evidencia detallada en el ledger compacto.</p>
          )}
        </div>
      </section>
    </main>
  );
}
