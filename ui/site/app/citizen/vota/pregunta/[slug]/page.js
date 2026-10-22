import { JsonLd, breadcrumbLd, pageMetadata } from "../../../../seo.js";
import { formatCount, formatDate } from "../../voteAtlasModel.mjs";
import { A, PositionTag, VOTA_ROOT_CRUMBS, VotaLinks, VoteRow } from "../../VotaSeo";
import {
  VOTA_PATHS,
  joinLabels,
  loadVotaData,
  ogPath,
  partyPagePath,
  questionPagePath,
  questionParties,
  questionSlug,
  questionTitle,
  statementTopic,
  statementVotes,
  topicPagePath,
  topicsWithVotes,
} from "../../votaSeoData.mjs";

// One indexable page per key question of the current test: the statement, every vote behind it and how each party voted.
// The game itself stays at /citizen/vota/t/<id>/ (shareable, opens the test on that question).
export const dynamicParams = false;

export function generateStaticParams() {
  return (loadVotaData().snapshot.statements || []).map((st) => ({ slug: questionSlug(st.statement_id) }));
}

function statementFromSlug(slug) {
  return (loadVotaData().snapshot.statements || []).find((st) => questionSlug(st.statement_id) === slug);
}

export async function generateMetadata({ params }) {
  const { slug } = await params;
  const st = statementFromSlug(slug);
  return pageMetadata({
    path: questionPagePath(st.statement_id),
    title: `${questionTitle(st)}: qué votó cada partido`,
    description: `Las ${formatCount(st.votes_total)} votaciones del Congreso (XV legislatura) sobre este tema: qué votó cada partido, el resultado y el enlace oficial. ¿Coincides? Haz el test.`,
    image: { path: ogPath(st.statement_id), alt: st.text },
    keywords: [questionTitle(st), `${st.theme} Congreso votaciones`, "qué votó cada partido", "test político"],
  });
}

const POSITION_GROUPS = [
  ["agree", "A favor de la afirmación"],
  ["disagree", "En contra"],
  ["mixed", "Votos distintos"],
  ["no_data", "Sin votos registrados"],
];

export default async function QuestionPage({ params }) {
  const { slug } = await params;
  const { snapshot, atlas } = loadVotaData();
  const st = statementFromSlug(slug);
  const topic = statementTopic(atlas, st);
  const path = questionPagePath(st.statement_id);
  const title = questionTitle(st);
  const crumbs = [...VOTA_ROOT_CRUMBS, ...(topic ? [{ name: topic.label, path: topicPagePath(topic) }] : []), { name: title, path }];
  const parties = questionParties(snapshot, st);
  const votes = statementVotes(snapshot, st);
  const dates = votes.map((v) => v.date).filter(Boolean).sort();
  const approved = votes.filter((v) => v.approved).length;
  const siblings = (snapshot.statements || []).filter((o) => o.theme === st.theme && o.statement_id !== st.statement_id);

  return (
    <main className="v-page vs-page">
      <header className="x-head__text">
        <p className="v-eyebrow">{st.theme} · Congreso de los Diputados · XV legislatura</p>
        <h1 className="v-h1">{title}: qué votó cada partido</h1>
        <blockquote className="vs-quote">
          <p>«{st.text}»</p>
          <footer>Pregunta del test «¿Con quién coincides?». {st.context}</footer>
        </blockquote>
        <p className="vs-cta">
          <A className="v-btn v-btn--primary" to={`/citizen/vota/t/${st.statement_id}/`}>
            ¿De acuerdo? Responde antes de mirar
          </A>
          <A className="v-btn" to={`${VOTA_PATHS.topics}#eje=${encodeURIComponent(st.axis_id)}`}>
            Ver el eje en el atlas
          </A>
        </p>
      </header>

      <section aria-labelledby="vs-parties" className="vs-section">
        <h2 className="v-h2" id="vs-parties">
          Cómo votó cada partido
        </h2>
        <p>
          La respaldan {formatCount(st.votes_total)} votaciones nominales del Pleno de {formatCount(st.initiatives_total)} iniciativas
          {dates.length ? `, entre el ${formatDate(dates[0])} y el ${formatDate(dates[dates.length - 1])}` : ""}; se aprobaron {formatCount(approved)}.{" "}
          {POSITION_GROUPS.map(([pos, label]) => {
            const names = parties.filter((p) => p.cell.position === pos).map((p) => p.label);
            return names.length ? `${label}: ${joinLabels(names)}. ` : "";
          }).join("")}
        </p>
        <table className="vs-table">
          <thead>
            <tr>
              <th scope="col">Partido</th>
              <th scope="col">Postura</th>
              <th scope="col">Votaciones con su voto</th>
            </tr>
          </thead>
          <tbody>
            {parties.map((p) => (
              <tr key={p.party_id}>
                <th scope="row">
                  <A to={partyPagePath(p.party_id)}>{p.label}</A>
                </th>
                <td>
                  <PositionTag cell={p.cell} />
                </td>
                <td>{p.cell.votes ? `${formatCount(p.cell.votes)} de ${formatCount(p.cell.total)}` : "ninguna"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="v-muted">
          El porcentaje es cuánto empujaron los votos de los diputados de cada partido en el sentido de la afirmación (100 % = siempre a
          favor). «A favor» desde el 67 %, «En contra» hasta el 33 %; entre medias, votos distintos. <A to={VOTA_PATHS.method}>Cómo se calcula</A>.
        </p>
      </section>

      <section aria-labelledby="vs-votes" className="vs-section">
        <h2 className="v-h2" id="vs-votes">
          Qué se votó: las {formatCount(votes.length)} votaciones
        </h2>
        <p className="v-muted">De la más reciente a la más antigua. Cada una enlaza al registro oficial del Congreso y, cuando existe, al texto votado.</p>
        <ol className="vs-votes">
          {votes.map((v) => (
            <VoteRow atlas={atlas} key={v.id} vote={v} />
          ))}
        </ol>
      </section>

      {siblings.length ? (
        <section aria-labelledby="vs-more" className="vs-section">
          <h2 className="v-h2" id="vs-more">
            Más preguntas sobre {st.theme.toLowerCase()}
          </h2>
          <ul className="vs-list">
            {siblings.map((o) => (
              <li key={o.statement_id}>
                <A to={questionPagePath(o.statement_id)}>{questionTitle(o)}</A>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <VotaLinks current={topic ? `t:${topic.topic_id}` : ""} parties={snapshot.parties || []} topics={topicsWithVotes(atlas)} />
      <JsonLd data={breadcrumbLd(crumbs)} />
    </main>
  );
}
