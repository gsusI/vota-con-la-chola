import LegacyFrame from "../legacy-frame";

export const metadata = {
  title: "Votaciones | Vota Con La Chola",
  description: "Vistazo de votaciones y evidencia con fallback de snapshot estático.",
};

export default function ExplorerVotacionesPage() {
  return (
    <LegacyFrame legacyPath="/legacy/graph/explorer-votaciones.html" title="Votaciones" />
  );
}
