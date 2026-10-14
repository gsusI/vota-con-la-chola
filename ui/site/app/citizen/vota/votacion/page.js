import { resolveBasePath } from "../../../path-utils.mjs";
import { SITE_ORIGIN } from "../votingAidHooks.mjs";
import VoteClient from "./VoteClient";

const title = "Votación del Congreso, diputado a diputado | Vota Con La Chola";
const description =
  "Qué se votó, el resultado y cómo votó cada diputado y cada partido en una votación del Pleno del Congreso, con enlace a la fuente oficial.";
const url = `${SITE_ORIGIN}${resolveBasePath()}/citizen/vota/votacion/`;

export const metadata = {
  title,
  description,
  alternates: { canonical: url },
  openGraph: { title: "Votación del Congreso, diputado a diputado", description, url, type: "website", siteName: "Vota Con La Chola", locale: "es_ES" },
};

export default function Page() {
  return <VoteClient />;
}
