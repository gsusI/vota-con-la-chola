import { formatDate, formatInt, readPublicJson, sourceStatusClass } from "../static-snapshot.mjs";
import {
  StaticRouteHero,
  StaticRouteLink,
  StaticRouteMetrics,
  StaticRouteStatusPill,
} from "../static-route-components";
import styles from "./obstruction-tracker.module.css";

const EMPTY_SNAPSHOT = {
  meta: {},
  policy: {},
  summary: { obstruction: {}, affected_coverage: {} },
  scale_readiness: { summary: {}, corpora: [], gaps: [] },
  blocked_sources: [],
  audit_links: {},
};

export const metadata = {
  title: "Obstrucción de datos públicos | Vota Con La Chola",
  description: "Registro verificable de bloqueos al acceso reproducible de datos públicos oficiales.",
};

function healthLabel(source) {
  if (source.current_health_state === "ok") {
    return "Datos recuperados; el bloqueo histórico o reproducible sigue abierto.";
  }
  return "Acceso reproducible afectado en el último corte disponible.";
}

function EvidenceLinks({ links, label }) {
  if (!Array.isArray(links) || !links.length) {
    return null;
  }
  return (
    <div className={`obstruction-evidence-links ${styles.evidenceLinks}`} aria-label={label}>
      {links.map((link) => (
        <StaticRouteLink href={link.url} key={link.path}>
          {link.label}
        </StaticRouteLink>
      ))}
    </div>
  );
}

function IncidentCard({ incident }) {
  return (
    <article className={`obstruction-incident-card ${styles.incidentCard}`} id={incident.incident_id}>
      <header className={`obstruction-incident-card__header ${styles.incidentHeader}`}>
        <div className={`obstruction-incident-card__identity ${styles.incidentIdentity}`}>
          <span className={`obstruction-incident-card__id ${styles.mono}`}>{incident.incident_id}</span>
          <h4 className={`obstruction-incident-card__title ${styles.incidentTitle}`}>{incident.organism}</h4>
        </div>
        <StaticRouteStatusPill value={{ className: sourceStatusClass("blocked"), label: incident.status }} />
      </header>
      <dl className={`obstruction-incident-card__facts ${styles.incidentFacts}`}>
        <div className={`obstruction-incident-card__fact ${styles.fact}`}>
          <dt className="obstruction-incident-card__fact-label">Primera señal</dt>
          <dd className="obstruction-incident-card__fact-value">{formatDate(incident.first_seen_utc)}</dd>
        </div>
        <div className={`obstruction-incident-card__fact ${styles.fact}`}>
          <dt className="obstruction-incident-card__fact-label">Última señal</dt>
          <dd className="obstruction-incident-card__fact-value">{formatDate(incident.last_seen_utc)}</dd>
        </div>
      </dl>
      <p className={`obstruction-incident-card__failure ${styles.failure}`}>{incident.failure_mode}</p>
      <p className={`obstruction-incident-card__endpoint ${styles.endpoint}`}>{incident.endpoint_or_page}</p>
      <div className={`obstruction-incident-card__next-step ${styles.nextStep}`}>
        <strong className="obstruction-incident-card__next-step-label">Siguiente escalado</strong>
        <span className="obstruction-incident-card__next-step-text">{incident.next_escalation}</span>
      </div>
      <EvidenceLinks links={incident.evidence} label={`Evidencia de ${incident.incident_id}`} />
      <EvidenceLinks links={incident.tracker_rows_impacted} label={`Filas afectadas por ${incident.incident_id}`} />
    </article>
  );
}

