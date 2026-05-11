import { withBasePath } from "../../path-utils.mjs";
import { formatDate, formatInt } from "../../static-snapshot.mjs";
import { loadEvidenceApiPayload, qaAnswerHref, safeArray, safeObject, EVIDENCE_API_DATA_PATH } from "../evidence-utils.mjs";

export const metadata = {
  title: "Q&A reproducible | Evidence API",
  description: "Indice estatico de respuestas Q&A con caveats y enlaces a evidencia.",
};

function QaIndexCard({ answer }) {
  const basis = safeObject(answer.evidence_basis);
  return (
    <article className="accountability-evidence-question-index-card kpiCard">
      <p className="accountability-evidence-question-index-card__eyebrow eyebrow">
        {answer.answer_status || "sin estado"} · {answer.source_collection || "qa"}
      </p>
      <h2 className="accountability-evidence-question-index-card__title">
        <a className="accountability-evidence-question-index-card__link" href={qaAnswerHref(answer)}>
          {answer.question || "Pregunta sin titulo"}
        </a>
      </h2>
      <p className="accountability-evidence-question-index-card__summary sub">{answer.answer_text || "Sin respuesta generada."}</p>
      <dl className="accountability-evidence-question-index-card__facts">
        <div className="accountability-evidence-question-index-card__fact">
          <dt>Entradas</dt>
          <dd>{formatInt(basis.entries_total)}</dd>
        </div>
        <div className="accountability-evidence-question-index-card__fact">
          <dt>Temas</dt>
          <dd>{formatInt(basis.issues_total)}</dd>
        </div>
        <div className="accountability-evidence-question-index-card__fact">
          <dt>Fechas</dt>
          <dd>
            {formatDate(basis.first_date)} / {formatDate(basis.last_date)}
          </dd>
        </div>
      </dl>
    </article>
  );
}

export default function AccountabilityEvidenceQuestionsIndexPage() {
  const payload = loadEvidenceApiPayload();
  const answers = safeArray(payload.qa_answers);
  const coverage = safeObject(payload.coverage);
  return (
    <main className="accountability-evidence-question-index-page shell">
      <section className="accountability-evidence-question-index-hero hero card">
        <p className="accountability-evidence-question-index-hero__eyebrow eyebrow">Evidence API · Q&A</p>
        <h1 className="accountability-evidence-question-index-hero__title">Q&A reproducible</h1>
        <p className="accountability-evidence-question-index-hero__summary sub">
          Respuestas estaticas y enlazables generadas desde el artifact, con caveats y ruta a evidencia primaria cuando existe.
        </p>
        <div className="accountability-evidence-question-index-hero__actions chips">
          <a className="accountability-evidence-question-index-hero__link chip" href={withBasePath("/accountability-evidence/")}>
            Volver a Evidence API
          </a>
          <a className="accountability-evidence-question-index-hero__link chip" href={withBasePath(EVIDENCE_API_DATA_PATH)}>
            Descargar JSON
          </a>
        </div>
      </section>

      <section className="accountability-evidence-question-index-metrics kpiGrid" aria-label="Cobertura de Q&A">
        <article className="accountability-evidence-question-index-metric kpiCard">
          <span className="accountability-evidence-question-index-metric__label kpiLabel">Q&A</span>
          <strong className="accountability-evidence-question-index-metric__value kpiValue">{formatInt(coverage.qa_answers_total)}</strong>
          <span className="accountability-evidence-question-index-metric__note kpiLabel">respuestas enlazables</span>
        </article>
        <article className="accountability-evidence-question-index-metric kpiCard">
          <span className="accountability-evidence-question-index-metric__label kpiLabel">Con ruta</span>
          <strong className="accountability-evidence-question-index-metric__value kpiValue">
            {formatInt(coverage.qa_answers_with_self_route_total)}
          </strong>
          <span className="accountability-evidence-question-index-metric__note kpiLabel">self route</span>
        </article>
      </section>

      <section className="accountability-evidence-question-index-list block">
        <div className="accountability-evidence-question-index-list__head blockHead">
          <h2 className="accountability-evidence-question-index-list__title">{formatInt(answers.length)} respuestas exportadas</h2>
        </div>
        <div className="accountability-evidence-question-index-list__grid grid">
          {answers.map((answer) => (
            <QaIndexCard answer={answer} key={answer.answer_id} />
          ))}
        </div>
      </section>
    </main>
  );
}
