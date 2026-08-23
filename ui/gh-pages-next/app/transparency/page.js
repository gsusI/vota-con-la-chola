import { formatDate, formatInt, readPublicJson, sourceStatusClass } from "../static-snapshot.mjs";
import {
  StaticRouteHero,
  StaticRouteLink,
  StaticRouteStatusPill,
} from "../static-route-components";
import styles from "./transparency.module.css";

const EMPTY_SNAPSHOT = {
  meta: {},
  policy: {},
  headline: {},
  metrics: [],
  source_health: { summary: {}, freshness: {} },
  obstruction: {},
  scale_readiness: { summary: {} },
  published_snapshot: { freshness: {}, corpora: [], warnings: [] },
  recent_changes: [],
  audit_links: {},
};

export const metadata = {
  title: "Transparencia del proyecto | Vota Con La Chola",
  description: "Frescura, salud de fuentes, versión pública, cambios y evidencia de cada métrica del proyecto.",
};

function freshnessStatus(tier) {
  if (tier === "fresh") return "ok";
  if (tier === "aging") return "partial";
  return "missing";
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const amount = bytes / 1024 ** index;
  return `${amount.toLocaleString("es-ES", { maximumFractionDigits: index ? 1 : 0 })} ${units[index]}`;
}

function shortHash(value) {
  const raw = String(value || "").trim();
  return raw ? `${raw.slice(0, 12)}…` : "sin versión";
}

function releaseStatusLabel(value) {
  const labels = {
    published_live_verified: "publicado · verificado live",
    published_mvp: "MVP publicado",
  };
  return labels[value] || String(value || "estado desconocido").replaceAll("_", " ");
}

function warningLabel(value) {
  const labels = {
    "remote scale origin does not contain the current readiness report": "El origen remoto no contiene el informe de readiness local actual.",
    "remote scale origin does not contain the current corpus registry": "El origen remoto no contiene el registro local de corpus actual.",
  };
  return labels[value] || value;
}

function MetricCard({ metric }) {
  return (
    <article className={`transparency-metric-card ${styles.metricCard}`}>
      <span className={`transparency-metric-card__label ${styles.metricLabel}`}>{metric.label}</span>
      <strong className={`transparency-metric-card__value ${styles.metricValue}`}>{formatInt(metric.value)}</strong>
      <span className={`transparency-metric-card__unit ${styles.metricUnit}`}>{metric.unit}</span>
      <div className={`transparency-metric-card__source ${styles.metricSource}`}>
        <StaticRouteLink href={metric.source_url}>Auditar cifra</StaticRouteLink>
      </div>
    </article>
  );
}

function FreshnessCard({ title, sourceAt, freshness, sourceUrl }) {
  return (
    <article className={`transparency-freshness-card ${styles.freshnessCard}`}>
      <header className={`transparency-freshness-card__header ${styles.cardHeader}`}>
        <h3 className={`transparency-freshness-card__title ${styles.cardTitle}`}>{title}</h3>
        <StaticRouteStatusPill
          value={{ className: sourceStatusClass(freshnessStatus(freshness.tier)), label: freshness.label || "desconocida" }}
        />
      </header>
      <time className={`transparency-freshness-card__time ${styles.mono}`} dateTime={sourceAt || undefined}>{formatDate(sourceAt)}</time>
      <p className={`transparency-freshness-card__detail ${styles.cardCopy}`}>{freshness.detail || "Sin evaluación de frescura."}</p>
      <div className={`transparency-freshness-card__source ${styles.inlineLink}`}>
        <StaticRouteLink href={sourceUrl}>Abrir fuente</StaticRouteLink>
      </div>
    </article>
  );
}

function SourceState({ label, value, status }) {
  return (
    <div className={`transparency-source-state ${styles.sourceState}`}>
      <span className={`transparency-source-state__label ${styles.sourceStateLabel}`}>{label}</span>
      <strong className={`transparency-source-state__value ${styles.sourceStateValue}`}>{formatInt(value)}</strong>
      <StaticRouteStatusPill value={{ className: sourceStatusClass(status), label }} />
    </div>
  );
}

function SnapshotCorpus({ corpus }) {
  return (
    <li className={`transparency-snapshot-corpus ${styles.corpusItem}`}>
      <div className="transparency-snapshot-corpus__identity">
        <strong className={`transparency-snapshot-corpus__id ${styles.corpusId}`}>{corpus.id}</strong>
        <span className={`transparency-snapshot-corpus__rows ${styles.corpusRows}`}>{formatInt(corpus.rows)} filas</span>
      </div>
      <div className={`transparency-snapshot-corpus__storage ${styles.corpusStorage}`}>
        <span className="transparency-snapshot-corpus__files">{formatInt(corpus.files)} ficheros</span>
        <span className="transparency-snapshot-corpus__bytes">{formatBytes(corpus.bytes)}</span>
      </div>
    </li>
  );
}

