import LegacyFrame from "../legacy-frame";

export const metadata = {
  title: "Ciudadanía | Vota Con La Chola",
  description: "Interfaz de ciudadanía con snapshots públicos estáticos y estado preservado por querystring.",
};

export default function CitizenPage() {
  return <LegacyFrame legacyPath="/legacy/citizen/" title="Ciudadanía" />;
}
