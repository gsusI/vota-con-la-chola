import { formatInt, readPublicJson } from "../static-snapshot.mjs";
import { StaticRouteHero, StaticRouteLink } from "../static-route-components";
import styles from "./actor-graph.module.css";

const EMPTY_SNAPSHOT = {
  meta: {},
  policy: {},
  coverage: {
    actors_by_kind: {},
    actors_by_subtype: {},
    database_counts: {},
    evidence_by_kind: {},
    relationships_by_type: {},
    resolution_outcomes: {},
  },
  methodology: {},
  limitations: [],
  sample_contract: {},
  sample_nodes: [],
  sample_relationships: [],
};

export const metadata = {
  title: "Grafo de actores con evidencia | Vota Con La Chola",
  description:
    "Actores públicos y relaciones políticas, institucionales, electorales y económicas con alcance de identidad, vigencia y evidencia oficial.",
};

const ACTOR_KIND_LABELS = {
  person: "Personas",
  organization: "Organizaciones",
  office: "Cargos",
  unknown: "Tipo sin resolver",
};

const ACTOR_SUBTYPE_LABELS = {
  government_position: "Cargo público",
  institution: "Institución",
  international_organization: "Organización internacional",
  organization: "Organización",
  parliamentary_group: "Grupo parlamentario",
  party: "Partido",
  person: "Persona observada",
  person_registry: "Persona en registro",
  public_body: "Organismo público",
  state: "Estado",
  unknown: "Tipo sin resolver",
};

const RELATIONSHIP_LABELS = {
  acts_in_geopolitical_action: "Interviene en acción exterior",
  acts_in_spending_item: "Interviene en adjudicación",
  affiliated_with_party: "Figura afiliado a partido",
  candidate_for: "Candidato en lista",
  effective_candidate_for: "Candidato efectivo en lista",
  elected_in: "Resultó electo en",
  holds_role_at: "Ocupa cargo en",
  member_of_organization: "Miembro de organización",
  member_of_parliamentary_group: "Miembro de grupo parlamentario",
  participates_in_meeting: "Participa en reunión",
  party_to_agreement: "Interviene en acuerdo",
  publishes_manifesto: "Publica programa electoral",
};

const CONTEXT_LABELS = {
  agreement: "acuerdo oficial",
  candidate_occurrence: "candidatura electoral",
  effective_candidate_occurrence: "candidatura electoral efectiva",
  election_result: "resultado electoral",
  geopolitical_action: "acción exterior",
  manifesto_document: "programa electoral",
  meeting: "reunión oficial",
  spending_item: "adjudicación pública",
};

const EVIDENCE_LABELS = {
  exact_document: "documento exacto",
  exact_record: "registro exacto",
  source_default: "fuente general",
};

function shortHash(value) {
  const raw = String(value || "");
  return raw ? `${raw.slice(0, 12)}…` : "sin hash";
}

function formatDate(value) {
  const raw = String(value || "").trim();
  if (!raw) return "fecha no publicada";
  const datePart = raw.slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(datePart)) return raw;
  return new Intl.DateTimeFormat("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${datePart}T00:00:00Z`));
}

function firstBy(items, key) {
  const selected = new Map();
  for (const item of Array.isArray(items) ? items : []) {
    const value = String(item?.[key] || "unknown");
    if (!selected.has(value)) selected.set(value, item);
  }
  return [...selected.values()];
}

function ActorSample({ actor }) {
  return (
    <li className={`actor-sample-list__item ${styles.actorSampleItem}`}>
      <article className={`actor-sample-card ${styles.actorSampleCard}`}>
        <header className={`actor-sample-card__header ${styles.actorSampleHeader}`}>
          <span className={`actor-sample-card__type ${styles.actorTypeBadge}`}>
            {ACTOR_SUBTYPE_LABELS[actor.actor_subtype] || actor.actor_subtype}
          </span>
          <span className={`actor-sample-card__scope ${styles.scopeBadge}`}>alcance: fuente</span>
        </header>
        <h3 className={`actor-sample-card__name ${styles.actorSampleName}`}>
          {actor.canonical_label || "Nombre no publicado"}
        </h3>
        <dl className={`actor-sample-card__metadata ${styles.actorMetadata}`}>
          <div className="actor-sample-card__metadata-item">
            <dt className="actor-sample-card__metadata-label">Fuente</dt>
            <dd className="actor-sample-card__metadata-value">{actor.source_scope_id || "sin fuente"}</dd>
          </div>
          <div className="actor-sample-card__metadata-item">
            <dt className="actor-sample-card__metadata-label">Observado</dt>
            <dd className="actor-sample-card__metadata-value">{formatDate(actor.observed_at)}</dd>
          </div>
          <div className="actor-sample-card__metadata-item">
            <dt className="actor-sample-card__metadata-label">Evidencia</dt>
            <dd className="actor-sample-card__metadata-value">
              {EVIDENCE_LABELS[actor.provenance_state] || actor.provenance_state || "sin clasificar"}
            </dd>
          </div>
        </dl>
        <footer className={`actor-sample-card__footer ${styles.actorSampleFooter}`}>
          <StaticRouteLink href={actor.source_url}>Abrir fuente oficial</StaticRouteLink>
          <code className={`actor-sample-card__id ${styles.identifier}`}>{shortHash(actor.actor_id)}</code>
        </footer>
      </article>
    </li>
  );
}

