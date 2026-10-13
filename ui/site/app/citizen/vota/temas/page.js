import { resolveBasePath } from "../../../path-utils.mjs";
import { SITE_ORIGIN } from "../votingAidHooks.mjs";
import VoteAtlasClient from "./VoteAtlasClient";

const title = "¿Hacia dónde ha empujado cada partido? | Vota Con La Chola";
const description =
  "Todas las votaciones nominales del Congreso de la XV legislatura, colocadas por temas: qué votó cada partido y hacia dónde empujó, con cada voto enlazado a la fuente oficial.";
const url = `${SITE_ORIGIN}${resolveBasePath()}/citizen/vota/temas/`;

export const metadata = {
  title,
  description,
  alternates: { canonical: url },
  openGraph: { title: "¿Hacia dónde ha empujado cada partido?", description, url, type: "website", siteName: "Vota Con La Chola", locale: "es_ES" },
};

export default function VoteAtlasPage() {
  return <VoteAtlasClient />;
}
