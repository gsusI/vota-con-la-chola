// Server-rendered pieces of the indexable voting-aid pages (no client JS): position tags, vote rows,
// the crawlable summaries of the client-only pages and the «Cómo funciona» + FAQ block of the test.
import { withBasePath } from "../../path-utils.mjs";
import "./explore.css";
import { formatCount, formatDate, officialVoteUrl, partyChoices } from "./voteAtlasModel.mjs";
import {
  VOTA_PATHS,
  codeLabel,
  joinLabels,
  kindLabel,
  partyPagePath,
  questionPagePath,
  questionTitle,
  statementTopic,
  testFacts,
  topicPagePath,
} from "./votaSeoData.mjs";

export const A = ({ to, children, ...rest }) => (
  <a href={withBasePath(to)} {...rest}>
    {children}
  </a>
);

// Root of the breadcrumb trail (breadcrumbLd) of every voting-aid page.
export const VOTA_ROOT_CRUMBS = [
  { name: "Inicio", path: "/" },
  { name: "¿Con quién coincides?", path: VOTA_PATHS.test },
];

/** Position of a party on a key question: «A favor · 83 %» with the share of its push towards the statement. */
export function PositionTag({ cell }) {
  return (
    <span
      className={`votingAidBadge votingAidBadge--${cell.position}`}
      title={cell.pct === null ? undefined : `En el ${cell.pct} % de sus votos empujó en el sentido de la afirmación`}
    >
      {cell.label}
      {cell.pct === null ? "" : ` · ${cell.pct} %`}
    </span>
  );
}


function resultText(vote) {
  const { yes, no, abstain } = vote.totals;
  const verdict = vote.approved ? "Aprobada" : yes === no ? "Rechazada por empate" : "Rechazada";
  return `${verdict}: ${yes} sí, ${no} no, ${abstain} abstenciones`;
}

/** One vote of a key question: what «Sí» meant, the result, each party's vote and the official links. */
export function VoteRow({ vote, atlas, highlight = null }) {
  return (
    <li className="vs-vote">
      <p className="vs-vote__title">{vote.title}</p>
      <p className="vs-vote__meta">
        {formatDate(vote.date)} · {kindLabel(atlas, vote.kind)}
        {vote.subgroup ? ` · ${vote.subgroup}` : ""} · {resultText(vote)} · votar «{vote.agreeVote}» = de acuerdo con la afirmación
      </p>
      <ul aria-label="Voto de cada partido" className="vs-codes">
        {vote.parties.map((p) => (
          <li className={`vs-code vs-code--${p.stance}${highlight === p.partyId ? " is-own" : ""}`} key={p.partyId}>
            {p.label}: {codeLabel(p.code)}
          </li>
        ))}
      </ul>
      <p className="vs-vote__links">
        <a href={vote.sourceUrl} rel="noopener">
          Votación oficial (Congreso)
        </a>
        {vote.textUrl ? (
          <>
            {" · "}
            <a href={vote.textUrl} rel="noopener">
              Texto votado (BOCG)
            </a>
          </>
        ) : null}
        {" · "}
        <A to={`${VOTA_PATHS.vote}#v=${encodeURIComponent(vote.id)}`}>Diputado a diputado</A>
      </p>
    </li>
  );
}

const CODE_CLASS = { S: "yes", N: "no", A: "abstain", "-": "absent" };

/** One atlas vote (any vote of the legislature): what «Sí» meant, the result and each party's majority vote. */
export function AtlasVoteRow({ vote, atlas }) {
  const [yes = 0, no = 0, abstain = 0] = Array.isArray(vote.totals) ? vote.totals : [];
  const url = officialVoteUrl(vote.path);
  return (
    <li className="vs-vote">
      <p className="vs-vote__title">{vote.summary_yes || atlas.titles?.[vote.t] || "Votación"}</p>
      <p className="vs-vote__meta">
        {formatDate(vote.date)} · {kindLabel(atlas, vote.kind)}
        {vote.subgroup ? ` · ${vote.subgroup}` : ""} · {resultText({ approved: vote.approved, totals: { yes, no, abstain } })}
      </p>
      <ul aria-label="Voto de cada partido" className="vs-codes">
        {partyChoices(atlas, vote).map((p) => (
          <li className={`vs-code vs-code--${CODE_CLASS[p.code] || "no_data"}`} key={p.party_id}>
            {p.label}: {codeLabel(p.code)}
          </li>
        ))}
      </ul>
      <p className="vs-vote__links">
        {url ? (
          <>
            <a href={url} rel="noopener">
              Votación oficial (Congreso)
            </a>
            {" · "}
          </>
        ) : null}
        <A to={`${VOTA_PATHS.vote}#v=${encodeURIComponent(vote.id)}`}>Diputado a diputado</A>
      </p>
    </li>
  );
}

