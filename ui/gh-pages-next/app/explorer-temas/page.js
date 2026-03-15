import LegacyFrame from "../legacy-frame";

export const metadata = {
  title: "Temas | Vota Con La Chola",
  description: "Vista de temas y evidencias con snapshot público y fallback de API local.",
};

export default function ExplorerTemasPage() {
  return <LegacyFrame legacyPath="/legacy/explorer-temas/" title="Temas" />;
}
