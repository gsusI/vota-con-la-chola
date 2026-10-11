import { readPublicJson } from "../../static-snapshot.mjs";
import VotingAidClient from "./VotingAidClient";

export const metadata = {
  title: "¿Con quién coincides? Generales | Vota Con La Chola",
  description:
    "Responde afirmaciones sobre lo que se votó en el Congreso y compara tus respuestas con cómo votó cada partido, con cada voto enlazado.",
};

export default function VotingAidPage() {
  const snapshot = readPublicJson("citizen/data/voting_aid_generales_v1.json", { meta: {}, parties: [], statements: [] });
  return <VotingAidClient snapshot={snapshot} />;
}
