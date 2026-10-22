import { JsonLd, breadcrumbLd, faqLd, pageMetadata, webApplicationLd } from "../../seo.js";
import VotingAidClient from "./VotingAidClient";
import { TestAbout, VOTA_ROOT_CRUMBS, testFaqs } from "./VotaSeo";
import { loadVotingAidPageSnapshot } from "./votingAidHooks.mjs";
import { VOTA_PATHS, loadVotaData, ogPath, testFacts, topicsWithVotes } from "./votaSeoData.mjs";

const facts = testFacts();
const title = "Test político: qué partido vota como tú";
const description = `Test de afinidad para las generales: responde ${facts.questions} preguntas y mira qué partidos votaron como tú en el Congreso, con cada voto enlazado.`;

export const metadata = pageMetadata({
  path: VOTA_PATHS.test,
  title,
  description,
  image: { path: ogPath("inicio"), alt: "¿Con quién coincides? Lo que votaron, no lo que dicen" },
  keywords: ["test político", "test de afinidad política", "a quién votar", "elecciones generales", "cómo vota cada partido", "Congreso de los Diputados"],
});

export default function VotingAidPage() {
  const { snapshot, atlas } = loadVotaData();
  return (
    <>
      <VotingAidClient snapshot={loadVotingAidPageSnapshot()} />
      <div className="v-page vs-page vs-page--below">
        <TestAbout atlas={atlas} snapshot={snapshot} topics={topicsWithVotes(atlas)} />
      </div>
      <JsonLd
        data={[
          webApplicationLd({
            path: VOTA_PATHS.test,
            name: "¿Con quién coincides? Test de afinidad política",
            description,
            image: ogPath("inicio"),
            featureList: [
              `${facts.questions} preguntas clave que resumen ${facts.votes} votaciones del Congreso`,
              `Compara con ${facts.parties} partidos: ${facts.partyLabels.join(", ")}`,
              "Cada postura enlazada a las votaciones oficiales",
              "Respuestas guardadas solo en tu navegador",
            ],
          }),
          faqLd(testFaqs(facts)),
          breadcrumbLd(VOTA_ROOT_CRUMBS),
        ]}
      />
    </>
  );
}
