import { resolveBasePath } from "../../../path-utils.mjs";
import { SITE_ORIGIN } from "../votingAidHooks.mjs";
import ExploreClient from "./ExploreClient";

const title = "Explora cómo vota el Congreso | Vota Con La Chola";
const description =
  "Busca partidos, diputados y votaciones del Congreso (XV legislatura) sin hacer el test: qué votó cada uno, con cada dato enlazado a la votación oficial.";
const url = `${SITE_ORIGIN}${resolveBasePath()}/citizen/vota/explorar/`;

export const metadata = {
  title,
  description,
  alternates: { canonical: url },
  openGraph: { title: "Explora cómo vota el Congreso", description, url, type: "website", siteName: "Vota Con La Chola", locale: "es_ES" },
};

export default function Page() {
  return <ExploreClient />;
}
