import {
  buildVoteExplainerHref,
  caveatSeverityClass,
  formatVoteDate,
  loadVoteExplainerManifest,
  withBasePath,
} from "./pageData.mjs";

export const metadata = {
  title: "Vote explainer | Vota Con La Chola",
  description: "Indice publico de votaciones compartibles con fuentes oficiales y caveats visibles.",
};

export default function VoteExplainerIndexPage() {
  const manifest = loadVoteExplainerManifest();
  const demoVote = manifest.votes?.[0] || null;

  return (
    <main className="shell">
      <section className="hero card explainerHero">
        <p className="eyebrow">Wedge principal</p>
        <h1>Vote explainer</h1>
        <p className="sub">
          Paginas publicas y compartibles para una votacion concreta: que se voto, que paso, como votaron los grupos, donde estan las fuentes oficiales y que caveats aplican.
        </p>
        <div className="chips">
          <span className="chip">Rutas canonicas por voto</span>
          <span className="chip">Snapshot estatico reproducible</span>
          <span className="chip">Sin API server-side</span>
        </div>
        <p className="sub" style={{ marginTop: 12 }}>
          {demoVote ? <a href={buildVoteExplainerHref(demoVote.public_vote_id)}>Abrir demo actual</a> : "Todavia no hay votos exportados para demo."}
          <span style={{ marginLeft: "10px" }}>
            <a href={withBasePath("/explorer-votaciones/")}>Ir al explorer de votaciones</a>
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
                  <span className="kpiLabel">{vote.chamber || "Institucion parlamentaria"} · {formatVoteDate(vote.vote_date)}</span>
                  <strong>{vote.headline || vote.vote_event_id}</strong>
                  <span className="sub" style={{ marginTop: 8 }}>{vote.result_label || vote.summary_text}</span>
                  {topCaveat ? (
                    <span className={`chip ${caveatSeverityClass(topCaveat.severity)}`} style={{ marginTop: 10 }}>
                      Caveat: {topCaveat.label}
                    </span>
                  ) : null}
                </a>
              );
            })}
          </div>
        ) : (
          <p className="sub">No encontramos votos exportados en el snapshot publico actual.</p>
        )}
      </section>
    </main>
  );
}
