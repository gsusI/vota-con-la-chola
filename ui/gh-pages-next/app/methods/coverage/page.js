import Link from "next/link";
import { withBasePath } from "../../siteCatalog.mjs";

const coverageArtifacts = [
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
    <main className="shell">
      <section className="hero card sectionHero">
        <p className="eyebrow">Datos y método</p>
        <h1>Cobertura y calidad de datos</h1>
        <p className="sub">
          Consulta qué datos existen, cuánto se ha publicado y qué bloqueos siguen abiertos.
        </p>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Entradas recomendadas</h2>
        </div>
        <div className="grid">
          {coverageArtifacts.map((item) => {
            const Component = item.href.endsWith(".json") ? "a" : Link;
            const props = item.href.endsWith(".json")
              ? { href: withBasePath(item.href) }
              : { href: withBasePath(item.href) };
            return (
              <Component key={item.href} className="tile" {...props}>
                <span className="tileTitle">{item.title}</span>
                <span className="tileNote">{item.note}</span>
                <span className="chip">Abrir</span>
              </Component>
            );
          })}
        </div>
      </section>
    </main>
  );
}
