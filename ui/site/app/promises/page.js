import { formatInt, readPublicJson } from "../static-snapshot.mjs";
import { StaticRouteHero, StaticRouteLink } from "../static-route-components";
import styles from "./promises.module.css";

const EMPTY_SNAPSHOT = {
  source: {},
  methodology: {},
  counts: {},
  items: [],
};

export const metadata = {
  title: "Promesas con evidencia | Vota Con La Chola",
  description:
    "Primer corte verificable de promesas electorales con actor, cita exacta, página, hash y clasificación versionada.",
};

function shortHash(value) {
  const raw = String(value || "");
  return raw ? `${raw.slice(0, 12)}…` : "sin hash";
}

function topicLabel(topic) {
  return topic.label || topic.canonical_key || "sin tema";
}

function PromiseCard({ item, index }) {
  const evidence = item.evidence || {};
  const sourceHref = `${evidence.source_url || ""}#page=${evidence.page_start || 1}`;
  return (
    <li className={`promise-sample-item ${styles.promiseItem}`}>
      <article className={`promise-evidence-card ${styles.promiseCard}`}>
        <header className={`promise-evidence-card__header ${styles.promiseHeader}`}>
          <div className="promise-evidence-card__identity">
            <span className={`promise-evidence-card__ordinal ${styles.ordinal}`}>
              Promesa {String(index + 1).padStart(2, "0")}
            </span>
            <span className={`promise-evidence-card__actor ${styles.actor}`}>
              {item.actor?.name || "Actor desconocido"}
            </span>
          </div>
          <span className={`promise-evidence-card__review ${styles.reviewBadge}`}>
            regla confirmada
          </span>
        </header>

        <blockquote className={`promise-evidence-card__quote ${styles.quote}`}>
          {evidence.exact_quote}
        </blockquote>

        <ul className={`promise-evidence-card__topics ${styles.topicList}`} aria-label="Temas">
          {(item.topics || []).map((topic) => (
            <li className={`promise-evidence-card__topic ${styles.topic}`} key={topic.canonical_key}>
              {topicLabel(topic)}
            </li>
          ))}
        </ul>

        <dl className={`promise-evidence-card__facts ${styles.factGrid}`}>
          <div className="promise-evidence-card__fact">
            <dt className={`promise-evidence-card__fact-label ${styles.factLabel}`}>Página</dt>
            <dd className={`promise-evidence-card__fact-value ${styles.factValue}`}>
              {evidence.page_start}
            </dd>
          </div>
          <div className="promise-evidence-card__fact">
            <dt className={`promise-evidence-card__fact-label ${styles.factLabel}`}>Medición</dt>
            <dd className={`promise-evidence-card__fact-value ${styles.factValue}`}>
              {item.measurability?.state === "measurable" ? "medible" : "parcialmente medible"}
            </dd>
          </div>
          <div className="promise-evidence-card__fact">
            <dt className={`promise-evidence-card__fact-label ${styles.factLabel}`}>Cumplimiento</dt>
            <dd className={`promise-evidence-card__fact-value ${styles.factValue}`}>no evaluado</dd>
          </div>
        </dl>

        <footer className={`promise-evidence-card__footer ${styles.promiseFooter}`}>
          <StaticRouteLink href={sourceHref}>Abrir PDF oficial · página {evidence.page_start}</StaticRouteLink>
          <code className={`promise-evidence-card__hash ${styles.hash}`}>
            cita {shortHash(evidence.quote_sha256)}
          </code>
        </footer>
      </article>
    </li>
  );
}

