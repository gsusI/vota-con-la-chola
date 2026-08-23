import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { formatDate, formatInt } from "../static-snapshot.mjs";
import { StaticRouteLink } from "../static-route-components";
import PolicyOutcomesRuntimeGate from "./PolicyOutcomesRuntimeGate";
import {
  isSafePolicyOutcomesManifestPath,
  resolvePolicyOutcomesEvidenceAssetPath,
  validatePolicyOutcomesPackage,
} from "./status-contract.mjs";
import styles from "./policy-outcomes.module.css";


const STATUS_PATH = "/policy-outcomes/data/policy-outcomes.json";

export const metadata = {
  title: "Estado de resultados | Vota Con La Chola",
  description:
    "Estado público verificable de la evidencia y los límites de los vínculos de resultado.",
};

function sha256(bytes) {
  return crypto.createHash("sha256").update(bytes).digest("hex");
}

function readPublicBytes(publicPath) {
  const segments = String(publicPath || "").split("/").filter(Boolean);
  const publicRoot = path.resolve(process.cwd(), "public");
  const filePath = path.resolve(publicRoot, ...segments);
  if (!filePath.startsWith(`${publicRoot}${path.sep}`) || !fs.existsSync(filePath)) return null;
  try {
    return fs.readFileSync(filePath);
  } catch (_error) {
    return null;
  }
}

function parseJsonBytes(bytes) {
  if (!bytes) return null;
  try {
    const value = JSON.parse(bytes.toString("utf8"));
    return value && typeof value === "object" && !Array.isArray(value) ? value : null;
  } catch (_error) {
    return null;
  }
}

function loadValidatedPackage() {
  const statusRaw = readPublicBytes(STATUS_PATH);
  const status = parseJsonBytes(statusRaw);
  const manifestPath = status?.evidence_package?.manifest_path;
  const manifestRaw = isSafePolicyOutcomesManifestPath(manifestPath)
    ? readPublicBytes(manifestPath)
    : null;
  const manifest = parseJsonBytes(manifestRaw);
  const observedAssets = {};
  if (manifest?.assets && typeof manifest.assets === "object" && !Array.isArray(manifest.assets)) {
    for (const [key, fact] of Object.entries(manifest.assets)) {
      const publicAssetPath = resolvePolicyOutcomesEvidenceAssetPath(manifestPath, fact?.path);
      const assetRaw = publicAssetPath ? readPublicBytes(publicAssetPath) : null;
      if (assetRaw) {
        observedAssets[key] = { bytes: assetRaw.length, sha256: sha256(assetRaw) };
      }
    }
  }
  const validation = validatePolicyOutcomesPackage({
    status,
    manifest,
    statusBytes: statusRaw?.length,
    statusSha256: statusRaw ? sha256(statusRaw) : "",
    manifestSha256: manifestRaw ? sha256(manifestRaw) : "",
    observedAssets,
  });
  return validation.ok ? { status, manifest } : { status: null, manifest: null };
}

function Metric({ label, value, note, state }) {
  return (
    <article className={`policy-outcome-metric policy-outcome-metric--${state} ${styles.metric}`}>
      <span className={`policy-outcome-metric__label ${styles.metricLabel}`}>{label}</span>
      <strong className={`policy-outcome-metric__value ${styles.metricValue}`}>{value}</strong>
      <span className={`policy-outcome-metric__note ${styles.metricNote}`}>{note}</span>
    </article>
  );
}

function GateStep({ number, title, state, children }) {
  return (
    <li className={`policy-outcome-gate-step policy-outcome-gate-step--${state} ${styles.gateStep}`}>
      <span className={`policy-outcome-gate-step__number ${styles.gateNumber}`} aria-hidden="true">{number}</span>
      <div className="policy-outcome-gate-step__copy">
        <div className={`policy-outcome-gate-step__heading ${styles.gateHeading}`}>
          <h3 className={`policy-outcome-gate-step__title ${styles.gateTitle}`}>{title}</h3>
          <span className={`policy-outcome-gate-step__status policy-outcome-gate-step__status--${state} ${styles.gateStatus}`}>
            {state === "complete" ? "completado" : "pendiente"}
          </span>
        </div>
        <p className={`policy-outcome-gate-step__description ${styles.gateDescription}`}>{children}</p>
      </div>
    </li>
  );
}