function BlockedSourceCard({ source }) {
  const coverage = source.affected_coverage || {};
  return (
    <article className={`obstruction-source-card ${styles.sourceCard}`}>
      <header className={`obstruction-source-card__header ${styles.sourceHeader}`}>
        <div className={`obstruction-source-card__identity ${styles.sourceIdentity}`}>
          <span className={`obstruction-source-card__id ${styles.mono}`}>{source.source_id}</span>
          <h3 className={`obstruction-source-card__title ${styles.sourceTitle}`}>{source.source_name}</h3>
          <p className={`obstruction-source-card__institution ${styles.sourceInstitution}`}>{source.incidents?.[0]?.organism || source.domain}</p>
        </div>
        <div className={`obstruction-source-card__status ${styles.sourceStatus}`}>
          <StaticRouteStatusPill
            value={{ className: sourceStatusClass(source.current_health_state), label: source.current_health_label }}
          />
          <span className="obstruction-source-card__status-note">{healthLabel(source)}</span>
        </div>
      </header>

      <dl className={`obstruction-source-card__facts ${styles.sourceFacts}`}>
        <div className={`obstruction-source-card__fact ${styles.fact}`}>
          <dt className="obstruction-source-card__fact-label">Incidencias</dt>
          <dd className="obstruction-source-card__fact-value">{formatInt(source.incident_count)}</dd>
        </div>
        <div className={`obstruction-source-card__fact ${styles.fact}`}>
          <dt className="obstruction-source-card__fact-label">Cargado / objetivo</dt>
          <dd className="obstruction-source-card__fact-value">
            {formatInt(coverage.loaded)} / {formatInt(coverage.target)}
          </dd>
        </div>
        <div className={`obstruction-source-card__fact ${styles.fact}`}>
          <dt className="obstruction-source-card__fact-label">Hueco atribuible</dt>
          <dd className="obstruction-source-card__fact-value">{formatInt(coverage.gap)}</dd>
        </div>
        <div className={`obstruction-source-card__fact ${styles.fact}`}>
          <dt className="obstruction-source-card__fact-label">Último cambio</dt>
          <dd className="obstruction-source-card__fact-value">{formatDate(source.last_change_at)}</dd>
        </div>
      </dl>

      <nav className={`obstruction-source-card__links ${styles.sourceLinks}`} aria-label={`Enlaces de ${source.source_name}`}>
        <StaticRouteLink href={source.explorer_sources_path}>Estado de la fuente</StaticRouteLink>
        {source.source_url_public ? <StaticRouteLink href={source.source_url_public}>Fuente oficial</StaticRouteLink> : null}
      </nav>

      <div className={`obstruction-source-card__incidents ${styles.incidentList}`}>
        {(source.incidents || []).map((incident) => (
          <IncidentCard incident={incident} key={incident.incident_id} />
        ))}
      </div>
    </article>
  );
}

function ScaleCorpusCard({ corpus }) {
  const status = corpus.promotion_gate_passed ? "ok" : corpus.scale_gate_passed ? "partial" : "missing";
  return (
    <article className={`obstruction-scale-corpus ${styles.corpusCard}`}>
      <header className={`obstruction-scale-corpus__header ${styles.corpusHeader}`}>
        <div className="obstruction-scale-corpus__identity">
          <span className={`obstruction-scale-corpus__id ${styles.mono}`}>{corpus.id}</span>
          <h3 className={`obstruction-scale-corpus__title ${styles.corpusTitle}`}>{corpus.label}</h3>
        </div>
        <StaticRouteStatusPill
          value={{ className: sourceStatusClass(status), label: corpus.promotion_gate_passed ? "promovido" : "validado, no promovido" }}
        />
      </header>
      <strong className={`obstruction-scale-corpus__rows ${styles.corpusRows}`}>{formatInt(corpus.rows)} registros reales</strong>
      <p className={`obstruction-scale-corpus__sources ${styles.corpusSources}`}>{(corpus.source_ids || []).join(" · ")}</p>
      <div className={`obstruction-scale-corpus__next-gate ${styles.nextStep}`}>
        <strong className="obstruction-scale-corpus__next-gate-label">Puerta siguiente</strong>
        <span className="obstruction-scale-corpus__next-gate-text">{corpus.next_gate}</span>
      </div>
    </article>
  );
}

