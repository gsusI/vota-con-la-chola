import { withBasePath } from "../path-utils.mjs";
import { formatDate, formatInt } from "../static-snapshot.mjs";
import { formatRole } from "../accountability-dossiers/dossier-utils.mjs";
import {
  EVIDENCE_API_DATA_PATH,
  loadEvidenceApiPayload,
  qaAnswerHref,
  safeArray,
  safeObject,
} from "./evidence-utils.mjs";

export const metadata = {
  title: "Evidence API | Vota Con La Chola",
  description:
    "API estatica para preguntas de accountability con respuestas parciales, caveats y evidencia trazable.",
};

function formatPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "0%";
  }
  return `${Math.round(number * 100)}%`;
}

function MetricCard({ label, value, note }) {
  return (
    <article className="accountability-evidence-api-metric kpiCard">
      <span className="accountability-evidence-api-metric__label kpiLabel">{label}</span>
      <strong className="accountability-evidence-api-metric__value kpiValue">{value}</strong>
      {note ? <span className="accountability-evidence-api-metric__note kpiLabel">{note}</span> : null}
    </article>
  );
}

function AnswerStatePills({ answer, classPrefix }) {
  const confidence = safeObject(answer.confidence);
  const freshness = safeObject(answer.freshness);
  const completeness = safeObject(confidence.completeness);
  return (
    <div className={`${classPrefix}__state-list accountability-evidence-answer-state-list chips`}>
      <span className={`${classPrefix}__confidence-chip accountability-evidence-answer-state-list__chip chip`}>
        Confianza {confidence.level || "sin nivel"} · {formatPercent(confidence.score)}
      </span>
      <span className={`${classPrefix}__freshness-chip accountability-evidence-answer-state-list__chip chip`}>
        Frescura {freshness.level || "sin fecha"}
      </span>
      <span className={`${classPrefix}__completeness-chip accountability-evidence-answer-state-list__chip chip`}>
        Cobertura {formatPercent(completeness.pct)}
      </span>
    </div>
  );
}

function RolePills({ roles }) {
  const items = safeArray(roles).slice(0, 4);
  if (!items.length) {
    return <span className="accountability-evidence-api-role-pill pill pill-muted">sin rol</span>;
  }
  return (
    <div className="accountability-evidence-api-role-list chips" aria-label="Roles principales">
      {items.map((item) => (
        <span className="accountability-evidence-api-role-pill chip" key={item.key}>
          {formatRole(item.key)} · {formatInt(item.count)}
        </span>
      ))}
    </div>
  );
}

function QuestionCard({ question }) {
  return (
    <article className="accountability-evidence-question-card kpiCard">
      <p className="accountability-evidence-question-card__eyebrow eyebrow">{question.route_kind || "question"}</p>
      <h3 className="accountability-evidence-question-card__title">{question.question || question.question_id}</h3>
      <p className="accountability-evidence-question-card__summary sub">{question.answer_shape || "sin contrato"}</p>
      <dl className="accountability-evidence-question-card__facts">
        <div className="accountability-evidence-question-card__fact">
          <dt>ID</dt>
          <dd>{question.question_id || "sin id"}</dd>
        </div>
        <div className="accountability-evidence-question-card__fact">
          <dt>Coleccion</dt>
          <dd>{question.answer_collection || "sin coleccion"}</dd>
        </div>
      </dl>
    </article>
  );
}

