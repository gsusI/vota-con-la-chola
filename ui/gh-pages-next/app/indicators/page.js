import { formatInt, readPublicJson } from "../static-snapshot.mjs";
import { StaticRouteHero, StaticRouteLink } from "../static-route-components";
import styles from "./indicators.module.css";

const EMPTY_SNAPSHOT = {
  source: {},
  full_corpus: {},
  indicator: {},
  indicator_release: {},
  coverage: {},
  limitations: [],
  series: [],
};

export const metadata = {
  title: "Indicadores oficiales y revisiones | Vota Con La Chola",
  description:
    "Indicadores económicos y sociales oficiales con geografía, periodo, unidad, estado estadístico, revisión y evidencia de celda.",
};

const LEVEL_LABELS = {
  country: "España",
  NUTS1: "NUTS 1",
  NUTS2: "NUTS 2",
  NUTS3: "NUTS 3",
};

function shortHash(value) {
  const raw = String(value || "");
  return raw ? `${raw.slice(0, 12)}…` : "sin hash";
}

function formatValue(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return "sin valor";
  return new Intl.NumberFormat("es-ES", { maximumFractionDigits: 2 }).format(parsed);
}

function latestObservation(series) {
  return [...(series.observations || [])].sort((left, right) =>
    String(right.period_label).localeCompare(String(left.period_label)),
  )[0];
}

function statusLabel(code) {
  if (code === "p") return "provisional";
  if (code === "e") return "estimado";
  if (code === "b") return "ruptura de serie";
  if (code === "|C") return "confidencial";
  return "sin marca adicional";
}

function latestSeriesRows(series) {
  return (series || [])
    .map((item) => ({ series: item, observation: latestObservation(item) }))
    .filter((item) => item.observation)
    .sort((left, right) => {
      const levelOrder = { country: 0, NUTS1: 1, NUTS2: 2, NUTS3: 3 };
      const byLevel =
        (levelOrder[left.series.geography_level] ?? 9) -
        (levelOrder[right.series.geography_level] ?? 9);
      return byLevel || String(left.series.geography_code).localeCompare(String(right.series.geography_code));
    });
}

