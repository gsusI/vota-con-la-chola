import Link from "next/link";

const ANALYSES = [
  {
    slug: "discipline",
    title: "Disciplina",
    description: "Rebeldía y alineación por persona y partido.",
  },
  {
    slug: "attendance",
    title: "Asistencia",
    description: "Asistencia y ausencias por contexto, partido y persona.",
  },
  {
    slug: "outcomes",
    title: "Resultados",
    description: "Resultados de votaciones, margen y partidos pivotales.",
  },
  {
    slug: "coalitions",
    title: "Coaliciones",
    description: "Similitud entre partidos y coaliciones por tema.",
  },
];

export default function ParliamentaryAccountabilityIndexPage() {
  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">Seguimiento parlamentario</p>
        <h1>Análisis disponibles</h1>
        <p className="sub">Selecciona un análisis para abrirlo como página dedicada.</p>
      </section>

      <section className="card block">
        <div className="kpiGrid">
          {ANALYSES.map((item) => (
            <Link key={item.slug} href={`/parliamentary-accountability/${item.slug}`} className="kpiCardLink">
              <article className="kpiCard">
                <h3 style={{ margin: "0 0 8px" }}>{item.title}</h3>
                <p className="sub" style={{ marginBottom: "10px" }}>{item.description}</p>
                <span className="chip">Abrir {item.title}</span>
              </article>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
