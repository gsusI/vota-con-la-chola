import { notFound } from "next/navigation";
import { withBasePath } from "../../../path-utils.mjs";
import { formatDate, formatInt } from "../../../static-snapshot.mjs";
import {
  actorKeyFromEntry,
  actorSlug,
  allLedgerEntries,
  findActorBySlug,
  findIssueById,
  formatRole,
  issueDossierHref,
  loadDossierPayload,
  loadLedgerPayload,
  safeArray,
  topPairs,
} from "../../dossier-utils.mjs";

const EMPTY_ACTOR_SLUG = "no-actors-exported";

export const dynamicParams = false;

export async function generateStaticParams() {
  const payload = loadDossierPayload();
  const params = safeArray(payload.actors).map((actor) => ({ actorSlug: actorSlug(actor) }));
  return params.length ? params : [{ actorSlug: EMPTY_ACTOR_SLUG }];
}

export async function generateMetadata({ params }) {
  const { actorSlug: currentSlug } = await params;
  const actor = findActorBySlug(loadDossierPayload(), currentSlug);
  if (!actor && currentSlug === EMPTY_ACTOR_SLUG) {
    return {
      title: "Sin actores exportados | Vota Con La Chola",
      description: "El corte publico actual no contiene actores de accountability exportados.",
    };
  }
  if (!actor) {
    return {
      title: "Actor no encontrado | Vota Con La Chola",
      description: "No encontramos ese actor en el corte publico actual.",
    };
  }
  return {
    title: `${actor.actor_label || actor.actor_key || "Actor"} | Dossier de accountability`,
    description: `Historial auditable por tema y rol para ${actor.actor_label || actor.actor_key || "este actor"}.`,
  };
}

function RolePills({ roles }) {
  const pairs = topPairs(roles, 6);
  if (!pairs.length) {
    return <span className="accountability-detail-role-pill pill pill-muted">sin rol</span>;
  }
  return (
    <div className="accountability-detail-role-list chips" aria-label="Roles del actor">
      {pairs.map((item) => (
        <span className="accountability-detail-role-pill chip" key={item.label}>
          {formatRole(item.label)} · {formatInt(item.count)}
        </span>
      ))}
    </div>
  );
}

function ActorMetric({ label, value, note }) {
  return (
    <article className="accountability-actor-detail-metric kpiCard">
      <span className="accountability-actor-detail-metric__label kpiLabel">{label}</span>
      <strong className="accountability-actor-detail-metric__value kpiValue">{value}</strong>
      {note ? <span className="accountability-actor-detail-metric__note kpiLabel">{note}</span> : null}
    </article>
  );
}

