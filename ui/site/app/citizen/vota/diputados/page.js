import { JsonLd, breadcrumbLd, pageMetadata } from "../../../seo.js";
import { xvPeople } from "../exploreModel.mjs";
import { formatCount } from "../voteAtlasModel.mjs";
import { A, VOTA_ROOT_CRUMBS } from "../VotaSeo";
import { VOTA_PATHS, loadVotaData, ogPath, partyPagePath } from "../votaSeoData.mjs";
import PeopleClient from "./PeopleClient";

const title = "Qué ha votado tu diputado/a";
const description =
  "Busca a cualquier diputado o diputada del Congreso (XV legislatura): hacia dónde ha empujado en cada tema, cuántas veces votó distinto de su partido y todas sus votaciones, enlazadas a la fuente oficial.";
const crumbs = [...VOTA_ROOT_CRUMBS, { name: "Diputados", path: VOTA_PATHS.people }];

export const metadata = pageMetadata({ path: VOTA_PATHS.people, title, description, image: { path: ogPath("diputados"), alt: title } });

// Crawlable list of every XV deputy by party, shown until the interactive search loads (then it takes over).
function DeputyIndex() {
  const { people } = loadVotaData();
  const list = xvPeople(people);
  const groups = [...(people.parties || []), { party_id: "", label: "Otros (Grupo Mixto o sin partido en el test)" }].map((p) => ({
    party: p,
    people: list
      .filter((x) => (p.party_id ? x.party_id === p.party_id : !(people.parties || []).some((q) => q.party_id === x.party_id)))
      .sort((a, b) => a.name.localeCompare(b.name, "es")),
  }));
  return (
    <section aria-labelledby="vs-dlist" className="vs-section">
      <h2 className="v-h2" id="vs-dlist">
        Los {formatCount(list.length)} diputados y diputadas de la XV legislatura
      </h2>
      <p className="v-muted">Incluye a quienes sustituyeron a otros durante la legislatura. Elige un nombre para ver todas sus votaciones.</p>
      {groups
        .filter((g) => g.people.length)
        .map((g) => (
          <div className="vs-theme" key={g.party.party_id || "otros"}>
            <h3 className="vs-theme__title">
              {g.party.party_id ? <A to={partyPagePath(g.party.party_id)}>{g.party.label}</A> : g.party.label} ({g.people.length})
            </h3>
            <ul className="vs-inline vs-inline--names">
              {g.people.map((x) => (
                <li key={x.id}>
                  <A to={`${VOTA_PATHS.people}#p=${encodeURIComponent(x.id)}`}>{x.name}</A>
                </li>
              ))}
            </ul>
          </div>
        ))}
    </section>
  );
}

export default function PeoplePage() {
  return (
    <>
      <PeopleClient
        fallback={
          <>
            <div className="x-head__text">
              <h1 className="v-h1">{title}</h1>
              <p className="v-lead">
                Cualquier diputado o diputada del Congreso desde octubre de 2022 (final de la XIV legislatura y toda la XV): cuántas veces votó
                distinto de su partido, hacia dónde empujó en cada tema y todas sus votaciones, enlazadas a la fuente oficial.
              </p>
            </div>
            <DeputyIndex />
          </>
        }
      />
      <JsonLd data={breadcrumbLd(crumbs)} />
    </>
  );
}
