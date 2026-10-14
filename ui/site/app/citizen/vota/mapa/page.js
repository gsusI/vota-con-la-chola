import { resolveBasePath } from "../../../path-utils.mjs";
import { SITE_ORIGIN } from "../votingAidHooks.mjs";
import MapClient from "./MapClient";

const title = "Dónde está cada partido, tema a tema | Vota Con La Chola";
const description =
  "Dónde está cada partido del Congreso según cómo votó en la XV legislatura: compáralos tema a tema, cruza dos temas en la brújula o juega a adivinar dónde está cada uno.";
const url = `${SITE_ORIGIN}${resolveBasePath()}/citizen/vota/mapa/`;

export const metadata = {
  title,
  description,
  alternates: { canonical: url },
  openGraph: { title: "Dónde está cada partido, tema a tema", description, url, type: "website", siteName: "Vota Con La Chola", locale: "es_ES" },
};

export default function MapPage() {
  return <MapClient />;
}