function IdentityFacts({ actor }) {
  const facts = [
    ["Clave", actor.actor_key],
    ["Persona", actor.person_id ? `person_id:${actor.person_id}` : ""],
    ["Partido", actor.party_id ? `party_id:${actor.party_id}` : ""],
    ["Grupo", actor.parliamentary_group_id ? `parliamentary_group_id:${actor.parliamentary_group_id}` : ""],
    ["Mandato", actor.mandate_id ? `mandate_id:${actor.mandate_id}` : ""],
    ["Institucion", actor.institution_id ? `institution_id:${actor.institution_id}` : ""],
  ].filter(([, value]) => value);

  return (
    <dl className="accountability-actor-identity__facts twoCols">
      {facts.map(([label, value]) => (
        <div className="accountability-actor-identity__fact kpiCard" key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function IssueRow({ item, payload }) {
  const issue = findIssueById(payload, item.issue_id) || item;
  return (
    <article className="accountability-actor-issue-row kpiCard">
      <p className="accountability-actor-issue-row__eyebrow eyebrow">{issue.scope || "tema"}</p>
      <h3 className="accountability-actor-issue-row__title">
        <a className="accountability-actor-issue-row__link" href={issueDossierHref(issue)}>
          {item.issue_label || issue.label || item.issue_id}
        </a>
      </h3>
      <dl className="accountability-actor-issue-row__facts">
        <div className="accountability-actor-issue-row__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(item.entries_total)}</dd>
        </div>
        <div className="accountability-actor-issue-row__fact">
          <dt>Fechas</dt>
          <dd>
            {formatDate(item.first_date)} / {formatDate(item.last_date)}
          </dd>
        </div>
      </dl>
      <RolePills roles={item.roles} />
    </article>
  );
}

function EvidenceRow({ entry }) {
  const sourceUrl = String(entry.source_url || "").trim();
  const hasSourceLink = sourceUrl.startsWith("http://") || sourceUrl.startsWith("https://");
  return (
    <article className="accountability-actor-evidence-row kpiCard">
      <div className="accountability-actor-evidence-row__head">
        <p className="accountability-actor-evidence-row__eyebrow eyebrow">tier {entry.evidence_tier || "sin tier"}</p>
        <span className="accountability-actor-evidence-row__role chip">{formatRole(entry.accountability_role)}</span>
      </div>
      <h3 className="accountability-actor-evidence-row__title">{entry.issue_label || entry.title || entry.issue_id}</h3>
      <p className="accountability-actor-evidence-row__summary sub">{entry.summary || "Sin resumen."}</p>
      <dl className="accountability-actor-evidence-row__facts">
        <div className="accountability-actor-evidence-row__fact">
          <dt>Fecha</dt>
          <dd>{formatDate(entry.event_date || entry.published_date)}</dd>
        </div>
        <div className="accountability-actor-evidence-row__fact">
          <dt>Fuente</dt>
          <dd>
            {hasSourceLink ? (
              <a className="accountability-actor-evidence-row__source-link" href={sourceUrl}>
                {entry.source_title || entry.source_id || "fuente"}
              </a>
            ) : (
              entry.source_title || entry.source_id || "sin fuente"
            )}
          </dd>
        </div>
        <div className="accountability-actor-evidence-row__fact">
          <dt>Localizador</dt>
          <dd>{entry.source_locator || entry.linked_object_id || entry.entry_id || "sin localizador"}</dd>
        </div>
        <div className="accountability-actor-evidence-row__fact">
          <dt>Cita</dt>
          <dd>{entry.evidence_quote || "sin cita"}</dd>
        </div>
      </dl>
    </article>
  );
}

function EmptyActorDossierPage() {
  return (
    <main className="accountability-actor-empty-page shell">
      <section className="accountability-actor-empty-hero hero card">
        <p className="accountability-actor-empty-hero__eyebrow eyebrow">Dossier de actor</p>
        <h1 className="accountability-actor-empty-hero__title">Sin actores exportados</h1>
        <p className="accountability-actor-empty-hero__summary sub">
          Este snapshot no contiene filas de accountability con actores. El catalogo de fuentes y el ledger JSON siguen disponibles para auditoria.
        </p>
        <div className="accountability-actor-empty-hero__actions chips">
          <a className="accountability-actor-empty-hero__link chip" href={withBasePath("/accountability-dossiers/")}>
            Volver a dossiers
          </a>
          <a className="accountability-actor-empty-hero__link chip" href={withBasePath("/accountability-dossiers/data/ledger.json")}>
            Ledger JSON
          </a>
        </div>
      </section>
    </main>
  );
}

export default async function AccountabilityActorDossierPage({ params }) {
  const { actorSlug: currentSlug } = await params;
  const payload = loadDossierPayload();
  const actor = findActorBySlug(payload, currentSlug);
  if (!actor) {
    if (currentSlug === EMPTY_ACTOR_SLUG) {
      return <EmptyActorDossierPage />;
    }
    return notFound();
  }

  const ledger = loadLedgerPayload();
  const fullActorEntries = allLedgerEntries(ledger).filter((entry) => actorKeyFromEntry(entry) === actor.actor_key);
  const ledgerActor = safeArray(ledger.actors).find((item) => item.actor_key === actor.actor_key) || {};
  const sampledActorEntries = safeArray(ledgerActor.sample_entries).map((entry) => ({
    ...entry,
    actor_label: entry.actor_label || actor.actor_label,
    actor_kind: actor.actor_kind,
  }));
  const seenEntryIds = new Set(fullActorEntries.map((entry) => entry.entry_id).filter(Boolean));
  const fallbackEntries = sampledActorEntries.filter((entry) => !entry.entry_id || !seenEntryIds.has(entry.entry_id));
  const actorEntries = [...fullActorEntries, ...fallbackEntries].slice(0, 60);
  const topIssues = safeArray(actor.top_issues);

  return (
    <main className="accountability-actor-detail-page shell">
      <section className="accountability-actor-detail-hero hero card">
        <p className="accountability-actor-detail-hero__eyebrow eyebrow">Dossier de actor · {actor.actor_kind || "actor"}</p>
        <h1 className="accountability-actor-detail-hero__title">{actor.actor_label || actor.actor_key || "Actor sin titulo"}</h1>
        <p className="accountability-actor-detail-hero__summary sub">
          Historial agregado desde el ledger generico: temas, roles, fechas, identidad resuelta y evidencia trazable.
        </p>
        <div className="accountability-actor-detail-hero__actions chips">
          <a className="accountability-actor-detail-hero__link chip" href={withBasePath("/accountability-dossiers/")}>
            Volver a dossiers
          </a>
          <a className="accountability-actor-detail-hero__link chip" href={withBasePath("/accountability-dossiers/data/ledger.json")}>
            Ledger JSON
          </a>
          <a className="accountability-actor-detail-hero__link chip" href={withBasePath("/explorer/")}>
            Auditar en SQL
          </a>
        </div>
      </section>

      <section className="accountability-actor-detail-metrics kpiGrid" aria-label="Cobertura del actor">
        <ActorMetric label="Entradas" value={formatInt(actor.entries_total)} note="filas vinculadas" />
        <ActorMetric label="Temas" value={formatInt(actor.issues_total)} note="issues distintos" />
        <ActorMetric label="Desde" value={formatDate(actor.first_date)} note="primera evidencia" />
        <ActorMetric label="Hasta" value={formatDate(actor.last_date)} note="ultima evidencia" />
      </section>

      <section className="accountability-actor-identity block">
        <div className="accountability-actor-identity__head blockHead">
          <h2 className="accountability-actor-identity__title">Identidad y roles</h2>
        </div>
        <IdentityFacts actor={actor} />
        <RolePills roles={actor.roles} />
      </section>

      <section className="accountability-actor-issues block">
        <div className="accountability-actor-issues__head blockHead">
          <h2 className="accountability-actor-issues__title">Temas donde aparece</h2>
        </div>
        <div className="accountability-actor-issues__grid grid">
          {topIssues.length ? (
            topIssues.map((item) => <IssueRow item={item} payload={payload} key={item.issue_id} />)
          ) : (
            <p className="accountability-actor-issues__empty sub">Sin temas exportados para este actor.</p>
          )}
        </div>
      </section>

      <section className="accountability-actor-evidence block">
        <div className="accountability-actor-evidence__head blockHead">
          <h2 className="accountability-actor-evidence__title">Evidencia del actor</h2>
        </div>
        <div className="accountability-actor-evidence__grid grid">
          {actorEntries.length ? (
            actorEntries.map((entry) => <EvidenceRow entry={entry} key={entry.entry_id} />)
          ) : (
            <p className="accountability-actor-evidence__empty sub">Sin filas de evidencia detallada en el ledger compacto.</p>
          )}
        </div>
      </section>
    </main>
  );
}