function ScaleGapCard({ gap }) {
  const remaining = Math.max(Number(gap.target_real_rows || 0) - Number(gap.current_real_rows || 0), 0);
  return (
    <article className={`obstruction-scale-gap ${styles.gapCard}`}>
      <header className={`obstruction-scale-gap__header ${styles.gapHeader}`}>
        <div className="obstruction-scale-gap__identity">
          <span className={`obstruction-scale-gap__id ${styles.mono}`}>{gap.id}</span>
          <h3 className={`obstruction-scale-gap__title ${styles.gapTitle}`}>{gap.status}</h3>
        </div>
        <StaticRouteStatusPill value={{ className: sourceStatusClass("missing"), label: "gap abierto" }} />
      </header>
      <dl className={`obstruction-scale-gap__facts ${styles.gapFacts}`}>
        <div className={`obstruction-scale-gap__fact ${styles.fact}`}>
          <dt className="obstruction-scale-gap__fact-label">Registros reales</dt>
          <dd className="obstruction-scale-gap__fact-value">{formatInt(gap.current_real_rows)}</dd>
        </div>
        <div className={`obstruction-scale-gap__fact ${styles.fact}`}>
          <dt className="obstruction-scale-gap__fact-label">Objetivo</dt>
          <dd className="obstruction-scale-gap__fact-value">{formatInt(gap.target_real_rows)}</dd>
        </div>
        <div className={`obstruction-scale-gap__fact ${styles.fact}`}>
          <dt className="obstruction-scale-gap__fact-label">Pendiente</dt>
          <dd className="obstruction-scale-gap__fact-value">{formatInt(remaining)}</dd>
        </div>
      </dl>
      <div className={`obstruction-scale-gap__next-action ${styles.nextStep}`}>
        <strong className="obstruction-scale-gap__next-action-label">Acción siguiente</strong>
        <span className="obstruction-scale-gap__next-action-text">{gap.next_action}</span>
      </div>
    </article>
  );
}

