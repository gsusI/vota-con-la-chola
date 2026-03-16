import Link from "next/link";
import SectionHub from "../components/SectionHub";
import { withBasePath } from "../siteCatalog.mjs";

export const metadata = {
  title: "Datos y método | Vota Con La Chola",
  description: "Consulta cobertura, archivos publicados y herramientas de comprobación.",
};

export default function MethodsHubPage() {
  return (
    <SectionHub sectionId="methods">
      <section className="card block">
        <div className="blockHead">
          <h2>Accesos principales</h2>
          </div>
          <div className="grid">
            <Link className="tile" href={withBasePath("/methods/coverage/")}>
              <span className="tileTitle">Cobertura</span>
              <span className="tileNote">Consulta fuentes, cobertura, bloqueos y señales de disponibilidad.</span>
              <span className="chip">Abrir cobertura</span>
            </Link>
            <Link className="tile" href={withBasePath("/methods/datasets/")}>
              <span className="tileTitle">Archivos publicados</span>
              <span className="tileNote">Consulta qué archivos hay disponibles y dónde se usan.</span>
              <span className="chip">Abrir archivos</span>
            </Link>
            <Link className="tile" href={withBasePath("/methods/explorer/")}>
              <span className="tileTitle">Explorador SQL</span>
              <span className="tileNote">Consulta tablas, registros y evidencias al nivel más detallado.</span>
              <span className="chip">Abrir explorador</span>
            </Link>
            <Link className="tile" href={withBasePath("/methods/graph/")}>
              <span className="tileTitle">Esquema y relaciones</span>
              <span className="tileNote">Consulta la estructura general del esquema y sus relaciones.</span>
              <span className="chip">Abrir esquema</span>
            </Link>
          </div>
      </section>
    </SectionHub>
  );
}