function RelationshipSample({ relationship }) {
  const objectLabel = relationship.object_label
    || CONTEXT_LABELS[relationship.context_kind]
    || "contexto publicado";

  return (
    <li className={`relationship-sample-list__item ${styles.relationshipSampleItem}`}>
      <article className={`relationship-sample-card ${styles.relationshipSampleCard}`}>
        <header className={`relationship-sample-card__header ${styles.relationshipSampleHeader}`}>
          <span className={`relationship-sample-card__type ${styles.relationshipType}`}>
            {RELATIONSHIP_LABELS[relationship.relationship_type] || relationship.relationship_type}
          </span>
          <span className={`relationship-sample-card__evidence ${styles.evidenceBadge}`}>
            {EVIDENCE_LABELS[relationship.evidence_kind] || relationship.evidence_kind}
          </span>
        </header>

        <div className={`relationship-sample-card__path ${styles.relationshipPath}`}>
          <strong className={`relationship-sample-card__subject ${styles.pathNode}`}>
            {relationship.subject_label || "Actor sin etiqueta"}
          </strong>
          <div className={`relationship-sample-card__edge ${styles.pathEdge}`}>
            <span className={`relationship-sample-card__edge-line ${styles.pathEdgeLine}`} aria-hidden="true" />
            <span className={`relationship-sample-card__edge-label ${styles.pathEdgeLabel}`}>
              {relationship.role_label || "relación publicada"}
            </span>
          </div>
          <strong className={`relationship-sample-card__object ${styles.pathNode}`}>
            {objectLabel}
          </strong>
        </div>

        <dl className={`relationship-sample-card__metadata ${styles.relationshipMetadata}`}>
          <div className="relationship-sample-card__metadata-item">
            <dt className="relationship-sample-card__metadata-label">Vigencia desde</dt>
            <dd className="relationship-sample-card__metadata-value">{formatDate(relationship.valid_from)}</dd>
          </div>
          <div className="relationship-sample-card__metadata-item">
            <dt className="relationship-sample-card__metadata-label">Vigencia hasta</dt>
            <dd className="relationship-sample-card__metadata-value">{formatDate(relationship.valid_to)}</dd>
          </div>
          <div className="relationship-sample-card__metadata-item">
            <dt className="relationship-sample-card__metadata-label">Fuente</dt>
            <dd className="relationship-sample-card__metadata-value">{relationship.source_id}</dd>
          </div>
        </dl>

        <footer className={`relationship-sample-card__footer ${styles.relationshipSampleFooter}`}>
          <StaticRouteLink href={relationship.source_url}>Comprobar registro oficial</StaticRouteLink>
          <code className={`relationship-sample-card__id ${styles.identifier}`}>
            {shortHash(relationship.relationship_id)}
          </code>
        </footer>
      </article>
    </li>
  );
}

