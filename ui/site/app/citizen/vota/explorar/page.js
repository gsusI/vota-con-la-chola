import { JsonLd, breadcrumbLd, pageMetadata } from "../../../seo.js";
import { QuestionIndex, VOTA_ROOT_CRUMBS, VotaLinks } from "../VotaSeo";
import { VOTA_PATHS, loadVotaData, ogPath, topicsWithVotes } from "../votaSeoData.mjs";
import ExploreClient from "./ExploreClient";

const title = "Explora cómo vota el Congreso";
const description =
  "Busca partidos, diputados y votaciones del Congreso (XV legislatura) sin hacer el test: qué votó cada uno, con cada dato enlazado a la votación oficial.";
const crumbs = [...VOTA_ROOT_CRUMBS, { name: "Explorar", path: VOTA_PATHS.explore }];

export const metadata = pageMetadata({ path: VOTA_PATHS.explore, title, description, image: { path: ogPath("explorar"), alt: title } });

export default function Page() {
  const { snapshot, atlas } = loadVotaData();
  return (
    <>
      <ExploreClient />
      <section aria-labelledby="vs-xq" className="v-page vs-page vs-page--below">
        <h2 className="v-h2" id="vs-xq">
          Las preguntas del test, con lo que votó cada partido
        </h2>
        <QuestionIndex atlas={atlas} snapshot={snapshot} />
        <VotaLinks parties={snapshot.parties || []} topics={topicsWithVotes(atlas)} />
      </section>
      <JsonLd data={breadcrumbLd(crumbs)} />
    </>
  );
}