function EvidenceLink({ manifest, assetKey, children }) {
  const fact = manifest?.assets?.[assetKey];
  if (!fact) return null;
  const href = `/policy-outcomes/evidence/${manifest.package_id}/${fact.path}`;
  return <StaticRouteLink href={href}>{children}</StaticRouteLink>;
}

export default function PolicyOutcomesPage() {
  const { status: snapshot, manifest } = loadValidatedPackage();
  const feedIsValid = Boolean(snapshot && manifest);

  if (!feedIsValid) {
    return (
      <main className={`shell policy-outcomes-status-page policy-outcomes-status-page--unverified ${styles.page}`}>
        <section className={`policy-outcomes-hero policy-outcomes-hero--unverified ${styles.hero}`} aria-labelledby="policy-outcomes-title">
          <div className="policy-outcomes-hero__copy">
            <p className={`policy-outcomes-hero__eyebrow ${styles.eyebrow}`}>Estado público no verificable</p>
            <h1 className={`policy-outcomes-hero__title ${styles.heroTitle}`} id="policy-outcomes-title">
              El paquete de evidencia no supera el contrato de publicación
            </h1>
            <p className={`policy-outcomes-hero__summary ${styles.heroSummary}`}>
              La página falla cerrada. No publica conteos, candidatos, fuentes ni conclusiones mientras estado, manifest y evidencia no coincidan exactamente.
            </p>
          </div>
        </section>
        <section
          className={`policy-outcomes-publication-state policy-outcomes-publication-state--unverified ${styles.statePanel}`}
          aria-labelledby="policy-outcomes-state-title"
          role="status"
        >
          <div className={`policy-outcomes-publication-state__marker ${styles.stateMarker}`} aria-hidden="true">!</div>
          <div className="policy-outcomes-publication-state__copy">
            <p className={`policy-outcomes-publication-state__eyebrow ${styles.eyebrow}`}>Bloqueo preventivo</p>
            <h2 className={`policy-outcomes-publication-state__title ${styles.sectionTitle}`} id="policy-outcomes-state-title">
              Estado, manifest o evidencia no verificables
            </h2>
            <p className={`policy-outcomes-publication-state__description ${styles.sectionCopy}`}>
              Ningún dato parcial se convierte en afirmación pública. El paquete completo debe volver a validarse antes de mostrar hechos.
            </p>
          </div>
        </section>
      </main>
    );
  }

  const pipeline = snapshot?.pipeline;
  const scope = snapshot?.bounded_universe;
  const inputs = snapshot?.selected_inputs;
  const identity = manifest?.identity_retention;

  return (
    <PolicyOutcomesRuntimeGate>
      <main className={`shell policy-outcomes-status-page ${styles.page}`}>
      <section className={`policy-outcomes-hero ${styles.hero}`} aria-labelledby="policy-outcomes-title">
        <div className="policy-outcomes-hero__copy">
          <p className={`policy-outcomes-hero__eyebrow ${styles.eyebrow}`}>
            {feedIsValid ? "Estado público verificable · C0 / L1" : "Estado público · no verificable"}
          </p>
          <h1 className={`policy-outcomes-hero__title ${styles.heroTitle}`} id="policy-outcomes-title">
            {feedIsValid
              ? "Un candidato metodológico pendiente; 0 vínculos de resultado validados"
              : "El paquete de evidencia no supera el contrato de publicación"}
          </h1>
          <p className={`policy-outcomes-hero__summary ${styles.heroSummary}`}>
            {feedIsValid
              ? "Una votación del Senado, su iniciativa y una serie de Eurostat fueron seleccionadas juntas dentro de un candidato metodológico pendiente. La selección es pública y verificable byte por byte. No es un vínculo validado ni una conclusión sobre resultados."
              : "La página falla cerrada. No muestra conteos ni fuentes como hechos mientras estado, manifest y hashes no coincidan con la identidad de release aprobada."}
          </p>
        </div>
        <dl className={`policy-outcomes-hero__facts ${styles.heroFacts}`}>
          <div className={`policy-outcomes-hero__fact ${styles.heroFact}`}>
            <dt className="policy-outcomes-hero__fact-label">Candidatos pendientes divulgados</dt>
            <dd className="policy-outcomes-hero__fact-value">
              {feedIsValid ? formatInt(pipeline.pending_methodological_candidates_disclosed) : "no verificable"}
            </dd>
          </div>
          <div className={`policy-outcomes-hero__fact ${styles.heroFact}`}>
            <dt className="policy-outcomes-hero__fact-label">Vínculos validados</dt>
            <dd className="policy-outcomes-hero__fact-value">
              {feedIsValid ? formatInt(pipeline.validated_outcome_links) : "no verificable"}
            </dd>
          </div>
          <div className={`policy-outcomes-hero__fact ${styles.heroFact}`}>
            <dt className="policy-outcomes-hero__fact-label">Gate actual</dt>
            <dd className="policy-outcomes-hero__fact-value">
              {feedIsValid ? "revisión humana pendiente" : "bloqueo preventivo"}
            </dd>
          </div>
        </dl>
      </section>

      <section
        className={`policy-outcomes-publication-state policy-outcomes-publication-state--${feedIsValid ? "verified" : "unverified"} ${styles.statePanel}`}
        aria-labelledby="policy-outcomes-state-title"
        role="status"
      >
        <div className={`policy-outcomes-publication-state__marker ${styles.stateMarker}`} aria-hidden="true">
          {feedIsValid ? "1/0" : "!"}
        </div>
        <div className="policy-outcomes-publication-state__copy">
          <p className={`policy-outcomes-publication-state__eyebrow ${styles.eyebrow}`}>
            {feedIsValid ? "Divulgación honesta" : "Bloqueo preventivo"}
          </p>
          <h2 className={`policy-outcomes-publication-state__title ${styles.sectionTitle}`} id="policy-outcomes-state-title">
            {feedIsValid
              ? "Un candidato pendiente divulgado; 0 vínculos de resultado validados"
              : "Estado, manifest o evidencia no verificables"}
          </h2>
          <p className={`policy-outcomes-publication-state__description ${styles.sectionCopy}`}>
            {feedIsValid
              ? "Las entradas no están sueltas ni se presentan como una asociación aprobada: están seleccionadas juntas en un candidato L1 que exige revisión humana. No pertenece a ningún release de resultados."
              : "Ningún dato parcial se convierte en afirmación pública. Corrige el paquete y vuelve a validar todos los bytes antes de publicar."}
          </p>
        </div>
      </section>

      <section className={`policy-outcomes-pending-candidate ${styles.section}`} aria-labelledby="policy-outcomes-candidate-title">
        <header className={`policy-outcomes-section-heading ${styles.sectionHeading}`}>
          <div className="policy-outcomes-section-heading__copy">
            <p className={`policy-outcomes-section-heading__eyebrow ${styles.eyebrow}`}>Candidato metodológico pendiente</p>
            <h2 className={`policy-outcomes-section-heading__title ${styles.sectionTitle}`} id="policy-outcomes-candidate-title">
              Las tres entradas seleccionadas juntas
            </h2>
          </div>
          <p className={`policy-outcomes-section-heading__note ${styles.sectionNote}`}>
            Selección metodológica no equivale a asociación estadística, causalidad, efecto, mérito, culpa, éxito, fracaso o corrupción.
          </p>
        </header>
        <div className={`policy-outcomes-input-grid ${styles.inputGrid}`}>
          <article className={`policy-outcomes-input policy-outcomes-input--vote ${styles.inputCard}`}>
            <p className={`policy-outcomes-input__eyebrow ${styles.eyebrow}`}>Acción seleccionada</p>
            <h3 className={`policy-outcomes-input__title ${styles.inputTitle}`}>Votación oficial del Senado</h3>
            <p className={`policy-outcomes-input__description ${styles.metricNote}`}>
              Registro normalizado exacto. Corte {formatDate(inputs?.senate_vote?.source_snapshot_date)}. XML original específico ausente: gap explícito.
            </p>
            {feedIsValid ? <StaticRouteLink href={inputs.senate_vote.official_page_url}>Abrir votación oficial</StaticRouteLink> : null}
          </article>
          <article className={`policy-outcomes-input policy-outcomes-input--initiative ${styles.inputCard}`}>
            <p className={`policy-outcomes-input__eyebrow ${styles.eyebrow}`}>Contexto de acción</p>
            <h3 className={`policy-outcomes-input__title ${styles.inputTitle}`}>Iniciativa oficial del Senado</h3>
            <p className={`policy-outcomes-input__description ${styles.metricNote}`}>
              Registro normalizado exacto enlazado a la votación. Corte {formatDate(inputs?.senate_initiative?.source_snapshot_date)}.
            </p>
            {feedIsValid ? <StaticRouteLink href={inputs.senate_initiative.official_url}>Abrir iniciativa oficial</StaticRouteLink> : null}
          </article>
          <article className={`policy-outcomes-input policy-outcomes-input--indicator ${styles.inputCard}`}>
            <p className={`policy-outcomes-input__eyebrow ${styles.eyebrow}`}>Indicador seleccionado</p>
            <h3 className={`policy-outcomes-input__title ${styles.inputTitle}`}>Serie oficial de Eurostat</h3>
            <p className={`policy-outcomes-input__description ${styles.metricNote}`}>
              Captura original exacta del dataset {inputs?.eurostat_indicator?.dataset_code || "no verificable"}. Corte {formatDate(inputs?.eurostat_indicator?.source_snapshot_date)}.
            </p>
            {feedIsValid ? <StaticRouteLink href={inputs.eurostat_indicator.official_url}>Abrir dataset oficial</StaticRouteLink> : null}
          </article>
        </div>
      </section>

      <section className={`policy-outcomes-bounded-universe ${styles.section}`} aria-labelledby="policy-outcomes-scope-title">
        <header className={`policy-outcomes-section-heading ${styles.sectionHeading}`}>
          <div className="policy-outcomes-section-heading__copy">
            <p className={`policy-outcomes-section-heading__eyebrow ${styles.eyebrow}`}>Cierre exacto del universo acotado</p>
            <h2 className={`policy-outcomes-section-heading__title ${styles.sectionTitle}`} id="policy-outcomes-scope-title">
              20 acciones × 1 serie elegible = 20 pares
            </h2>
          </div>
          <p className={`policy-outcomes-section-heading__note ${styles.sectionNote}`}>
            Cierre verificable de este alcance. No se buscaron todas las acciones, todos los indicadores ni todos los pares posibles.
          </p>
        </header>
        <div className={`policy-outcomes-metrics ${styles.metricGrid}`}>
          <Metric label="Acciones candidatas" value={feedIsValid ? formatInt(scope.action_candidates) : "—"} note="Las 20 filas canónicas se descargan completas." state="bounded" />
          <Metric label="Series elegibles" value={feedIsValid ? formatInt(scope.eligible_indicator_series) : "—"} note="Filtro geográfico exacto ES / country." state="bounded" />
          <Metric label="Pares acotados" value={feedIsValid ? formatInt(scope.candidate_pairs) : "—"} note="Producto exacto 20 × 1; no búsqueda global." state="machine" />
          <Metric label="Revisados por persona" value={feedIsValid ? formatInt(pipeline.human_reviewed_pairs) : "—"} note="Ninguna decisión humana registrada aún." state="pending" />
        </div>
        <dl className={`policy-outcomes-closure-facts ${styles.provenanceFacts}`}>
          <div className="policy-outcomes-closure-facts__fact">
            <dt className="policy-outcomes-closure-facts__label">SHA universo de acciones</dt>
            <dd className="policy-outcomes-closure-facts__value"><code className="policy-outcomes-closure-facts__hash">{scope?.action_universe_sha256 || "no verificable"}</code></dd>
          </div>
          <div className="policy-outcomes-closure-facts__fact">
            <dt className="policy-outcomes-closure-facts__label">SHA serie elegible</dt>
            <dd className="policy-outcomes-closure-facts__value"><code className="policy-outcomes-closure-facts__hash">{scope?.eligible_indicator_series_sha256 || "no verificable"}</code></dd>
          </div>
          <div className="policy-outcomes-closure-facts__fact">
            <dt className="policy-outcomes-closure-facts__label">SHA cierre combinado</dt>
            <dd className="policy-outcomes-closure-facts__value"><code className="policy-outcomes-closure-facts__hash">{scope?.combined_scope_sha256 || "no verificable"}</code></dd>
          </div>
        </dl>
      </section>

      <section className={`policy-outcomes-public-evidence ${styles.auditSection}`} aria-labelledby="policy-outcomes-evidence-title">
        <div className="policy-outcomes-public-evidence__copy">
          <p className={`policy-outcomes-public-evidence__eyebrow ${styles.eyebrow}`}>Evidencia pública byte por byte</p>
          <h2 className={`policy-outcomes-public-evidence__title ${styles.sectionTitle}`} id="policy-outcomes-evidence-title">
            Verificar el candidato y auditar sus límites
          </h2>
          <p className={`policy-outcomes-public-evidence__description ${styles.sectionCopy}`}>
            El manifest content-addressed fija ruta, bytes, SHA-256 y función de cada activo. Se publica al final de la promoción. El manifest es unsigned: aporta integridad por hash, no autenticación criptográfica propia.
          </p>
        </div>
        <nav className={`policy-outcomes-public-evidence__downloads ${styles.auditLinks}`} aria-label="Descargas de evidencia de resultados">
          {feedIsValid ? <StaticRouteLink href={snapshot.evidence_package.manifest_path}>Descargar manifest de evidencia</StaticRouteLink> : null}
          {feedIsValid ? <StaticRouteLink href={STATUS_PATH}>Descargar estado público</StaticRouteLink> : null}
          <EvidenceLink manifest={manifest} assetKey="action_candidate_universe">Descargar universo exacto de 20 acciones</EvidenceLink>
          <EvidenceLink manifest={manifest} assetKey="eligible_indicator_series_universe">Descargar universo exacto de 1 serie elegible</EvidenceLink>
          <EvidenceLink manifest={manifest} assetKey="senate_vote_normalized_record">Descargar registro exacto de votación</EvidenceLink>
          <EvidenceLink manifest={manifest} assetKey="senate_initiative_normalized_record">Descargar registro exacto de iniciativa</EvidenceLink>
          <EvidenceLink manifest={manifest} assetKey="eurostat_raw_capture">Descargar captura original de Eurostat</EvidenceLink>
          <EvidenceLink manifest={manifest} assetKey="independent_validation_evidence_projection">Descargar proyección determinista de validación independiente</EvidenceLink>
          <EvidenceLink manifest={manifest} assetKey="materialization_evidence_projection">Descargar proyección determinista de materialización</EvidenceLink>
          <EvidenceLink manifest={manifest} assetKey="semantic_evidence">Descargar evidencia semántica con nombres oficiales</EvidenceLink>
          <EvidenceLink manifest={manifest} assetKey="sqlite_bundle">Descargar bundle SQLite exacto</EvidenceLink>
          <EvidenceLink manifest={manifest} assetKey="scale_origin_allowed_signers">Descargar trust root público Ed25519</EvidenceLink>
          <EvidenceLink manifest={manifest} assetKey="scale_origin_attestation">Descargar attestation del origen de escala</EvidenceLink>
          <EvidenceLink manifest={manifest} assetKey="scale_origin_attestation_signature">Descargar firma del origen de escala</EvidenceLink>
        </nav>
      </section>

      <section className={`policy-outcomes-boundaries ${styles.boundaryGrid}`} aria-label="Límites e identidad pública">
        <article className={`policy-outcomes-claim-boundary ${styles.boundaryCard}`}>
          <p className={`policy-outcomes-claim-boundary__eyebrow ${styles.eyebrow}`}>Límite de afirmación</p>
          <h2 className={`policy-outcomes-claim-boundary__title ${styles.sectionTitle}`}>Qué no se concluye</h2>
          <ul className={`policy-outcomes-claim-boundary__list ${styles.boundaryList}`}>
            <li className="policy-outcomes-claim-boundary__item">No hay asociación estadística validada ni causalidad.</li>
            <li className="policy-outcomes-claim-boundary__item">No se calculó un efecto.</li>
            <li className="policy-outcomes-claim-boundary__item">No se atribuye mérito, culpa, éxito o fracaso.</li>
            <li className="policy-outcomes-claim-boundary__item">No se evalúa corrupción, legalidad o intención.</li>
          </ul>
        </article>
        <article className={`policy-outcomes-identity-boundary ${styles.boundaryCard}`}>
          <p className={`policy-outcomes-identity-boundary__eyebrow ${styles.eyebrow}`}>Identidad oficial preservada</p>
          <h2 className={`policy-outcomes-identity-boundary__title ${styles.sectionTitle}`}>No se eliminó ni seudonimizó ningún nombre público</h2>
          <p className={`policy-outcomes-identity-boundary__description ${styles.sectionCopy}`}>
            {feedIsValid
              ? `La evidencia semántica pública conserva, byte por byte, ${formatInt(identity.official_public_names_retained)} nombres oficiales, escaños, grupos, votos y referencias de procedencia. El estado agregado no duplica filas individuales; la descarga pública sí las conserva completas.`
              : "El contrato exige retener toda identidad oficial pública en la evidencia semántica. Un paquete no verificable no permite afirmar el conteo."}
          </p>
        </article>
      </section>

      <section className={`policy-outcomes-review-gate ${styles.section}`} aria-labelledby="policy-outcomes-gate-title">
        <header className={`policy-outcomes-section-heading ${styles.sectionHeading}`}>
          <div className="policy-outcomes-section-heading__copy">
            <p className={`policy-outcomes-section-heading__eyebrow ${styles.eyebrow}`}>Gate de publicación</p>
            <h2 className={`policy-outcomes-section-heading__title ${styles.sectionTitle}`} id="policy-outcomes-gate-title">
              Qué falta para validar un vínculo de resultado
            </h2>
          </div>
          <p className={`policy-outcomes-section-heading__note ${styles.sectionNote}`}>
            Más datos, más cómputo o una puntuación automática nunca sustituyen una decisión humana auditable.
          </p>
        </header>
        <ol className={`policy-outcomes-review-gate__steps ${styles.gateList}`}>
          <GateStep number="1" state={feedIsValid ? "complete" : "pending"} title="Fuentes y universo verificables">
            Copias exactas, SQL de cierre, 20 filas de acción, una serie elegible, hashes y bundle verificables.
          </GateStep>
          <GateStep number="2" state="pending" title="Revisión humana identificada">
            Una persona revisora debe decidir encaje semántico, geográfico y temporal, documentar razones, fecha y sign-off.
          </GateStep>
          <GateStep number="3" state="pending" title="Release versionado">
            La decisión debe quedar append-only y pertenecer a un release exacto; hoy hay cero releases y cero membresías.
          </GateStep>
          <GateStep number="4" state="pending" title="Publicación trazable">
            Solo entonces puede existir un vínculo validado con acceso directo a acción, indicador, decisión y evidencia.
          </GateStep>
        </ol>
      </section>

      <section className={`policy-outcomes-audit ${styles.auditSection}`} aria-labelledby="policy-outcomes-audit-title">
        <div className="policy-outcomes-audit__copy">
          <p className={`policy-outcomes-audit__eyebrow ${styles.eyebrow}`}>Procedencia y autenticación</p>
          <h2 className={`policy-outcomes-audit__title ${styles.sectionTitle}`} id="policy-outcomes-audit-title">
            La firma de escala no cubre este paquete
          </h2>
          <p className={`policy-outcomes-audit__description ${styles.sectionCopy}`}>
            Cada export verifica criptográficamente el origen de escala contra el signer, fingerprint y trust root Ed25519 fijados. Este paquete de candidato no forma parte de ese origen firmado y su manifest propio está explícitamente unsigned.
          </p>
        </div>
        <dl className={`policy-outcomes-audit__provenance ${styles.provenanceFacts}`}>
          <div className="policy-outcomes-audit__provenance-fact">
            <dt className="policy-outcomes-audit__provenance-label">Fecha contractual</dt>
            <dd className="policy-outcomes-audit__provenance-value"><time className="policy-outcomes-audit__contract-date" dateTime={snapshot?.contract_date || undefined}>{formatDate(snapshot?.contract_date)}</time></dd>
          </div>
          <div className="policy-outcomes-audit__provenance-fact">
            <dt className="policy-outcomes-audit__provenance-label">Checks independientes</dt>
            <dd className="policy-outcomes-audit__provenance-value">{feedIsValid ? formatInt(snapshot.validation_identity.check_count) : "no verificable"}</dd>
          </div>
          <div className="policy-outcomes-audit__provenance-fact">
            <dt className="policy-outcomes-audit__provenance-label">Manifest propio</dt>
            <dd className="policy-outcomes-audit__provenance-value">{feedIsValid ? "unsigned" : "no verificable"}</dd>
          </div>
          <div className="policy-outcomes-audit__provenance-fact">
            <dt className="policy-outcomes-audit__provenance-label">Membresía en origen firmado</dt>
            <dd className="policy-outcomes-audit__provenance-value">{feedIsValid ? "no" : "no verificable"}</dd>
          </div>
        </dl>
      </section>
      </main>
    </PolicyOutcomesRuntimeGate>
  );
}
