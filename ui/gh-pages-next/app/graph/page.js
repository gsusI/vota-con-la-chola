import LegacyFrame from "../legacy-frame";

export const metadata = {
  title: "Graph | Vota Con La Chola",
  description: "Vista de grafo de relaciones institucionales con fallback de snapshot estático.",
};

export default function GraphPage() {
  return <LegacyFrame legacyPath="/legacy/graph/" title="Graph" />;
}
