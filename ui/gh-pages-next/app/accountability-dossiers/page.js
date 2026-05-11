import { withBasePath } from "../path-utils.mjs";
import { formatDate, formatInt, readPublicJson } from "../static-snapshot.mjs";
import { actorDossierHref, issueDossierHref } from "./dossier-utils.mjs";

const DOSSIER_DATA_PATH = "/accountability-dossiers/data/dossiers.json";
const LEDGER_DATA_PATH = "/accountability-dossiers/data/ledger.json";

export const metadata = {
  title: "Dossiers de accountability | Vota Con La Chola",
  description:
    "Resumen estático issue-led y actor-led de responsabilidades, votos y actores vinculados con evidencia trazable.",
};

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function safeObject(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function formatRole(role) {
  const labels = {
    abstained: "abstención",
    appointed: "nombró",
    approved: "aprobó",
    delegated: "delegó",
    proposed: "propuso",
    responsible: "responsable",
    unknown: "sin señal",
    voted_against: "votó no",
    voted_for: "votó sí",
  };
  return labels[role] || role.replaceAll("_", " ");
}

function topPairs(map, limit = 4) {
  return Object.entries(safeObject(map))
    .map(([label, count]) => ({ label, count: Number(count) || 0 }))
    .sort((left, right) => right.count - left.count || left.label.localeCompare(right.label))
    .slice(0, limit);
}

function MetricCard({ label, value, note }) {
  return (
    <article className="accountability-dossier-metric kpiCard">
      <span className="accountability-dossier-metric__label kpiLabel">{label}</span>
      <strong className="accountability-dossier-metric__value kpiValue">{value}</strong>
      {note ? <span className="accountability-dossier-metric__note kpiLabel">{note}</span> : null}
    </article>
  );
}

function RolePills({ roles }) {
  const pairs = topPairs(roles);
  if (!pairs.length) {
    return <span className="accountability-role-pill pill pill-muted">sin rol</span>;
  }
  return (
    <div className="accountability-role-list chips" aria-label="Roles principales">
      {pairs.map((item) => (
        <span className="accountability-role-pill chip" key={item.label}>
          {formatRole(item.label)} · {formatInt(item.count)}
        </span>
      ))}
    </div>
  );
}

function IssueCard({ issue }) {
  return (
    <article className="accountability-issue-card kpiCard">
      <p className="accountability-issue-card__eyebrow eyebrow">{issue.scope || "sin ámbito"}</p>
      <h3 className="accountability-issue-card__title">
        <a className="accountability-issue-card__link" href={issueDossierHref(issue)}>
          {issue.label || issue.issue_id || "Tema sin título"}
        </a>
      </h3>
      <p className="accountability-issue-card__summary sub">{issue.summary || "Sin resumen disponible."}</p>
      <dl className="accountability-issue-card__facts">
        <div className="accountability-issue-card__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(issue.entries_total)}</dd>
        </div>
        <div className="accountability-issue-card__fact">
          <dt>Actores</dt>
          <dd>{formatInt(issue.actors_total)}</dd>
        </div>
        <div className="accountability-issue-card__fact">
          <dt>Fechas</dt>
          <dd>
            {formatDate(issue.first_date)} / {formatDate(issue.last_date)}
          </dd>
        </div>
      </dl>
      <RolePills roles={issue.roles} />
    </article>
  );
}

function ActorCard({ actor }) {
  const topIssue = safeArray(actor.top_issues)[0];
  return (
    <article className="accountability-actor-card kpiCard">
      <p className="accountability-actor-card__eyebrow eyebrow">{actor.actor_kind || "actor"}</p>
      <h3 className="accountability-actor-card__title">
        <a className="accountability-actor-card__link" href={actorDossierHref(actor)}>
          {actor.actor_label || actor.actor_key || "Actor sin título"}
        </a>
      </h3>
      <dl className="accountability-actor-card__facts">
        <div className="accountability-actor-card__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(actor.entries_total)}</dd>
        </div>
        <div className="accountability-actor-card__fact">
          <dt>Temas</dt>
          <dd>{formatInt(actor.issues_total)}</dd>
        </div>
        <div className="accountability-actor-card__fact">
          <dt>Identidad</dt>
          <dd>{actor.actor_key || "sin clave"}</dd>
        </div>
      </dl>
      {topIssue ? (
        <p className="accountability-actor-card__issue sub">
          Tema principal: {topIssue.issue_label || topIssue.issue_id}
        </p>
      ) : null}
      <RolePills roles={actor.roles} />
    </article>
  );
}

function EvidenceCard({ entry }) {
  return (
    <article className="accountability-evidence-card kpiCard">
      <div className="accountability-evidence-card__head">
        <p className="accountability-evidence-card__eyebrow eyebrow">tier {entry.evidence_tier || "sin tier"}</p>
        <span className="accountability-evidence-card__role chip">{formatRole(entry.accountability_role || "")}</span>
      </div>
      <h3 className="accountability-evidence-card__title">{entry.actor_label || "Actor sin etiqueta"}</h3>
      <p className="accountability-evidence-card__summary sub">{entry.summary || entry.title || "Sin resumen."}</p>
      <dl className="accountability-evidence-card__facts">
        <div className="accountability-evidence-card__fact">
          <dt>Fuente</dt>
          <dd>{entry.source_title || entry.source_id || "sin fuente"}</dd>
        </div>
        <div className="accountability-evidence-card__fact">
          <dt>Fecha</dt>
          <dd>{formatDate(entry.event_date || entry.published_date)}</dd>
        </div>
        <div className="accountability-evidence-card__fact">
          <dt>Localizador</dt>
          <dd>{entry.source_locator || entry.linked_object_id || entry.entry_id || "sin localizador"}</dd>
        </div>
        <div className="accountability-evidence-card__fact">
          <dt>Cita</dt>
          <dd>{entry.evidence_quote || "sin cita"}</dd>
        </div>
      </dl>
    </article>
  );
}

export default function AccountabilityDossiersPage() {
  const payload = readPublicJson(DOSSIER_DATA_PATH, {
    meta: {},
    coverage: {},
    actors: [],
    issues: [],
  });
  const ledger = readPublicJson(LEDGER_DATA_PATH, {
    issues: [],
  });
  const meta = safeObject(payload.meta);
  const coverage = safeObject(payload.coverage);
  const issues = safeArray(payload.issues);
  const actors = safeArray(payload.actors);
  const topIssues = issues.slice(0, 8);
  const topActors = actors.slice(0, 12);
  const evidenceSamples = safeArray(ledger.issues)
    .flatMap((issue) => safeArray(issue.entries))
    .slice(0, 12);

  return (
    <main className="accountability-dossiers-page shell">
      <section className="accountability-dossiers-hero hero card">
        <p className="accountability-dossiers-hero__eyebrow eyebrow">Accountability · dossiers</p>
        <h1 className="accountability-dossiers-hero__title">Qué hicieron, por tema y por actor</h1>
        <p className="accountability-dossiers-hero__summary sub">
          Corte compacto del ledger genérico: cada tema lista actores implicados y cada actor lista asuntos donde aparece.
        </p>
        <div className="accountability-dossiers-hero__actions chips">
          <a className="accountability-dossiers-hero__link chip" href={withBasePath(DOSSIER_DATA_PATH)}>
            Descargar dossiers JSON
          </a>
          <a className="accountability-dossiers-hero__link chip" href={withBasePath(LEDGER_DATA_PATH)}>
            Descargar ledger JSON
          </a>
          <a className="accountability-dossiers-hero__link chip" href="#accountability-evidence-samples">
            Ver evidencia
          </a>
          <a className="accountability-dossiers-hero__link chip" href={withBasePath("/accountability-evidence/")}>
            Evidence API
          </a>
          <a className="accountability-dossiers-hero__link chip" href={withBasePath("/explorer/")}>
            Auditar en SQL
          </a>
        </div>
      </section>

      <section className="accountability-dossier-metrics kpiGrid" aria-label="Cobertura del corte">
        <MetricCard label="Entradas" value={formatInt(coverage.entries_total)} note="filas de ledger" />
        <MetricCard label="Actores" value={formatInt(coverage.actors_total)} note="personas, grupos, partidos u organismos" />
        <MetricCard label="Temas" value={formatInt(coverage.issues_total)} note="issue-led dossiers" />
        <MetricCard label="Actor-tema" value={formatInt(coverage.issue_actor_edges_total)} note="pares resumidos" />
        <MetricCard label="Person IDs" value={formatInt(coverage.entries_with_person_id)} note="identidad normalizada" />
        <MetricCard label="Party IDs" value={formatInt(coverage.entries_with_party_id)} note="partido fuente-resuelto" />
        <MetricCard label="Grupo IDs" value={formatInt(coverage.entries_with_parliamentary_group_id)} note="grupo parlamentario resuelto" />
      </section>

      <section className="accountability-dossiers-status card block">
        <div className="accountability-dossiers-status__head blockHead">
          <h2 className="accountability-dossiers-status__title">Estado del artefacto</h2>
        </div>
        <dl className="accountability-dossiers-status__facts twoCols">
          <div className="accountability-dossiers-status__fact kpiCard">
            <dt>Schema</dt>
            <dd>{meta.schema_version || "sin schema"}</dd>
          </div>
          <div className="accountability-dossiers-status__fact kpiCard">
            <dt>Corte</dt>
            <dd>{meta.snapshot_date || payload.snapshot_date || "sin fecha"}</dd>
          </div>
          <div className="accountability-dossiers-status__fact kpiCard">
            <dt>Generado</dt>
            <dd>{meta.generated_at || "sin timestamp"}</dd>
          </div>
          <div className="accountability-dossiers-status__fact kpiCard">
            <dt>Truncado</dt>
            <dd>{coverage.actors_truncated || coverage.issues_truncated ? "sí" : "no"}</dd>
          </div>
        </dl>
      </section>

      <section className="accountability-issue-section card block">
        <div className="accountability-issue-section__head blockHead">
          <h2 className="accountability-issue-section__title">Temas con actores</h2>
        </div>
        <div className="accountability-issue-section__grid grid">
          {topIssues.length ? (
            topIssues.map((issue) => <IssueCard issue={issue} key={issue.issue_id || issue.label} />)
          ) : (
            <p className="accountability-issue-section__empty sub">Sin temas exportados en este corte.</p>
          )}
        </div>
      </section>

      <section className="accountability-actor-section card block">
        <div className="accountability-actor-section__head blockHead">
          <h2 className="accountability-actor-section__title">Actores con historial</h2>
        </div>
        <div className="accountability-actor-section__grid grid">
          {topActors.length ? (
            topActors.map((actor) => <ActorCard actor={actor} key={actor.actor_key || actor.actor_label} />)
          ) : (
            <p className="accountability-actor-section__empty sub">Sin actores exportados en este corte.</p>
          )}
        </div>
      </section>

      <section className="accountability-evidence-section card block" id="accountability-evidence-samples">
        <div className="accountability-evidence-section__head blockHead">
          <h2 className="accountability-evidence-section__title">Muestras de evidencia</h2>
        </div>
        <div className="accountability-evidence-section__grid grid">
          {evidenceSamples.length ? (
            evidenceSamples.map((entry) => <EvidenceCard entry={entry} key={entry.entry_id} />)
          ) : (
            <p className="accountability-evidence-section__empty sub">Sin filas de evidencia en el ledger publicado.</p>
          )}
        </div>
      </section>
    </main>
  );
}
