import { formatInt, readPublicJson } from "../static-snapshot.mjs";
import { StaticRouteHero, StaticRouteLink } from "../static-route-components";
import styles from "./geopolitics.module.css";

const EMPTY_SNAPSHOT = {
  source: {},
  policy: {},
  coverage: {},
  limitations: [],
  records: [],
};

export const metadata = {
  title: "Geopolítica con evidencia oficial | Vota Con La Chola",
  description:
    "Acciones de política exterior con etapa jurídica, actores, texto oficial y límites explícitos sobre vigencia, ejecución e impacto.",
};

const ACTOR_ROLES = {
  acting_state: "Estado parte",
  approving_body: "Órgano que aprueba",
  publishing_body: "Publica",
  parliamentary_recipient: "Remisión parlamentaria",
  counterparty_state: "Estado contraparte",
  counterparty_organization: "Organización contraparte",
};

const SCOPE_LABELS = {
  bilateral: "bilateral",
  multilateral: "multilateral",
  global: "global",
  domestic_external: "acción doméstica con alcance exterior",
  unknown: "alcance desconocido",
};

function shortHash(value) {
  const raw = String(value || "");
  return raw ? `${raw.slice(0, 12)}…` : "sin hash";
}

function formatDate(value) {
  const raw = String(value || "");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw || "fecha desconocida";
  return new Intl.DateTimeFormat("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${raw}T00:00:00Z`));
}

function stateLabel(value) {
  if (value === "not_assessed") return "no evaluado";
  if (value === "unknown") return "desconocido";
  return String(value || "no publicado");
}

function GeopoliticalActionCard({ record, index }) {
  const evidence = record.evidence?.[0];

  return (
    <li className={`geopolitics-action-list__item ${styles.actionItem}`}>
      <article className={`geopolitics-action-card ${styles.actionCard}`}>
        <header className={`geopolitics-action-card__header ${styles.cardHeader}`}>
          <div className="geopolitics-action-card__identity">
            <span className={`geopolitics-action-card__ordinal ${styles.ordinal}`}>
              Acción {String(index + 1).padStart(2, "0")} · {formatDate(record.action_date)}
            </span>
            <h3 className={`geopolitics-action-card__title ${styles.cardTitle}`}>
              {record.title}
            </h3>
          </div>
          <span className={`geopolitics-action-card__status ${styles.statusBadge}`}>
            autorización doméstica
          </span>
        </header>

        <div className={`geopolitics-action-card__scope ${styles.scopeLine}`}>
          <span className="geopolitics-action-card__scope-label">Alcance clasificado</span>
          <strong className="geopolitics-action-card__scope-value">
            {SCOPE_LABELS[record.scope_kind] || record.scope_kind}
          </strong>
          <span className="geopolitics-action-card__scope-method">regla derivada</span>
        </div>

        <blockquote className={`geopolitics-action-card__evidence-quote ${styles.quote}`}>
          {evidence?.exact_quote || record.summary}
        </blockquote>

        <section className={`geopolitics-action-card__actors ${styles.cardSection}`} aria-label="Actores publicados por la fuente">
          <h4 className={`geopolitics-action-card__section-title ${styles.cardSectionTitle}`}>
            Actores y papel en este registro
          </h4>
          <ul className={`geopolitics-action-card__actor-list ${styles.actorList}`}>
            {(record.actors || []).map((actor) => (
              <li className={`geopolitics-action-card__actor ${styles.actorChip}`} key={actor.geopolitical_action_actor_id}>
                <span className={`geopolitics-action-card__actor-role ${styles.actorRole}`}>
                  {ACTOR_ROLES[actor.actor_role] || actor.actor_role}
                </span>
                <strong className="geopolitics-action-card__actor-name">{actor.source_label}</strong>
              </li>
            ))}
          </ul>
        </section>

        <section className={`geopolitics-action-card__topics ${styles.cardSection}`} aria-label="Temas derivados sin revisión humana">
          <h4 className={`geopolitics-action-card__section-title ${styles.cardSectionTitle}`}>
            Temas · regla sin revisar
          </h4>
          <ul className={`geopolitics-action-card__topic-list ${styles.topicList}`}>
            {(record.topics || []).map((topic) => (
              <li className={`geopolitics-action-card__topic ${styles.topicChip}`} key={topic.geopolitical_action_topic_id}>
                {topic.topic_label}
              </li>
            ))}
          </ul>
        </section>

        <dl className={`geopolitics-action-card__state-grid ${styles.stateGrid}`}>
          <div className="geopolitics-action-card__state">
            <dt className="geopolitics-action-card__state-label">Vinculante</dt>
            <dd className="geopolitics-action-card__state-value">{stateLabel(record.binding_state)}</dd>
          </div>
          <div className="geopolitics-action-card__state">
            <dt className="geopolitics-action-card__state-label">Entrada en vigor</dt>
            <dd className="geopolitics-action-card__state-value">{stateLabel(record.entry_into_force_state)}</dd>
          </div>
          <div className="geopolitics-action-card__state">
            <dt className="geopolitics-action-card__state-label">Implementación</dt>
            <dd className="geopolitics-action-card__state-value">{stateLabel(record.implementation_state)}</dd>
          </div>
          <div className="geopolitics-action-card__state">
            <dt className="geopolitics-action-card__state-label">Resultado</dt>
            <dd className="geopolitics-action-card__state-value">{stateLabel(record.outcome_state)}</dd>
          </div>
        </dl>

        <footer className={`geopolitics-action-card__footer ${styles.cardFooter}`}>
          <StaticRouteLink href={evidence?.source_url}>Abrir referencia oficial</StaticRouteLink>
          <code className={`geopolitics-action-card__hash ${styles.hash}`}>
            registro {shortHash(evidence?.content_sha256)}
          </code>
        </footer>
      </article>
    </li>
  );
}

export default function GeopoliticsPage() {
  const snapshot = readPublicJson(
    "geopolitics/data/moncloa-sample.json",
    EMPTY_SNAPSHOT,
  );
  const coverage = snapshot.coverage || {};

  return (
    <main className={`shell geopolitics-page ${styles.page}`}>
      <StaticRouteHero
        actions={[
          { href: "/geopolitics/data/moncloa-sample.json", label: "Descargar muestra JSON" },
          { href: snapshot.source?.source_url, label: "Abrir fuente La Moncloa" },
        ]}
        eyebrow="Política exterior · etapa jurídica · evidencia"
        meta={[
          { label: "Fuente", value: "La Moncloa" },
          { label: "Acciones", value: formatInt(coverage.actions) },
          { label: "Release", value: shortHash(snapshot.release_id) },
        ]}
        summary="Dos acciones exteriores reales con texto, fecha, actores y etapa procesal. Se publica lo que el Gobierno documentó. Vigencia, ejecución, alineamiento e impacto siguen como no evaluados."
        title="Geopolítica sin rellenar los huecos"
      />

      <section className={`geopolitics-truth-panel ${styles.truthPanel}`} aria-labelledby="geopolitics-truth-title">
        <div className="geopolitics-truth-panel__copy">
          <p className={`geopolitics-truth-panel__eyebrow ${styles.eyebrow}`}>Contrato de lectura</p>
          <h2 className={`geopolitics-truth-panel__title ${styles.sectionTitle}`} id="geopolitics-truth-title">
            Autorización no significa tratado en vigor
          </h2>
          <p className={`geopolitics-truth-panel__summary ${styles.sectionCopy}`}>
            La fuente acredita que el Consejo de Ministros aprobó la remisión a las Cortes y autorizó manifestar el consentimiento de España. No acredita aquí firma, ratificación, entrada en vigor, implementación, uso ni resultado.
          </p>
        </div>
        <dl className={`geopolitics-truth-panel__metrics ${styles.metricGrid}`}>
          <div className={`geopolitics-truth-panel__metric ${styles.metric}`}>
            <dt className="geopolitics-truth-panel__metric-label">Referencias capturadas</dt>
            <dd className="geopolitics-truth-panel__metric-value">{formatInt(coverage.source_records)}</dd>
          </div>
          <div className={`geopolitics-truth-panel__metric ${styles.metric}`}>
            <dt className="geopolitics-truth-panel__metric-label">Acciones exteriores</dt>
            <dd className="geopolitics-truth-panel__metric-value">{formatInt(coverage.actions)}</dd>
          </div>
          <div className={`geopolitics-truth-panel__metric ${styles.metric}`}>
            <dt className="geopolitics-truth-panel__metric-label">Actores publicados</dt>
            <dd className="geopolitics-truth-panel__metric-value">{formatInt(coverage.actors)}</dd>
          </div>
          <div className={`geopolitics-truth-panel__metric ${styles.metric}`}>
            <dt className="geopolitics-truth-panel__metric-label">Inferencias geopolíticas</dt>
            <dd className="geopolitics-truth-panel__metric-value">0</dd>
          </div>
        </dl>
      </section>

      <section className={`geopolitics-coverage-panel ${styles.coveragePanel}`} aria-labelledby="geopolitics-coverage-title">
        <div className="geopolitics-coverage-panel__copy">
          <p className={`geopolitics-coverage-panel__eyebrow ${styles.eyebrow}`}>Cobertura honesta</p>
          <h2 className={`geopolitics-coverage-panel__title ${styles.sectionTitle}`} id="geopolitics-coverage-title">
            Dos hechos verificables; no una historia completa de política exterior
          </h2>
          <p className={`geopolitics-coverage-panel__summary ${styles.sectionCopy}`}>
            Esta primera vertical prueba el modelo sobre tratados y contrapartes internacionales. Faltan fuentes posteriores que demuestren publicación jurídica, entrada en vigor, ejecución y resultados.
          </p>
        </div>
        <dl className={`geopolitics-coverage-panel__limits ${styles.limitGrid}`}>
          <div className="geopolitics-coverage-panel__limit">
            <dt className="geopolitics-coverage-panel__limit-label">Posiciones explícitas</dt>
            <dd className="geopolitics-coverage-panel__limit-value">{formatInt(coverage.positions)}</dd>
          </div>
          <div className="geopolitics-coverage-panel__limit">
            <dt className="geopolitics-coverage-panel__limit-label">Observaciones posteriores</dt>
            <dd className="geopolitics-coverage-panel__limit-value">{formatInt(coverage.later_observations)}</dd>
          </div>
          <div className="geopolitics-coverage-panel__limit">
            <dt className="geopolitics-coverage-panel__limit-label">Etapas en vigor probadas</dt>
            <dd className="geopolitics-coverage-panel__limit-value">0</dd>
          </div>
        </dl>
      </section>

      <section className={`geopolitics-sample-section ${styles.sampleSection}`} aria-labelledby="geopolitics-sample-title">
        <header className={`geopolitics-sample-section__header ${styles.sectionHeader}`}>
          <div className="geopolitics-sample-section__heading">
            <p className={`geopolitics-sample-section__eyebrow ${styles.eyebrow}`}>
              Fuente → acción → actores → etapa → evidencia
            </p>
            <h2 className={`geopolitics-sample-section__title ${styles.sectionTitle}`} id="geopolitics-sample-title">
              Acciones oficiales y estados desconocidos a la vista
            </h2>
          </div>
          <p className={`geopolitics-sample-section__note ${styles.sectionNote}`}>
            Cada nombre procede del registro oficial. Las etiquetas temáticas y de alcance muestran que son clasificaciones derivadas sin revisión humana.
          </p>
        </header>
        <ol className={`geopolitics-action-list ${styles.actionList}`}>
          {(snapshot.records || []).map((record, index) => (
            <GeopoliticalActionCard
              index={index}
              key={record.geopolitical_action_id}
              record={record}
            />
          ))}
        </ol>
      </section>
    </main>
  );
}