function NationalHistory({ series }) {
  const observations = series?.observations || [];
  const maximum = Math.max(...observations.map((item) => Number(item.value_decimal) || 0), 1);

  return (
    <ol className={`indicator-history__list ${styles.historyList}`}>
      {observations.map((observation) => {
        const width = `${Math.max(2, ((Number(observation.value_decimal) || 0) / maximum) * 100)}%`;
        return (
          <li className={`indicator-history__item ${styles.historyItem}`} key={observation.indicator_observation_version_id}>
            <span className={`indicator-history__period ${styles.historyPeriod}`}>{observation.period_label}</span>
            <span className={`indicator-history__track ${styles.historyTrack}`} aria-hidden="true">
              <span className={`indicator-history__bar ${styles.historyBar}`} style={{ width }} />
            </span>
            <strong className={`indicator-history__value ${styles.historyValue}`}>
              {formatValue(observation.value_decimal)}
            </strong>
            <span className={`indicator-history__status ${styles.historyStatus}`}>
              {statusLabel(observation.source_status_code)}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export default function IndicatorsPage() {
  const snapshot = readPublicJson(
    "indicators/data/eurostat-gdp-es.json",
    EMPTY_SNAPSHOT,
  );
  const coverage = snapshot.coverage || {};
  const fullCorpus = snapshot.full_corpus || {};
  const rows = latestSeriesRows(snapshot.series);
  const nationalSeries = (snapshot.series || []).find(
    (series) => series.geography_code === "ES",
  );

  return (
    <main className={`shell indicators-page ${styles.page}`}>
      <StaticRouteHero
        actions={[
          { href: "/indicators/data/eurostat-gdp-es.json", label: "Descargar 2.091 observaciones" },
          { href: snapshot.source?.source_url, label: "Abrir dataset Eurostat" },
        ]}
        eyebrow="Outcomes · revisiones · evidencia de celda"
        meta={[
          { label: "Corpus oficial", value: `${formatInt(fullCorpus.observations)} observaciones` },
          { label: "Slice España", value: `${formatInt(coverage.observations)} observaciones` },
          { label: "Release", value: shortHash(snapshot.release_id) },
        ]}
        summary="Primera familia pública: PIB por habitante en PPS para todos los códigos españoles presentes en Eurostat. Valor, territorio, periodo, provisionalidad y celda bruta permanecen unidos."
        title="Lo que cambió, sin inventar por qué"
      />

      <section className={`indicators-truth-panel ${styles.truthPanel}`} aria-labelledby="indicators-truth-title">
        <div className="indicators-truth-panel__copy">
          <p className={`indicators-truth-panel__eyebrow ${styles.eyebrow}`}>Contrato de lectura</p>
          <h2 className={`indicators-truth-panel__title ${styles.sectionTitle}`} id="indicators-truth-title">
            Un indicador no reparte mérito ni culpa
          </h2>
          <p className={`indicators-truth-panel__summary ${styles.sectionCopy}`}>
            Este release demuestra qué publicó Eurostat. No demuestra que una política, partido o cargo causara la variación. PIB por habitante tampoco equivale a bienestar, reparto, calidad de servicios o ausencia de corrupción.
          </p>
        </div>
        <dl className={`indicators-truth-panel__metrics ${styles.metricGrid}`}>
          <div className={`indicators-truth-panel__metric ${styles.metric}`}>
            <dt className="indicators-truth-panel__metric-label">Series españolas</dt>
            <dd className="indicators-truth-panel__metric-value">{formatInt(coverage.series)}</dd>
          </div>
          <div className={`indicators-truth-panel__metric ${styles.metric}`}>
            <dt className="indicators-truth-panel__metric-label">Celdas exactas</dt>
            <dd className="indicators-truth-panel__metric-value">{formatInt(coverage.observations)}</dd>
          </div>
          <div className={`indicators-truth-panel__metric ${styles.metric}`}>
            <dt className="indicators-truth-panel__metric-label">Celdas provisionales</dt>
            <dd className="indicators-truth-panel__metric-value">{formatInt(coverage.source_status_codes?.p)}</dd>
          </div>
          <div className={`indicators-truth-panel__metric ${styles.metric}`}>
            <dt className="indicators-truth-panel__metric-label">Claims causales</dt>
            <dd className="indicators-truth-panel__metric-value">0</dd>
          </div>
        </dl>
      </section>

      <section className={`indicators-revision-panel ${styles.revisionPanel}`} aria-labelledby="indicators-revision-title">
        <div className="indicators-revision-panel__copy">
          <p className={`indicators-revision-panel__eyebrow ${styles.eyebrow}`}>Historial honesto</p>
          <h2 className={`indicators-revision-panel__title ${styles.sectionTitle}`} id="indicators-revision-title">
            Baseline no significa dato definitivo
          </h2>
          <p className={`indicators-revision-panel__summary ${styles.sectionCopy}`}>
            Hay una captura oficial verificada. Por eso las {formatInt(coverage.revision_baseline)} observaciones son baseline, no “sin revisiones”. El siguiente gate exige otra captura real y un balance de valores iguales, cambiados y retirados.
          </p>
        </div>
        <dl className={`indicators-revision-panel__states ${styles.stateGrid}`}>
          <div className="indicators-revision-panel__state">
            <dt className="indicators-revision-panel__state-label">Comparación entre releases</dt>
            <dd className="indicators-revision-panel__state-value">pendiente de segunda captura</dd>
          </div>
          <div className="indicators-revision-panel__state">
            <dt className="indicators-revision-panel__state-label">Incertidumbre publicada</dt>
            <dd className="indicators-revision-panel__state-value">no proporcionada</dd>
          </div>
          <div className="indicators-revision-panel__state">
            <dt className="indicators-revision-panel__state-label">Versión geográfica explícita</dt>
            <dd className="indicators-revision-panel__state-value">no declarada en la captura</dd>
          </div>
        </dl>
      </section>

      <section className={`indicator-history ${styles.historySection}`} aria-labelledby="indicator-history-title">
        <header className={`indicator-history__header ${styles.sectionHeader}`}>
          <div className="indicator-history__heading">
            <p className={`indicator-history__eyebrow ${styles.eyebrow}`}>España · 2000–2024</p>
            <h2 className={`indicator-history__title ${styles.sectionTitle}`} id="indicator-history-title">
              Serie nacional publicada por Eurostat
            </h2>
          </div>
          <p className={`indicator-history__note ${styles.sectionNote}`}>
            Unidad: {snapshot.indicator?.unit_label}. Las barras muestran magnitud dentro de esta serie; no inflación, distribución ni causalidad.
          </p>
        </header>
        <NationalHistory series={nationalSeries} />
      </section>

      <section className={`indicator-geography ${styles.geographySection}`} aria-labelledby="indicator-geography-title">
        <header className={`indicator-geography__header ${styles.sectionHeader}`}>
          <div className="indicator-geography__heading">
            <p className={`indicator-geography__eyebrow ${styles.eyebrow}`}>Último punto disponible por código</p>
            <h2 className={`indicator-geography__title ${styles.sectionTitle}`} id="indicator-geography-title">
              Toda la geografía española del slice
            </h2>
          </div>
          <p className={`indicator-geography__note ${styles.sectionNote}`}>
            Incluye país, NUTS 1, NUTS 2 y NUTS 3. Los códigos históricos se conservan; no se fusionan fronteras por conveniencia.
          </p>
        </header>
        <div className={`indicator-geography__table-wrap ${styles.tableWrap}`}>
          <table className={`indicator-geography__table ${styles.table}`}>
            <thead className="indicator-geography__table-head">
              <tr className="indicator-geography__table-row indicator-geography__table-row--head">
                <th className="indicator-geography__table-heading" scope="col">Código</th>
                <th className="indicator-geography__table-heading" scope="col">Territorio</th>
                <th className="indicator-geography__table-heading" scope="col">Nivel</th>
                <th className="indicator-geography__table-heading" scope="col">Periodo</th>
                <th className="indicator-geography__table-heading" scope="col">Valor PPS/hab.</th>
                <th className="indicator-geography__table-heading" scope="col">Estado fuente</th>
                <th className="indicator-geography__table-heading" scope="col">Celda</th>
              </tr>
            </thead>
            <tbody className="indicator-geography__table-body">
              {rows.map(({ series, observation }) => (
                <tr className={`indicator-geography__table-row ${styles.tableRow}`} key={series.indicator_series_version_id}>
                  <td className={`indicator-geography__code ${styles.codeCell}`}>{series.geography_code}</td>
                  <th className="indicator-geography__name" scope="row">{series.geography_name || "nombre no publicado"}</th>
                  <td className="indicator-geography__level">{LEVEL_LABELS[series.geography_level] || series.geography_level}</td>
                  <td className="indicator-geography__period">{observation.period_label}</td>
                  <td className={`indicator-geography__value ${styles.valueCell}`}>{formatValue(observation.value_decimal)}</td>
                  <td className="indicator-geography__status">
                    <span className={`indicator-geography__status-badge ${observation.source_status_code ? styles.statusProvisional : styles.statusNeutral}`}>
                      {statusLabel(observation.source_status_code)}
                    </span>
                  </td>
                  <td className={`indicator-geography__cell-index ${styles.codeCell}`}>{observation.raw_cell_index}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className={`indicator-provenance ${styles.provenanceSection}`} aria-labelledby="indicator-provenance-title">
        <div className="indicator-provenance__copy">
          <p className={`indicator-provenance__eyebrow ${styles.eyebrow}`}>Auditar el origen</p>
          <h2 className={`indicator-provenance__title ${styles.sectionTitle}`} id="indicator-provenance-title">
            Cada valor conserva celda, hash y método
          </h2>
          <p className={`indicator-provenance__summary ${styles.sectionCopy}`}>
            El artefacto público enlaza las {formatInt(coverage.indicator_observation_evidence)} observaciones a índices JSON-stat concretos del bruto oficial de {formatInt(snapshot.source?.raw_bytes)} bytes.
          </p>
        </div>
        <div className={`indicator-provenance__actions ${styles.provenanceActions}`}>
          <StaticRouteLink href={snapshot.source?.methodology_url}>Leer metodología Eurostat</StaticRouteLink>
          <StaticRouteLink href={snapshot.source?.license_url}>Ver política de reutilización</StaticRouteLink>
          <code className={`indicator-provenance__hash ${styles.hash}`}>SHA-256 {snapshot.source?.raw_content_sha256}</code>
        </div>
      </section>
    </main>
  );
}
