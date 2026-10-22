import { JsonLd, breadcrumbLd, pageMetadata } from "../../../../seo.js";
import { formatCount, formatDate } from "../../voteAtlasModel.mjs";
import { A, PositionTag, VOTA_ROOT_CRUMBS, VotaLinks, VoteRow } from "../../VotaSeo";
import {
  VOTA_PATHS,
  loadVotaData,
  ogPath,
  partyPagePath,
  partySlug,
  partySummary,
  questionPagePath,
  questionTitle,
  statementTopic,
  testFacts,
  topicPagePath,
  topicsWithVotes,
} from "../../votaSeoData.mjs";

// One indexable page per party: how it voted on each key question of the test, who it votes with and its closest votes.
export const dynamicParams = false;

export function generateStaticParams() {
  return (loadVotaData().snapshot.parties || []).map((p) => ({ party: partySlug(p.party_id) }));
}

function partyFromSlug(slug) {
  return (loadVotaData().snapshot.parties || []).find((p) => partySlug(p.party_id) === slug);
}

export async function generateMetadata({ params }) {
  const { party: slug } = await params;
  const party = partyFromSlug(slug);
  const facts = testFacts();
  return pageMetadata({
    path: partyPagePath(party.party_id),
    title: `Cómo vota ${party.label} en el Congreso`,
    description: `Qué ha votado ${party.label} en la XV legislatura, tema a tema: su postura en las ${facts.questions} preguntas del test, con quién vota igual y cada votación enlazada a la fuente oficial.`,
    image: { path: ogPath(`partido-${party.party_id}`), alt: `Cómo vota ${party.label} en el Congreso` },
    keywords: [`cómo vota ${party.label}`, `qué vota ${party.label}`, `${party.label} Congreso votaciones`, "test político"],
  });
}

const pct = (share) => `${Math.round(share * 100)} %`;