function QaAnswerCard({ answer }) {
  const evidenceBasis = safeObject(answer.evidence_basis);
  const caveat = safeArray(answer.caveats)[0];
  const primaryRoute = answer.routes?.primary;
  return (
    <article className="accountability-evidence-qa-answer-card kpiCard">
      <p className="accountability-evidence-qa-answer-card__eyebrow eyebrow">
        {answer.answer_status || "sin estado"} · {answer.source_collection || "qa"}
      </p>
      <h3 className="accountability-evidence-qa-answer-card__question">{answer.question || "Pregunta sin titulo"}</h3>
      <p className="accountability-evidence-qa-answer-card__answer sub">{answer.answer_text || "Sin respuesta generada."}</p>
      <dl className="accountability-evidence-qa-answer-card__facts">
        <div className="accountability-evidence-qa-answer-card__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(evidenceBasis.entries_total)}</dd>
        </div>
        <div className="accountability-evidence-qa-answer-card__fact">
          <dt>Fuente API</dt>
          <dd>{answer.source_answer_id || "sin id"}</dd>
        </div>
        <div className="accountability-evidence-qa-answer-card__fact">
          <dt>Fechas</dt>
          <dd>
            {formatDate(evidenceBasis.first_date)} / {formatDate(evidenceBasis.last_date)}
          </dd>
        </div>
      </dl>
      <div className="accountability-evidence-qa-answer-card__actions chips">
        <a className="accountability-evidence-qa-answer-card__link chip" href={qaAnswerHref(answer)}>
          Abrir Q&A
        </a>
        {primaryRoute ? (
          <a className="accountability-evidence-qa-answer-card__link chip" href={withBasePath(primaryRoute)}>
            Abrir evidencia
          </a>
        ) : null}
      </div>
      {caveat ? <p className="accountability-evidence-qa-answer-card__caveat sub">{caveat}</p> : null}
    </article>
  );
}

function ActorAnswerCard({ answer }) {
  return (
    <article className="accountability-evidence-actor-answer-card kpiCard">
      <p className="accountability-evidence-actor-answer-card__eyebrow eyebrow">
        {answer.answer_status || "sin estado"} · {answer.actor_kind || "actor"}
      </p>
      <h3 className="accountability-evidence-actor-answer-card__title">
        <a className="accountability-evidence-actor-answer-card__link" href={withBasePath(answer.routes?.dossier || "/accountability-dossiers/")}>
          {answer.actor_label || answer.actor_key || "Actor sin titulo"}
        </a>
      </h3>
      <p className="accountability-evidence-actor-answer-card__summary sub">{answer.summary || "Sin respuesta."}</p>
      <dl className="accountability-evidence-actor-answer-card__facts">
        <div className="accountability-evidence-actor-answer-card__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(answer.coverage?.entries_total)}</dd>
        </div>
        <div className="accountability-evidence-actor-answer-card__fact">
          <dt>Temas</dt>
          <dd>{formatInt(answer.coverage?.issues_total)}</dd>
        </div>
        <div className="accountability-evidence-actor-answer-card__fact">
          <dt>Fechas</dt>
          <dd>
            {formatDate(answer.coverage?.first_date)} / {formatDate(answer.coverage?.last_date)}
          </dd>
        </div>
      </dl>
      <AnswerStatePills answer={answer} classPrefix="accountability-evidence-actor-answer-card" />
      <RolePills roles={answer.role_counts} />
      {safeArray(answer.caveats)[0] ? (
        <p className="accountability-evidence-actor-answer-card__caveat sub">{safeArray(answer.caveats)[0]}</p>
      ) : null}
    </article>
  );
}

function ActorIssueRefCard({ item }) {
  const routes = safeObject(item.routes);
  return (
    <article className="accountability-evidence-actor-issue-card kpiCard">
      <p className="accountability-evidence-actor-issue-card__eyebrow eyebrow">
        {item.answer_status || "sin estado"} · {item.actor_kind || "actor"}
      </p>
      <h3 className="accountability-evidence-actor-issue-card__title">
        <a className="accountability-evidence-actor-issue-card__actor-link" href={withBasePath(routes.actor_dossier || "/accountability-dossiers/")}>
          {item.actor_label || item.actor_key || "Actor sin titulo"}
        </a>
      </h3>
      <p className="accountability-evidence-actor-issue-card__issue sub">
        <a className="accountability-evidence-actor-issue-card__issue-link" href={withBasePath(routes.issue_dossier || "/accountability-dossiers/")}>
          {item.issue_label || item.issue_id || "Tema sin titulo"}
        </a>
      </p>
      <dl className="accountability-evidence-actor-issue-card__facts">
        <div className="accountability-evidence-actor-issue-card__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(item.entries_total)}</dd>
        </div>
        <div className="accountability-evidence-actor-issue-card__fact">
          <dt>Fechas</dt>
          <dd>
            {formatDate(item.first_date)} / {formatDate(item.last_date)}
          </dd>
        </div>
      </dl>
      <RolePills roles={item.role_counts} />
    </article>
  );
}

