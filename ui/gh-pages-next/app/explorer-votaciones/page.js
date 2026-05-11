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
  description: "Vistazo estático de votaciones, totales y enlaces a explicadores de voto.",
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
          { href: "/vote-explainer/", label: "Índice de explicadores" },
          { href: "/parliamentary-accountability/", label: "Responsabilidad parlamentaria" },
        ]}
        eyebrow="Votaciones"
        meta={[
          { label: "Total", value: formatInt(snapshot.meta?.total) },
          { label: "Exportadas", value: formatInt(snapshot.meta?.returned || latestVotes.length) },
        ]}
        summary="Corte público de votaciones con totales, grupos y rutas estáticas a explicadores individuales. Sin llamadas a API en Cloudflare."
        title="Votaciones rastreables"
      />

      <StaticRouteMetrics
        metrics={[
          { label: "Eventos", value: formatInt(snapshot.meta?.total) },
          { label: "Muestra publicada", value: formatInt(votes.length) },
          { label: "Explicadores", value: formatInt(voteManifest.votes?.length || 0) },
          { label: "Implicaciones revisadas", value: formatInt(snapshot.meta?.reviewed_implications_returned) },
        ]}
      />

      <StaticRoutePanelGrid>
        <StaticRoutePanel note="Las primeras filas se cruzan contra vote-explainer/data/manifest.json." title="Últimas votaciones">
          <StaticRouteList
            items={latestVotes}
            renderItem={(vote) => {
              const explainer = explainerByEvent.get(vote.vote_event_id);
              return (
                <>
                  <strong>{compactText(vote.title || vote.vote_event_id, 150)}</strong>
                  <span>{vote.source_name || vote.source_id} · {formatDate(vote.vote_date)}</span>
                  <span className="staticRouteList__meta">
                    Sí {formatInt(vote.totals?.yes)} · No {formatInt(vote.totals?.no)} · Abst. {formatInt(vote.totals?.abstain)}
                  </span>
                  {explainer ? <StaticRouteLink href={`/vote-explainer/${explainer.public_vote_id}/`}>Abrir explicador</StaticRouteLink> : null}
                </>
              );
            }}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Primeros grupos de la votación más reciente." title="Desglose por grupo">
          <StaticRouteList
            items={latestVotes[0]?.group_breakdown || []}
            renderItem={(group) => (
              <>
                <strong>{group.group_code || "Grupo"}</strong>
                <span>Sí {formatInt(group.yes)} · No {formatInt(group.no)} · Abst. {formatInt(group.abstain)} · NV {formatInt(group.no_vote)}</span>
                <span className="staticRouteList__meta">Total {formatInt(group.total)}</span>
              </>
            )}
          />
        </StaticRoutePanel>
      </StaticRoutePanelGrid>
    </main>
  );
}
