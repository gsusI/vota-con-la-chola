import { readPublicJson } from "../../../static-snapshot.mjs";
import { StaticRouteHero } from "../../../static-route-components";
import { absoluteSiteUrl, withBasePath } from "../../../path-utils.mjs";
import { JsonLd, breadcrumbLd, pageMetadata } from "../../../seo";
import { DRAWS, SCENARIOS, SCENARIOS_PATH, SIM_PATH, scenarioPath, scenarioResult, simulatorHref } from "../scenarios.mjs";
import "../sistema.css";

export const metadata = pageMetadata({
  path: SCENARIOS_PATH,
  title: "Escenarios: pensiones, IVA, IRPF, alquiler y quién paga",
  description:
    "Qué pasa si se suben las pensiones, el IVA o el IRPF, se topa el alquiler o se construye vivienda pública: cuánto cuesta, a quién y con qué incertidumbre.",
  image: { path: "/visualizaciones/sistema/og/escenarios.png", alt: "Escenarios del simulador de pensiones, impuestos y vivienda" },
  keywords: ["simulador pensiones", "subir IVA", "bajar IRPF", "tope alquiler", "vivienda pública", "quién paga"],
});

export default function ScenariosIndex() {
  const model = readPublicJson("visualizaciones/data/sistema.json", null);
  if (!model) throw new Error("Missing visualizaciones/data/sistema.json");
  const groups = [...new Set(SCENARIOS.map((s) => s.group))];
  const crumbs = [
    { name: "Visualizaciones", path: "/visualizaciones/" },
    { name: "Simulador", path: SIM_PATH },
    { name: "Escenarios", path: SCENARIOS_PATH },
  ];
  const list = {
    "@type": "ItemList",
    itemListElement: SCENARIOS.map((sc, i) => ({ "@type": "ListItem", position: i + 1, name: sc.question, url: absoluteSiteUrl(scenarioPath(sc)) })),
  };
  return (
    <main className="shell vizArticle scn">
      <JsonLd data={[breadcrumbLd(crumbs), list]} />
      <nav className="scn__crumbs" aria-label="Ruta">
        <a href={withBasePath("/visualizaciones/")}>Visualizaciones</a> › <a href={withBasePath(SIM_PATH)}>Simulador</a> › <span aria-current="page">Escenarios</span>
      </nav>
      <StaticRouteHero
        eyebrow="Visualizaciones · simulador"
        title="Escenarios: qué pasa si se cambian las pensiones, los impuestos o la vivienda"
        summary={`${SCENARIOS.length} preguntas con su respuesta calculada por el simulador: el valor central, el rango de ${DRAWS} simulaciones, a quién le toca y de dónde sale cada número. Son escenarios de un modelo con supuestos visibles, no predicciones.`}
        actions={[{ href: SIM_PATH, label: "Ir al simulador" }]}
      />
      {groups.map((g) => (
        <section className="vizProse" key={g} aria-label={g}>
          <h2>{g}</h2>
          <ul className="scn__index">
            {SCENARIOS.filter((s) => s.group === g).map((sc) => {
              const r = scenarioResult(model, sc);
              return (
                <li key={sc.slug}>
                  <h3><a href={withBasePath(scenarioPath(sc))}>{sc.question}</a></h3>
                  <p>{r.lead}</p>
                  <p className="sim__muted">
                    <a href={withBasePath(simulatorHref(sc))}>Abrir en el simulador</a>
                  </p>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </main>
  );
}
