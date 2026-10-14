import { resolveBasePath } from "../../../path-utils.mjs";
import { SITE_ORIGIN } from "../votingAidHooks.mjs";
import PartyClient from "./PartyClient";

const title = "Cómo vota cada partido en el Congreso | Vota Con La Chola";
const description =
  "Los 12 partidos del Congreso (XV legislatura): hacia dónde empujan sus votos en cada tema y con quién votan igual, con cada dato enlazado a las votaciones oficiales.";
const url = `${SITE_ORIGIN}${resolveBasePath()}/citizen/vota/partidos/`;

export const metadata = {
  title,
  description,
  alternates: { canonical: url },
  openGraph: { title: "Cómo vota cada partido en el Congreso", description, url, type: "website", siteName: "Vota Con La Chola", locale: "es_ES" },
};

export default function Page() {
  return <PartyClient />;
}