function IssueAnswerCard({ answer }) {
  return (
    <article className="accountability-evidence-issue-answer-card kpiCard">
      <p className="accountability-evidence-issue-answer-card__eyebrow eyebrow">
        {answer.answer_status || "sin estado"} · {answer.coverage?.scope || "sin ambito"}
      </p>
      <h3 className="accountability-evidence-issue-answer-card__title">
        <a className="accountability-evidence-issue-answer-card__link" href={withBasePath(answer.routes?.dossier || "/accountability-dossiers/")}>
          {answer.issue_label || answer.issue_id || "Tema sin titulo"}
        </a>
      </h3>
      <p className="accountability-evidence-issue-answer-card__summary sub">{answer.summary || "Sin respuesta."}</p>
      <dl className="accountability-evidence-issue-answer-card__facts">
        <div className="accountability-evidence-issue-answer-card__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(answer.coverage?.entries_total)}</dd>
        </div>
        <div className="accountability-evidence-issue-answer-card__fact">
          <dt>Actores</dt>
          <dd>{formatInt(answer.coverage?.actors_total)}</dd>
        </div>
        <div className="accountability-evidence-issue-answer-card__fact">
          <dt>Fechas</dt>
          <dd>
            {formatDate(answer.coverage?.first_date)} / {formatDate(answer.coverage?.last_date)}
          </dd>
        </div>
      </dl>
      <AnswerStatePills answer={answer} classPrefix="accountability-evidence-issue-answer-card" />
      <RolePills roles={answer.role_counts} />
    </article>
  );
}

function IssueClusterCard({ cluster }) {
  const coverage = safeObject(cluster.coverage);
  const method = safeObject(cluster.method);
  const topIssues = safeArray(cluster.top_issues).slice(0, 3);
  return (
    <article className="accountability-evidence-issue-cluster-card kpiCard">
      <p className="accountability-evidence-issue-cluster-card__eyebrow eyebrow">
        {cluster.answer_status || "sin estado"} · {method.confidence || "heuristico"}
      </p>
      <h3 className="accountability-evidence-issue-cluster-card__title">{cluster.label || cluster.cluster_id}</h3>
      <p className="accountability-evidence-issue-cluster-card__summary sub">{cluster.summary || "Sin agrupacion."}</p>
      <dl className="accountability-evidence-issue-cluster-card__facts">
        <div className="accountability-evidence-issue-cluster-card__fact">
          <dt>Issues fuente</dt>
          <dd>{formatInt(coverage.issues_total)}</dd>
        </div>
        <div className="accountability-evidence-issue-cluster-card__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(coverage.entries_total)}</dd>
        </div>
        <div className="accountability-evidence-issue-cluster-card__fact">
          <dt>Fechas</dt>
          <dd>
            {formatDate(coverage.first_date)} / {formatDate(coverage.last_date)}
          </dd>
        </div>
      </dl>
      <RolePills roles={cluster.role_counts} />
      <p className="accountability-evidence-issue-cluster-card__method sub">{method.basis || "Agrupacion determinista."}</p>
      <div className="accountability-evidence-issue-cluster-card__issues chips">
        {topIssues.map((issue) => (
          <a className="accountability-evidence-issue-cluster-card__issue-link chip" href={withBasePath(issue.route || "/accountability-dossiers/")} key={issue.answer_id || issue.issue_id}>
            {issue.label || issue.issue_id}
          </a>
        ))}
      </div>
    </article>
  );
}

function IssueClusterReviewCard({ item }) {
  const coverage = safeObject(item.coverage);
  const method = safeObject(item.method);
  const review = safeObject(item.review);
  const sampleIssues = safeArray(item.sample_issues).slice(0, 3);
  const summary =
    item.review_status === "reviewed"
      ? review.rationale || item.review_prompt || "Etiqueta publica revisada; pertenencia de issues aun heuristica."
      : item.review_prompt || "Revision pendiente.";
  return (
    <article className="accountability-evidence-cluster-review-card kpiCard">
      <p className="accountability-evidence-cluster-review-card__eyebrow eyebrow">
        {item.review_status || "sin estado"} · {method.method_id || "sin metodo"}
      </p>
      <h3 className="accountability-evidence-cluster-review-card__title">{item.label || item.cluster_id}</h3>
      <p className="accountability-evidence-cluster-review-card__summary sub">{summary}</p>
      <dl className="accountability-evidence-cluster-review-card__facts">
        <div className="accountability-evidence-cluster-review-card__fact">
          <dt>Issues</dt>
          <dd>{formatInt(coverage.issues_total)}</dd>
        </div>
        <div className="accountability-evidence-cluster-review-card__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(coverage.entries_total)}</dd>
        </div>
        <div className="accountability-evidence-cluster-review-card__fact">
          <dt>Fechas</dt>
          <dd>
            {formatDate(coverage.first_date)} / {formatDate(coverage.last_date)}
          </dd>
        </div>
        <div className="accountability-evidence-cluster-review-card__fact">
          <dt>Reviewer</dt>
          <dd>{review.reviewer || "pendiente"}</dd>
        </div>
      </dl>
      <div className="accountability-evidence-cluster-review-card__samples chips">
        {sampleIssues.map((issue) => (
          <a className="accountability-evidence-cluster-review-card__sample-link chip" href={withBasePath(issue.route || "/accountability-dossiers/")} key={issue.answer_id || issue.issue_id}>
            {issue.label || issue.issue_id}
          </a>
        ))}
      </div>
    </article>
  );
}