/** Links to the other indexable surfaces of the section (internal linking between them). */
export function VotaLinks({ parties = [], topics = [], current = "" }) {
  return (
    <nav aria-label="Más sobre cómo vota el Congreso" className="vs-links">
      {parties.length ? (
        <div>
          <h2 className="vs-links__title">Cómo vota cada partido</h2>
          <ul className="vs-inline">
            {parties.map((p) => (
              <li key={p.party_id}>{current === `p:${p.party_id}` ? <strong>{p.label}</strong> : <A to={partyPagePath(p.party_id)}>{p.label}</A>}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {topics.length ? (
        <div>
          <h2 className="vs-links__title">Qué se votó, por temas</h2>
          <ul className="vs-inline">
            {topics.map((t) => (
              <li key={t.topic_id}>{current === `t:${t.topic_id}` ? <strong>{t.label}</strong> : <A to={topicPagePath(t)}>{t.label}</A>}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <p className="vs-inline vs-inline--tools">
        <A to={VOTA_PATHS.test}>Hacer el test</A>
        <A to={VOTA_PATHS.people}>Qué ha votado tu diputado/a</A>
        <A to={VOTA_PATHS.map}>Mapa de partidos</A>
        <A to={VOTA_PATHS.explore}>Buscar votaciones</A>
        <A to={VOTA_PATHS.method}>Metodología</A>
      </p>
    </nav>
  );
}

/** Key questions grouped by theme, each linked to its page. */
export function QuestionIndex({ snapshot, atlas, headingLevel = 3 }) {
  const H = `h${headingLevel}`;
  const groups = new Map();
  for (const st of snapshot.statements || []) {
    if (!groups.has(st.theme)) groups.set(st.theme, []);
    groups.get(st.theme).push(st);
  }
  return (
    <div className="vs-qindex">
      {[...groups.entries()].map(([theme, list]) => {
        const topic = statementTopic(atlas, list[0]);
        return (
          <section key={theme}>
            <H className="vs-qindex__theme">{topic ? <A to={topicPagePath(topic)}>{theme}</A> : theme}</H>
            <ul>
              {list.map((st) => (
                <li key={st.statement_id}>
                  <A to={questionPagePath(st.statement_id)}>{questionTitle(st)}</A>
                  <span className="v-muted"> · {formatCount(st.votes_total)} votaciones</span>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// The test's own crawlable content: «Cómo funciona» + FAQ. Answers are plain text so faqLd can reuse them verbatim.

export function testFaqs(facts = testFacts()) {
  const span = `entre el ${formatDate(facts.firstDate)} y el ${formatDate(facts.lastDate)}`;
  return [
    {
      q: "¿A quién votar en las elecciones generales?",
      a: `Este test no te dice a quién votar: te enseña qué partidos votaron como tú habrías votado. Compara tus respuestas a ${facts.questions} preguntas con lo que votaron en el Pleno del Congreso los ${facts.parties} partidos con diputados (${joinLabels(facts.partyLabels)}) en la XV legislatura, ${span}. Lo que prometan para las próximas generales no está en el cálculo; lo que votaron, sí, y cada voto se puede comprobar en la fuente oficial.`,
    },
    {
      q: "¿Es un test político fiable?",
      a: `Las posturas no salen de opiniones ni de programas, sino de ${formatCount(facts.votes)} votaciones nominales del Congreso, cada una enlazada a su registro oficial. Qué votación va a cada pregunta lo decidió una IA leyendo el texto oficial sin ver cómo votó nadie${facts.agreement ? ` (acuerdo con un segundo clasificador independiente: ${facts.agreement})` : ""}. Falta la revisión humana, así que úsalo para explorar, no como veredicto: la metodología completa, con los prompts, es pública.`,
    },
    {
      q: "¿Cómo se calcula la coincidencia?",
      a: "Cada respuesta vale +1 (de acuerdo), 0 (neutral) o −1 (en desacuerdo). La postura de un partido es la media de cómo votaron sus diputados en todas las votaciones de esa pregunta, de −1 (siempre en contra) a +1 (siempre a favor). La coincidencia en cada pregunta es 1 − |tu respuesta − partido| / 2, y el resultado es la media de todas las que respondes; las que marcas como «me importa mucho» cuentan doble. Las preguntas saltadas y las que no tienen votos de un partido no cuentan: nunca se rellenan huecos.",
    },
    {
      q: "¿Guardáis mis respuestas?",
      a: "No. Tus respuestas se guardan solo en tu navegador (almacenamiento local) y no se envían a ningún servidor. Si decides compartir tus resultados, el enlace las lleva codificadas detrás de «#», una parte de la dirección que el navegador no envía al servidor.",
    },
    {
      q: "¿En qué se diferencia de otros test de afinidad política?",
      a: "La mayoría de test de afinidad comparan tus respuestas con los programas electorales o con lo que dicen los partidos. Este las compara con lo que votaron en el Congreso: hechos registrados, no promesas. Además, cada postura enlaza a las votaciones concretas que la sostienen, puedes partir una pregunta en sus votaciones una a una y ver qué votó cada diputado.",
    },
  ];
}

export function TestAbout({ snapshot, atlas, topics }) {
  const facts = testFacts(snapshot);
  const faqs = testFaqs(facts);
  return (
    <div className="vs-about">
      <section aria-labelledby="vs-how" className="vs-section">
        <h2 className="v-h2" id="vs-how">
          Cómo funciona este test político
        </h2>
        <p>
          «¿Con quién coincides?» es un test de afinidad política para las elecciones generales que no te compara con promesas, sino con
          votos. Respondes {facts.questions} preguntas clave sobre {facts.themes.length} temas (vivienda, impuestos, inmigración, modelo
          territorial…) y ves con qué partidos coincides según lo que votaron sus diputados en el Pleno del Congreso durante la XV
          legislatura.
        </p>
        <ul className="vs-facts">
          <li>
            <strong>{facts.questions}</strong> preguntas clave
          </li>
          <li>
            <strong>{formatCount(facts.votes)}</strong> votaciones nominales{facts.initiatives ? ` de ${formatCount(facts.initiatives)} iniciativas` : ""}
          </li>
          <li>
            <strong>{facts.parties}</strong> partidos comparados
          </li>
          <li>
            Del <strong>{formatDate(facts.firstDate)}</strong> al <strong>{formatDate(facts.lastDate)}</strong>
          </li>
        </ul>
        <p>
          Cada pregunta resume todas las votaciones de un tema (leyes, decretos ley, mociones, proposiciones no de ley y enmiendas), y
          la postura de cada partido es hacia dónde empujaron sus votos en todas ellas. Tras responder ves cómo votó cada partido, quién votó como tú y quién lo
          contrario, y puedes partir la pregunta en sus votaciones concretas. Al terminar las preguntas clave el test sigue con votaciones
          reales una a una, sin límite. Partidos comparados: {joinLabels(facts.partyLabels)}.
        </p>
        <p>
          Sin hacer el test también puedes ver <A to={VOTA_PATHS.parties}>cómo vota cada partido</A>,{" "}
          <A to={VOTA_PATHS.people}>qué ha votado tu diputado o diputada</A>, <A to={VOTA_PATHS.topics}>todas las votaciones por temas</A>{" "}
          y el <A to={VOTA_PATHS.map}>mapa de dónde está cada partido</A>. Cómo se hizo, con fuentes, modelos de IA y prompts:{" "}
          <A to={VOTA_PATHS.method}>metodología</A>.
        </p>
      </section>

      <section aria-labelledby="vs-questions" className="vs-section">
        <h2 className="v-h2" id="vs-questions">
          Las {facts.questions} preguntas del test y cómo votó cada partido
        </h2>
        <p className="v-muted">Cada enlace abre la pregunta con lo que se votó y el voto de cada partido. Si quieres jugar sin spoilers, responde antes en el test.</p>
        <QuestionIndex atlas={atlas} snapshot={snapshot} />
      </section>

      <section aria-labelledby="vs-faq" className="vs-section">
        <h2 className="v-h2" id="vs-faq">
          Preguntas frecuentes
        </h2>
        <div className="vs-faq">
          {faqs.map((f) => (
            <div className="vs-faq__item" key={f.q}>
              <h3>{f.q}</h3>
              <p>{f.a}</p>
            </div>
          ))}
        </div>
      </section>

      <VotaLinks parties={snapshot.parties || []} topics={topics} />
    </div>
  );
}
