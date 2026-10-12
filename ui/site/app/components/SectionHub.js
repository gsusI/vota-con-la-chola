import Link from "next/link";
import { getDatasetsForSection, getSectionById, withBasePath } from "../siteCatalog.mjs";

export default function SectionHub({ sectionId, children = null }) {
  const section = getSectionById(sectionId);
  if (!section) {
    return null;
  }

  const datasets = getDatasetsForSection(sectionId);

  return (
    <main className="shell">
      <section className="hero card sectionHero">
        <p className="eyebrow">Explora</p>
        <h1>{section.title}</h1>
        <p className="sub">{section.description}</p>
        <div className="chips">
          <span className="chip">Pregunta clave</span>
          <span className="chip">{section.question}</span>
        </div>
        <div className="chips">
          {section.chips.map((chip) => (
            <span key={`${section.id}-${chip}`} className="chip">
              {chip}
            </span>
          ))}
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Rutas recomendadas</h2>
        </div>
        <div className="grid">
          {section.tasks.map((task) => (
            <Link key={`${section.id}-${task.href}`} className="tile" href={withBasePath(task.href)}>
              <span className="tileTitle">{task.title}</span>
              <span className="tileNote">{task.note}</span>
              <span className="chip">{task.cta}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Herramientas disponibles</h2>
        </div>
        <div className="grid">
          {section.surfaces.map((surface) => (
            <Link key={`${section.id}-${surface.href}`} className="tile" href={withBasePath(surface.href)}>
              <span className="tileTitle">{surface.title}</span>
              <span className="tileNote">{surface.note}</span>
              <span className="chip">Abrir herramienta</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Archivos relacionados</h2>
        </div>
        <div className="grid">
          {datasets.map((dataset) => (
            <a key={`${section.id}-${dataset.id}`} className="tile" href={withBasePath(dataset.path)}>
              <span className="tileTitle">{dataset.label}</span>
              <span className="tileNote">{dataset.note}</span>
              <span className="chip">{dataset.confidence}</span>
            </a>
          ))}
        </div>
      </section>
      {children}
    </main>
  );
}