function IssueClusterAssignmentReviewCard({ item }) {
  const coverage = safeObject(item.coverage);
  const matches = safeArray(item.current_matches).slice(0, 3);
  return (
    <article className="accountability-evidence-assignment-review-card kpiCard">
      <p className="accountability-evidence-assignment-review-card__eyebrow eyebrow">
        {item.review_status || "sin estado"} · {item.primary_cluster_id || "sin cluster"}
      </p>
      <h3 className="accountability-evidence-assignment-review-card__title">
        <a className="accountability-evidence-assignment-review-card__link" href={withBasePath(item.routes?.dossier || "/accountability-dossiers/")}>
          {item.label || item.issue_id}
        </a>
      </h3>
      <p className="accountability-evidence-assignment-review-card__summary sub">
        {item.review_prompt || "Asignacion pendiente de revision."}
      </p>
      <dl className="accountability-evidence-assignment-review-card__facts">
        <div className="accountability-evidence-assignment-review-card__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(coverage.entries_total)}</dd>
        </div>
        <div className="accountability-evidence-assignment-review-card__fact">
          <dt>Actores</dt>
          <dd>{formatInt(coverage.actors_total)}</dd>
        </div>
        <div className="accountability-evidence-assignment-review-card__fact">
          <dt>Fechas</dt>
          <dd>
            {formatDate(coverage.first_date)} / {formatDate(coverage.last_date)}
          </dd>
        </div>
      </dl>
      <div className="accountability-evidence-assignment-review-card__matches chips">
        {matches.map((match) => (
          <span className="accountability-evidence-assignment-review-card__match chip" key={`${item.review_id}-${match.cluster_id}`}>
            {match.label || match.cluster_id}
          </span>
        ))}
      </div>
    </article>
  );
}

function GapAnswerCard({ answer }) {
  const coverage = safeObject(answer.coverage);
  const sampleIssues = safeArray(answer.sample_missing_issues).slice(0, 2);
  const sampleActors = safeArray(answer.sample_missing_actors).slice(0, 2);
  return (
    <article className="accountability-evidence-gap-answer-card kpiCard">
      <p className="accountability-evidence-gap-answer-card__eyebrow eyebrow">
        {answer.answer_status || "sin estado"} · {answer.dimension || "dimension"}
      </p>
      <h3 className="accountability-evidence-gap-answer-card__title">{answer.dimension_label || answer.dimension}</h3>
      <p className="accountability-evidence-gap-answer-card__summary sub">{answer.summary || "Sin gap calculado."}</p>
      <dl className="accountability-evidence-gap-answer-card__facts">
        <div className="accountability-evidence-gap-answer-card__fact">
          <dt>Issues sin evidencia</dt>
          <dd>{formatInt(coverage.issue_answers_missing)}</dd>
        </div>
        <div className="accountability-evidence-gap-answer-card__fact">
          <dt>Actores sin evidencia</dt>
          <dd>{formatInt(coverage.actor_answers_missing)}</dd>
        </div>
        <div className="accountability-evidence-gap-answer-card__fact">
          <dt>Con señal</dt>
          <dd>{formatInt(coverage.present_answers_total)}</dd>
        </div>
      </dl>
      <p className="accountability-evidence-gap-answer-card__next sub">{answer.next_evidence_needed || "Falta evidencia primaria."}</p>
      <div className="accountability-evidence-gap-answer-card__samples">
        {sampleIssues.map((issue) => (
          <a className="accountability-evidence-gap-answer-card__sample-link chip" href={withBasePath(issue.route || "/accountability-dossiers/")} key={issue.answer_id}>
            {issue.label || issue.issue_id}
          </a>
        ))}
        {sampleActors.map((actor) => (
          <a className="accountability-evidence-gap-answer-card__sample-link chip" href={withBasePath(actor.route || "/accountability-dossiers/")} key={actor.answer_id}>
            {actor.label || actor.actor_key}
          </a>
        ))}
      </div>
    </article>
  );
}

