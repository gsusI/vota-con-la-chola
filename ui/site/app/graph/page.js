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
  title: "Grafo | Vota Con La Chola",
  description: "Grafo político estático con corte público.",
};

export default function GraphPage() {
  const graph = readPublicJson("legacy/graph/data/graph.json", { meta: {}, nodes: [], edges: [] });
  const sources = graph.meta?.sources || [];
  const nodeCounts = graph.meta?.node_counts || {};

  return (
    <main className="shell staticRoute staticRouteGraph">
      <StaticRouteHero
        actions={[
          { href: "/explorer-politico/", label: "Explorador político" },
          { href: "/people/", label: "Personas" },
        ]}
        eyebrow="Grafo"
        meta={[
          { label: "Registros", value: formatInt(graph.meta?.rows) },
          { label: "Límite", value: formatInt(graph.meta?.limit) },
        ]}
        summary="Resumen estático del grafo de personas, partidos, instituciones y fuentes. Sin llamadas a /api/graph en el navegador."
        title="Grafo"
      />

      <StaticRouteMetrics
        metrics={[
          { label: "Nodos", value: formatInt(graph.nodes?.length || 0) },
          { label: "Aristas", value: formatInt(graph.edges?.length || 0) },
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
                <span>{source.scope || "ámbito"} · {source.data_format || "formato"}</span>
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
