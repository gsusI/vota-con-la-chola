import { resolveBasePath } from "../../../path-utils.mjs";
import VotingAidClient from "../VotingAidClient";
import { SITE_ORIGIN, loadVotingAidSnapshot } from "../votingAidHooks.mjs";
import { CURRENT_VERSION, versionById } from "../votingAidVersions.mjs";

// An earlier version of the test, kept online with its own questions and answers (see votingAidVersions.mjs).
const version = versionById("v1");
const url = `${SITE_ORIGIN}${resolveBasePath()}${version.path}`;

export const metadata = {
  title: "¿Con quién coincides? (versión anterior) | Vota Con La Chola",
  description: `Versión anterior del test: ${version.summary}. Tus respuestas siguen guardadas en este navegador.`,
  alternates: { canonical: `${SITE_ORIGIN}${resolveBasePath()}${CURRENT_VERSION.path}` },
  robots: { index: false, follow: true },
  openGraph: { title: "¿Con quién coincides? (versión anterior)", url, type: "website", siteName: "Vota Con La Chola", locale: "es_ES" },
};

export default function VotingAidV1Page() {
  return <VotingAidClient snapshot={loadVotingAidSnapshot(version.id)} versionId={version.id} />;
}
