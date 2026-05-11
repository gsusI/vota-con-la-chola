import { notFound } from "next/navigation";
import {
  formatDate,
  formatInt,
  loadResponsibilityExplainerCasePayload,
  loadResponsibilityExplainerManifest,
  withBasePath,
} from "../pageData.mjs";

export const dynamicParams = false;

export async function generateStaticParams() {
  const manifest = loadResponsibilityExplainerManifest();
  return (manifest.cases || []).map((item) => ({ caseId: item.case_id }));
}

export async function generateMetadata({ params }) {
  const { caseId } = await params;
  const payload = loadResponsibilityExplainerCasePayload(caseId);
  if (!payload) {
    return {
      title: "Caso no encontrado | Vota Con La Chola",
      description: "No encontramos ese caso en el corte público actual.",
    };
  }

  return {
    title: `${payload.case?.title || payload.case?.short_label || "Caso de responsabilidad"} | Vota Con La Chola`,
    description: payload.case?.summary || "Página pública y auditable de un caso de responsabilidad.",
    alternates: {
      canonical: payload.case?.canonical_url || undefined,
    },
  };
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function sourceHref(value) {
  const raw = String(value || "").trim();
  return raw.startsWith("http://") || raw.startsWith("https://") ? raw : "";
}

function formatTimestamp(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "sin fecha";
  }
  const [datePart, timePart] = raw.split("T");
  if (datePart && timePart) {
    return `${formatDate(datePart)} · ${timePart.slice(0, 5)}`;
  }
  return formatDate(raw);
}

function statusLabel(status) {
  if (status === "partial") {
    return "Parcial";
  }
  if (status === "pending") {
    return "Pendiente";
  }
  return status || "Sin estado";
}

function statusClassName(status) {
  if (status === "partial") {
    return "responsibility-status-pill responsibility-status-pill--partial";
  }
  return "responsibility-status-pill responsibility-status-pill--pending";
}

function signalClassName(level) {
  const normalized = String(level || "").toLowerCase();
  if (normalized.includes("rojo")) {
    return "responsibility-signal responsibility-signal--red";
  }
  if (normalized.includes("naranja")) {
    return "responsibility-signal responsibility-signal--orange";
  }
  if (normalized.includes("amarillo")) {
    return "responsibility-signal responsibility-signal--yellow";
  }
  return "responsibility-signal responsibility-signal--neutral";
}

function countQuestionsByStatus(questions) {
  return questions.reduce(
    (acc, question) => {
      if (question.status === "partial") {
        acc.partial += 1;
      } else {
        acc.pending += 1;
      }
      return acc;
    },
    { partial: 0, pending: 0 },
  );
}

function groupRowsByTarget(rows) {
  return rows.reduce((acc, row) => {
    const key = row.target_id || "unscoped";
    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(row);
    return acc;
  }, {});
}

function SourceLink({ href, label }) {
  const safeHref = sourceHref(href);
  if (!safeHref) {
    return null;
  }
  return (
    <a className="responsibility-source-link" href={safeHref}>
      {label || "Abrir fuente oficial"}
    </a>
  );
}

