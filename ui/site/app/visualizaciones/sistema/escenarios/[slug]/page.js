import { readPublicJson } from "../../../../static-snapshot.mjs";
import { pageMetadata } from "../../../../seo";
import { SCENARIOS, scenarioBySlug, scenarioPath, scenarioResult } from "../../scenarios.mjs";
import ScenarioView from "../ScenarioView";
import "../../sistema.css";

export const dynamicParams = false;

export function generateStaticParams() {
  return SCENARIOS.map((sc) => ({ slug: sc.slug }));
}

const loadModel = () => {
  const model = readPublicJson("visualizaciones/data/sistema.json", null);
  if (!model) throw new Error("Missing visualizaciones/data/sistema.json");
  return model;
};

export async function generateMetadata({ params }) {
  const { slug } = await params;
  const sc = scenarioBySlug(slug);
  const r = scenarioResult(loadModel(), sc);
  return pageMetadata({
    path: scenarioPath(sc),
    title: sc.title,
    description: r.lead,
    image: { path: `/visualizaciones/sistema/og/${sc.slug}.png`, alt: `${sc.question} ${r.badge}` },
    keywords: sc.keywords,
  });
}

export default async function ScenarioPage({ params }) {
  const { slug } = await params;
  return <ScenarioView model={loadModel()} sc={scenarioBySlug(slug)} />;
}
