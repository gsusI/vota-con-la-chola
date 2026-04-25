import { formatInt, readPublicJson, sourceStatusClass } from "../static-snapshot.mjs";
import {
  StaticRouteHero,
  StaticRouteLink,
  StaticRouteList,
  StaticRouteMetrics,
  StaticRoutePanel,
  StaticRoutePanelGrid,
  StaticRouteStatusPill,
} from "../static-route-components";

export const metadata = {
  title: "Graph | Vota Con La Chola",
  description: "Grafo politico estatico con snapshot publico.",
};

export default function GraphPage() {
  const graph = readPublicJson("legacy/graph/data/graph.json", { meta: {}, nodes: [], edges: [] });
  const sources = graph.meta?.sources || [];
  const nodeCounts = graph.meta?.node_counts || {};

  return (
    <main className="shell staticRoute staticRouteGraph">
      <StaticRouteHero
        actions={[
          { href: "/explorer-politico/", label: "Explorer politico" },
          { href: "/people/", label: "Personas" },
        ]}
        eyebrow="Grafo"
        meta={[
          { label: "Rows", value: formatInt(graph.meta?.rows) },
          { label: "Limit", value: formatInt(graph.meta?.limit) },
        ]}
        summary="Resumen estatico del grafo de personas, partidos, instituciones y fuentes. Sin llamadas a /api/graph en el navegador."
        title="Graph"
      />

      <StaticRouteMetrics
        metrics={[
          { label: "Nodos", value: formatInt(graph.nodes?.length || 0) },
          { label: "Edges", value: formatInt(graph.edges?.length || 0) },
          { label: "Personas", value: formatInt(nodeCounts.person) },
          { label: "Partidos", value: formatInt(nodeCounts.party) },
        ]}
      />

      <StaticRoutePanelGrid>
        <StaticRoutePanel note="Fuentes que alimentan el grafo." title="Fuentes del grafo">
          <StaticRouteList
            items={sources.slice(0, 12)}
            renderItem={(source) => (
              <>
                <strong>{source.name || source.source_id}</strong>
                <span>{source.scope || "scope"} · {source.data_format || "format"}</span>
                <StaticRouteStatusPill value={{ className: sourceStatusClass(source.is_active ? "ok" : "missing"), label: source.is_active ? "activa" : "inactiva" }} />
                {source.default_url ? <StaticRouteLink href={source.default_url}>Origen</StaticRouteLink> : null}
              </>
            )}
          />
        </StaticRoutePanel>
      </StaticRoutePanelGrid>
    </main>
  );
}