export default async function ResponsibilityExplainerCasePage({ params }) {
  const { caseId } = await params;
  const payload = loadResponsibilityExplainerCasePayload(caseId);
  if (!payload) {
    return notFound();
  }

  const caseInfo = payload.case || {};
  const coverage = payload.coverage || {};
  const normative = payload.normative_evidence || {};
  const ledger = payload.accountability_ledger || {};
  const structural = payload.structural_evidence || {};
  const parliamentary = payload.parliamentary_evidence || {};
  const questions = asList(payload.questions);
  const duties = asList(normative.normative_duties);
  const warningChannels = asList(normative.warning_channels);
  const warningTimelineEvents = asList(normative.warning_timeline_events);
  const governingRules = asList(ledger.governing_rules);
  const officialFindings = asList(ledger.official_findings);
  const administrativeActs = asList(ledger.administrative_acts);
  const responsibilityLinks = asList(ledger.responsibility_links);
  const structuralFactors = asList(structural.structural_risk_factors);
  const auditTargets = asList(structural.structural_audit_targets);
  const evidenceRows = asList(structural.evidence_rows);
  const initiatives = asList(parliamentary.initiatives);
  const votes = asList(parliamentary.votes);
  const measures = asList(parliamentary.reviewed_measures);
  const gaps = payload.gaps || {};
  const knownGaps = asList(gaps.known_gaps);
  const nextLanes = asList(gaps.next_lanes);
  const targetTitleById = Object.fromEntries(
    auditTargets.map((target) => [target.target_id, target.title || target.category || target.target_id]),
  );
  const evidenceRowsByTarget = groupRowsByTarget(evidenceRows);
  const questionCounts = countQuestionsByStatus(questions);
  const highCertaintyEvidenceCount = evidenceRows.filter((row) => row.certainty === "high").length;
  const hasTimeline = warningTimelineEvents.length > 0;
  const hasStructuralSection = structuralFactors.length || auditTargets.length || evidenceRows.length;
  const hasLedgerSection = governingRules.length || officialFindings.length || administrativeActs.length || responsibilityLinks.length;
  const hasParliamentarySection = initiatives.length || votes.length || measures.length;
  const primaryMetric = hasTimeline
    ? { value: warningTimelineEvents.length, label: "avisos normalizados" }
    : { value: governingRules.length, label: "reglas de base" };
  const chainMetric = duties.length
    ? { value: duties.length, label: "deberes oficiales" }
    : { value: responsibilityLinks.length, label: "cadenas de responsabilidad" };
  const evidenceMetric = evidenceRows.length
    ? { value: evidenceRows.length, label: "filas de evidencia" }
    : { value: officialFindings.length + administrativeActs.length, label: "hallazgos y actos" };

  return (
    <main className="responsibility-article">
      <article className="responsibility-article__body">
        <section className="responsibility-hero" aria-labelledby="responsibility-hero-title">
          <div className="responsibility-hero__copy">
            <nav className="responsibility-hero__breadcrumbs" aria-label="Migas de pan">
              <a className="responsibility-hero__breadcrumb-link" href={withBasePath("/")}>
                Inicio
              </a>
              <a className="responsibility-hero__breadcrumb-link" href={withBasePath("/responsibility-explainer/")}>
                Casos de responsabilidad
              </a>
            </nav>
            <p className="responsibility-hero__eyebrow">Casos de responsabilidad</p>
            <h1 className="responsibility-hero__title" id="responsibility-hero-title">
              {caseInfo.title || caseInfo.short_label || "Caso sin titular legible"}
            </h1>
            <p className="responsibility-hero__dek">
              {caseInfo.summary || "Página pública para seguir reglas, actos, responsabilidades y huecos abiertos."}
            </p>
            <dl className="responsibility-hero__facts" aria-label="Cobertura principal">
              <div className="responsibility-hero__fact">
                <dt className="responsibility-hero__fact-label">{primaryMetric.label}</dt>
                <dd className="responsibility-hero__fact-value">{formatInt(primaryMetric.value)}</dd>
              </div>
              <div className="responsibility-hero__fact">
                <dt className="responsibility-hero__fact-label">{chainMetric.label}</dt>
                <dd className="responsibility-hero__fact-value">{formatInt(chainMetric.value)}</dd>
              </div>
              <div className="responsibility-hero__fact">
                <dt className="responsibility-hero__fact-label">{evidenceMetric.label}</dt>
                <dd className="responsibility-hero__fact-value">{formatInt(evidenceMetric.value)}</dd>
              </div>
            </dl>
            <p className="responsibility-hero__scope">
              {caseInfo.current_scope_note || "Corte parcial. Las lagunas quedan visibles para no convertir incertidumbre en conclusión."}
            </p>
            <div className="responsibility-hero__links" aria-label="Enlaces del caso">
              <a className="responsibility-hero__link" href={withBasePath("/responsibility-explainer/")}>
                Volver al índice
              </a>
            </div>
          </div>

          <aside className="responsibility-hero__visual" aria-label="Resumen visual del caso">
            <div className="responsibility-radar">
              <p className="responsibility-radar__label">{caseInfo.geography || "Ámbito no disponible"}</p>
              <p className="responsibility-radar__window">{caseInfo.incident_window?.label || "Ventana temporal no disponible"}</p>
              <div className="responsibility-radar__bars" aria-hidden="true">
                {(hasTimeline ? warningTimelineEvents : governingRules).slice(0, 5).map((item, index) => (
                  <span
                    className={`responsibility-radar__bar responsibility-radar__bar--${index + 1}`}
                    key={item.event_id || item.rule_id || item.title || index}
                  />
                ))}
              </div>
              <p className="responsibility-radar__caption">
                Corte {payload.meta?.snapshot_date || "sin fecha"} · {formatInt(questions.length)} preguntas · {formatInt(questionCounts.partial)} parciales
              </p>
            </div>
          </aside>
        </section>

        <nav className="responsibility-chapter-nav" aria-label="Capítulos del explicador">
          <a className="responsibility-chapter-nav__link" href="#resumen">
            Resumen
          </a>
          <a className="responsibility-chapter-nav__link" href="#cronologia">
            Cronología
          </a>
          <a className="responsibility-chapter-nav__link" href="#cadena">
            Cadena
          </a>
          <a className="responsibility-chapter-nav__link" href="#evidencia">
            Evidencia
          </a>
          <a className="responsibility-chapter-nav__link" href="#pendiente">
            Pendiente
          </a>
        </nav>

        <section className="responsibility-summary-section" id="resumen" aria-labelledby="responsibility-summary-title">
          <p className="responsibility-section-kicker">Qué muestra este recorte</p>
          <h2 className="responsibility-section-title" id="responsibility-summary-title">
            No es una sentencia. Es un mapa navegable de deberes, señales y huecos.
          </h2>
          <div className="responsibility-summary-grid">
            <article className="responsibility-summary-card">
              <span className="responsibility-summary-card__number">{formatInt(questionCounts.partial)}</span>
              <h3 className="responsibility-summary-card__title">Preguntas con respuesta parcial</h3>
              <p className="responsibility-summary-card__copy">
                Hay anclajes suficientes para orientar la auditoría, pero no para cerrar causalidad.
              </p>
            </article>
            <article className="responsibility-summary-card">
              <span className="responsibility-summary-card__number">{formatInt(highCertaintyEvidenceCount || evidenceRows.length)}</span>
              <h3 className="responsibility-summary-card__title">Registros con evidencia sólida</h3>
              <p className="responsibility-summary-card__copy">
                La lectura pública debe poder volver desde cada afirmación a un documento oficial.
              </p>
            </article>
            <article className="responsibility-summary-card">
              <span className="responsibility-summary-card__number">{formatInt(knownGaps.length)}</span>
              <h3 className="responsibility-summary-card__title">Huecos declarados</h3>
              <p className="responsibility-summary-card__copy">
                Lo que falta queda en portada: cronología operativa, decisiones internas y cruces territoriales.
              </p>
            </article>
          </div>
        </section>

        <section className="responsibility-story-section responsibility-story-section--timeline" id="cronologia" aria-labelledby="responsibility-timeline-title">
          <div className="responsibility-section-heading">
            <p className="responsibility-section-kicker">1 / Cronología</p>
            <h2 className="responsibility-section-title" id="responsibility-timeline-title">
              Primero, ordenar las señales en el tiempo.
            </h2>
            <p className="responsibility-section-dek">
              El lector necesita ver cuándo aparece cada aviso antes de entrar en competencias, omisiones o responsabilidades.
            </p>
          </div>

          {hasTimeline ? (
            <div className="responsibility-scrolly">
              <aside className="responsibility-scrolly__visual" aria-label="Escalera de avisos">
                <div className="responsibility-signal-panel">
                  <p className="responsibility-signal-panel__label">Escalada documentada</p>
                  <ol className="responsibility-signal-panel__list">
                    {warningTimelineEvents.map((event) => (
                      <li className="responsibility-signal-panel__item" key={`panel-${event.event_id || event.event_time}`}>
                        <span className={signalClassName(event.signal_level)}>{event.signal_level || "señal"}</span>
                        <time className="responsibility-signal-panel__time">{formatTimestamp(event.event_time)}</time>
                      </li>
                    ))}
                  </ol>
                </div>
              </aside>
              <ol className="responsibility-timeline">
                {warningTimelineEvents.map((event, index) => {
                  const eventHref = sourceHref(event.source_url);
                  return (
                    <li className="responsibility-timeline__item" key={event.event_id || `${event.channel_id}-${event.event_time}`}>
                      <article className="responsibility-timeline__card">
                        <span className="responsibility-timeline__index">{String(index + 1).padStart(2, "0")}</span>
                        <time className="responsibility-timeline__time">{formatTimestamp(event.event_time)}</time>
                        <h3 className="responsibility-timeline__title">{event.channel_name || event.channel_id || "Canal sin nombre"}</h3>
                        <span className={signalClassName(event.signal_level)}>{event.signal_level || "señal sin nivel"}</span>
                        <p className="responsibility-timeline__copy">{event.event_summary || "Sin resumen de aviso."}</p>
                        {event.why_it_matters ? <p className="responsibility-timeline__why">{event.why_it_matters}</p> : null}
                        <SourceLink href={eventHref} label={event.source_title || "Abrir fuente del aviso"} />
                      </article>
                    </li>
                  );
                })}
              </ol>
            </div>
          ) : (
            <div className="responsibility-empty-state">
              <p className="responsibility-empty-state__copy">No hay cronología de señales normalizada en este caso.</p>
            </div>
          )}
        </section>

        <section className="responsibility-story-section responsibility-story-section--chain" id="cadena" aria-labelledby="responsibility-chain-title">
          <div className="responsibility-section-heading">
            <p className="responsibility-section-kicker">2 / Cadena</p>
            <h2 className="responsibility-section-title" id="responsibility-chain-title">
              Después, separar competencia de culpa.
            </h2>
            <p className="responsibility-section-dek">
              Una cadena legible muestra quién tenía el deber, quién tenía los datos y qué pregunta queda abierta para cada actor.
            </p>
          </div>

          {duties.length ? (
            <div className="responsibility-chain">
              {duties.map((duty, index) => {
                const dutyHref = sourceHref(duty.source_url);
                return (
                  <article className="responsibility-chain__node" key={duty.duty_id || `${duty.actor}-${duty.category}`}>
                    <span className="responsibility-chain__node-index">{String(index + 1).padStart(2, "0")}</span>
                    <p className="responsibility-chain__node-type">{duty.category || "Deber oficial"}</p>
                    <h3 className="responsibility-chain__node-title">{duty.actor || "Actor no identificado"}</h3>
                    {duty.actor_scope ? <p className="responsibility-chain__node-scope">{duty.actor_scope}</p> : null}
                    <p className="responsibility-chain__node-copy">{duty.duty_summary || "Sin resumen de deber."}</p>
                    {duty.why_it_matters ? <p className="responsibility-chain__node-why">{duty.why_it_matters}</p> : null}
                    <SourceLink href={dutyHref} label={duty.source_title || "Abrir fuente del deber"} />
                  </article>
                );
              })}
            </div>
          ) : null}

          {hasLedgerSection ? (
            <div className="responsibility-ledger">
              <div className="responsibility-ledger__column">
                <h3 className="responsibility-ledger__title">Reglas y hallazgos</h3>
                <div className="responsibility-ledger__list">
                  {[...governingRules, ...officialFindings].map((item) => {
                    const itemHref = sourceHref(item.source_url || item.source_note);
                    return (
                      <article className="responsibility-ledger__item" key={item.rule_id || item.finding_id || item.title || item.entity_name}>
                        <p className="responsibility-ledger__item-label">{item.rule_kind || item.category || item.entity_name || "Registro"}</p>
                        <h4 className="responsibility-ledger__item-title">{item.title || item.finding_summary || "Registro sin título"}</h4>
                        {item.duty_summary || item.accountability_implication ? (
                          <p className="responsibility-ledger__item-copy">{item.duty_summary || item.accountability_implication}</p>
                        ) : null}
                        <SourceLink href={itemHref} label={item.source_title || "Abrir fuente"} />
                      </article>
                    );
                  })}
                </div>
              </div>
              <div className="responsibility-ledger__column">
                <h3 className="responsibility-ledger__title">Actos y preguntas</h3>
                <div className="responsibility-ledger__list">
                  {[...administrativeActs, ...responsibilityLinks].map((item) => {
                    const itemHref = sourceHref(item.source_url || item.source_locator || item.accountability_question);
                    return (
                      <article className="responsibility-ledger__item" key={item.act_id || item.link_id || item.role_in_chain}>
                        <p className="responsibility-ledger__item-label">{item.act_type || item.actor || "Cadena"}</p>
                        <h4 className="responsibility-ledger__item-title">{item.act_summary || item.role_in_chain || item.status || "Registro sin título"}</h4>
                        {item.accountability_implication || item.obligation_basis ? (
                          <p className="responsibility-ledger__item-copy">{item.accountability_implication || item.obligation_basis}</p>
                        ) : null}
                        <SourceLink href={itemHref} label={item.source_title || "Abrir fuente"} />
                      </article>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : null}
        </section>

        <section className="responsibility-story-section responsibility-story-section--evidence" id="evidencia" aria-labelledby="responsibility-evidence-title">
          <div className="responsibility-section-heading">
            <p className="responsibility-section-kicker">3 / Evidencia</p>
            <h2 className="responsibility-section-title" id="responsibility-evidence-title">
              La evidencia debe poder recorrerse sin saturar la pantalla.
            </h2>
            <p className="responsibility-section-dek">
              Los factores estructurales se leen como rutas de auditoría. Los registros concretos viven dentro de desplegables con fuente.
            </p>
          </div>

          {hasStructuralSection ? (
            <>
              {structuralFactors.length ? (
                <div className="responsibility-factor-strip">
                  {structuralFactors.map((factor) => {
                    const factorHref = sourceHref(factor.source_url);
                    return (
                      <article className="responsibility-factor-strip__item" key={factor.factor_id || `${factor.category}-${factor.title}`}>
                        <p className="responsibility-factor-strip__category">{factor.category || "Factor regulatorio"}</p>
                        <h3 className="responsibility-factor-strip__title">{factor.title || "Factor sin título"}</h3>
                        <p className="responsibility-factor-strip__copy">{factor.risk_mechanism || "Sin mecanismo de riesgo resumido."}</p>
                        {factor.accountability_focus ? <p className="responsibility-factor-strip__focus">{factor.accountability_focus}</p> : null}
                        <SourceLink href={factorHref} label={factor.source_title || "Abrir fuente del factor"} />
                      </article>
                    );
                  })}
                </div>
              ) : null}

              {auditTargets.length || Object.keys(evidenceRowsByTarget).length ? (
                <div className="responsibility-evidence-browser">
                  {(auditTargets.length ? auditTargets : Object.keys(evidenceRowsByTarget).map((targetId) => ({ target_id: targetId }))).map((target, targetIndex) => {
                    const targetId = target.target_id || "unscoped";
                    const rows = evidenceRowsByTarget[targetId] || [];
                    const targetHref = sourceHref(target.source_url);
                    return (
                      <details className="responsibility-evidence-target" key={targetId} open={targetIndex === 0}>
                        <summary className="responsibility-evidence-target__summary">
                          <span className="responsibility-evidence-target__category">{target.category || "Blanco de auditoría"}</span>
                          <span className="responsibility-evidence-target__title">{target.title || targetTitleById[targetId] || targetId}</span>
                          <span className="responsibility-evidence-target__count">{formatInt(rows.length)} registros</span>
                        </summary>
                        <div className="responsibility-evidence-target__body">
                          {target.audit_question ? <p className="responsibility-evidence-target__question">{target.audit_question}</p> : null}
                          {target.why_priority ? <p className="responsibility-evidence-target__priority">{target.why_priority}</p> : null}
                          <SourceLink href={targetHref} label={target.source_title || "Abrir fuente del blanco de auditoría"} />
                          {rows.length ? (
                            <ul className="responsibility-evidence-list">
                              {rows.map((row) => {
                                const rowHref = sourceHref(row.source_url);
                                return (
                                  <li className="responsibility-evidence-row" key={row.evidence_id || `${row.target_id}-${row.entity_name}-${row.signal_title}`}>
                                    <article className="responsibility-evidence-row__card">
                                      <div className="responsibility-evidence-row__meta">
                                        <span className="responsibility-evidence-row__entity">{row.entity_name || "Entidad sin nombre"}</span>
                                        {row.certainty ? <span className="responsibility-evidence-row__certainty">Certeza: {row.certainty}</span> : null}
                                      </div>
                                      <h4 className="responsibility-evidence-row__title">{row.signal_title || row.signal_type || "Señal sin título"}</h4>
                                      <p className="responsibility-evidence-row__copy">{row.pre_dana_reading || "Sin lectura contextual resumida."}</p>
                                      {row.why_it_matters ? <p className="responsibility-evidence-row__why">{row.why_it_matters}</p> : null}
                                      <SourceLink href={rowHref} label={row.source_title || "Abrir fuente oficial"} />
                                    </article>
                                  </li>
                                );
                              })}
                            </ul>
                          ) : (
                            <p className="responsibility-empty-state__copy">Este blanco aún no tiene registros de evidencia publicados.</p>
                          )}
                        </div>
                      </details>
                    );
                  })}
                </div>
              ) : null}
            </>
          ) : (
            <div className="responsibility-empty-state">
              <p className="responsibility-empty-state__copy">No hay evidencia estructural publicada para este caso.</p>
            </div>
          )}
        </section>

        {hasParliamentarySection ? (
          <section className="responsibility-story-section responsibility-story-section--parliament" aria-labelledby="responsibility-parliament-title">
            <div className="responsibility-section-heading">
              <p className="responsibility-section-kicker">4 / Parlamento</p>
              <h2 className="responsibility-section-title" id="responsibility-parliament-title">
                Rastro parlamentario enlazado.
              </h2>
            </div>
            <div className="responsibility-parliament-grid">
              {initiatives.map((item) => (
                <article className="responsibility-parliament-card" key={item.initiative_id}>
                  <p className="responsibility-parliament-card__meta">
                    {item.initiative_id} · {item.presented_date ? formatDate(item.presented_date) : "sin fecha"}
                  </p>
                  <h3 className="responsibility-parliament-card__title">{item.title || item.initiative_id}</h3>
                  <p className="responsibility-parliament-card__copy">{item.current_status || "Estado no disponible"}</p>
                </article>
              ))}
              {votes.map((vote) => (
                <article className="responsibility-parliament-card" key={vote.vote_event_id}>
                  <p className="responsibility-parliament-card__meta">
                    {vote.vote_event_id} · {vote.vote_date ? formatDate(vote.vote_date) : "sin fecha"}
                  </p>
                  <h3 className="responsibility-parliament-card__title">{vote.title || vote.vote_event_id}</h3>
                  <p className="responsibility-parliament-card__copy">Iniciativa: {vote.initiative_id || "sin iniciativa"}</p>
                </article>
              ))}
              {measures.map((measure) => (
                <article className="responsibility-parliament-card" key={`${measure.initiative_id}-${measure.measure_rank}`}>
                  <p className="responsibility-parliament-card__meta">{measure.policy_area || measure.initiative_id}</p>
                  <h3 className="responsibility-parliament-card__title">{measure.measure_title || "Medida sin título"}</h3>
                  <p className="responsibility-parliament-card__copy">{measure.citizen_summary || "Sin resumen para la vista ciudadana."}</p>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        <section className="responsibility-story-section responsibility-story-section--open" id="pendiente" aria-labelledby="responsibility-open-title">
          <div className="responsibility-section-heading">
            <p className="responsibility-section-kicker">Cierre / Lo que falta</p>
            <h2 className="responsibility-section-title" id="responsibility-open-title">
              Separar probado, parcial y pendiente.
            </h2>
            <p className="responsibility-section-dek">
              La página debe acabar con incertidumbre accionable, no con una falsa conclusión.
            </p>
          </div>

          <div className="responsibility-question-columns">
            <div className="responsibility-question-column">
              <h3 className="responsibility-question-column__title">Preguntas de responsabilidad</h3>
              <div className="responsibility-question-list">
                {questions.map((question) => (
                  <article className="responsibility-question-item" key={question.question_id}>
                    <div className="responsibility-question-item__head">
                      <span className={statusClassName(question.status)}>{question.status_label || statusLabel(question.status)}</span>
                      <span className="responsibility-question-item__category">{question.category || "Pregunta"}</span>
                    </div>
                    <p className="responsibility-question-item__prompt">{question.prompt || "Sin pregunta publicada."}</p>
                    {asList(question.next_evidence_needed).length ? (
                      <p className="responsibility-question-item__next">Siguiente evidencia: {asList(question.next_evidence_needed).join(" · ")}</p>
                    ) : null}
                  </article>
                ))}
              </div>
            </div>

            <div className="responsibility-question-column responsibility-question-column--gaps">
              <h3 className="responsibility-question-column__title">Huecos y próximas líneas</h3>
              {knownGaps.length ? (
                <ul className="responsibility-gap-list">
                  {knownGaps.map((item) => (
                    <li className="responsibility-gap-list__item" key={item}>
                      {item}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="responsibility-empty-state__copy">No hay huecos conocidos publicados.</p>
              )}
              {nextLanes.length ? (
                <div className="responsibility-next-lanes" aria-label="Siguientes líneas">
                  {nextLanes.map((item) => (
                    <span className="responsibility-next-lanes__item" key={item}>
                      {item}
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <footer className="responsibility-footer">
            <p className="responsibility-footer__text">
              Cobertura total: {formatInt(coverage.governing_rules_total || governingRules.length)} reglas,{" "}
              {formatInt(coverage.official_findings_total || officialFindings.length)} hallazgos,{" "}
              {formatInt(coverage.administrative_acts_total || administrativeActs.length)} actos,{" "}
              {formatInt(coverage.structural_evidence_rows_total || evidenceRows.length)} registros de evidencia.
            </p>
          </footer>
        </section>
      </article>
    </main>
  );
}
