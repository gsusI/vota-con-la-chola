import { formatInt, readPublicJson } from "../static-snapshot.mjs";
import {
  StaticRouteHero,
  StaticRouteLink,
  StaticRouteList,
  StaticRouteMetrics,
  StaticRoutePanel,
  StaticRoutePanelGrid,
} from "../static-route-components";

export const metadata = {
  title: "Explorer SQL | Vota Con La Chola",
  description: "Indice estatico de tablas y snapshots publicos para navegacion en Cloudflare Pages.",
};

export default function ExplorerPage() {
  const graph = readPublicJson("legacy/graph/data/graph.json", { meta: {}, nodes: [], edges: [] });
  const topics = readPublicJson("legacy/explorer-temas/data/temas-preview.json", { tables: {} });
  const votes = readPublicJson("legacy/explorer-votaciones/data/votes-preview.json", { meta: {}, events: [] });
  const sources = readPublicJson("legacy/explorer-sources/data/status.json", { summary: {}, sources: [] });
  const tableCards = [
    { id: "topic_sets", label: "topic_sets", href: "/explorer-temas/", total: topics.tables?.topic_sets?.meta?.total },
    { id: "topics", label: "topics", href: "/explorer-temas/", total: topics.tables?.topics?.meta?.total },
    { id: "topic_positions", label: "topic_positions", href: "/explorer-temas/", total: topics.tables?.topic_positions?.meta?.total },
    { id: "topic_evidence", label: "topic_evidence", href: "/explorer-temas/", total: topics.tables?.topic_evidence?.meta?.total },
    { id: "parl_vote_events", label: "parl_vote_events", href: "/explorer-votaciones/", total: votes.meta?.total },
    { id: "sources", label: "sources", href: "/explorer-sources/", total: sources.summary?.desired },
  ];

  return (
    <main className="shell staticRoute staticRouteSqlIndex">
      <StaticRouteHero
        actions={[
          { href: "/explorer-temas/", label: "Temas" },
          { href: "/explorer-votaciones/", label: "Votaciones" },
          { href: "/explorer-sources/", label: "Fuentes" },
        ]}
        eyebrow="Indice estatico"
        meta={[
          { label: "Runtime", value: "static export" },
          { label: "API", value: "no requerida" },
        ]}
        summary="Sustituye el explorador SQL con una portada de tablas publicas. Las rutas enlazan a snapshots materializados para que Cloudflare no dependa de backend."
        title="Explorer"
      />

      <StaticRouteMetrics
        metrics={[
          { label: "Nodos graph", value: formatInt(graph.nodes?.length || 0) },
          { label: "Edges graph", value: formatInt(graph.edges?.length || 0) },
          { label: "Eventos voto", value: formatInt(votes.meta?.total) },
          { label: "Fuentes deseadas", value: formatInt(sources.summary?.desired) },
        ]}
      />

      <StaticRoutePanelGrid>
        <StaticRoutePanel note="Tablas publicas con vista dedicada." title="Tablas navegables">
          <StaticRouteList
            items={tableCards}
            renderItem={(row) => (
              <>
                <strong>{row.label}</strong>
                <span>Total snapshot {formatInt(row.total)}</span>
                <StaticRouteLink href={row.href}>Abrir vista</StaticRouteLink>
              </>
            )}
          />
        </StaticRoutePanel>
      </StaticRoutePanelGrid>
    </main>
  );
}
