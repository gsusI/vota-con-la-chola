import { readPublicJson } from "../../static-snapshot.mjs";
import { withBasePath } from "../../path-utils.mjs";
import styles from "./water-receipt.module.css";

export const metadata = {
  title: "El recibo del agua de Andalucía | Vota Con La Chola",
  description:
    "Tres compromisos de investidura sobre agua, su estado público y las fuentes oficiales revisadas.",
};

const EMPTY_RECEIPT = {
  commitments: [],
  context: {},
  evidence_check: {},
  method: {},
  scope: {},
  sources: [],
  summary: {},
};

function classes(localClass, stableClass) {
  return `${localClass} ${stableClass}`;
}

function formatDate(value) {
  if (!value) return "sin fecha";
  return new Intl.DateTimeFormat("es-ES", {
    day: "numeric",
    month: "long",
    timeZone: "UTC",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00Z`));
}

function sourceMap(sources) {
  return new Map((Array.isArray(sources) ? sources : []).map((source) => [source.source_id, source]));
}

function OfficialSourceLink({ source, compact = false }) {
  if (!source?.url) return null;
  return (
    <a
      className={classes(
        compact ? styles.sourceLinkCompact : styles.sourceLink,
        compact ? "water-receipt-source-link-compact" : "water-receipt-source-link",
      )}
      href={source.url}
      rel="noreferrer"
      target="_blank"
    >
      <span className={classes(styles.sourceLinkLabel, "water-receipt-source-link-label")}>
        {source.label}
      </span>
      <span className={classes(styles.sourceLinkMeta, "water-receipt-source-link-meta")}>
        {source.locator}
      </span>
      <span aria-hidden="true" className={classes(styles.sourceLinkArrow, "water-receipt-source-link-arrow")}>
        ↗
      </span>
    </a>
  );
}

function EvidenceFinding({ commitment, sourcesById }) {
  const evidence = Array.isArray(commitment.post_investiture_evidence)
    ? commitment.post_investiture_evidence
    : [];

  return (
    <div className={classes(styles.finding, "water-receipt-commitment-finding")}>
      <h3 className={classes(styles.findingTitle, "water-receipt-commitment-finding-title")}>
        Qué hay desde la investidura
      </h3>
      <p className={classes(styles.findingCopy, "water-receipt-commitment-finding-copy")}>
        {commitment.status_detail}
      </p>
      {evidence.length > 0 ? (
        <ul className={classes(styles.evidenceList, "water-receipt-evidence-list")}>
          {evidence.map((item) => {
            const source = sourcesById.get(item.source_id);
            return (
              <li
                className={classes(styles.evidenceItem, "water-receipt-evidence-item")}
                key={`${commitment.commitment_id}-${item.source_id}`}
              >
                <time
                  className={classes(styles.evidenceDate, "water-receipt-evidence-date")}
                  dateTime={item.date}
                >
                  {formatDate(item.date)}
                </time>
                <span className={classes(styles.evidenceLabel, "water-receipt-evidence-label")}>
                  {item.label}
                </span>
                <span className={classes(styles.evidenceQualifier, "water-receipt-evidence-qualifier")}>
                  Reiteración; no mueve el estado
                </span>
                <OfficialSourceLink compact source={source} />
              </li>
            );
          })}
        </ul>
      ) : (
        <p className={classes(styles.emptyEvidence, "water-receipt-empty-evidence")}>
          Sin hito público localizado en la ventana revisada.
        </p>
      )}
    </div>
  );
}

function CommitmentReceipt({ commitment, sourcesById }) {
  const declaredSource = sourcesById.get(commitment.declared_source_id);
  const historicalContext = Array.isArray(commitment.historical_context)
    ? commitment.historical_context
    : [];
  const directHref = withBasePath(
    `/elecciones/andalucia-2026/#${commitment.commitment_id}`,
  );

  return (
    <article
      className={classes(styles.commitment, "water-receipt-commitment")}
      id={commitment.commitment_id}
    >
      <header className={classes(styles.commitmentHeader, "water-receipt-commitment-header")}>
        <span className={classes(styles.commitmentNumber, "water-receipt-commitment-number")}>
          {commitment.number}
        </span>
        <div className={classes(styles.commitmentHeading, "water-receipt-commitment-heading")}>
          <p className={classes(styles.commitmentEyebrow, "water-receipt-commitment-eyebrow")}>
            Compromiso de investidura
          </p>
          <h2 className={classes(styles.commitmentTitle, "water-receipt-commitment-title")}>
            {commitment.title}
          </h2>
        </div>
        <span className={classes(styles.statusStamp, "water-receipt-status-stamp")}>
          {commitment.status_label}
        </span>
      </header>

      <div className={classes(styles.commitmentBody, "water-receipt-commitment-body")}>
        <section
          className={classes(styles.declaration, "water-receipt-declaration")}
          aria-label="Compromiso declarado"
        >
          <p className={classes(styles.declarationCopy, "water-receipt-declaration-copy")}>
            {commitment.declaration}
          </p>
          <blockquote className={classes(styles.sourceExcerpt, "water-receipt-source-excerpt")}>
            <p className={classes(styles.sourceExcerptText, "water-receipt-source-excerpt-text")}>
              {commitment.source_excerpt}
            </p>
            <cite className={classes(styles.sourceExcerptCite, "water-receipt-source-excerpt-cite")}>
              {declaredSource?.locator || "Fuente primaria"}
            </cite>
          </blockquote>
          <OfficialSourceLink source={declaredSource} />
        </section>

        <div className={classes(styles.progressRail, "water-receipt-progress-rail")}>
          <div className={classes(styles.progressStepDone, "water-receipt-progress-step-declared")}>
            <span className={classes(styles.progressMarker, "water-receipt-progress-marker")}>1</span>
            <span className={classes(styles.progressLabel, "water-receipt-progress-label")}>
              Declarado
            </span>
          </div>
          <div className={classes(styles.progressStepOpen, "water-receipt-progress-step-official")}>
            <span className={classes(styles.progressMarker, "water-receipt-progress-marker")}>2</span>
            <span className={classes(styles.progressLabel, "water-receipt-progress-label")}>
              Acto oficial
            </span>
          </div>
          <div className={classes(styles.progressStepOpen, "water-receipt-progress-step-result")}>
            <span className={classes(styles.progressMarker, "water-receipt-progress-marker")}>3</span>
            <span className={classes(styles.progressLabel, "water-receipt-progress-label")}>
              Resultado
            </span>
          </div>
        </div>

        <div className={classes(styles.evidenceGrid, "water-receipt-evidence-grid")}>
          <EvidenceFinding commitment={commitment} sourcesById={sourcesById} />

          <div className={classes(styles.checkpoint, "water-receipt-checkpoint")}>
            <h3 className={classes(styles.checkpointTitle, "water-receipt-checkpoint-title")}>
              Próximo hito que sí cuenta
            </h3>
            <p className={classes(styles.checkpointCopy, "water-receipt-checkpoint-copy")}>
              {commitment.checkpoint}
            </p>
          </div>
        </div>

        <dl className={classes(styles.responsibilityList, "water-receipt-responsibility-list")}>
          <div className={classes(styles.responsibilityItem, "water-receipt-responsibility-item")}>
            <dt className={classes(styles.responsibilityTerm, "water-receipt-responsibility-term")}>
              Ejecutivo
            </dt>
            <dd
              className={classes(
                styles.responsibilityDescription,
                "water-receipt-responsibility-description",
              )}
            >
              {commitment.ownership.executive}
            </dd>
          </div>
          <div className={classes(styles.responsibilityItem, "water-receipt-responsibility-item")}>
            <dt className={classes(styles.responsibilityTerm, "water-receipt-responsibility-term")}>
              Parlamento
            </dt>
            <dd
              className={classes(
                styles.responsibilityDescription,
                "water-receipt-responsibility-description",
              )}
            >
              {commitment.ownership.legislature}
            </dd>
          </div>
          <div className={classes(styles.responsibilityItem, "water-receipt-responsibility-item")}>
            <dt className={classes(styles.responsibilityTerm, "water-receipt-responsibility-term")}>
              Dinero y entrega
            </dt>
            <dd
              className={classes(
                styles.responsibilityDescription,
                "water-receipt-responsibility-description",
              )}
            >
              {commitment.money_and_delivery}
            </dd>
          </div>
        </dl>

        {historicalContext.length > 0 ? (
          <aside className={classes(styles.historyNote, "water-receipt-history-note")}>
            <h3 className={classes(styles.historyTitle, "water-receipt-history-title")}>
              Contexto anterior que no contamos como avance
            </h3>
            <ul className={classes(styles.historyList, "water-receipt-history-list")}>
              {historicalContext.map((item) => (
                <li
                  className={classes(styles.historyItem, "water-receipt-history-item")}
                  key={`${commitment.commitment_id}-${item.source_id}`}
                >
                  <span className={classes(styles.historyCopy, "water-receipt-history-copy")}>
                    {item.label}
                  </span>
                  <OfficialSourceLink compact source={sourcesById.get(item.source_id)} />
                </li>
              ))}
            </ul>
          </aside>
        ) : null}

        <div className={classes(styles.unknowns, "water-receipt-unknowns")}>
          <h3 className={classes(styles.unknownsTitle, "water-receipt-unknowns-title")}>
            Lo que aún no sabemos
          </h3>
          <ul className={classes(styles.unknownsList, "water-receipt-unknowns-list")}>
            {commitment.unknowns.map((item) => (
              <li className={classes(styles.unknownsItem, "water-receipt-unknowns-item")} key={item}>
                {item}
              </li>
            ))}
          </ul>
        </div>

        <footer className={classes(styles.commitmentFooter, "water-receipt-commitment-footer")}>
          <p className={classes(styles.limitationCopy, "water-receipt-limitation-copy")}>
            {commitment.limitations.join(" ")}
          </p>
          <a className={classes(styles.directLink, "water-receipt-direct-link")} href={directHref}>
            Enlace directo a este compromiso
          </a>
        </footer>
      </div>
    </article>
  );
}

export default function Andalucia2026WaterReceiptPage() {
  const receipt = readPublicJson(
    "elecciones/andalucia-2026/data/water-receipt.json",
    EMPTY_RECEIPT,
  );
  const commitments = Array.isArray(receipt.commitments) ? receipt.commitments : [];
  const sources = Array.isArray(receipt.sources) ? receipt.sources : [];
  const sourcesById = sourceMap(sources);
  const summary = receipt.summary || {};
  const scope = receipt.scope || {};
  const context = receipt.context || {};
  const evidenceCheck = receipt.evidence_check || {};
  const method = receipt.method || {};
  const ownerSource = sourcesById.get("government-structure-2026-07-09");
  const lawSource = sourcesById.get("water-law-consolidated-2026-06-20");

  return (
    <main className={classes(styles.page, "water-receipt-page")}>
      <header className={classes(styles.masthead, "water-receipt-masthead")}>
        <div className={classes(styles.mastheadMeta, "water-receipt-masthead-meta")}>
          <p className={classes(styles.kicker, "water-receipt-kicker")}>
            Andalucía · XIII legislatura · control ciudadano
          </p>
          <time
            className={classes(styles.snapshotDate, "water-receipt-snapshot-date")}
            dateTime={receipt.snapshot_date}
          >
            Corte cerrado: {formatDate(receipt.snapshot_date)}
          </time>
        </div>
        <h1 className={classes(styles.title, "water-receipt-title")}>
          {receipt.title || "El recibo del agua de Andalucía"}
        </h1>
        <p className={classes(styles.question, "water-receipt-question")}>
          {receipt.question}
        </p>
      </header>

      <section className={classes(styles.answer, "water-receipt-answer")} aria-labelledby="water-answer-title">
        <div className={classes(styles.answerFigure, "water-receipt-answer-figure")}>
          <strong className={classes(styles.answerNumber, "water-receipt-answer-number")}>
            {summary.post_investiture_actions_total ?? 0}
          </strong>
          <span className={classes(styles.answerUnit, "water-receipt-answer-unit")}>
            hitos jurídicos posteriores localizados
          </span>
        </div>
        <div className={classes(styles.answerCopyBlock, "water-receipt-answer-copy-block")}>
          <h2 className={classes(styles.answerTitle, "water-receipt-answer-title")} id="water-answer-title">
            La respuesta, hoy
          </h2>
          <p className={classes(styles.answerCopy, "water-receipt-answer-copy")}>
            {context.answer}
          </p>
          <p className={classes(styles.answerCaveat, "water-receipt-answer-caveat")}>
            {context.caveat}
          </p>
        </div>
      </section>

      <nav className={classes(styles.commitmentNav, "water-receipt-commitment-nav")} aria-label="Tres compromisos">
        <p className={classes(styles.commitmentNavLabel, "water-receipt-commitment-nav-label")}>
          Abrir un compromiso
        </p>
        <ol className={classes(styles.commitmentNavList, "water-receipt-commitment-nav-list")}>
          {commitments.map((commitment) => (
            <li
              className={classes(styles.commitmentNavItem, "water-receipt-commitment-nav-item")}
              key={commitment.commitment_id}
            >
              <a
                className={classes(styles.commitmentNavLink, "water-receipt-commitment-nav-link")}
                href={`#${commitment.commitment_id}`}
              >
                <span className={classes(styles.commitmentNavNumber, "water-receipt-commitment-nav-number")}>
                  {commitment.number}
                </span>
                <span className={classes(styles.commitmentNavTitle, "water-receipt-commitment-nav-title")}>
                  {commitment.title}
                </span>
                <span className={classes(styles.commitmentNavStatus, "water-receipt-commitment-nav-status")}>
                  {commitment.status_label}
                </span>
              </a>
            </li>
          ))}
        </ol>
      </nav>

      <section
        className={classes(styles.commitments, "water-receipt-commitments")}
        aria-label="Recibos de los compromisos"
      >
        {commitments.map((commitment) => (
          <CommitmentReceipt
            commitment={commitment}
            key={commitment.commitment_id}
            sourcesById={sourcesById}
          />
        ))}
      </section>

      <section className={classes(styles.baseline, "water-receipt-baseline")} aria-labelledby="water-baseline-title">
        <div className={classes(styles.baselineHeading, "water-receipt-baseline-heading")}>
          <p className={classes(styles.baselineEyebrow, "water-receipt-baseline-eyebrow")}>
            Separación obligatoria
          </p>
          <h2 className={classes(styles.baselineTitle, "water-receipt-baseline-title")} id="water-baseline-title">
            El pasado explica. No acredita entrega.
          </h2>
        </div>
        <div className={classes(styles.baselineContent, "water-receipt-baseline-content")}>
          <p className={classes(styles.baselineCopy, "water-receipt-baseline-copy")}>
            {context.historical_baseline_note}
          </p>
          <p className={classes(styles.baselineOwner, "water-receipt-baseline-owner")}>
            {context.owner_note}
          </p>
          <div className={classes(styles.baselineLinks, "water-receipt-baseline-links")}>
            <OfficialSourceLink compact source={lawSource} />
            <OfficialSourceLink compact source={ownerSource} />
          </div>
        </div>
      </section>

      <section className={classes(styles.method, "water-receipt-method")} aria-labelledby="water-method-title">
        <div className={classes(styles.methodHeading, "water-receipt-method-heading")}>
          <p className={classes(styles.methodEyebrow, "water-receipt-method-eyebrow")}>Método</p>
          <h2 className={classes(styles.methodTitle, "water-receipt-method-title")} id="water-method-title">
            Cómo se mueve el recibo
          </h2>
        </div>
        <div className={classes(styles.methodContent, "water-receipt-method-content")}>
          <p className={classes(styles.methodRule, "water-receipt-method-rule")}>
            {method.rule}
          </p>
          <p className={classes(styles.methodCheck, "water-receipt-method-check")}>
            Revisión del {formatDate(scope.evidence_window_start)} al {formatDate(scope.evidence_window_end)}.
            {" "}{evidenceCheck.method}
          </p>
          <p className={classes(styles.methodLimitation, "water-receipt-method-limitation")}>
            {evidenceCheck.limitation}
          </p>
          <ul className={classes(styles.scopeList, "water-receipt-scope-list")}>
            {(evidenceCheck.official_scopes || []).map((sourceScope) => (
              <li className={classes(styles.scopeItem, "water-receipt-scope-item")} key={sourceScope.url}>
                <a
                  className={classes(styles.scopeLink, "water-receipt-scope-link")}
                  href={sourceScope.url}
                  rel="noreferrer"
                  target="_blank"
                >
                  {sourceScope.label} ↗
                </a>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <footer className={classes(styles.pageFooter, "water-receipt-page-footer")}>
        <p className={classes(styles.citation, "water-receipt-citation")}>
          Cita: “El recibo del agua de Andalucía”, corte {receipt.snapshot_date}, Vota Con La Chola.
        </p>
        <div className={classes(styles.footerLinks, "water-receipt-footer-links")}>
          <a
            className={classes(styles.downloadLink, "water-receipt-download-link")}
            href={withBasePath("/elecciones/andalucia-2026/data/water-receipt.json")}
          >
            Descargar recibo JSON
          </a>
          <a className={classes(styles.indexLink, "water-receipt-index-link")} href={withBasePath("/elecciones/")}>
            Ver elecciones
          </a>
        </div>
      </footer>
    </main>
  );
}
