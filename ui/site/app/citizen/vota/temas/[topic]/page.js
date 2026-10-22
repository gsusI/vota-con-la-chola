import { JsonLd, breadcrumbLd, pageMetadata } from "../../../../seo.js";
import { axisParties, directionText, formatCount, votesForAxis } from "../../voteAtlasModel.mjs";
import { A, AtlasVoteRow, VOTA_ROOT_CRUMBS, VotaLinks } from "../../VotaSeo";
import {
  VOTA_PATHS,
  joinLabels,
  loadVotaData,
  ogPath,
  partyPagePath,
  questionPagePath,
  questionParties,
  questionTitle,
  statementTopic,
  topicPagePath,
  topicSlug,
  topicsWithVotes,
} from "../../votaSeoData.mjs";

// One indexable page per topic: the key questions of the test on it and every axis of the vote atlas, party by party.
export const dynamicParams = false;
const LATEST_PER_AXIS = 5;

export function generateStaticParams() {
  return topicsWithVotes(loadVotaData().atlas).map((t) => ({ topic: topicSlug(t) }));
}

function topicFromSlug(slug) {
  return topicsWithVotes(loadVotaData().atlas).find((t) => topicSlug(t) === slug);
}

function topicAxes(atlas, topic) {
  return (atlas.axes || []).filter((a) => a.topic_id === topic.topic_id && a.votes > 0);
}

export async function generateMetadata({ params }) {
  const { topic: slug } = await params;
  const { atlas } = loadVotaData();
  const topic = topicFromSlug(slug);
  const votes = topicAxes(atlas, topic).reduce((n, a) => n + a.votes, 0);
  return pageMetadata({
    path: topicPagePath(topic),
    title: `${topic.label}: qué vota cada partido`,
    description: `${topic.label} en el Congreso (XV legislatura): hacia dónde empujaron PSOE, PP, Vox, Sumar y los demás partidos en ${formatCount(votes)} votaciones, cada una enlazada a la fuente oficial.`,
    image: { path: ogPath(`tema-${topic.topic_id}`), alt: `${topic.label}: qué vota cada partido en el Congreso` },
    keywords: [`${topic.label} votaciones Congreso`, `qué vota cada partido ${topic.label.toLowerCase()}`, "test político"],
  });
}

export default async function TopicPage({ params }) {
  const { topic: slug } = await params;
  const { snapshot, atlas } = loadVotaData();
  const topic = topicFromSlug(slug);
  const path = topicPagePath(topic);
  const crumbs = [...VOTA_ROOT_CRUMBS, { name: "Temas", path: VOTA_PATHS.topics }, { name: topic.label, path }];
  const axes = topicAxes(atlas, topic);
  const questions = (snapshot.statements || []).filter((st) => statementTopic(atlas, st)?.topic_id === topic.topic_id);
  const votesTotal = axes.reduce((n, a) => n + a.votes, 0);

  return (
    <main className="v-page vs-page">
      <header className="x-head__text">
        <p className="v-eyebrow">Congreso de los Diputados · XV legislatura</p>
        <h1 className="v-h1">{topic.label}: qué vota cada partido en el Congreso</h1>
        <p className="v-lead">
          {formatCount(votesTotal)} votaciones nominales del Pleno sobre {topic.label.toLowerCase()}, leídas y colocadas en{" "}
          {axes.length === 1 ? "un eje" : `${axes.length} ejes`}. Para cada partido, hacia dónde empujaron sus votos: hechos registrados, no
          promesas.
        </p>
        <p className="vs-cta">
          <A className="v-btn v-btn--primary" to={VOTA_PATHS.test}>
            Haz el test y mira con quién coincides
          </A>
          <A className="v-btn" to={`${VOTA_PATHS.topics}#tema=${encodeURIComponent(topic.topic_id)}`}>
            Atlas interactivo del tema
          </A>
        </p>
      </header>

      {questions.length ? (
        <section aria-labelledby="vs-tq" className="vs-section">
          <h2 className="v-h2" id="vs-tq">
            {questions.length === 1 ? "La pregunta del test" : `Las ${questions.length} preguntas del test`} sobre {topic.label.toLowerCase()}
          </h2>
          <ul className="vs-rows">
            {questions.map((st) => {
              const parties = questionParties(snapshot, st);
              const by = (pos) => joinLabels(parties.filter((p) => p.cell.position === pos).map((p) => p.label));
              return (
                <li className="vs-row vs-row--stack" key={st.statement_id}>
                  <A to={questionPagePath(st.statement_id)}>{questionTitle(st)}</A>
                  <span className="vs-row__quote">«{st.text}»</span>
                  <span className="v-muted">
                    {by("agree") ? `A favor: ${by("agree")}. ` : ""}
                    {by("disagree") ? `En contra: ${by("disagree")}. ` : ""}
                    {by("mixed") ? `Votos distintos: ${by("mixed")}. ` : ""}
                    {by("no_data") ? `Sin votos: ${by("no_data")}. ` : ""}
                    {formatCount(st.votes_total)} votaciones.
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      ) : (
        <p className="v-muted">El test no tiene una pregunta clave sobre este tema; sus votaciones cuentan en el atlas de abajo.</p>
      )}

      {axes.map((axis) => {
        const rows = axisParties(atlas, axis.axis_id);
        const latest = votesForAxis(atlas, axis.axis_id).slice(0, LATEST_PER_AXIS);
        return (
          <section aria-labelledby={`vs-ax-${axis.axis_id}`} className="vs-section" key={axis.axis_id}>
            <h2 className="v-h2" id={`vs-ax-${axis.axis_id}`}>
              {axis.label}
            </h2>
            <p>
              <strong>{axis.pos_short}:</strong> {axis.pos} <strong>{axis.neg_short}:</strong> {axis.neg}
            </p>
            <table className="vs-table">
              <caption className="v-muted">
                {formatCount(axis.votes)} votaciones de {formatCount(axis.initiatives)} iniciativas; de «{axis.pos_short}» a «{axis.neg_short}».
              </caption>
              <thead>
                <tr>
                  <th scope="col">Partido</th>
                  <th scope="col">Hacia dónde empujó</th>
                  <th scope="col">Votaciones</th>
                </tr>
              </thead>
              <tbody>
                {[...rows].reverse().map((p) => (
                  <tr key={p.party_id}>
                    <th scope="row">
                      <A to={partyPagePath(p.party_id)}>{p.label}</A>
                    </th>
                    <td>
                      {directionText(axis, p.score)} ({p.score > 0 ? "+" : ""}
                      {Math.round(p.score * 100)})
                    </td>
                    <td>{formatCount(p.votes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {latest.length ? (
              <>
                <h3 className="vs-theme__title">Últimas votaciones del eje</h3>
                <ol className="vs-votes">
                  {latest.map((v) => (
                    <AtlasVoteRow atlas={atlas} key={v.id} vote={v} />
                  ))}
                </ol>
                <p>
                  <A to={`${VOTA_PATHS.topics}#eje=${encodeURIComponent(axis.axis_id)}`}>Las {formatCount(axis.votes)} votaciones del eje →</A>
                </p>
              </>
            ) : null}
          </section>
        );
      })}

      <VotaLinks current={`t:${topic.topic_id}`} parties={snapshot.parties || []} topics={topicsWithVotes(atlas)} />
      <JsonLd data={breadcrumbLd(crumbs)} />
    </main>
  );
}
