import { readPublicJson } from "../static-snapshot.mjs";
import { withBasePath } from "../path-utils.mjs";
import styles from "./election-hub.module.css";

function classes(localClass, stableClass) {
  return `${localClass} ${stableClass}`;
}

function formatInt(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return "0";
  }
  return Math.trunc(parsed).toLocaleString("es-ES");
}

export default function ElectionIndexPage() {
  const andalucia = readPublicJson(
    "elecciones/andalucia-2026/data/water-receipt.json",
    {},
  );
  const summary = andalucia.summary || {};
  const status = summary.post_investiture_actions_total
    ? "Con hito posterior"
    : "Primer corte publicado";

  return (
    <main className={classes(styles.page, "election-hub-page")}>
      <section
        className={classes(styles.hero, "election-hub-hero")}
        aria-labelledby="election-hub-title"
      >
        <p className={classes(styles.eyebrow, "election-hub-hero-eyebrow")}>Elecciones</p>
        <h1 className={classes(styles.title, "election-hub-hero-title")} id="election-hub-title">
          Páginas electorales con evidencia
        </h1>
        <p className={classes(styles.summary, "election-hub-hero-summary")}>
          Preguntas concretas, estado verificable y fuentes oficiales. Sin rankings ni atribuciones automáticas.
        </p>
      </section>

      <section
        className={classes(styles.list, "election-hub-list")}
        aria-label="Elecciones disponibles"
      >
        <article className={classes(styles.card, "election-hub-card")}>
          <div className={classes(styles.cardHead, "election-hub-card-head")}>
            <p className={classes(styles.eyebrow, "election-hub-card-eyebrow")}>Autonómicas</p>
            <h2 className={classes(styles.cardTitle, "election-hub-card-title")}>
              Andalucía 2026 · el recibo del agua
            </h2>
            <span className={classes(styles.cardStatus, "election-hub-card-status")}>{status}</span>
          </div>
          <dl className={classes(styles.cardFacts, "election-hub-card-facts")}>
            <div className={classes(styles.cardFact, "election-hub-card-fact")}>
              <dt>Corte</dt>
              <dd>{andalucia.snapshot_date || "sin dato"}</dd>
            </div>
            <div className={classes(styles.cardFact, "election-hub-card-fact")}>
              <dt>Compromisos</dt>
              <dd>{formatInt(summary.commitments_total)}</dd>
            </div>
            <div className={classes(styles.cardFact, "election-hub-card-fact")}>
              <dt>Hitos posteriores</dt>
              <dd>{formatInt(summary.post_investiture_actions_total)}</dd>
            </div>
            <div className={classes(styles.cardFact, "election-hub-card-fact")}>
              <dt>Plazo anunciado</dt>
              <dd>No</dd>
            </div>
          </dl>
          <a
            className={classes(styles.cardLink, "election-hub-card-link")}
            href={withBasePath("/elecciones/andalucia-2026/")}
          >
            Abrir el recibo
          </a>
        </article>
      </section>
    </main>
  );
}
