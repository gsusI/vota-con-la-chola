import { formatInt, readPublicJson } from "../static-snapshot.mjs";
import { StaticRouteHero, StaticRouteLink } from "../static-route-components";
import styles from "./comparisons.module.css";

const STATUS_ORDER = [
  "aligned",
  "conflicted",
  "insufficient_evidence",
  "ambiguous_mapping",
  "changed_framing",
  "not_comparable",
];

const STATUS_CONTENT = {
  aligned: {
    label: "Alineado en este par",
    shortLabel: "Alineado",
    definition:
      "La acción observada avanza la misma proposición. No es una evaluación de cumplimiento total.",
    className: styles.statusAligned,
  },
  conflicted: {
    label: "En conflicto en este par",
    shortLabel: "En conflicto",
    definition:
      "La acción observada va en dirección opuesta bajo un mapping confirmado. No prueba intención, culpa ni corrupción.",
    className: styles.statusConflicted,
  },
  insufficient_evidence: {
    label: "Evidencia insuficiente",
    shortLabel: "Evidencia insuficiente",
    definition:
      "No podemos determinar la relación sin inventar datos ni tratar ausencia como incumplimiento.",
    className: styles.statusInsufficient,
  },
  ambiguous_mapping: {
    label: "Mapping ambiguo",
    shortLabel: "Mapping ambiguo",
    definition:
      "Existe más de una relación plausible entre lo declarado y la acción.",
    className: styles.statusAmbiguous,
  },
  changed_framing: {
    label: "Cambio de enfoque",
    shortLabel: "Cambio de enfoque",
    definition:
      "Ambos objetos están relacionados, pero cambia una dimensión material.",
    className: styles.statusChanged,
  },
  not_comparable: {
    label: "No comparable",
    shortLabel: "No comparable",
    definition: "Los objetos no responden la misma pregunta bajo este método.",
    className: styles.statusNotComparable,
  },
};

const EMPTY_SNAPSHOT = {
  items: [],
  counts: {},
  status_counts: {},
  methodology: {},
  input_releases: {},
  coverage: {},
  freshness: {},
  caveats: [],
};

export const metadata = {
  title: "Dicho frente a hecho | Vota Con La Chola",
  description:
    "Evaluaciones conservadoras de compromisos frente a acciones posteriores o búsquedas acotadas, con incertidumbre y evidencia oficial visibles.",
};