function ReleaseCard({ release }) {
  return (
    <article className={`transparency-release-card ${styles.releaseCard}`}>
      <header className={`transparency-release-card__header ${styles.releaseHeader}`}>
        <div className="transparency-release-card__identity">
          <time className={`transparency-release-card__date ${styles.mono}`} dateTime={release.date}>{release.date}</time>
          <h3 className={`transparency-release-card__title ${styles.releaseTitle}`}>{release.title}</h3>
        </div>
        <StaticRouteStatusPill value={{ className: sourceStatusClass("ok"), label: releaseStatusLabel(release.status) }} />
      </header>
      <p className={`transparency-release-card__summary ${styles.cardCopy}`}>{release.summary}</p>
      <nav className={`transparency-release-card__routes ${styles.releaseLinks}`} aria-label={`Rutas de ${release.title}`}>
        {(release.public_routes || []).map((route) => (
          <StaticRouteLink href={route} key={route}>{route}</StaticRouteLink>
        ))}
      </nav>
      <div className={`transparency-release-card__evidence ${styles.releaseEvidence}`}>
        <StaticRouteLink href={release.note.url}>Nota de versión</StaticRouteLink>
        {(release.evidence || []).map((evidence) => (
          <StaticRouteLink href={evidence.url} key={evidence.path}>{evidence.path.split("/").pop()}</StaticRouteLink>
        ))}
      </div>
      <code className={`transparency-release-card__note-hash ${styles.hash}`}>nota sha256 {shortHash(release.note.sha256)}</code>
    </article>
  );
}