export default async function PartyPage({ params }) {
  const { party: slug } = await params;
  const { snapshot, atlas } = loadVotaData();
  const party = partyFromSlug(slug);
  const s = partySummary(party.party_id);
  const facts = testFacts(snapshot);
  const path = partyPagePath(party.party_id);
  const crumbs = [...VOTA_ROOT_CRUMBS, { name: "Partidos", path: VOTA_PATHS.parties }, { name: party.label, path }];
  const closest = s.allies.slice(0, 3);
  const farthest = s.allies.slice(-2).reverse();

  return (
    <main className="v-page vs-page">
      <header className="x-head__text">
        <p className="v-eyebrow">Congreso de los Diputados · XV legislatura</p>
        <h1 className="v-h1">Cómo vota {party.label} en el Congreso</h1>
        <p className="v-lead">
          Lo que votó {party.label} en el Pleno entre el {formatDate(facts.firstDate)} y el {formatDate(facts.lastDate)}, resumido en las{" "}
          {facts.questions} preguntas del test «¿Con quién coincides?»: hechos registrados, no su programa. De esas preguntas, vota a favor
          de la afirmación en {s.counts.agree}, en contra en {s.counts.disagree} y con votos distintos en {s.counts.mixed}
          {s.counts.no_data ? `; en ${s.counts.no_data} no tiene votos` : ""}.
        </p>
        <p className="vs-cta">
          <A className="v-btn v-btn--primary" to={VOTA_PATHS.test}>
            Haz el test y mira cuánto coincides con {party.label}
          </A>
          <A className="v-btn" to={`${VOTA_PATHS.parties}#p=${encodeURIComponent(party.party_id)}`}>
            Todos sus ejes, interactivo
          </A>
        </p>
      </header>

      <ul className="vs-facts">
        <li>
          <strong>{formatCount(s.atlasVotes)}</strong> votaciones del Pleno con voto de {party.label} en la XV legislatura
        </li>
        <li>
          <strong>{formatCount(s.deputies)}</strong> personas han sido diputadas de {party.label} en la legislatura (con sustituciones)
        </li>
        {closest[0] ? (
          <li>
            Vota igual que <strong>{closest[0].label}</strong> en el {pct(closest[0].share)} de las votaciones
          </li>
        ) : null}
      </ul>

      <section aria-labelledby="vs-themes" className="vs-section">
        <h2 className="v-h2" id="vs-themes">
          Qué vota {party.label}, tema a tema
        </h2>
        <p className="v-muted">
          «A favor» o «En contra» de cada afirmación del test; el porcentaje es cuánto de su voto empujó en ese sentido en todas las
          votaciones de la pregunta (100 % = siempre a favor, 0 % = siempre en contra).
        </p>
        {s.themes.map(({ theme, rows }) => {
          const topic = statementTopic(atlas, rows[0].statement);
          return (
            <div className="vs-theme" key={theme}>
              <h3 className="vs-theme__title">{topic ? <A to={topicPagePath(topic)}>{theme}</A> : theme}</h3>
              <ul className="vs-rows">
                {rows.map(({ statement, cell }) => (
                  <li className="vs-row" key={statement.statement_id}>
                    <span className="vs-row__text">
                      <A to={questionPagePath(statement.statement_id)}>{questionTitle(statement)}</A>
                      <span className="vs-row__quote">«{statement.text}»</span>
                    </span>
                    <span className="vs-row__stat">
                      <PositionTag cell={cell} />
                      <span className="v-muted">
                        {cell.votes ? `${formatCount(cell.votes)} de ${formatCount(cell.total)} votaciones` : "sin votos registrados"}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </section>

      <section aria-labelledby="vs-allies" className="vs-section">
        <h2 className="v-h2" id="vs-allies">
          Con quién vota igual {party.label}
        </h2>
        <p>
          En las votaciones de la XV legislatura en que ambos votaron, {party.label} votó lo mismo que {closest.map((a) => `${a.label} (${pct(a.share)})`).join(", ")}{" "}
          y lo menos parecido a {farthest.map((a) => `${a.label} (${pct(a.share)})`).join(" y ")}. Se compara el voto de la mayoría de cada grupo.
        </p>
        <table className="vs-table">
          <thead>
            <tr>
              <th scope="col">Partido</th>
              <th scope="col">Votó igual</th>
              <th scope="col">Votaciones comparadas</th>
            </tr>
          </thead>
          <tbody>
            {s.allies.map((a) => (
              <tr key={a.party_id}>
                <th scope="row">
                  <A to={partyPagePath(a.party_id)}>{a.label}</A>
                </th>
                <td>{a.share === null ? "sin datos" : pct(a.share)}</td>
                <td>{formatCount(a.n)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {s.closeVotes.length ? (
        <section aria-labelledby="vs-close" className="vs-section">
          <h2 className="v-h2" id="vs-close">
            Votaciones ajustadas: qué votó {party.label}
          </h2>
          <p className="v-muted">Votaciones del test que se decidieron por 5 votos o menos, las más ajustadas primero.</p>
          <ol className="vs-votes">
            {s.closeVotes.map((v) => (
              <VoteRow atlas={atlas} highlight={party.party_id} key={v.id} vote={v} />
            ))}
          </ol>
        </section>
      ) : null}

      <p className="vs-cta">
        <A to={`${VOTA_PATHS.people}#partido=${encodeURIComponent(party.party_id)}`}>Sus diputados y diputadas, uno a uno</A>
        {" · "}
        <A to={`${VOTA_PATHS.map}#vista=mapa&p=${encodeURIComponent(party.party_id)}`}>{party.label} en el mapa de partidos</A>
      </p>
      <VotaLinks current={`p:${party.party_id}`} parties={snapshot.parties || []} topics={topicsWithVotes(atlas)} />
      <JsonLd data={breadcrumbLd(crumbs)} />
    </main>
  );
}
