import LegacyFrame from "../legacy-frame";

export const metadata = {
  title: "Explorer SQL | Vota Con La Chola",
  description: "Interfaz API/tabla con fallback estático de snapshot para navegación en GitHub Pages.",
};

export default function ExplorerPage() {
  return <LegacyFrame legacyPath="/legacy/graph/explorer.html" title="Explorer SQL" />;
}
