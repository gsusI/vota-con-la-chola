import {
  buildVoteExplainerHref,
  caveatSeverityClass,
  formatVoteDate,
  loadVoteExplainerManifest,
  withBasePath,
} from "./pageData.mjs";

export const metadata = {
  title: "Explicador de votos | Vota Con La Chola",
  description: "Índice público de votaciones compartibles con fuentes oficiales y salvedades visibles.",
};

export default function VoteExplainerIndexPage() {
  const manifest = loadVoteExplainerManifest();
  const demoVote = manifest.votes?.[0] || null;

  return (
    <main className="shell">
      <section className="hero card explainerHero">
        <p className="eyebrow">Votaciones explicadas</p>
        <h1>Explicador de votos</h1>
        <p className="sub">
          Páginas públicas y compartibles para una votación concreta: qué se votó, qué pasó, cómo votaron los grupos, dónde están las fuentes oficiales y qué salvedades aplican.
        </p>
        <div className="chips">
          <span className="chip">Rutas canónicas por voto</span>
          <span className="chip">Corte estático reproducible</span>
          <span className="chip">Sin API de servidor</span>
        </div>
        <p className="sub" style={{ marginTop: 12 }}>
          {demoVote ? <a href={buildVoteExplainerHref(demoVote.public_vote_id)}>Abrir ejemplo actual</a> : "Todavía no hay votos exportados."}
          <span style={{ marginLeft: "10px" }}>
            <a href={withBasePath("/explorer-votaciones/")}>Ir al explorador de votaciones</a>
          </span>
        </p>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Votos disponibles</h2>
        </div>
        {manifest.votes?.length ? (
          <div className="voteIndexGrid">
            {manifest.votes.slice(0, 12).map((vote) => {
              const topCaveat = vote.top_caveat || null;
              return (
                <a className="voteIndexCard" href={buildVoteExplainerHref(vote.public_vote_id)} key={vote.public_vote_id}>
                  <span className="kpiLabel">{vote.chamber || "Institución parlamentaria"} · {formatVoteDate(vote.vote_date)}</span>
                  <strong>{vote.headline || vote.vote_event_id}</strong>
                  <span className="sub" style={{ marginTop: 8 }}>{vote.result_label || vote.summary_text}</span>
                  {topCaveat ? (
                    <span className={`chip ${caveatSeverityClass(topCaveat.severity)}`} style={{ marginTop: 10 }}>
                      Salvedad: {topCaveat.label}
                    </span>
                  ) : null}
                </a>
              );
            })}
          </div>
        ) : (
          <p className="sub">No encontramos votos exportados en el corte público actual.</p>
        )}
      </section>
    </main>
  );
}
