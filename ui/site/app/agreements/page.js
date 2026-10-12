import { formatInt, readPublicJson } from "../static-snapshot.mjs";
import { StaticRouteHero, StaticRouteLink } from "../static-route-components";
import styles from "./agreements.module.css";

const EMPTY_SNAPSHOT = {
  source: { corpus_counts: {}, capture: {} },
  methodology: {},
  counts: {},
  records: [],
  influence_assertions: [],
};

export const metadata = {
  title: "Acuerdos y reuniones con evidencia | Vota Con La Chola",
  description:
    "Acuerdos reales del Consejo de Ministros con fecha, actores institucionales, temas derivados y evidencia oficial de La Moncloa.",
};

const PARTY_ROLES = {
  adopter: "Adopta",
  publishing_body: "Publica",
  affected_body: "Organismo mencionado",
  counterparty: "Contraparte mencionada",
};

function shortHash(value) {
  const raw = String(value || "");
  return raw ? `${raw.slice(0, 12)}…` : "sin hash";
}

function formatDate(value) {
  const raw = String(value || "");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw || "fecha desconocida";
  return new Intl.DateTimeFormat("es-ES", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${raw}T00:00:00Z`));
}

function AgreementCard({ record, index }) {
  const agreement = record.agreement || {};
  const meeting = record.meeting || {};
  const provenance = record.provenance || {};
  const evidence = agreement.evidence?.[0];

  return (
    <li className={`agreement-sample-item ${styles.agreementItem}`}>
      <article className={`agreement-evidence-card ${styles.agreementCard}`}>
        <header className={`agreement-evidence-card__header ${styles.cardHeader}`}>
          <div className="agreement-evidence-card__identity">
            <span className={`agreement-evidence-card__ordinal ${styles.ordinal}`}>
              Acuerdo {String(index + 1).padStart(2, "0")} · {formatDate(agreement.adopted_on)}
            </span>
            <h3 className={`agreement-evidence-card__title ${styles.cardTitle}`}>
              {agreement.title}
            </h3>
          </div>
          <span className={`agreement-evidence-card__status ${styles.statusBadge}`}>adoptado</span>
        </header>

        <blockquote className={`agreement-evidence-card__excerpt ${styles.excerpt}`}>
          {agreement.summary}
        </blockquote>

        <section className={`agreement-evidence-card__actors ${styles.cardSection}`} aria-label="Actores institucionales publicados">
          <h4 className={`agreement-evidence-card__section-title ${styles.cardSectionTitle}`}>Actores del registro</h4>
          <ul className={`agreement-evidence-card__actor-list ${styles.actorList}`}>
            {(agreement.parties || []).map((party) => (
              <li className={`agreement-evidence-card__actor ${styles.actorChip}`} key={party.agreement_party_id}>
                <span className={`agreement-evidence-card__actor-role ${styles.actorRole}`}>
                  {PARTY_ROLES[party.party_role] || party.party_role}
                </span>
                <strong className="agreement-evidence-card__actor-name">{party.source_label}</strong>
              </li>
            ))}
          </ul>
        </section>

        <section className={`agreement-evidence-card__topics ${styles.cardSection}`} aria-label="Clasificación temática derivada">
          <h4 className={`agreement-evidence-card__section-title ${styles.cardSectionTitle}`}>Temas · regla sin revisar</h4>
          <ul className={`agreement-evidence-card__topic-list ${styles.topicList}`}>
            {(agreement.topics || []).map((topic) => (
              <li className={`agreement-evidence-card__topic ${styles.topicChip}`} key={topic.agreement_topic_id}>
                {topic.topic_label}
              </li>
            ))}
          </ul>
        </section>

        <dl className={`agreement-evidence-card__facts ${styles.factGrid}`}>
          <div className="agreement-evidence-card__fact">
            <dt>Sesión</dt>
            <dd>{meeting.meeting_kind === "council_session" ? "Consejo de Ministros" : meeting.meeting_kind}</dd>
          </div>
          <div className="agreement-evidence-card__fact">
            <dt>Asistentes</dt>
            <dd>{meeting.attendance_disclosure_state === "not_disclosed" ? "no publicados en esta captura" : meeting.attendance_disclosure_state}</dd>
          </div>
          <div className="agreement-evidence-card__fact">
            <dt>Firma / vigencia / ejecución</dt>
            <dd>no demostradas</dd>
          </div>
          <div className="agreement-evidence-card__fact">
            <dt>Influencia</dt>
            <dd>{agreement.influence_state === "not_asserted" ? "no afirmada" : agreement.influence_state}</dd>
          </div>
        </dl>

        <footer className={`agreement-evidence-card__footer ${styles.cardFooter}`}>
          <StaticRouteLink href={evidence?.source_url}>Abrir referencia oficial</StaticRouteLink>
          <code className={`agreement-evidence-card__hash ${styles.hash}`}>
            fuente {shortHash(provenance.source_record_sha256)}
          </code>
        </footer>
      </article>
    </li>
  );
}

export default function AgreementsPage() {
  const snapshot = readPublicJson("agreements/data/moncloa-sample.json", EMPTY_SNAPSHOT);
  const counts = snapshot.counts || {};
  const corpus = snapshot.source?.corpus_counts || {};

  return (
    <main className={`shell agreements-page ${styles.page}`}>
      <StaticRouteHero
        actions={[
          { href: "/agreements/data/moncloa-sample.json", label: "Descargar muestra JSON" },
          { href: snapshot.source?.default_url, label: "Abrir fuente La Moncloa" },
        ]}
        eyebrow="Acuerdos · reuniones · evidencia oficial"
        meta={[
          { label: "Fuente", value: "La Moncloa" },
          { label: "Hechos", value: `${formatInt(counts.agreements)} acuerdos` },
          { label: "Release", value: shortHash(snapshot.release_id) },
        ]}
        summary="Primer recorrido público desde una sesión colegiada hasta un acuerdo y su resumen oficial. Conserva actores públicos, fechas y texto fuente. No inventa asistentes ni convierte proximidad en influencia."
        title="Acuerdos y reuniones con evidencia"
      />

      <section className={`agreements-truth-panel ${styles.truthPanel}`} aria-labelledby="agreements-truth-title">
        <div className="agreements-truth-panel__copy">
          <p className={`agreements-truth-panel__eyebrow ${styles.eyebrow}`}>Contrato de lectura</p>
          <h2 className={`agreements-truth-panel__title ${styles.sectionTitle}`} id="agreements-truth-title">
            Reunión no significa influencia
          </h2>
          <p className={`agreements-truth-panel__summary ${styles.sectionCopy}`}>
            La fuente prueba que el Consejo de Ministros publicó estos acuerdos. No publica aquí una lista completa de asistentes. Tampoco prueba negociación previa, presión externa, firma, vigencia, ejecución, cumplimiento ni influencia indebida.
          </p>
        </div>
        <dl className={`agreements-truth-panel__metrics ${styles.metricGrid}`}>
          <div className={`agreements-truth-panel__metric ${styles.metric}`}>
            <dt>Referencias capturadas</dt>
            <dd>{formatInt(corpus.moncloa_referencias_records)}</dd>
          </div>
          <div className={`agreements-truth-panel__metric ${styles.metric}`}>
            <dt>Acuerdos explícitos</dt>
            <dd>{formatInt(counts.agreements)}</dd>
          </div>
          <div className={`agreements-truth-panel__metric ${styles.metric}`}>
            <dt>Actores del registro</dt>
            <dd>{formatInt(counts.agreement_parties)}</dd>
          </div>
          <div className={`agreements-truth-panel__metric ${styles.metric}`}>
            <dt>Afirmaciones de influencia</dt>
            <dd>{formatInt(counts.influence_assertions)}</dd>
          </div>
        </dl>
      </section>

      <section className={`agreements-method-panel ${styles.methodPanel}`} aria-labelledby="agreements-method-title">
        <div className="agreements-method-panel__copy">
          <p className={`agreements-method-panel__eyebrow ${styles.eyebrow}`}>Hecho separado de clasificación</p>
          <h2 className={`agreements-method-panel__title ${styles.sectionTitle}`} id="agreements-method-title">
            Once acuerdos reales; etiquetas temáticas visibles como derivadas
          </h2>
          <p className={`agreements-method-panel__summary ${styles.sectionCopy}`}>
            El resumen, la fecha y los nombres vienen de la captura oficial. Los temas proceden de un codebook reproducible y siguen sin revisión humana. Nunca se presentan como palabras literales de la fuente.
          </p>
        </div>
        <dl className={`agreements-method-panel__limits ${styles.limitGrid}`}>
          <div className="agreements-method-panel__limit">
            <dt>Asistencias afirmadas</dt>
            <dd>{formatInt(counts.attendance_claims)}</dd>
          </div>
          <div className="agreements-method-panel__limit">
            <dt>Evidencias exactas</dt>
            <dd>{formatInt(counts.agreement_evidence)}</dd>
          </div>
          <div className="agreements-method-panel__limit">
            <dt>Temas derivados</dt>
            <dd>{formatInt(counts.agreement_topics)}</dd>
          </div>
        </dl>
      </section>

      <section className={`agreements-sample-section ${styles.sampleSection}`} aria-labelledby="agreements-sample-title">
        <header className={`agreements-sample-section__header ${styles.sectionHeader}`}>
          <div className="agreements-sample-section__heading">
            <p className={`agreements-sample-section__eyebrow ${styles.eyebrow}`}>Sesión → acuerdo → actores → fuente</p>
            <h2 className={`agreements-sample-section__title ${styles.sectionTitle}`} id="agreements-sample-title">
              Resúmenes oficiales, sin completar huecos
            </h2>
          </div>
          <p className={`agreements-sample-section__note ${styles.sectionNote}`}>
            Cada tarjeta enlaza la referencia viva y conserva el hash del registro capturado. “Adoptado” no se muestra como “ejecutado”.
          </p>
        </header>
        <ol className={`agreements-sample-list ${styles.agreementList}`}>
          {(snapshot.records || []).map((record, index) => (
            <AgreementCard index={index} key={record.agreement?.agreement_id} record={record} />
          ))}
        </ol>
      </section>
    </main>
  );
}
