import LegacyFrame from "../legacy-frame";

export const metadata = {
  title: "Explorador SQL | Vota Con La Chola",
  description: "Consulta tablas, registros y relaciones desde una vista técnica publicada.",
};

export default function ExplorerPage() {
  return <LegacyFrame legacyPath="/legacy/explorer/" title="Explorador SQL" />;
}