export default function ObstructionTrackerPage() {
  const snapshot = readPublicJson("obstruction-tracker/data/obstructions.json", EMPTY_SNAPSHOT);
  const obstruction = snapshot.summary?.obstruction || {};
  const coverage = snapshot.summary?.affected_coverage || {};
  const readiness = snapshot.scale_readiness || EMPTY_SNAPSHOT.scale_readiness;
  const freshness = snapshot.meta?.freshness || {};

  return (
    <main className={`shell obstruction-tracker-page ${styles.page}`}>
      <StaticRouteHero
        actions={[
          { href: "/explorer-sources/", label: "Estado de fuentes" },
          { href: "/obstruction-tracker/data/obstructions.json", label: "Descargar JSON" },
          { href: snapshot.audit_links?.name_and_shame_log || "/methods/coverage/", label: "Registro íntegro" },
        ]}
        eyebrow="Accountability de acceso público"
        meta={[
          { label: "Generado", value: formatDate(snapshot.meta?.generated_at) },
          { label: "Corte de fuentes", value: formatDate(snapshot.meta?.source_snapshot_generated_at) },
          { label: "Contrato", value: snapshot.meta?.schema_version || "sin feed" },
        ]}
        summary="Documentamos cuándo una institución impide o degrada el acceso técnico reproducible a información pública. Cada entrada conserva señal, fecha, fuente oficial, evidencia y siguiente escalado."
        title="Obstrucción de datos públicos"
      />

      {freshness.should_warn ? (
        <aside className={`obstruction-freshness-warning ${styles.warning}`}>
          <strong className="obstruction-freshness-warning__title">Advertencia de frescura</strong>
          <span className="obstruction-freshness-warning__detail">{freshness.detail}</span>
        </aside>
      ) : null}

      <StaticRouteMetrics
        metrics={[
          { label: "Incidencias abiertas", value: formatInt(obstruction.open_incidents_total), note: "todas con evidencia" },
          { label: "Fuentes afectadas", value: `${formatInt(obstruction.blocked_desired_sources_total)} / ${formatInt(coverage.desired_sources_total)}`, note: "del inventario deseado" },
          { label: "Artefactos", value: formatInt(obstruction.evidence_artifacts_total), note: "pruebas enlazadas" },
          { label: "Hueco atribuible", value: formatInt(coverage.affected_gap), note: "registros frente al objetivo" },
          { label: "Cohortes reales", value: formatInt(readiness.summary?.validated_real_corpora), note: "validadas" },
          { label: "Lanes de millón", value: formatInt(readiness.summary?.real_million_scale_lanes), note: "≥ 1.000.000 filas" },
        ]}
      />

      <section className={`obstruction-method-note ${styles.methodNote}`} aria-labelledby="obstruction-method-note-title">
        <div className="obstruction-method-note__copy">
          <p className={`obstruction-method-note__eyebrow ${styles.eyebrow}`}>Lectura correcta</p>
          <h2 className={`obstruction-method-note__title ${styles.sectionTitle}`} id="obstruction-method-note-title">Hechos técnicos, no atribución de motivos</h2>
          <p className={`obstruction-method-note__text ${styles.sectionCopy}`}>
            Una incidencia prueba un fallo de acceso observado y reproducible. No prueba por sí sola ilegalidad, intención ni corrupción. El historial es append-only: una resolución futura no borra el bloqueo original.
          </p>
        </div>
        <dl className={`obstruction-method-note__policy ${styles.policyList}`}>
          <div className={`obstruction-method-note__policy-item ${styles.policyItem}`}>
            <dt className="obstruction-method-note__policy-label">Datos</dt>
            <dd className="obstruction-method-note__policy-value">Solo registros oficiales reales</dd>
          </div>
          <div className={`obstruction-method-note__policy-item ${styles.policyItem}`}>
            <dt className="obstruction-method-note__policy-label">Identidad pública</dt>
            <dd className="obstruction-method-note__policy-value">Se conserva para accountability</dd>
          </div>
          <div className={`obstruction-method-note__policy-item ${styles.policyItem}`}>
            <dt className="obstruction-method-note__policy-label">Exclusiones</dt>
            <dd className="obstruction-method-note__policy-value">Secretos, sesiones privadas y datos no públicos</dd>
          </div>
        </dl>
      </section>

      <section className={`obstruction-scale-section ${styles.section}`} aria-labelledby="obstruction-scale-title">
        <header className={`obstruction-section-heading ${styles.sectionHeading}`}>
          <div className="obstruction-section-heading__copy">
            <p className={`obstruction-section-heading__eyebrow ${styles.eyebrow}`}>Escala real verificable</p>
            <h2 className={`obstruction-section-heading__title ${styles.sectionTitle}`} id="obstruction-scale-title">Qué ya procesa millones y qué falta para promoverlo</h2>
          </div>
          <StaticRouteLink href={snapshot.audit_links?.scale_readiness || "/obstruction-tracker/data/obstructions.json"}>Auditar readiness</StaticRouteLink>
        </header>
        <div className={`obstruction-scale-grid ${styles.corpusGrid}`}>
          {(readiness.corpora || []).map((corpus) => (
            <ScaleCorpusCard corpus={corpus} key={corpus.id} />
          ))}
        </div>
        <div className={`obstruction-scale-gaps ${styles.gapSection}`}>
          <header className={`obstruction-scale-gaps__heading ${styles.gapSectionHeading}`}>
            <p className={`obstruction-scale-gaps__eyebrow ${styles.eyebrow}`}>Brechas abiertas</p>
            <h3 className={`obstruction-scale-gaps__title ${styles.gapSectionTitle}`}>Trabajo todavía no promovible</h3>
          </header>
          <div className={`obstruction-scale-gap-grid ${styles.gapGrid}`}>
            {(readiness.gaps || []).map((gap) => (
              <ScaleGapCard gap={gap} key={gap.id} />
            ))}
          </div>
        </div>
      </section>

      <section className={`obstruction-source-section ${styles.section}`} aria-labelledby="obstruction-source-title">
        <header className={`obstruction-section-heading ${styles.sectionHeading}`}>
          <div className="obstruction-section-heading__copy">
            <p className={`obstruction-section-heading__eyebrow ${styles.eyebrow}`}>Registro abierto</p>
            <h2 className={`obstruction-section-heading__title ${styles.sectionTitle}`} id="obstruction-source-title">Fuentes con obstrucción documentada</h2>
            <p className={`obstruction-section-heading__summary ${styles.sectionCopy}`}>
              Ordenadas por estado actual, número de incidencias y hueco de cobertura. Se publican todas las incidencias abiertas del registro fuente.
            </p>
          </div>
          <StaticRouteLink href={snapshot.audit_links?.tracker_log || "/methods/coverage/"}>Tracker operativo</StaticRouteLink>
        </header>
        <div className={`obstruction-source-list ${styles.sourceList}`}>
          {(snapshot.blocked_sources || []).map((source) => (
            <BlockedSourceCard source={source} key={source.source_id} />
          ))}
        </div>
      </section>
    </main>
  );
}
