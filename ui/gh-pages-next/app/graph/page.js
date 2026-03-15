import LegacyFrame from "../legacy-frame";

export const metadata = {
  title: "Esquema y Relaciones | Vota Con La Chola",
  description: "Consulta el esquema publicado y las relaciones principales entre tablas y entidades.",
};

export default function GraphPage() {
  return <LegacyFrame legacyPath="/legacy/graph/" title="Esquema y relaciones" />;
}
