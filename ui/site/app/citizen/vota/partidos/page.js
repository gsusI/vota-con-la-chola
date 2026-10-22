import { JsonLd, breadcrumbLd, pageMetadata } from "../../../seo.js";
import { formatCount } from "../voteAtlasModel.mjs";
import { A, VOTA_ROOT_CRUMBS, VotaLinks } from "../VotaSeo";
import { VOTA_PATHS, loadVotaData, ogPath, partyPagePath, partySummary, testFacts, topicsWithVotes } from "../votaSeoData.mjs";
import PartyClient from "./PartyClient";

const title = "Cómo vota cada partido en el Congreso";
const facts = testFacts();
const description = `Los ${facts.parties} partidos del Congreso (XV legislatura): hacia dónde empujan sus votos en cada tema y con quién votan igual, con cada dato enlazado a las votaciones oficiales.`;
const crumbs = [...VOTA_ROOT_CRUMBS, { name: "Partidos", path: VOTA_PATHS.parties }];

export const metadata = pageMetadata({ path: VOTA_PATHS.parties, title, description, image: { path: ogPath("partidos"), alt: title } });

export default function Page() {
  const { snapshot, atlas } = loadVotaData();
  const rows = (snapshot.parties || []).map((p) => partySummary(p.party_id));
  return (
    <>
      <PartyClient
        fallback={
          <div className="x-head__text">
            <h1 className="v-h1">{title}</h1>
            <p className="v-lead">
              Cómo ha votado cada uno de los {facts.parties} partidos con diputados en el Congreso, tema a tema, y con quién vota igual.
            </p>
          </div>
        }
      />
      <section aria-labelledby="vs-psum" className="v-page vs-page vs-page--below">
        <h2 className="v-h2" id="vs-psum">
          Los {facts.parties} partidos, en las {facts.questions} preguntas del test
        </h2>
        <p className="v-muted">
          Cuántas afirmaciones del test apoyó cada partido con sus votos en el Pleno (XV legislatura) y con quién votó igual más a menudo.
        </p>
        <table className="vs-table">
          <thead>
            <tr>
              <th scope="col">Partido</th>
              <th scope="col">A favor</th>
              <th scope="col">En contra</th>
              <th scope="col">Votos distintos</th>
              <th scope="col">Vota más igual que</th>
              <th scope="col">Votaciones</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.party.party_id}>
                <th scope="row">
                  <A to={partyPagePath(r.party.party_id)}>Cómo vota {r.party.label}</A>
                </th>
                <td>{r.counts.agree}</td>
                <td>{r.counts.disagree}</td>
                <td>
                  {r.counts.mixed}
                  {r.counts.no_data ? ` (+${r.counts.no_data} sin datos)` : ""}
                </td>
                <td>{r.allies[0] ? `${r.allies[0].label} (${Math.round(r.allies[0].share * 100)} %)` : "sin datos"}</td>
                <td>{formatCount(r.atlasVotes)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <VotaLinks topics={topicsWithVotes(atlas)} />
      </section>
      <JsonLd data={breadcrumbLd(crumbs)} />
    </>
  );
}
