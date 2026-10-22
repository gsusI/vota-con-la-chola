import { JsonLd, breadcrumbLd, pageMetadata } from "../../../seo.js";
import { A, AtlasVoteRow, VOTA_ROOT_CRUMBS } from "../VotaSeo";
import { VOTA_PATHS, latestAtlasVotes, loadVotaData, ogPath } from "../votaSeoData.mjs";
import VoteClient from "./VoteClient";

const title = "Votación del Congreso, diputado a diputado";
const description =
  "Qué se votó, el resultado y cómo votó cada diputado y cada partido en una votación del Pleno del Congreso, con enlace a la fuente oficial.";
const crumbs = [...VOTA_ROOT_CRUMBS, { name: "Votaciones", path: VOTA_PATHS.vote }];
const LATEST = 20;

export const metadata = pageMetadata({ path: VOTA_PATHS.vote, title, description, image: { path: ogPath("votacion"), alt: title } });

export default function Page() {
  const { atlas } = loadVotaData();
  return (
    <>
      <VoteClient
        fallback={
          <>
            <div className="x-head__text">
              <h1 className="v-h1">{title}</h1>
              <p className="v-lead">
                Cada votación nominal del Pleno: qué significaba votar «sí», el resultado y el voto de cada partido y de cada diputado. Búscalas
                en <A to={VOTA_PATHS.explore}>Explorar</A> o recórrelas por <A to={VOTA_PATHS.topics}>temas</A>.
              </p>
            </div>
            <section aria-labelledby="vs-latest" className="vs-section">
              <h2 className="v-h2" id="vs-latest">
                Las {LATEST} últimas votaciones del Congreso
              </h2>
              <ol className="vs-votes">
                {latestAtlasVotes(atlas, LATEST).map((v) => (
                  <AtlasVoteRow atlas={atlas} key={v.id} vote={v} />
                ))}
              </ol>
            </section>
          </>
        }
      />
      <JsonLd data={breadcrumbLd(crumbs)} />
    </>
  );
}
