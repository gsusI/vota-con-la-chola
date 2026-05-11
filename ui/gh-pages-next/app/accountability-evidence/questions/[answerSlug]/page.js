import { notFound } from "next/navigation";
import { withBasePath } from "../../../path-utils.mjs";
import { formatDate, formatInt } from "../../../static-snapshot.mjs";
import { formatRole } from "../../../accountability-dossiers/dossier-utils.mjs";
import {
  EVIDENCE_API_DATA_PATH,
  findQaAnswerBySlug,
  loadEvidenceApiPayload,
  qaAnswerSlug,
  safeArray,
  safeObject,
} from "../../evidence-utils.mjs";

export const dynamicParams = false;

export async function generateStaticParams() {
  const payload = loadEvidenceApiPayload();
  return safeArray(payload.qa_answers).map((answer) => ({ answerSlug: qaAnswerSlug(answer) }));
}

export async function generateMetadata({ params }) {
  const { answerSlug: currentSlug } = await params;
  const answer = findQaAnswerBySlug(loadEvidenceApiPayload(), currentSlug);
  if (!answer) {
    return {
      title: "Q&A no encontrada | Vota Con La Chola",
      description: "No encontramos esa respuesta en el corte publico actual.",
    };
  }
  return {
    title: `${answer.question || "Q&A"} | Evidence API`,
    description: answer.answer_text || "Respuesta auditable con caveats y enlace a evidencia.",
  };
}

function QaMetric({ label, value, note }) {
  return (
    <article className="accountability-evidence-question-detail-metric kpiCard">
      <span className="accountability-evidence-question-detail-metric__label kpiLabel">{label}</span>
      <strong className="accountability-evidence-question-detail-metric__value kpiValue">{value}</strong>
      {note ? <span className="accountability-evidence-question-detail-metric__note kpiLabel">{note}</span> : null}
    </article>
  );
}

function basisValue(value) {
  if (Array.isArray(value)) {
    return value.length ? value.map((item) => formatRole(item)).join(", ") : "sin señal";
  }
  if (value && typeof value === "object") {
    return Object.entries(value)
      .map(([key, item]) => `${key}: ${item}`)
      .join(", ");
  }
  if (typeof value === "number") {
    return formatInt(value);
  }
  return String(value || "sin dato");
}

function EvidenceBasis({ basis }) {
  const facts = Object.entries(safeObject(basis)).filter(([, value]) => value !== null && value !== undefined && value !== "");
  return (
    <dl className="accountability-evidence-question-basis__facts twoCols">
      {facts.map(([key, value]) => (
        <div className="accountability-evidence-question-basis__fact kpiCard" key={key}>
          <dt>{key.replaceAll("_", " ")}</dt>
          <dd>{basisValue(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function RouteLinks({ answer }) {
  const routes = safeObject(answer.routes);
  const primaryRoute = String(routes.primary || "").trim();
  return (
    <div className="accountability-evidence-question-route-list chips">
      <a className="accountability-evidence-question-route-list__link chip" href={withBasePath("/accountability-evidence/")}>
        Volver a Evidence API
      </a>
      <a className="accountability-evidence-question-route-list__link chip" href={withBasePath(EVIDENCE_API_DATA_PATH)}>
        Descargar JSON
      </a>
      {primaryRoute ? (
        <a className="accountability-evidence-question-route-list__link chip" href={withBasePath(primaryRoute)}>
          Abrir evidencia primaria
        </a>
      ) : null}
    </div>
  );
}

function CaveatList({ caveats }) {
  const items = safeArray(caveats);
  if (!items.length) {
    return <p className="accountability-evidence-question-caveats__empty sub">Sin caveats adicionales.</p>;
  }
  return (
    <ul className="accountability-evidence-question-caveats__list">
      {items.map((caveat) => (
        <li className="accountability-evidence-question-caveats__item kpiCard" key={caveat}>
          {caveat}
        </li>
      ))}
    </ul>
  );
}

export default async function AccountabilityEvidenceQuestionPage({ params }) {
  const { answerSlug: currentSlug } = await params;
  const payload = loadEvidenceApiPayload();
  const answer = findQaAnswerBySlug(payload, currentSlug);
  if (!answer) {
    return notFound();
  }
  const basis = safeObject(answer.evidence_basis);

  return (
    <main className="accountability-evidence-question-detail-page shell">
      <section className="accountability-evidence-question-detail-hero hero card">
        <p className="accountability-evidence-question-detail-hero__eyebrow eyebrow">
          Q&A · {answer.answer_status || "sin estado"} · {answer.source_collection || "evidence_api"}
        </p>
        <h1 className="accountability-evidence-question-detail-hero__title">{answer.question || "Pregunta sin titulo"}</h1>
        <p className="accountability-evidence-question-detail-hero__summary sub">{answer.answer_text || "Sin respuesta generada."}</p>
        <RouteLinks answer={answer} />
      </section>

      <section className="accountability-evidence-question-detail-metrics kpiGrid" aria-label="Cobertura de la respuesta">
        <QaMetric label="Entradas" value={formatInt(basis.entries_total)} note="filas fuente" />
        <QaMetric label="Actores" value={formatInt(basis.actors_total)} note="si aplica" />
        <QaMetric label="Temas" value={formatInt(basis.issues_total)} note="si aplica" />
        <QaMetric label="Desde" value={formatDate(basis.first_date)} note="primera fecha" />
        <QaMetric label="Hasta" value={formatDate(basis.last_date)} note="ultima fecha" />
      </section>

      <section className="accountability-evidence-question-basis block">
        <div className="accountability-evidence-question-basis__head blockHead">
          <h2 className="accountability-evidence-question-basis__title">Base de evidencia</h2>
        </div>
        <EvidenceBasis basis={basis} />
      </section>

      <section className="accountability-evidence-question-caveats block">
        <div className="accountability-evidence-question-caveats__head blockHead">
          <h2 className="accountability-evidence-question-caveats__title">Caveats</h2>
        </div>
        <CaveatList caveats={answer.caveats} />
      </section>
    </main>
  );
}
