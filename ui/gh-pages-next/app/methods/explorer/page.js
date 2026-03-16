import LegacyFrame from "../../legacy-frame";

export const metadata = {
  title: "Explorador SQL | Vota Con La Chola",
  description: "Consulta tablas, relaciones y registros cuando necesites auditar el detalle.",
};

export default function MethodsExplorerPage() {
  return <LegacyFrame legacyPath="/legacy/explorer/" title="Explorador SQL" />;
}
