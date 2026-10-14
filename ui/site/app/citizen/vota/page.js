import { resolveBasePath } from "../../path-utils.mjs";
import VotingAidClient from "./VotingAidClient";
import { SITE_ORIGIN, hookImagePath, loadVotingAidPageSnapshot } from "./votingAidHooks.mjs";

const title = "¿Con quién coincides? Generales | Vota Con La Chola";
const description =
  "Responde afirmaciones sobre lo que se votó en el Congreso y compara tus respuestas con cómo votó cada partido, con cada voto enlazado.";
const url = `${SITE_ORIGIN}${resolveBasePath()}/citizen/vota/`;
const image = { url: `${SITE_ORIGIN}${hookImagePath("inicio")}`, width: 1200, height: 630, alt: "¿Con quién coincides?" };

export const metadata = {
  title,
  description,
  alternates: { canonical: url },
  openGraph: { title: "¿Con quién coincides?", description, url, type: "website", siteName: "Vota Con La Chola", locale: "es_ES", images: [image] },
  twitter: { card: "summary_large_image", title: "¿Con quién coincides?", description, images: [image.url] },
};

export default function VotingAidPage() {
  return <VotingAidClient snapshot={loadVotingAidPageSnapshot()} />;
}
