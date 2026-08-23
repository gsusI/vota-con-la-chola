import { formatInt, readPublicJson } from "../static-snapshot.mjs";
import { StaticRouteHero, StaticRouteLink } from "../static-route-components";
import styles from "./spending.module.css";

const EMPTY_SNAPSHOT = {
  source: { corpus_counts: {}, archives: [] },
  methodology: {},
  counts: {},
  amounts: {},
  items: [],
};

export const metadata = {
  title: "Dinero público con evidencia | Vota Con La Chola",
  description:
    "Adjudicaciones públicas reales con órgano, proveedor, identificadores, importe exacto y evidencia oficial PLACSP.",
};

function shortHash(value) {
  const raw = String(value || "");
  return raw ? `${raw.slice(0, 12)}…` : "sin hash";
}

function formatDecimal(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return "desconocido";
  const [whole, fraction] = raw.split(".");
  const sign = whole.startsWith("-") ? "-" : "";
  const digits = sign ? whole.slice(1) : whole;
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${sign}${grouped}${fraction ? `,${fraction}` : ""}`;
}

function exactActorIdentifier(actor) {
  if (!actor?.source_identifier) return "sin identificador publicado";
  return `${actor.source_identifier_scheme || "ID fuente"} ${actor.source_identifier}`;
}

function counterpartyType(actor) {
  const labels = {
    legal_entity: "persona jurídica",
    potential_natural_person: "posible persona física",
    unclassified: "tipo no resuelto",
  };
  return labels[actor?.source_category] || "tipo no resuelto";
}

function SpendingCard({ item, index }) {
  const authority = item.actors?.find((actor) => actor.actor_role === "contracting_authority");
  const supplier = item.actors?.find((actor) => actor.actor_role === "supplier");
  const primaryEvidence = item.evidence?.find((evidence) => evidence.evidence_role === "primary_record");
  const documentEvidence = item.evidence?.find((evidence) => evidence.document_url);

  return (
    <li className={`spending-sample-item ${styles.spendingItem}`}>
      <article className={`spending-award-card ${styles.spendingCard}`}>
        <header className={`spending-award-card__header ${styles.cardHeader}`}>
          <div className="spending-award-card__identity">
            <span className={`spending-award-card__ordinal ${styles.ordinal}`}>
              Adjudicación {String(index + 1).padStart(2, "0")}
            </span>
            <h3 className={`spending-award-card__title ${styles.cardTitle}`}>{item.title}</h3>
          </div>
          <span className={`spending-award-card__phase ${styles.phaseBadge}`}>no es pago</span>
        </header>

        <dl className={`spending-award-card__money ${styles.moneyPanel}`}>
          <div className="spending-award-card__money-fact">
            <dt className="spending-award-card__money-label">Importe adjudicado sin impuestos</dt>
            <dd className={`spending-award-card__money-value ${styles.moneyValue}`}>
              {formatDecimal(item.money?.amount_decimal)} {item.money?.currency}
            </dd>
          </div>
          <div className="spending-award-card__money-fact">
            <dt className="spending-award-card__money-label">Importe pagadero publicado</dt>
            <dd className={`spending-award-card__money-secondary ${styles.moneySecondary}`}>
              {formatDecimal(item.money?.payable_amount_decimal)} {item.money?.currency}
            </dd>
          </div>
        </dl>

        <div className={`spending-award-card__actors ${styles.actorGrid}`}>
          <section className={`spending-award-card__actor ${styles.actorPanel}`} aria-label="Órgano de contratación">
            <span className={`spending-award-card__actor-role ${styles.actorRole}`}>Órgano de contratación</span>
            <strong className="spending-award-card__actor-name">{authority?.source_label || "desconocido"}</strong>
            <code className={`spending-award-card__actor-id ${styles.actorId}`}>
              {exactActorIdentifier(authority)}
            </code>
          </section>
          <section className={`spending-award-card__actor ${styles.actorPanel}`} aria-label="Proveedor adjudicatario">
            <span className={`spending-award-card__actor-role ${styles.actorRole}`}>Proveedor · {counterpartyType(supplier)}</span>
            <strong className="spending-award-card__actor-name">{supplier?.source_label || "desconocido"}</strong>
            <code className={`spending-award-card__actor-id ${styles.actorId}`}>
              {exactActorIdentifier(supplier)}
            </code>
          </section>
        </div>

        <dl className={`spending-award-card__facts ${styles.factGrid}`}>
          <div className="spending-award-card__fact">
            <dt>Decisión</dt>
            <dd>{item.dates?.decision_on || "desconocida"}</dd>
          </div>
          <div className="spending-award-card__fact">
            <dt>Expediente</dt>
            <dd>{item.external_contract_id || "sin referencia"}</dd>
          </div>
          <div className="spending-award-card__fact">
            <dt>CPV</dt>
            <dd>{item.classification?.code || "sin código"}</dd>
          </div>
          <div className="spending-award-card__fact">
            <dt>Ofertas recibidas</dt>
            <dd>{item.procedure?.received_tender_quantity ?? "desconocidas"}</dd>
          </div>
        </dl>

        <footer className={`spending-award-card__footer ${styles.cardFooter}`}>
          <div className={`spending-award-card__links ${styles.cardLinks}`}>
            <StaticRouteLink href={primaryEvidence?.source_url}>Abrir expediente oficial</StaticRouteLink>
            {documentEvidence ? (
              <StaticRouteLink href={documentEvidence.document_url}>Abrir documento enlazado</StaticRouteLink>
            ) : null}
          </div>
          <code className={`spending-award-card__hash ${styles.hash}`}>
            fuente {shortHash(item.provenance?.source_record_sha256)}
          </code>
        </footer>
      </article>
    </li>
  );
}

export default function SpendingPage() {
  const snapshot = readPublicJson("spending/data/placsp-sample.json", EMPTY_SNAPSHOT);
  const counts = snapshot.counts || {};
  const corpus = snapshot.source?.corpus_counts || {};
  const amounts = snapshot.amounts || {};

  return (
    <main className={`shell spending-page ${styles.page}`}>
      <StaticRouteHero
        actions={[
          { href: "/spending/data/placsp-sample.json", label: "Descargar muestra JSON" },
          { href: snapshot.source?.default_url, label: "Abrir fuente PLACSP" },
        ]}
        eyebrow="Dinero público · evidencia oficial"
        meta={[
          { label: "Fuente", value: "PLACSP" },
          { label: "Fase", value: "Adjudicación" },
          { label: "Release", value: shortHash(snapshot.release_id) },
        ]}
        summary="Primer recorrido público desde un actor hasta una adjudicación y su evidencia oficial. Conserva nombres e identificadores publicados. No convierte adjudicaciones en pagos ni señales en acusaciones."
        title="Dinero público con evidencia"
      />

      <section className={`spending-truth-panel ${styles.truthPanel}`} aria-labelledby="spending-truth-title">
        <div className="spending-truth-panel__copy">
          <p className={`spending-truth-panel__eyebrow ${styles.eyebrow}`}>Contrato de lectura</p>
          <h2 className={`spending-truth-panel__title ${styles.sectionTitle}`} id="spending-truth-title">
            Adjudicado no significa pagado
          </h2>
          <p className={`spending-truth-panel__summary ${styles.sectionCopy}`}>
            Estas filas prueban decisiones de adjudicación publicadas por PLACSP. No prueban firma, factura, pago, entrega, irregularidad ni corrupción. Esos pasos necesitan evidencia distinta y quedan explícitamente desconocidos.
          </p>
        </div>
        <dl className={`spending-truth-panel__metrics ${styles.metricGrid}`}>
          <div className={`spending-truth-panel__metric ${styles.metric}`}>
            <dt>Registros PLACSP</dt>
            <dd>{formatInt(corpus.money_contract_records)}</dd>
          </div>
          <div className={`spending-truth-panel__metric ${styles.metric}`}>
            <dt>Resultados de adjudicación</dt>
            <dd>{formatInt(corpus.money_contract_award_results)}</dd>
          </div>
          <div className={`spending-truth-panel__metric ${styles.metric}`}>
            <dt>Referencias documentales</dt>
            <dd>{formatInt(corpus.money_contract_documents)}</dd>
          </div>
          <div className={`spending-truth-panel__metric ${styles.metric}`}>
            <dt>Muestra pública</dt>
            <dd>{formatInt(counts.published_items)}</dd>
          </div>
        </dl>
      </section>

      <section className={`spending-sample-summary ${styles.summaryPanel}`} aria-labelledby="spending-summary-title">
        <div className="spending-sample-summary__copy">
          <p className={`spending-sample-summary__eyebrow ${styles.eyebrow}`}>Muestra deliberadamente bounded</p>
          <h2 className={`spending-sample-summary__title ${styles.sectionTitle}`} id="spending-summary-title">
            {formatDecimal(amounts.award_amount_total_decimal)} EUR adjudicados en este corte
          </h2>
          <p className={`spending-sample-summary__note ${styles.sectionCopy}`}>
            Selección determinista y estratificada para auditar el contrato de datos. No es una estimación ni una muestra representativa del gasto público.
          </p>
        </div>
        <dl className={`spending-sample-summary__identity-counts ${styles.identityGrid}`}>
          <div className="spending-sample-summary__identity-count">
            <dt>Personas jurídicas</dt>
            <dd>{formatInt(counts.counterparty_legal_entity)}</dd>
          </div>
          <div className="spending-sample-summary__identity-count">
            <dt>Posibles personas físicas</dt>
            <dd>{formatInt(counts.counterparty_potential_natural_person)}</dd>
          </div>
          <div className="spending-sample-summary__identity-count">
            <dt>Tipo no resuelto</dt>
            <dd>{formatInt(counts.counterparty_unclassified)}</dd>
          </div>
        </dl>
      </section>

      <section className={`spending-sample-section ${styles.sampleSection}`} aria-labelledby="spending-sample-title">
        <header className={`spending-sample-section__header ${styles.sectionHeader}`}>
          <div className="spending-sample-section__heading">
            <p className={`spending-sample-section__eyebrow ${styles.eyebrow}`}>Actor → adjudicación → fuente</p>
            <h2 className={`spending-sample-section__title ${styles.sectionTitle}`} id="spending-sample-title">
              Veinte adjudicaciones reales, identidad pública intacta
            </h2>
          </div>
          <p className={`spending-sample-section__note ${styles.sectionNote}`}>
            Identificadores mostrados exactamente como los publicó la fuente, incluidos valores enmascarados por el propio origen.
          </p>
        </header>
        <ol className={`spending-sample-list ${styles.spendingList}`}>
          {(snapshot.items || []).map((item, index) => (
            <SpendingCard index={index} item={item} key={item.spending_item_id} />
          ))}
        </ol>
      </section>
    </main>
  );
}