export default function TransparencyPage() {
  const snapshot = readPublicJson("transparency/data/transparency.json", EMPTY_SNAPSHOT);
  const sourceHealth = snapshot.source_health || EMPTY_SNAPSHOT.source_health;
  const sourceSummary = sourceHealth.summary || {};
  const published = snapshot.published_snapshot || EMPTY_SNAPSHOT.published_snapshot;
  const readiness = snapshot.scale_readiness || EMPTY_SNAPSHOT.scale_readiness;
  const obstruction = snapshot.obstruction || {};

  return (
    <main className={`shell transparency-dashboard-page ${styles.page}`}>
      <StaticRouteHero
        actions={[
          { href: "/transparency/data/transparency.json", label: "Descargar estado JSON" },
          { href: published.manifest_url || snapshot.audit_links?.roadmap, label: "Snapshot inmutable" },
          { href: snapshot.audit_links?.release_registry || snapshot.audit_links?.roadmap, label: "Registro de versiones" },
        ]}
        eyebrow="Estado verificable del proyecto"
        meta={[
          { label: "Último refresco", value: formatDate(snapshot.headline?.last_refresh_at) },
          { label: "Snapshot público", value: formatDate(snapshot.headline?.latest_snapshot_date) },
          { label: "Contrato", value: snapshot.meta?.schema_version || "sin feed" },
        ]}
        summary="Una vista compacta de frescura, fuentes, obstrucciones, escala, versión pública y cambios. Cada cifra enlaza al artefacto que la demuestra."
        title="Transparencia operativa"
      />

      <section className={`transparency-policy ${styles.policy}`} aria-labelledby="transparency-policy-title">
        <div className="transparency-policy__copy">
          <p className={`transparency-policy__eyebrow ${styles.eyebrow}`}>Contrato público</p>
          <h2 className={`transparency-policy__title ${styles.sectionTitle}`} id="transparency-policy-title">Nada verde sin evidencia</h2>
          <p className={`transparency-policy__text ${styles.sectionCopy}`}>Los estados incompletos siguen visibles. Un snapshot publicado no equivale a cobertura representativa ni a promoción metodológica.</p>
        </div>
        <dl className={`transparency-policy__facts ${styles.policyFacts}`}>
          <div className={`transparency-policy__fact ${styles.policyFact}`}>
            <dt className="transparency-policy__fact-label">Datos</dt>
            <dd className="transparency-policy__fact-value">Solo registros oficiales reales</dd>
          </div>
          <div className={`transparency-policy__fact ${styles.policyFact}`}>
            <dt className="transparency-policy__fact-label">Fixtures públicos</dt>
            <dd className="transparency-policy__fact-value">Sintéticos, mock y placeholders: prohibidos</dd>
          </div>
          <div className={`transparency-policy__fact ${styles.policyFact}`}>
            <dt className="transparency-policy__fact-label">Identidad</dt>
            <dd className="transparency-policy__fact-value">Información personal oficial de dominio público: retenida</dd>
          </div>
        </dl>
      </section>

      <section className={`transparency-metrics-section ${styles.section}`} aria-labelledby="transparency-metrics-title">
        <header className={`transparency-section-heading ${styles.sectionHeading}`}>
          <div className="transparency-section-heading__copy">
            <p className={`transparency-section-heading__eyebrow ${styles.eyebrow}`}>Cifras trazables</p>
            <h2 className={`transparency-section-heading__title ${styles.sectionTitle}`} id="transparency-metrics-title">Pulso del sistema</h2>
          </div>
          <p className={`transparency-section-heading__note ${styles.sectionNote}`}>Cada tarjeta abre su fuente exacta.</p>
        </header>
        <div className={`transparency-metric-grid ${styles.metricGrid}`}>
          {(snapshot.metrics || []).map((metric) => <MetricCard metric={metric} key={metric.id} />)}
        </div>
      </section>

      <section className={`transparency-freshness-section ${styles.section}`} aria-labelledby="transparency-freshness-title">
        <header className={`transparency-section-heading ${styles.sectionHeading}`}>
          <div className="transparency-section-heading__copy">
            <p className={`transparency-section-heading__eyebrow ${styles.eyebrow}`}>Frescura explícita</p>
            <h2 className={`transparency-section-heading__title ${styles.sectionTitle}`} id="transparency-freshness-title">Cuándo se comprobó</h2>
          </div>
          <StaticRouteLink href={snapshot.audit_links?.roadmap || "/methods/coverage/"}>Ver roadmap</StaticRouteLink>
        </header>
        <div className={`transparency-freshness-grid ${styles.twoColumnGrid}`}>
          <FreshnessCard title="Estado de fuentes" sourceAt={snapshot.meta?.source_status_generated_at} freshness={sourceHealth.freshness || {}} sourceUrl={sourceHealth.source_url} />
          <FreshnessCard title="Último snapshot público" sourceAt={published.snapshot_date} freshness={published.freshness || {}} sourceUrl={published.pointer_url} />
        </div>
      </section>

      <section className={`transparency-source-health-section ${styles.section}`} aria-labelledby="transparency-source-health-title">
        <header className={`transparency-section-heading ${styles.sectionHeading}`}>
          <div className="transparency-section-heading__copy">
            <p className={`transparency-section-heading__eyebrow ${styles.eyebrow}`}>Cobertura operativa</p>
            <h2 className={`transparency-section-heading__title ${styles.sectionTitle}`} id="transparency-source-health-title">Salud de fuentes</h2>
          </div>
          <StaticRouteLink href={sourceHealth.source_url || "/explorer-sources/"}>Auditar las {formatInt(sourceSummary.present)} fuentes</StaticRouteLink>
        </header>
        <div className={`transparency-source-state-grid ${styles.sourceStateGrid}`}>
          <SourceState label="OK" value={sourceSummary.ok} status="ok" />
          <SourceState label="Degradadas" value={sourceSummary.degraded} status="partial" />
          <SourceState label="No ejecutadas" value={sourceSummary.not_run} status="missing" />
          <SourceState label="Errores" value={sourceSummary.error} status="blocked" />
        </div>
        <aside className={`transparency-obstruction-callout ${styles.callout}`}>
          <div className="transparency-obstruction-callout__copy">
            <strong className="transparency-obstruction-callout__title">{formatInt(obstruction.open_incidents_total)} incidencias abiertas · {formatInt(obstruction.blocked_sources_total)} fuentes afectadas</strong>
            <p className={`transparency-obstruction-callout__text ${styles.cardCopy}`}>{formatInt(obstruction.evidence_files_total)} ficheros públicos permiten comprobar las señales técnicas. Un bloqueo observado no prueba por sí solo ilegalidad, intención, corrupción ni motivo.</p>
          </div>
          <StaticRouteLink href={snapshot.audit_links?.obstruction_tracker || "/obstruction-tracker/"}>Abrir obstrucciones</StaticRouteLink>
        </aside>
      </section>

      <section className={`transparency-snapshot-section ${styles.section}`} aria-labelledby="transparency-snapshot-title">
        <header className={`transparency-section-heading ${styles.sectionHeading}`}>
          <div className="transparency-section-heading__copy">
            <p className={`transparency-section-heading__eyebrow ${styles.eyebrow}`}>Origen durable verificado</p>
            <h2 className={`transparency-section-heading__title ${styles.sectionTitle}`} id="transparency-snapshot-title">Último snapshot público</h2>
          </div>
          <StaticRouteStatusPill value={{ className: sourceStatusClass(published.verification_passed ? "ok" : "blocked"), label: published.verification_passed ? "verificado" : "sin verificar" }} />
        </header>
        <div className={`transparency-snapshot-layout ${styles.snapshotLayout}`}>
          <article className={`transparency-snapshot-summary ${styles.snapshotSummary}`}>
            <dl className={`transparency-snapshot-summary__facts ${styles.snapshotFacts}`}>
              <div className={`transparency-snapshot-summary__fact ${styles.snapshotFact}`}>
                <dt className="transparency-snapshot-summary__fact-label">Fecha</dt>
                <dd className="transparency-snapshot-summary__fact-value">{published.snapshot_date}</dd>
              </div>
              <div className={`transparency-snapshot-summary__fact ${styles.snapshotFact}`}>
                <dt className="transparency-snapshot-summary__fact-label">Release ID</dt>
                <dd className={`transparency-snapshot-summary__fact-value ${styles.hash}`}>{shortHash(published.release_id)}</dd>
              </div>
              <div className={`transparency-snapshot-summary__fact ${styles.snapshotFact}`}>
                <dt className="transparency-snapshot-summary__fact-label">Corpus remotos</dt>
                <dd className="transparency-snapshot-summary__fact-value">{formatInt(published.corpora_total)}</dd>
              </div>
              <div className={`transparency-snapshot-summary__fact ${styles.snapshotFact}`}>
                <dt className="transparency-snapshot-summary__fact-label">Filas</dt>
                <dd className="transparency-snapshot-summary__fact-value">{formatInt(published.rows_total)}</dd>
              </div>
              <div className={`transparency-snapshot-summary__fact ${styles.snapshotFact}`}>
                <dt className="transparency-snapshot-summary__fact-label">Ficheros</dt>
                <dd className="transparency-snapshot-summary__fact-value">{formatInt(published.data_files_total)}</dd>
              </div>
              <div className={`transparency-snapshot-summary__fact ${styles.snapshotFact}`}>
                <dt className="transparency-snapshot-summary__fact-label">Bytes</dt>
                <dd className="transparency-snapshot-summary__fact-value">{formatBytes(published.data_bytes_total)}</dd>
              </div>
            </dl>
            <nav className={`transparency-snapshot-summary__links ${styles.releaseLinks}`} aria-label="Evidencia del snapshot">
              <StaticRouteLink href={published.pointer_url}>Puntero latest.json</StaticRouteLink>
              <StaticRouteLink href={published.manifest_url}>Manifest inmutable</StaticRouteLink>
              <StaticRouteLink href={published.verification_evidence_url}>Verificación live</StaticRouteLink>
            </nav>
            {!published.metadata_freshness ? (
              <aside className={`transparency-snapshot-summary__warning ${styles.warning}`}>
                <strong className="transparency-snapshot-summary__warning-title">Metadata local posterior al origen publicado</strong>
                {(published.warnings || []).map((warning) => <span className="transparency-snapshot-summary__warning-item" key={warning}>{warningLabel(warning)}</span>)}
              </aside>
            ) : null}
          </article>
          <ul className={`transparency-snapshot-corpora ${styles.corpusList}`}>
            {(published.corpora || []).map((corpus) => <SnapshotCorpus corpus={corpus} key={corpus.id} />)}
          </ul>
        </div>
        <aside className={`transparency-scale-callout ${styles.callout}`}>
          <div className="transparency-scale-callout__copy">
            <strong className="transparency-scale-callout__title">Readiness local: {formatInt(readiness.summary?.validated_real_corpora)} corpus validados · {formatInt(readiness.summary?.real_million_scale_lanes)} lanes de millón · {formatInt(readiness.summary?.promoted_lanes)} promovidas</strong>
            <p className={`transparency-scale-callout__text ${styles.cardCopy}`}>El origen durable remoto contiene {formatInt(published.corpora_total)} corpus. El registro local posterior contiene {formatInt(readiness.summary?.registered_real_corpora)}; la diferencia se muestra, no se oculta.</p>
          </div>
          <StaticRouteLink href={readiness.source_url}>Auditar readiness</StaticRouteLink>
        </aside>
      </section>

      <section className={`transparency-release-section ${styles.section}`} aria-labelledby="transparency-release-title">
        <header className={`transparency-section-heading ${styles.sectionHeading}`}>
          <div className="transparency-section-heading__copy">
            <p className={`transparency-section-heading__eyebrow ${styles.eyebrow}`}>Registro verificable</p>
            <h2 className={`transparency-section-heading__title ${styles.sectionTitle}`} id="transparency-release-title">Cambios publicados</h2>
          </div>
          <StaticRouteLink href={snapshot.audit_links?.release_registry || snapshot.audit_links?.roadmap}>Abrir registro JSON</StaticRouteLink>
        </header>
        <div className={`transparency-release-list ${styles.releaseList}`}>
          {(snapshot.recent_changes || []).map((release) => <ReleaseCard release={release} key={release.id} />)}
        </div>
      </section>
    </main>
  );
}