function formatDate(value) {
  const raw = String(value || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/u.test(raw)) return raw || "fecha no publicada";
  return new Intl.DateTimeFormat("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${raw}T00:00:00Z`));
}

function shortHash(value) {
  const raw = String(value || "").trim();
  return raw ? `${raw.slice(0, 12)}…` : "no publicado";
}

function evidenceFor(comparison, side, role = "") {
  return (comparison.evidence || []).find(
    (item) => item.evidence_side === side && (!role || item.evidence_role === role),
  ) || null;
}

function statusContent(status) {
  return STATUS_CONTENT[status] || {
    label: "Estado no reconocido",
    shortLabel: "Estado no reconocido",
    definition: "El artefacto no contiene un estado admitido por el método.",
    className: styles.statusNotComparable,
  };
}

function confidenceLabel(comparison) {
  const value = comparison.confidence?.aggregate_value ?? comparison.confidence?.aggregate;
  if (!Number.isFinite(Number(value))) return "no evaluada";
  const numeric = Number(value);
  if (numeric >= 0.66) return `alta (${numeric.toFixed(2)})`;
  if (numeric >= 0.33) return `media (${numeric.toFixed(2)})`;
  if (numeric > 0) return `baja (${numeric.toFixed(2)})`;
  return "sin confianza útil";
}

function mappingState(comparison) {
  return comparison.mapping_review?.mapping_state
    || comparison.mapping_review?.review_method
    || "no publicado";
}

function actorCapacity(comparison, side) {
  if (side === "claim") {
    return comparison.actor_capacity?.assertion_capacity
      || comparison.claim?.responsible_capacity
      || comparison.claim?.actor_capacity
      || comparison.claim?.capacity
      || "partido autor del programa";
  }
  return comparison.actor_capacity?.action_capacity
    || comparison.action?.responsible_capacity
    || comparison.action?.actor_capacity
    || comparison.action?.capacity
    || (comparison.action ? "voto nominal individual" : "sin acción atribuida");
}

function freshnessState(comparison, snapshot) {
  return comparison.freshness?.tier
    || comparison.freshness?.state
    || comparison.freshness_state
    || snapshot.freshness?.tier
    || snapshot.freshness?.state
    || "no evaluada";
}

function coverageState(comparison, snapshot) {
  return comparison.coverage?.state
    || comparison.coverage_state
    || snapshot.coverage?.state
    || "recorte acotado";
}

function counterevidenceState(comparison) {
  return comparison.counterevidence?.search_state
    || comparison.counterevidence?.state
    || comparison.counterevidence_state
    || comparison.mapping_review?.counterevidence_state
    || "no publicada como búsqueda exhaustiva";
}

function EvidenceSide({ comparison, side }) {
  const isClaim = side === "claim";
  const claim = comparison.claim || {};
  const action = comparison.action || null;
  const evidence = evidenceFor(comparison, isClaim ? "claim" : "action", "primary");
  const searchScope = comparison.action_search?.scope || {};
  const searchedEvents = Number(searchScope.candidate_events_scanned || 0);
  const sideTitle = isClaim
    ? "Lo declarado"
    : action
      ? "Acción posterior observada"
      : "Búsqueda acotada de acciones";
  const title = isClaim
    ? `${claim.actor_label || "Actor no publicado"} · página ${claim.page_start || "—"}`
    : action?.title || `No se localizó una acción revisada entre ${formatInt(searchedEvents)} eventos del recorte`;
  const quote = isClaim
    ? evidence?.exact_quote || claim.exact_text || "Texto exacto no publicado"
    : evidence?.exact_quote
      || action?.title
      || "Resultado de una búsqueda acotada: ausencia de acción revisada, no prueba de inacción ni incumplimiento.";
  const sourceUrl = evidence?.source_url || action?.source_url || "";
  const date = isClaim ? claim.published_date : action?.action_date;
  const sourceId = evidence?.source_id
    || action?.source_id
    || (comparison.action_search?.state === "no_reviewed_action_found" ? "corpus de votaciones acotado" : "sin fuente de acción");
  const publicActor = isClaim
    ? claim.actor_label || "actor no publicado"
    : action?.member_name || "sin actor de acción";

  return (
    <section
      className={`comparison-evidence-side comparison-evidence-side--${side} ${styles.evidenceSide} ${isClaim ? styles.assertionSide : styles.actionSide}`}
      aria-label={sideTitle}
    >
      <header className={`comparison-evidence-side__header ${styles.evidenceSideHeader}`}>
        <span className={`comparison-evidence-side__label ${styles.evidenceSideLabel}`}>{sideTitle}</span>
        <time className={`comparison-evidence-side__date ${styles.evidenceSideDate}`} dateTime={date || undefined}>
          {formatDate(date)}
        </time>
      </header>
      <h3 className={`comparison-evidence-side__title ${styles.evidenceTitle}`}>{title}</h3>
      <blockquote className={`comparison-evidence-side__quote ${styles.evidenceQuote}`}>{quote}</blockquote>
      <dl className={`comparison-evidence-side__facts ${styles.evidenceFacts}`}>
        <div className={`comparison-evidence-side__fact ${styles.evidenceFact}`}>
          <dt className="comparison-evidence-side__fact-label">Actor oficial</dt>
          <dd className="comparison-evidence-side__fact-value">{publicActor}</dd>
        </div>
        <div className={`comparison-evidence-side__fact ${styles.evidenceFact}`}>
          <dt className="comparison-evidence-side__fact-label">Capacidad</dt>
          <dd className="comparison-evidence-side__fact-value">{actorCapacity(comparison, side)}</dd>
        </div>
        <div className={`comparison-evidence-side__fact ${styles.evidenceFact}`}>
          <dt className="comparison-evidence-side__fact-label">Fuente</dt>
          <dd className="comparison-evidence-side__fact-value">{sourceId}</dd>
        </div>
        <div className={`comparison-evidence-side__fact ${styles.evidenceFact}`}>
          <dt className="comparison-evidence-side__fact-label">{isClaim ? "Claim" : "Opción registrada"}</dt>
          <dd className="comparison-evidence-side__fact-value">
            {isClaim ? shortHash(claim.claim_id) : action?.vote_choice || "no aplicable"}
          </dd>
        </div>
      </dl>
      <footer className={`comparison-evidence-side__footer ${styles.evidenceFooter}`}>
        {sourceUrl ? <StaticRouteLink href={sourceUrl}>Abrir evidencia oficial</StaticRouteLink> : (
          <span className="comparison-evidence-side__source-missing">Sin URL de acción porque no se localizó una acción vinculada</span>
        )}
        <code className={`comparison-evidence-side__hash ${styles.evidenceHash}`}>
          SHA-256 {shortHash(evidence?.content_sha256)}
        </code>
      </footer>
    </section>
  );
}

function ComparisonCard({ comparison, snapshot }) {
  const content = statusContent(comparison.comparison_status);
  const review = comparison.mapping_review || {};
  const actorEvidence = evidenceFor(comparison, "actor_link", "identity");
  const reasonCodes = Array.isArray(comparison.reason_codes) ? comparison.reason_codes : [];
  const materialDifferences = comparison.frame?.material_differences
    || comparison.material_differences
    || [];

  return (
    <li className={`comparison-list__item ${styles.comparisonItem}`}>
      <article className={`comparison-card comparison-card--${comparison.comparison_status} ${styles.comparisonCard}`}>
        <header className={`comparison-card__header ${styles.comparisonHeader}`}>
          <div className={`comparison-card__heading ${styles.comparisonHeading}`}>
            <h3 className={`comparison-card__actor ${styles.actorName}`}>
              {comparison.claim?.actor_label || "Actor no publicado"}
            </h3>
            <p className={`comparison-card__frame ${styles.frameLabel}`}>{comparison.public_summary}</p>
          </div>
          <span className={`comparison-card__status ${styles.statusBadge} ${content.className}`}>
            {content.label}
          </span>
        </header>

        <div className={`comparison-card__evidence-comparison ${styles.comparisonBody}`}>
          <EvidenceSide comparison={comparison} side="claim" />
          <div className={`comparison-card__connector ${styles.comparisonConnector}`} aria-label="Comparado mediante revisión explícita">
            <span className={`comparison-card__connector-line ${styles.connectorLine}`} aria-hidden="true" />
            <span className={`comparison-card__connector-label ${styles.connectorLabel}`}>revisión explícita</span>
            <span className={`comparison-card__connector-line ${styles.connectorLine}`} aria-hidden="true" />
          </div>
          <EvidenceSide comparison={comparison} side="action" />
        </div>

        <section className={`comparison-card__mapping ${styles.mappingPanel}`} aria-label="Decisión de comparabilidad">
          <div className="comparison-card__mapping-copy">
            <p className={`comparison-card__status-definition ${styles.mappingReason}`}>
              <strong className="comparison-card__status-definition-label">Qué significa: </strong>
              {content.definition}
            </p>
            <p className={`comparison-card__review-rationale ${styles.mappingReason}`}>
              <strong className="comparison-card__review-rationale-label">Por qué: </strong>
              {review.review_rationale || "El artefacto no publicó una razón revisable."}
            </p>
          </div>
          <dl className={`comparison-card__mapping-facts ${styles.mappingFacts}`}>
            <div className={`comparison-card__mapping-fact ${styles.mappingFact}`}>
              <dt className="comparison-card__mapping-fact-label">Estado del mapping</dt>
              <dd className="comparison-card__mapping-fact-value">{mappingState(comparison)}</dd>
            </div>
            <div className={`comparison-card__mapping-fact ${styles.mappingFact}`}>
              <dt className="comparison-card__mapping-fact-label">Base</dt>
              <dd className="comparison-card__mapping-fact-value">{review.mapping_basis || "no publicada"}</dd>
            </div>
            <div className={`comparison-card__mapping-fact ${styles.mappingFact}`}>
              <dt className="comparison-card__mapping-fact-label">Confianza de lectura</dt>
              <dd className="comparison-card__mapping-fact-value">{confidenceLabel(comparison)}</dd>
            </div>
            <div className={`comparison-card__mapping-fact ${styles.mappingFact}`}>
              <dt className="comparison-card__mapping-fact-label">Cobertura · frescura</dt>
              <dd className="comparison-card__mapping-fact-value">
                {coverageState(comparison, snapshot)} · {freshnessState(comparison, snapshot)}
              </dd>
            </div>
          </dl>
        </section>

        <section className={`comparison-card__counterevidence ${styles.counterEvidence}`} aria-label="Estado de contraevidencia">
          <h4 className={`comparison-card__counterevidence-title ${styles.counterEvidenceTitle}`}>Contraevidencia</h4>
          <p className={`comparison-card__counterevidence-copy ${styles.counterEvidenceCopy}`}>
            {counterevidenceState(comparison)}. Esta evaluación no se presenta como búsqueda exhaustiva de toda acción relacionada.
          </p>
          {actorEvidence ? (
            <p className={`comparison-card__actor-scope ${styles.counterEvidenceCopy}`}>
              Identidad/capacidad: {actorEvidence.exact_quote}. Alcance: {actorEvidence.metadata?.scope_note || "revisión acotada"}.
            </p>
          ) : null}
        </section>

        <ul className={`comparison-card__caveats ${styles.caveatList}`} aria-label="Salvedades del par">
          <li className={`comparison-card__caveat ${styles.caveatItem}`}>{comparison.caveat}</li>
          {reasonCodes.map((reason) => (
            <li className={`comparison-card__reason-code ${styles.caveatItem}`} key={reason}>{reason}</li>
          ))}
          {(Array.isArray(materialDifferences) ? materialDifferences : [materialDifferences]).filter(Boolean).map((difference) => (
            <li className={`comparison-card__material-difference ${styles.caveatItem}`} key={String(difference)}>
              Diferencia material: {String(difference)}
            </li>
          ))}
        </ul>

        <footer className={`comparison-card__footer ${styles.evidenceFooter}`}>
          <StaticRouteLink href="/actor-graph/">Auditar identidades en el grafo</StaticRouteLink>
          <code className={`comparison-card__id ${styles.evidenceHash}`}>{comparison.comparison_id}</code>
        </footer>
      </article>
    </li>
  );
}

export default function ComparisonsPage() {
  const snapshot = readPublicJson("comparisons/data/comparisons.json", EMPTY_SNAPSHOT);
  const comparisons = Array.isArray(snapshot.items) ? snapshot.items : [];
  const counts = snapshot.counts || {};
  const statusCounts = snapshot.status_counts || {};
  const methodology = snapshot.methodology || {};
  const inputReleases = snapshot.input_releases || {};
  const strongCount = Number(statusCounts.aligned || 0) + Number(statusCounts.conflicted || 0);
  const caveats = Array.isArray(snapshot.caveats) ? snapshot.caveats : [];

  return (
    <main className={`shell comparisons-page ${styles.page}`}>
      <StaticRouteHero
        actions={[
          { href: "/comparisons/data/comparisons.json", label: "Descargar corte JSON" },
          { href: "/promises/", label: "Abrir promesas originales" },
          { href: "/political-positions/", label: "Explorar posturas" },
        ]}
        eyebrow="Dicho · acción o búsqueda acotada · evidencia · límites"
        meta={[
          { label: "Evaluaciones revisadas", value: formatInt(counts.comparisons_total || comparisons.length) },
          { label: "Pares con acción", value: formatInt(counts.action_pairs_total) },
          { label: "Búsquedas acotadas", value: formatInt(counts.bounded_action_search_assessments_total) },
          { label: "Evidencias", value: formatInt(counts.evidence_total) },
          { label: "Estados fuertes", value: formatInt(strongCount) },
          { label: "Corte", value: formatDate(snapshot.snapshot_date) },
        ]}
        summary="Publica cinco evaluaciones reales: cuatro pares entre compromisos y acciones posteriores concretas, más una búsqueda acotada sin acción revisada localizada. Conserva identidades, fechas, mapping, cobertura y fuentes."
        title="Lo dicho frente a lo observado"
      />

      <section className={`comparison-truth-panel ${styles.truthPanel}`} aria-labelledby="comparison-truth-title">
        <div className="comparison-truth-panel__copy">
          <p className={`comparison-truth-panel__eyebrow ${styles.eyebrow}`}>Antes de interpretar</p>
          <h2 className={`comparison-truth-panel__title ${styles.sectionTitle}`} id="comparison-truth-title">
            Comparar no es sentenciar
          </h2>
          <p className={`comparison-truth-panel__summary ${styles.sectionCopy}`}>
            Una evaluación describe un par concreto o el resultado de una búsqueda acotada. No decide cumplimiento total, sinceridad, legalidad, intención, mérito, culpa, causalidad ni corrupción.
          </p>
        </div>
        <ul className={`comparison-truth-panel__rules ${styles.truthList}`}>
          {[
            "Una coincidencia de tema solo propone una revisión; no crea un veredicto.",
            "Un voto individual no se convierte en postura colectiva completa del partido.",
            "No encontrar una acción en un recorte no demuestra inacción ni incumplimiento.",
            "Confianza mide calidad de lectura, nunca probabilidad de honestidad.",
          ].map((rule) => (
            <li className={`comparison-truth-panel__rule ${styles.truthItem}`} key={rule}>
              <span className={`comparison-truth-panel__rule-marker ${styles.truthMarker}`} aria-hidden="true" />
              <span className="comparison-truth-panel__rule-text">{rule}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className={`comparison-coverage ${styles.coverageSection}`} aria-labelledby="comparison-coverage-title">
        <header className={`comparison-coverage__header ${styles.sectionHeader}`}>
          <div className="comparison-coverage__heading">
            <p className={`comparison-coverage__eyebrow ${styles.eyebrow}`}>Todos los estados, incluidos los ceros</p>
            <h2 className={`comparison-coverage__title ${styles.sectionTitle}`} id="comparison-coverage-title">
              Cobertura del corte v1
            </h2>
          </div>
          <p className={`comparison-coverage__note ${styles.sectionNote}`}>
            Cinco evaluaciones reales: cuatro pares con acción y una búsqueda acotada. Muestra de método; todavía no prueba ejecución física a escala de un millón de comparaciones.
          </p>
        </header>

        <dl className={`comparison-status-ledger ${styles.statusLedger}`}>
          {STATUS_ORDER.map((status) => (
            <div className={`comparison-status-ledger__item comparison-status-ledger__item--${status} ${styles.statusLedgerItem}`} key={status}>
              <dt className={`comparison-status-ledger__label ${styles.statusLedgerLabel}`}>{statusContent(status).shortLabel}</dt>
              <dd className={`comparison-status-ledger__value ${styles.statusLedgerValue}`}>{formatInt(statusCounts[status] || 0)}</dd>
            </div>
          ))}
        </dl>

        <div className={`comparison-strong-status-notice ${styles.strongStatusNotice}`} role="note">
          <strong className="comparison-strong-status-notice__count">{formatInt(strongCount)} estados fuertes</strong>
          <span className="comparison-strong-status-notice__copy">
            Ranking oculto: la muestra comparable no alcanza el mínimo para una lectura responsable. V1 no publica ningún aligned/conflicted.
          </span>
        </div>
      </section>

      <section className={`comparison-results ${styles.comparisonsSection}`} aria-labelledby="comparison-results-title">
        <header className={`comparison-results__header ${styles.sectionHeader}`}>
          <div className="comparison-results__heading">
            <p className={`comparison-results__eyebrow ${styles.eyebrow}`}>Cuatro acciones y una búsqueda acotada</p>
            <h2 className={`comparison-results__title ${styles.sectionTitle}`} id="comparison-results-title">
              Evaluaciones revisadas con evidencia
            </h2>
          </div>
          <p className={`comparison-results__note ${styles.sectionNote}`}>
            Cada evaluación conserva identidad pública oficial. Cuando existe una acción, abre ambos registros antes de extraer conclusiones.
          </p>
        </header>

        {comparisons.length ? (
          <ol className={`comparison-list ${styles.comparisonList}`}>
            {comparisons.map((comparison) => (
              <ComparisonCard comparison={comparison} key={comparison.comparison_id} snapshot={snapshot} />
            ))}
          </ol>
        ) : (
          <p className={`comparison-results__empty ${styles.emptyState}`}>
            No hay evaluaciones publicadas en este corte. No sustituimos la ausencia por ejemplos ni por datos sintéticos.
          </p>
        )}
      </section>

      <section className={`comparison-method ${styles.methodSection}`} aria-labelledby="comparison-method-title">
        <header className={`comparison-method__header ${styles.sectionHeader}`}>
          <div className="comparison-method__heading">
            <p className={`comparison-method__eyebrow ${styles.eyebrow}`}>Auditoría de release</p>
            <h2 className={`comparison-method__title ${styles.sectionTitle}`} id="comparison-method-title">
              Método y procedencia
            </h2>
          </div>
          <StaticRouteLink href="/methods/">Abrir datos y método</StaticRouteLink>
        </header>
        <div className={`comparison-method__body ${styles.methodGrid}`}>
          <ul className={`comparison-method__rules ${styles.methodRules}`}>
            <li className="comparison-method__rule">Método: {methodology.method_version || "no publicado"}.</li>
            <li className="comparison-method__rule">Mapping: {methodology.mapping_review_version || "no publicado"}.</li>
            <li className="comparison-method__rule">Datos reales: {snapshot.real_data_only === true ? "sí" : "política no publicada"}; datos sintéticos: {snapshot.synthetic_or_mock === false ? "no" : "estado no publicado"}.</li>
            <li className="comparison-method__rule">Identidad pública oficial: {snapshot.public_domain_information_policy ? "retenida" : "validación externa requerida"}.</li>
          </ul>
          <dl className={`comparison-provenance-grid ${styles.provenanceGrid}`}>
            <div className={`comparison-provenance-grid__fact ${styles.provenanceFact}`}>
              <dt className="comparison-provenance-grid__label">Release</dt>
              <dd className="comparison-provenance-grid__value">{snapshot.release_id || "no publicada"}</dd>
            </div>
            <div className={`comparison-provenance-grid__fact ${styles.provenanceFact}`}>
              <dt className="comparison-provenance-grid__label">Hash semántico</dt>
              <dd className="comparison-provenance-grid__value">{snapshot.semantic_sha256 || "no publicado"}</dd>
            </div>
            <div className={`comparison-provenance-grid__fact ${styles.provenanceFact}`}>
              <dt className="comparison-provenance-grid__label">Actor graph</dt>
              <dd className="comparison-provenance-grid__value">{shortHash(inputReleases.actor_graph?.release_id)}</dd>
            </div>
            <div className={`comparison-provenance-grid__fact ${styles.provenanceFact}`}>
              <dt className="comparison-provenance-grid__label">Review input</dt>
              <dd className="comparison-provenance-grid__value">{shortHash(inputReleases.reviewed_mappings?.canonical_sha256)}</dd>
            </div>
          </dl>
        </div>
        {caveats.length ? (
          <ul className={`comparison-method__caveats ${styles.caveatList}`} aria-label="Límites del corte">
            {caveats.map((caveat) => (
              <li className={`comparison-method__caveat ${styles.caveatItem}`} key={caveat}>{caveat}</li>
            ))}
          </ul>
        ) : null}
      </section>
    </main>
  );
}
