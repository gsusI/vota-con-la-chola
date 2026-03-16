import { datasetCatalog, getSectionById, withBasePath } from "../../siteCatalog.mjs";

export const metadata = {
  title: "Archivos publicados | Vota Con La Chola",
  description: "Consulta los archivos publicados y la sección donde se usan.",
};

export default function MethodsDatasetsPage() {
  return (
    <main className="shell">
      <section className="hero card sectionHero">
        <p className="eyebrow">Datos y método</p>
        <h1>Archivos publicados</h1>
        <p className="sub">
          Consulta los archivos disponibles y la sección donde se usan para interpretar cada pantalla con contexto.
        </p>
        <div className="chips">
          <span className="chip">Archivos</span>
          <span className="chip">Sección</span>
          <span className="chip">Ruta</span>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Listado de archivos</h2>
        </div>
        <div className="grid">
          {datasetCatalog.map((dataset) => {
            const section = getSectionById(dataset.sectionId);
            return (
              <a key={dataset.id} className="tile" href={withBasePath(dataset.path)}>
                <span className="tileTitle">{dataset.label}</span>
                <span className="tileNote">{dataset.note}</span>
                <span className="tileNote">Sección: {section ? section.navLabel : dataset.sectionId}</span>
                <span className="chip">{dataset.path}</span>
              </a>
            );
          })}
        </div>
      </section>
    </main>
  );
}
