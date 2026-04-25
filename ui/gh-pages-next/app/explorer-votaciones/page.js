import { compactText, formatDate, formatInt, readPublicJson } from "../static-snapshot.mjs";
import {
  StaticRouteHero,
  StaticRouteLink,
  StaticRouteList,
  StaticRouteMetrics,
  StaticRoutePanel,
  StaticRoutePanelGrid,
} from "../static-route-components";

export const metadata = {
  title: "Votaciones | Vota Con La Chola",
  description: "Vistazo estatico de votaciones, totales y enlaces a vote explainer.",
};

export default function ExplorerVotacionesPage() {
  const snapshot = readPublicJson("legacy/explorer-votaciones/data/votes-preview.json", { meta: {}, events: [] });
  const voteManifest = readPublicJson("vote-explainer/data/manifest.json", { votes: [] });
  const votes = Array.isArray(snapshot.events) ? snapshot.events : [];
  const explainerByEvent = new Map((voteManifest.votes || []).map((vote) => [vote.vote_event_id, vote]));
  const latestVotes = votes.slice(0, 12);

  return (
    <main className="shell staticRoute staticRouteVotes">
      <StaticRouteHero
        actions={[
          { href: "/vote-explainer/", label: "Indice vote explainer" },
          { href: "/parliamentary-accountability/", label: "Accountability parlamentaria" },
        ]}
        eyebrow="Votaciones"
        meta={[
          { label: "Total", value: formatInt(snapshot.meta?.total) },
          { label: "Exportadas", value: formatInt(snapshot.meta?.returned || latestVotes.length) },
        ]}
        summary="Corte publico de votaciones con totales, grupos y rutas estaticas a explicadores individuales. Sin llamadas a API en Cloudflare."
        title="Votaciones rastreables"
      />

      <StaticRouteMetrics
        metrics={[
          { label: "Eventos", value: formatInt(snapshot.meta?.total) },
          { label: "Muestra publicada", value: formatInt(votes.length) },
          { label: "Explainers", value: formatInt(voteManifest.votes?.length || 0) },
          { label: "Implicaciones revisadas", value: formatInt(snapshot.meta?.reviewed_implications_returned) },
        ]}
      />

      <StaticRoutePanelGrid>
        <StaticRoutePanel note="Las primeras filas se cruzan contra vote-explainer/data/manifest.json." title="Ultimas votaciones">
          <StaticRouteList
            items={latestVotes}
            renderItem={(vote) => {
              const explainer = explainerByEvent.get(vote.vote_event_id);
              return (
                <>
                  <strong>{compactText(vote.title || vote.vote_event_id, 150)}</strong>
                  <span>{vote.source_name || vote.source_id} · {formatDate(vote.vote_date)}</span>
                  <span className="staticRouteList__meta">
                    Si {formatInt(vote.totals?.yes)} · No {formatInt(vote.totals?.no)} · Abst. {formatInt(vote.totals?.abstain)}
                  </span>
                  {explainer ? <StaticRouteLink href={`/vote-explainer/${explainer.public_vote_id}/`}>Abrir explainer</StaticRouteLink> : null}
                </>
              );
            }}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Primeros grupos de la votacion mas reciente." title="Desglose por grupo">
          <StaticRouteList
            items={latestVotes[0]?.group_breakdown || []}
            renderItem={(group) => (
              <>
                <strong>{group.group_code || "Grupo"}</strong>
                <span>Si {formatInt(group.yes)} · No {formatInt(group.no)} · Abst. {formatInt(group.abstain)} · NV {formatInt(group.no_vote)}</span>
                <span className="staticRouteList__meta">Total {formatInt(group.total)}</span>
              </>
            )}
          />
        </StaticRoutePanel>
      </StaticRoutePanelGrid>
    </main>
  );
}
