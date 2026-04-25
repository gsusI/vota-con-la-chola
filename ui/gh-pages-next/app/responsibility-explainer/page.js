import {
  buildResponsibilityExplainerHref,
  formatDate,
  formatInt,
  loadResponsibilityExplainerManifest,
  withBasePath,
} from "./pageData.mjs";

export const metadata = {
  title: "Responsibility explainer | Vota Con La Chola",
  description: "Indice publico de casos de responsabilidad con reglas, actos, cadenas y huecos visibles.",
};

export default function ResponsibilityExplainerIndexPage() {
  const manifest = loadResponsibilityExplainerManifest();
  const firstCase = manifest.cases?.[0] || null;

  return (
    <main className="shell">
      <section className="hero card explainerHero">
        <p className="eyebrow">Wedge de responsabilidad</p>
        <h1>Responsibility explainer</h1>
        <p className="sub">
          Paginas publicas y compartibles para seguir reglas, actos, cadenas de responsabilidad y huecos abiertos en
          fallos publicos, captura regulatoria, urbanismo, enforcement o crisis concretas.
        </p>
        <div className="chips">
          <span className="chip">Casos static-first</span>
          <span className="chip">Ledger de reglas y actos</span>
          <span className="chip">Huecos explicitados</span>
          <span className="chip">Snapshot: {manifest.meta?.snapshot_date || "sin fecha"}</span>
        </div>
        <p className="sub" style={{ marginTop: 12 }}>
          {firstCase ? <a href={buildResponsibilityExplainerHref(firstCase.case_id)}>Abrir caso destacado</a> : "Todavia no hay casos exportados para demo."}
          <span style={{ marginLeft: "10px" }}>
            <a href={withBasePath("/explorer/")}>Ir al explorer</a>
          </span>
        </p>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Casos disponibles</h2>
        </div>
        {manifest.cases?.length ? (
          <div className="voteIndexGrid">
            {manifest.cases.map((item) => {
              const coverage = item.coverage || {};
              const statusCounts = item.question_status_counts || {};
              return (
                <a className="voteIndexCard" href={buildResponsibilityExplainerHref(item.case_id)} key={item.case_id}>
                  <span className="kpiLabel">
                    {item.case_id} · {formatDate(manifest.meta?.snapshot_date)}
                  </span>
                  <strong>{item.title || item.case_id}</strong>
                  <span className="sub" style={{ marginTop: 8 }}>
                    {item.summary || "Sin resumen disponible."}
                  </span>
                  <div className="chips" style={{ marginTop: 10 }}>
                    <span className="chip">Reglas: {formatInt(coverage.governing_rules_total || 0)}</span>
                    <span className="chip">Hallazgos: {formatInt(coverage.official_findings_total || 0)}</span>
                    <span className="chip">Actos: {formatInt(coverage.administrative_acts_total || 0)}</span>
                    <span className="chip">Cadenas: {formatInt(coverage.responsibility_links_total || 0)}</span>
                    <span className="chip">Deberes: {formatInt(coverage.normative_duties_total || 0)}</span>
                    <span className="chip">Evidencia estructural: {formatInt(coverage.structural_evidence_rows_total || 0)}</span>
                    <span className="chip">Iniciativas: {formatInt(coverage.initiatives_total || 0)}</span>
                    <span className="chip">Preguntas parciales: {formatInt(statusCounts.partial || 0)}</span>
                  </div>
                </a>
              );
            })}
          </div>
        ) : (
          <p className="sub">No encontramos casos exportados en el snapshot publico actual.</p>
        )}
      </section>
    </main>
  );
}