function EvidenceSampleCard({ sample }) {
  return (
    <article className="accountability-evidence-sample-card kpiCard">
      <div className="accountability-evidence-sample-card__head">
        <p className="accountability-evidence-sample-card__eyebrow eyebrow">tier {sample.evidence_tier || "sin tier"}</p>
        <span className="accountability-evidence-sample-card__role chip">{formatRole(sample.accountability_role || "")}</span>
      </div>
      <h3 className="accountability-evidence-sample-card__title">{sample.actor_label || "Actor sin etiqueta"}</h3>
      <p className="accountability-evidence-sample-card__summary sub">{sample.summary || "Sin resumen."}</p>
      <dl className="accountability-evidence-sample-card__facts">
        <div className="accountability-evidence-sample-card__fact">
          <dt>Fuente</dt>
          <dd>
            {sample.source_url ? (
              <a className="accountability-evidence-sample-card__source-link" href={sample.source_url}>
                {sample.source_title || "fuente"}
              </a>
            ) : (
              sample.source_title || "sin fuente"
            )}
          </dd>
        </div>
        <div className="accountability-evidence-sample-card__fact">
          <dt>Fecha</dt>
          <dd>{formatDate(sample.event_date)}</dd>
        </div>
        <div className="accountability-evidence-sample-card__fact">
          <dt>Cita</dt>
          <dd>{sample.evidence_quote || "sin cita"}</dd>
        </div>
      </dl>
    </article>
  );
}

