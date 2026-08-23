import Link from "next/link";
import { withBasePath } from "../../siteCatalog.mjs";

const coverageArtifacts = [
  {
    title: "Obstrucción de datos públicos",
    href: "/obstruction-tracker/",
    note: "Registro por institución con señal técnica, evidencia y siguiente escalado.",
  },
  {
    title: "Fuentes y calidad",
    href: "/explorer-sources/",
    note: "Panel con estado de fuentes, cobertura y bloqueos abiertos.",
  },
  {
    title: "status.json",
    href: "/explorer-sources/data/status.json",
    note: "Archivo principal con el estado operativo y los indicadores del corte.",
  },
  {
    title: "ideal.json",
    href: "/explorer-sources/data/ideal.json",
    note: "Inventario objetivo de fuentes y alcance deseado.",
  },
  {
    title: "coverage-capacity.json",
    href: "/legacy/graph/data/coverage-capacity.json",
    note: "Cobertura frente al total esperado en cada dimensión.",
  },
  {
    title: "coverage-model.json",
    href: "/legacy/graph/data/coverage-model.json",
    note: "Definición de unidades y criterios usados para medir cobertura.",
  },
];

export const metadata = {
  title: "Cobertura | Vota Con La Chola",
  description: "Consulta cobertura real, huecos de información y trazabilidad de fuentes.",
};

export default function MethodsCoveragePage() {
  return (
    <main className="shell methods-coverage-page">
      <section className="hero card sectionHero methods-coverage-hero">
        <p className="eyebrow methods-coverage-hero__eyebrow">Datos y método</p>
        <h1 className="methods-coverage-hero__title">Cobertura y calidad de datos</h1>
        <p className="sub methods-coverage-hero__summary">
          Consulta qué datos existen, cuánto se ha publicado y qué bloqueos siguen abiertos.
        </p>
      </section>

      <section className="card block methods-coverage-artifacts">
        <div className="blockHead methods-coverage-artifacts__heading">
          <h2 className="methods-coverage-artifacts__title">Entradas recomendadas</h2>
        </div>
        <div className="grid methods-coverage-artifacts__grid">
          {coverageArtifacts.map((item) => {
            const Component = item.href.endsWith(".json") ? "a" : Link;
            const props = item.href.endsWith(".json")
              ? { href: withBasePath(item.href) }
              : { href: withBasePath(item.href) };
            return (
              <Component key={item.href} className="tile methods-coverage-artifact" {...props}>
                <span className="tileTitle methods-coverage-artifact__title">{item.title}</span>
                <span className="tileNote methods-coverage-artifact__note">{item.note}</span>
                <span className="chip methods-coverage-artifact__action">Abrir</span>
              </Component>
            );
          })}
        </div>
      </section>
    </main>
  );
}
