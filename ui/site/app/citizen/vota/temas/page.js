import { JsonLd, breadcrumbLd, pageMetadata } from "../../../seo.js";
import { formatCount } from "../voteAtlasModel.mjs";
import { A, VOTA_ROOT_CRUMBS, VotaLinks } from "../VotaSeo";
import { VOTA_PATHS, loadVotaData, ogPath, topicPagePath, topicsWithVotes } from "../votaSeoData.mjs";
import VoteAtlasClient from "./VoteAtlasClient";

const title = "¿Hacia dónde ha empujado cada partido?";
const description =
  "Todas las votaciones nominales del Congreso de la XV legislatura, colocadas por temas: qué votó cada partido y hacia dónde empujó, con cada voto enlazado a la fuente oficial.";
const crumbs = [...VOTA_ROOT_CRUMBS, { name: "Temas", path: VOTA_PATHS.topics }];

export const metadata = pageMetadata({ path: VOTA_PATHS.topics, title, description, image: { path: ogPath("temas"), alt: title } });

export default function VoteAtlasPage() {
  const { snapshot, atlas } = loadVotaData();
  const topics = topicsWithVotes(atlas);
  return (
    <>
      <VoteAtlasClient />
      <section aria-labelledby="vs-tlist" className="v-page vs-page vs-page--below">
        <h2 className="v-h2" id="vs-tlist">
          Qué vota cada partido, tema a tema
        </h2>
        <ul className="vs-rows">
          {topics.map((t) => {
            const axes = (atlas.axes || []).filter((a) => a.topic_id === t.topic_id && a.votes > 0);
            return (
              <li className="vs-row vs-row--stack" key={t.topic_id}>
                <A to={topicPagePath(t)}>{t.label}: qué vota cada partido</A>
                <span className="v-muted">
                  {axes.map((a) => a.label).join(" · ")} · {formatCount(axes.reduce((n, a) => n + a.votes, 0))} votaciones
                </span>
              </li>
            );
          })}
        </ul>
        <VotaLinks parties={snapshot.parties || []} />
      </section>
      <JsonLd data={breadcrumbLd(crumbs)} />
    </>
  );
}
