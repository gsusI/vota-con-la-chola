import { resolveBasePath } from "../../../path-utils.mjs";
import { SITE_ORIGIN } from "../votingAidHooks.mjs";
import PeopleClient from "./PeopleClient";

const title = "Qué ha votado tu diputado/a | Vota Con La Chola";
const description =
  "Busca a cualquier diputado o diputada del Congreso (XV legislatura): hacia dónde ha empujado en cada tema, cuántas veces votó distinto de su partido y todas sus votaciones, enlazadas a la fuente oficial.";
const url = `${SITE_ORIGIN}${resolveBasePath()}/citizen/vota/diputados/`;

export const metadata = {
  title,
  description,
  alternates: { canonical: url },
  openGraph: { title: "Qué ha votado tu diputado/a", description, url, type: "website", siteName: "Vota Con La Chola", locale: "es_ES" },
};

export default function PeoplePage() {
  return <PeopleClient />;
}
