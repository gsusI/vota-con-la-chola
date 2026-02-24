import LegacyFrame from "../../legacy-frame";

export const metadata = {
  title: "Leaderboards | Vota Con La Chola",
  description: "Tablero de posiciones y señales de incertidumbre por partido.",
};

export default function CitizenLeaderboardPage() {
  return (
    <LegacyFrame legacyPath="/legacy/citizen/leaderboards.html" title="Leaderboards" />
  );
}