export default function AccountabilityEvidenceApiPage() {
  const payload = loadEvidenceApiPayload();
  const meta = safeObject(payload.meta);
  const coverage = safeObject(payload.coverage);
  const confidenceCounts = safeObject(coverage.confidence_level_counts);
  const freshnessCounts = safeObject(coverage.freshness_level_counts);
  const reviewStatusCounts = safeObject(coverage.issue_cluster_review_status_counts);
  const questions = safeArray(payload.question_templates);
  const actorAnswers = safeArray(payload.actor_answers).slice(0, 6);
  const issueAnswers = safeArray(payload.issue_answers).slice(0, 6);
  const actorIssueRefs = safeArray(payload.actor_issue_refs).slice(0, 6);
  const issueClusters = safeArray(payload.issue_clusters).slice(0, 6);
  const issueClusterReviewItems = safeArray(payload.issue_cluster_review_queue).slice(0, 6);
  const issueClusterAssignmentReviewItems = safeArray(payload.issue_cluster_assignment_review_queue).slice(0, 6);
  const gapAnswers = safeArray(payload.gap_answers);
  const qaAnswers = safeArray(payload.qa_answers).slice(0, 8);
  const evidenceSamples = [
    ...safeArray(payload.issue_answers).flatMap((answer) => safeArray(answer.evidence_samples)),
    ...safeArray(payload.actor_answers).flatMap((answer) => safeArray(answer.evidence_samples)),
  ].slice(0, 8);

  return (
    <main className="accountability-evidence-api-page shell">
      <section className="accountability-evidence-api-hero hero card">
        <p className="accountability-evidence-api-hero__eyebrow eyebrow">Evidence API · accountability</p>
        <h1 className="accountability-evidence-api-hero__title">Preguntas repetibles con caveats</h1>
        <p className="accountability-evidence-api-hero__summary sub">
          Capa estatica para responder por tema, actor y evidencia sin reconstruccion manual.
        </p>
        <div className="accountability-evidence-api-hero__actions chips">
          <a className="accountability-evidence-api-hero__link chip" href={withBasePath(EVIDENCE_API_DATA_PATH)}>
            Descargar API JSON
          </a>
          <a className="accountability-evidence-api-hero__link chip" href={withBasePath("/accountability-dossiers/")}>
            Abrir dossiers
          </a>
          <a className="accountability-evidence-api-hero__link chip" href={withBasePath("/explorer/")}>
            Auditar SQL
          </a>
        </div>
      </section>

      <section className="accountability-evidence-api-metrics kpiGrid" aria-label="Cobertura Evidence API">
        <MetricCard label="Preguntas" value={formatInt(coverage.question_templates_total)} note="contratos publicos" />
        <MetricCard label="Actores" value={formatInt(coverage.actor_answers_total)} note="respuestas actor-led" />
        <MetricCard label="Temas" value={formatInt(coverage.issue_answers_total)} note="respuestas issue-led" />
        <MetricCard label="Actor-tema" value={formatInt(coverage.actor_issue_refs_total)} note="cruces acotados" />
        <MetricCard label="Clusters" value={formatInt(coverage.issue_clusters_total)} note="agrupacion heuristica" />
        <MetricCard label="Review" value={formatInt(coverage.issue_cluster_review_items_total)} note={`${formatInt(reviewStatusCounts.reviewed)} revisados`} />
        <MetricCard
          label="Issue review"
          value={formatInt(coverage.issue_cluster_issue_reviews_applied_total)}
          note="asignaciones revisadas"
        />
        <MetricCard
          label="Issue queue"
          value={formatInt(coverage.issue_cluster_assignment_review_needed_total)}
          note={`${formatInt(coverage.issue_cluster_assignment_review_queue_total)} visibles`}
        />
        <MetricCard label="Huecos" value={formatInt(coverage.gap_answers_total)} note="dimensiones auditadas" />
        <MetricCard label="Q&A" value={formatInt(coverage.qa_answers_total)} note="respuestas narrativas" />
        <MetricCard label="Evidencia" value={formatInt(coverage.evidence_samples_total)} note="muestras enlazadas" />
        <MetricCard
          label="Confianza"
          value={formatInt((Number(confidenceCounts.high) || 0) + (Number(confidenceCounts.medium) || 0))}
          note="alta/media"
        />
        <MetricCard
          label="Frescura"
          value={formatInt((Number(freshnessCounts.current) || 0) + (Number(freshnessCounts.recent) || 0))}
          note="actual/reciente"
        />
      </section>

      <section className="accountability-evidence-api-status card block">
        <div className="accountability-evidence-api-status__head blockHead">
          <h2 className="accountability-evidence-api-status__title">Estado del corte</h2>
        </div>
        <dl className="accountability-evidence-api-status__facts twoCols">
          <div className="accountability-evidence-api-status__fact kpiCard">
            <dt>Schema</dt>
            <dd>{meta.schema_version || "sin schema"}</dd>
          </div>
          <div className="accountability-evidence-api-status__fact kpiCard">
            <dt>Corte</dt>
            <dd>{meta.snapshot_date || payload.snapshot_date || "sin fecha"}</dd>
          </div>
          <div className="accountability-evidence-api-status__fact kpiCard">
            <dt>Estado</dt>
            <dd>{safeObject(coverage.answer_status_counts).partial ? "parcial con caveats" : "sin caveats"}</dd>
          </div>
          <div className="accountability-evidence-api-status__fact kpiCard">
            <dt>Confianza</dt>
            <dd>
              alta {formatInt(confidenceCounts.high)} / media {formatInt(confidenceCounts.medium)}
            </dd>
          </div>
          <div className="accountability-evidence-api-status__fact kpiCard">
            <dt>Frescura</dt>
            <dd>
              actual {formatInt(freshnessCounts.current)} / reciente {formatInt(freshnessCounts.recent)}
            </dd>
          </div>
          <div className="accountability-evidence-api-status__fact kpiCard">
            <dt>Generado</dt>
            <dd>{meta.generated_at || "sin timestamp"}</dd>
          </div>
        </dl>
      </section>

      <section className="accountability-evidence-question-section card block">
        <div className="accountability-evidence-question-section__head blockHead">
          <h2 className="accountability-evidence-question-section__title">Catalogo de preguntas</h2>
        </div>
        <div className="accountability-evidence-question-section__grid grid">
          {questions.map((question) => (
            <QuestionCard question={question} key={question.question_id} />
          ))}
        </div>
      </section>

      <section className="accountability-evidence-qa-answer-section card block">
        <div className="accountability-evidence-qa-answer-section__head blockHead">
          <h2 className="accountability-evidence-qa-answer-section__title">Q&A reproducible</h2>
        </div>
        <div className="accountability-evidence-qa-answer-section__grid grid">
          {qaAnswers.map((answer) => (
            <QaAnswerCard answer={answer} key={answer.answer_id} />
          ))}
        </div>
      </section>

      <section className="accountability-evidence-issue-cluster-section card block">
        <div className="accountability-evidence-issue-cluster-section__head blockHead">
          <h2 className="accountability-evidence-issue-cluster-section__title">Clusters ciudadanos</h2>
        </div>
        <div className="accountability-evidence-issue-cluster-section__grid grid">
          {issueClusters.map((cluster) => (
            <IssueClusterCard cluster={cluster} key={cluster.cluster_id} />
          ))}
        </div>
      </section>

      <section className="accountability-evidence-cluster-review-section card block">
        <div className="accountability-evidence-cluster-review-section__head blockHead">
          <h2 className="accountability-evidence-cluster-review-section__title">Cola de revision de clusters</h2>
        </div>
        <div className="accountability-evidence-cluster-review-section__grid grid">
          {issueClusterReviewItems.map((item) => (
            <IssueClusterReviewCard item={item} key={item.review_id} />
          ))}
        </div>
      </section>

      <section className="accountability-evidence-assignment-review-section card block">
        <div className="accountability-evidence-assignment-review-section__head blockHead">
          <h2 className="accountability-evidence-assignment-review-section__title">Cola de revision issue-cluster</h2>
        </div>
        <div className="accountability-evidence-assignment-review-section__grid grid">
          {issueClusterAssignmentReviewItems.map((item) => (
            <IssueClusterAssignmentReviewCard item={item} key={item.review_id} />
          ))}
        </div>
      </section>

      <section className="accountability-evidence-issue-answer-section card block">
        <div className="accountability-evidence-issue-answer-section__head blockHead">
          <h2 className="accountability-evidence-issue-answer-section__title">Respuestas por tema</h2>
        </div>
        <div className="accountability-evidence-issue-answer-section__grid grid">
          {issueAnswers.map((answer) => (
            <IssueAnswerCard answer={answer} key={answer.answer_id} />
          ))}
        </div>
      </section>

      <section className="accountability-evidence-actor-issue-section card block">
        <div className="accountability-evidence-actor-issue-section__head blockHead">
          <h2 className="accountability-evidence-actor-issue-section__title">Cruces actor-tema</h2>
        </div>
        <div className="accountability-evidence-actor-issue-section__grid grid">
          {actorIssueRefs.map((ref) => (
            <ActorIssueRefCard item={ref} key={ref.answer_id} />
          ))}
        </div>
      </section>

      <section className="accountability-evidence-actor-answer-section card block">
        <div className="accountability-evidence-actor-answer-section__head blockHead">
          <h2 className="accountability-evidence-actor-answer-section__title">Respuestas por actor</h2>
        </div>
        <div className="accountability-evidence-actor-answer-section__grid grid">
          {actorAnswers.map((answer) => (
            <ActorAnswerCard answer={answer} key={answer.answer_id} />
          ))}
        </div>
      </section>

      <section className="accountability-evidence-gap-answer-section card block">
        <div className="accountability-evidence-gap-answer-section__head blockHead">
          <h2 className="accountability-evidence-gap-answer-section__title">Huecos no contestables</h2>
        </div>
        <div className="accountability-evidence-gap-answer-section__grid grid">
          {gapAnswers.map((answer) => (
            <GapAnswerCard answer={answer} key={answer.answer_id} />
          ))}
        </div>
      </section>

      <section className="accountability-evidence-sample-section card block">
        <div className="accountability-evidence-sample-section__head blockHead">
          <h2 className="accountability-evidence-sample-section__title">Muestras de evidencia</h2>
        </div>
        <div className="accountability-evidence-sample-section__grid grid">
          {evidenceSamples.map((sample) => (
            <EvidenceSampleCard sample={sample} key={sample.entry_id || `${sample.actor_label}-${sample.event_date}`} />
          ))}
        </div>
      </section>
    </main>
  );
}
