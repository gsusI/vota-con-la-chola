import LegacyFrame from "../legacy-frame";

export const metadata = {
  title: "Fuentes | Vota Con La Chola",
  description: "Seguimiento de fuentes y cobertura de adquisición para la exploración política.",
};

export default function ExplorerSourcesPage() {
  return <LegacyFrame legacyPath="/legacy/graph/explorer-sources.html" title="Fuentes" />;
}