export default function PromisesPage() {
  const snapshot = readPublicJson("promises/data/bng-2023.json", EMPTY_SNAPSHOT);
  const source = snapshot.source || {};
  const counts = snapshot.counts || {};

  return (
    <main className={`shell promises-page ${styles.page}`}>
      <StaticRouteHero
        actions={[
          { href: "/promises/data/bng-2023.json", label: "Descargar muestra JSON" },
          { href: source.source_url, label: "Abrir manifiesto oficial" },
        ]}
        eyebrow="Antes del voto · texto original"
        meta={[
          { label: "Actor", value: "BNG" },
          { label: "Documento", value: "Eleccións Xerais 2023" },
          { label: "Release", value: shortHash(snapshot.release_id) },
        ]}
        summary="Promesas extraídas de un manifiesto oficial real. Cada fila conserva actor, cita, página y hash. Este corte identifica compromisos; todavía no afirma si se cumplieron."
        title="Promesas con evidencia"
      />

      <section className={`promises-contract-panel ${styles.contractPanel}`} aria-labelledby="promises-contract-title">
        <div className="promises-contract-panel__copy">
          <p className={`promises-contract-panel__eyebrow ${styles.eyebrow}`}>Contrato de lectura</p>
          <h2 className={`promises-contract-panel__title ${styles.sectionTitle}`} id="promises-contract-title">
            Lo dicho no es lo cumplido
          </h2>
          <p className={`promises-contract-panel__summary ${styles.sectionCopy}`}>
            La muestra publica solo viñetas con acción explícita y contexto completo. Los fragmentos ambiguos siguen fuera. El estado de cumplimiento permanece “no evaluado” hasta enlazar evidencia posterior independiente.
          </p>
        </div>
        <dl className={`promises-contract-panel__metrics ${styles.metricGrid}`}>
          <div className={`promises-contract-panel__metric ${styles.metric}`}>
            <dt className="promises-contract-panel__metric-label">Páginas</dt>
            <dd className="promises-contract-panel__metric-value">{formatInt(source.page_count)}</dd>
          </div>
          <div className={`promises-contract-panel__metric ${styles.metric}`}>
            <dt className="promises-contract-panel__metric-label">Segmentos</dt>
            <dd className="promises-contract-panel__metric-value">{formatInt(counts.segments_seen)}</dd>
          </div>
          <div className={`promises-contract-panel__metric ${styles.metric}`}>
            <dt className="promises-contract-panel__metric-label">Promesas modeladas</dt>
            <dd className="promises-contract-panel__metric-value">{formatInt(counts.promises_loaded)}</dd>
          </div>
          <div className={`promises-contract-panel__metric ${styles.metric}`}>
            <dt className="promises-contract-panel__metric-label">Muestra pública</dt>
            <dd className="promises-contract-panel__metric-value">{formatInt(counts.published_promises)}</dd>
          </div>
        </dl>
      </section>

      <section className={`promises-source-panel ${styles.sourcePanel}`} aria-labelledby="promises-source-title">
        <div className="promises-source-panel__copy">
          <p className={`promises-source-panel__eyebrow ${styles.eyebrow}`}>Fuente oficial verificada</p>
          <h2 className={`promises-source-panel__title ${styles.sectionTitle}`} id="promises-source-title">
            {source.title || "Documento sin título"}
          </h2>
          <p className={`promises-source-panel__summary ${styles.sectionCopy}`}>
            {formatInt(source.bytes)} bytes · {formatInt(source.page_count)} páginas · gallego · información pública conservada.
          </p>
        </div>
        <code className={`promises-source-panel__hash ${styles.documentHash}`}>
          sha256 {source.content_sha256 || "sin hash"}
        </code>
      </section>

      <section className={`promises-sample-section ${styles.sampleSection}`} aria-labelledby="promises-sample-title">
        <header className={`promises-sample-section__header ${styles.sectionHeader}`}>
          <div className="promises-sample-section__heading">
            <p className={`promises-sample-section__eyebrow ${styles.eyebrow}`}>Muestra auditada</p>
            <h2 className={`promises-sample-section__title ${styles.sectionTitle}`} id="promises-sample-title">
              Veinte compromisos, veinte anclas
            </h2>
          </div>
          <p className={`promises-sample-section__note ${styles.sectionNote}`}>
            Orden documental. Sin ranking, puntuación política ni imputación de cumplimiento.
          </p>
        </header>
        <ol className={`promises-sample-list ${styles.promiseList}`}>
          {(snapshot.items || []).map((item, index) => (
            <PromiseCard index={index} item={item} key={item.promise_id} />
          ))}
        </ol>
      </section>
    </main>
  );
}