export default function ActorGraphPage() {
  const snapshot = readPublicJson("actor-graph/data/graph.json", EMPTY_SNAPSHOT);
  const coverage = snapshot.coverage || EMPTY_SNAPSHOT.coverage;
  const databaseCounts = coverage.database_counts || {};
  const actorKinds = Object.entries(coverage.actors_by_kind || {});
  const relationshipTypes = Object.entries(coverage.relationships_by_type || {})
    .sort((left, right) => Number(right[1]) - Number(left[1]));
  const largestRelationshipCount = Math.max(
    ...relationshipTypes.map(([, count]) => Number(count) || 0),
    1,
  );
  const actorSamples = firstBy(snapshot.sample_nodes, "actor_subtype");
  const relationshipSamples = firstBy(snapshot.sample_relationships, "relationship_type");

  return (
    <main className={`shell actor-graph-page ${styles.page}`}>
      <StaticRouteHero
        actions={[
          { href: "/actor-graph/data/graph.json", label: "Descargar corte JSON" },
          { href: "/actors/", label: "Volver al hub de actores" },
        ]}
        eyebrow="Actores · relaciones · vigencia · evidencia"
        meta={[
          { label: "Actores", value: formatInt(databaseCounts.actor_graph_nodes) },
          { label: "Relaciones", value: formatInt(databaseCounts.actor_graph_relationships) },
          { label: "Corte", value: formatDate(snapshot.meta?.snapshot_date) },
          { label: "Release", value: shortHash(snapshot.meta?.release_id) },
        ]}
        summary="Mapa temporal de personas, partidos, instituciones, cargos y organizaciones construido solo con registros públicos reales. Cada identidad conserva su fuente; cada relación baja a evidencia."
        title="Quién aparece conectado con qué"
      />

      <section className={`actor-graph-identity-panel ${styles.identityPanel}`} aria-labelledby="actor-graph-identity-title">
        <div className="actor-graph-identity-panel__copy">
          <p className={`actor-graph-identity-panel__eyebrow ${styles.eyebrow}`}>Regla de identidad</p>
          <h2 className={`actor-graph-identity-panel__title ${styles.sectionTitle}`} id="actor-graph-identity-title">
            Mismo nombre no significa misma persona
          </h2>
          <p className={`actor-graph-identity-panel__summary ${styles.sectionCopy}`}>
            El nombre por sí solo nunca fusiona actores entre fuentes. Esta primera release mantiene cada identidad dentro de su registro de origen hasta disponer de identificadores o evidencia revisable suficiente.
          </p>
        </div>
        <dl className={`actor-graph-identity-panel__metrics ${styles.identityMetrics}`}>
          <div className={`actor-graph-identity-panel__metric ${styles.identityMetric}`}>
            <dt className="actor-graph-identity-panel__metric-label">Ámbitos de fuente</dt>
            <dd className="actor-graph-identity-panel__metric-value">{formatInt(coverage.source_scopes)}</dd>
          </div>
          <div className={`actor-graph-identity-panel__metric ${styles.identityMetric}`}>
            <dt className="actor-graph-identity-panel__metric-label">Identidades fuente-específicas</dt>
            <dd className="actor-graph-identity-panel__metric-value">
              {formatInt(coverage.resolution_outcomes?.source_scoped)}
            </dd>
          </div>
          <div className={`actor-graph-identity-panel__metric ${styles.identityMetric}`}>
            <dt className="actor-graph-identity-panel__metric-label">Fusiones entre fuentes publicadas</dt>
            <dd className="actor-graph-identity-panel__metric-value">{formatInt(coverage.cross_source_resolved_actors)}</dd>
          </div>
          <div className={`actor-graph-identity-panel__metric ${styles.identityMetric}`}>
            <dt className="actor-graph-identity-panel__metric-label">Nombres oficiales ocultados</dt>
            <dd className="actor-graph-identity-panel__metric-value">0</dd>
          </div>
        </dl>
      </section>

      <section className={`actor-graph-scale-section ${styles.scaleSection}`} aria-labelledby="actor-graph-scale-title">
        <header className={`actor-graph-scale-section__header ${styles.sectionHeader}`}>
          <div className="actor-graph-scale-section__heading">
            <p className={`actor-graph-scale-section__eyebrow ${styles.eyebrow}`}>Cobertura del corpus seleccionado en SQLite</p>
            <h2 className={`actor-graph-scale-section__title ${styles.sectionTitle}`} id="actor-graph-scale-title">
              Grafo materializado; navegador deliberadamente acotado
            </h2>
          </div>
          <p className={`actor-graph-scale-section__note ${styles.sectionNote}`}>
            El archivo web publica agregados completos y una muestra estable de {formatInt(snapshot.sample_nodes?.length)} actores y {formatInt(snapshot.sample_relationships?.length)} relaciones. No descarga las {formatInt(databaseCounts.actor_graph_relationships)} relaciones al móvil.
          </p>
        </header>

        <div className={`actor-graph-scale-section__body ${styles.scaleBody}`}>
          <dl className={`actor-graph-kind-grid ${styles.kindGrid}`} aria-label="Actores por tipo principal">
            {actorKinds.map(([kind, count]) => (
              <div className={`actor-graph-kind-grid__item ${styles.kindMetric}`} key={kind}>
                <dt className="actor-graph-kind-grid__label">{ACTOR_KIND_LABELS[kind] || kind}</dt>
                <dd className="actor-graph-kind-grid__value">{formatInt(count)}</dd>
              </div>
            ))}
          </dl>

          <dl className={`actor-graph-evidence-grid ${styles.evidenceGrid}`} aria-label="Evidencia de relaciones">
            <div className="actor-graph-evidence-grid__item">
              <dt className="actor-graph-evidence-grid__label">Documento exacto</dt>
              <dd className="actor-graph-evidence-grid__value">{formatInt(coverage.evidence_by_kind?.exact_document)}</dd>
            </div>
            <div className="actor-graph-evidence-grid__item">
              <dt className="actor-graph-evidence-grid__label">Registro exacto</dt>
              <dd className="actor-graph-evidence-grid__value">{formatInt(coverage.evidence_by_kind?.exact_record)}</dd>
            </div>
            <div className="actor-graph-evidence-grid__item">
              <dt className="actor-graph-evidence-grid__label">Fuente general</dt>
              <dd className="actor-graph-evidence-grid__value">{formatInt(coverage.evidence_by_kind?.source_default)}</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className={`actor-graph-relationship-coverage ${styles.relationshipCoverage}`} aria-labelledby="actor-graph-relationship-coverage-title">
        <header className={`actor-graph-relationship-coverage__header ${styles.sectionHeader}`}>
          <div className="actor-graph-relationship-coverage__heading">
            <p className={`actor-graph-relationship-coverage__eyebrow ${styles.eyebrow}`}>
              {formatInt(databaseCounts.actor_graph_relationships)} aristas trazables
            </p>
            <h2 className={`actor-graph-relationship-coverage__title ${styles.sectionTitle}`} id="actor-graph-relationship-coverage-title">
              Qué relaciones contiene el corte
            </h2>
          </div>
          <p className={`actor-graph-relationship-coverage__note ${styles.sectionNote}`}>
            Contar una relación describe cobertura. No mide poder, influencia, responsabilidad ni comportamiento ilícito.
          </p>
        </header>
        <ol className={`relationship-coverage-list ${styles.relationshipCoverageList}`}>
          {relationshipTypes.map(([type, count]) => (
            <li className={`relationship-coverage-list__item ${styles.relationshipCoverageItem}`} key={type}>
              <div className={`relationship-coverage-list__label-row ${styles.relationshipCoverageLabelRow}`}>
                <span className="relationship-coverage-list__label">{RELATIONSHIP_LABELS[type] || type}</span>
                <strong className="relationship-coverage-list__count">{formatInt(count)}</strong>
              </div>
              <span className={`relationship-coverage-list__track ${styles.relationshipTrack}`} aria-hidden="true">
                <span
                  className={`relationship-coverage-list__bar ${styles.relationshipBar}`}
                  style={{ width: `${Math.max(1, (Number(count) / largestRelationshipCount) * 100)}%` }}
                />
              </span>
            </li>
          ))}
        </ol>
      </section>

      <section className={`actor-graph-actor-samples ${styles.actorSamplesSection}`} aria-labelledby="actor-graph-actor-samples-title">
        <header className={`actor-graph-actor-samples__header ${styles.sectionHeader}`}>
          <div className="actor-graph-actor-samples__heading">
            <p className={`actor-graph-actor-samples__eyebrow ${styles.eyebrow}`}>Muestra pública estable</p>
            <h2 className={`actor-graph-actor-samples__title ${styles.sectionTitle}`} id="actor-graph-actor-samples-title">
              Un actor real por subtipo
            </h2>
          </div>
          <p className={`actor-graph-actor-samples__note ${styles.sectionNote}`}>
            {formatInt(actorSamples.length)} ejemplos seleccionados en orden estable. Los nombres y cargos se conservan como aparecen en fuentes oficiales públicas.
          </p>
        </header>
        <ul className={`actor-sample-list ${styles.actorSampleList}`}>
          {actorSamples.map((actor) => <ActorSample actor={actor} key={actor.actor_id} />)}
        </ul>
      </section>

      <section className={`actor-graph-relationship-samples ${styles.relationshipSamplesSection}`} aria-labelledby="actor-graph-relationship-samples-title">
        <header className={`actor-graph-relationship-samples__header ${styles.sectionHeader}`}>
          <div className="actor-graph-relationship-samples__heading">
            <p className={`actor-graph-relationship-samples__eyebrow ${styles.eyebrow}`}>Actor → relación → contexto</p>
            <h2 className={`actor-graph-relationship-samples__title ${styles.sectionTitle}`} id="actor-graph-relationship-samples-title">
              Un registro real por tipo de relación
            </h2>
          </div>
          <p className={`actor-graph-relationship-samples__note ${styles.sectionNote}`}>
            Cada ejemplo enlaza su registro oficial. Fechas desconocidas siguen desconocidas; no se rellenan por proximidad ni por contexto.
          </p>
        </header>
        <ol className={`relationship-sample-list ${styles.relationshipSampleList}`}>
          {relationshipSamples.map((relationship) => (
            <RelationshipSample relationship={relationship} key={relationship.relationship_id} />
          ))}
        </ol>
      </section>

      <section className={`actor-graph-causality-panel ${styles.causalityPanel}`} aria-labelledby="actor-graph-causality-title">
        <div className="actor-graph-causality-panel__copy">
          <p className={`actor-graph-causality-panel__eyebrow ${styles.eyebrow}`}>Límite de interpretación</p>
          <h2 className={`actor-graph-causality-panel__title ${styles.sectionTitle}`} id="actor-graph-causality-title">
            Una ruta del grafo no prueba corrupción
          </h2>
          <p className={`actor-graph-causality-panel__summary ${styles.sectionCopy}`}>
            Una conexión sirve para localizar registros que merecen revisión. Por sí sola no demuestra causalidad, influencia, mérito, culpa, conflicto de interés, conducta incorrecta ni delito.
          </p>
        </div>
        <ul className={`actor-graph-causality-panel__limits ${styles.limitList}`}>
          <li className="actor-graph-causality-panel__limit">Sin fusiones por coincidencia de nombre</li>
          <li className="actor-graph-causality-panel__limit">Sin fechas inventadas</li>
          <li className="actor-graph-causality-panel__limit">Sin cambios organizativos no revisados</li>
          <li className="actor-graph-causality-panel__limit">Sin inferencia causal desde conexiones</li>
        </ul>
      </section>

      <section className={`actor-graph-provenance ${styles.provenanceSection}`} aria-labelledby="actor-graph-provenance-title">
        <div className="actor-graph-provenance__copy">
          <p className={`actor-graph-provenance__eyebrow ${styles.eyebrow}`}>Reproducir y auditar</p>
          <h2 className={`actor-graph-provenance__title ${styles.sectionTitle}`} id="actor-graph-provenance-title">
            Release inmutable, manifiesto y SQL de evidencia
          </h2>
          <p className={`actor-graph-provenance__summary ${styles.sectionCopy}`}>
            El corte declara datos reales, cero filas sintéticas y conservación de información oficial de dominio público. La release queda ligada al manifiesto de entrada y al hash semántico de sus fuentes.
          </p>
        </div>
        <dl className={`actor-graph-provenance__hashes ${styles.hashGrid}`}>
          <div className="actor-graph-provenance__hash-item">
            <dt className="actor-graph-provenance__hash-label">Release</dt>
            <dd className="actor-graph-provenance__hash-value">
              <code className="actor-graph-provenance__hash-code">{snapshot.meta?.release_id || "sin release"}</code>
            </dd>
          </div>
          <div className="actor-graph-provenance__hash-item">
            <dt className="actor-graph-provenance__hash-label">Manifiesto de entrada</dt>
            <dd className="actor-graph-provenance__hash-value">
              <code className="actor-graph-provenance__hash-code">{snapshot.meta?.input_manifest_sha256 || "sin hash"}</code>
            </dd>
          </div>
          <div className="actor-graph-provenance__hash-item">
            <dt className="actor-graph-provenance__hash-label">Semántica de fuente</dt>
            <dd className="actor-graph-provenance__hash-value">
              <code className="actor-graph-provenance__hash-code">{snapshot.meta?.source_semantic_sha256 || "sin hash"}</code>
            </dd>
          </div>
          <div className="actor-graph-provenance__hash-item">
            <dt className="actor-graph-provenance__hash-label">Método</dt>
            <dd className="actor-graph-provenance__hash-value">
              <code className="actor-graph-provenance__hash-code">{snapshot.methodology?.architecture || "sin documento"}</code>
            </dd>
          </div>
        </dl>
      </section>
    </main>
  );
}
