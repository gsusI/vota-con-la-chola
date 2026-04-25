import { compactText, formatDate, formatInt, formatPct, readPublicJson, sourceStatusClass } from "../static-snapshot.mjs";
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
  title: "Fuentes | Vota Con La Chola",
  description: "Seguimiento estatico de fuentes, cobertura de adquisicion y acciones pendientes.",
};

export default function ExplorerSourcesPage() {
  const status = readPublicJson("legacy/explorer-sources/data/status.json", { summary: {}, sources: [], actions: [] });
  const catalog = readPublicJson("legacy/explorer-sources/data/catalog.json", { sources: [] });
  const ideal = readPublicJson("legacy/explorer-sources/data/ideal.json", { sources: [] });
  const sources = Array.isArray(status.sources) ? status.sources : [];
  const actions = Array.isArray(status.actions) ? status.actions : [];
  const idealSources = Array.isArray(ideal.sources) ? ideal.sources : [];

  return (
    <main className="shell staticRoute staticRouteSources">
      <StaticRouteHero
        actions={[
          { href: "/explorer-politico/", label: "Ver politicos" },
          { href: "/explorer-votaciones/", label: "Ver votaciones" },
        ]}
        eyebrow="Operaciones de datos"
        meta={[
          { label: "Generado", value: formatDate(status.generated_at || catalog.generated_at) },
          { label: "Contrato", value: "snapshot estatico" },
        ]}
        summary="Estado publico de fuentes, ejecuciones y bloqueos. Esta ruta usa los JSON publicados; no intenta consultar endpoints privados desde el navegador."
        title="Fuentes y cobertura"
      />

      <StaticRouteMetrics
        metrics={[
          { label: "Fuentes deseadas", value: formatInt(status.summary?.desired) },
          { label: "Presentes", value: formatInt(status.summary?.present) },
          { label: "OK", value: formatInt(status.summary?.ok), note: formatPct(status.ops?.ingestion_runs_ok_pct) },
          { label: "Acciones", value: formatInt(actions.length), note: "priorizadas" },
        ]}
      />

      <StaticRoutePanelGrid>
        <StaticRoutePanel note="Estado operativo actual por fuente." title="Fuentes publicadas">
          <StaticRouteList
            items={sources.slice(0, 14)}
            renderItem={(source) => (
              <>
                <strong>{source.source_name || source.source_id}</strong>
                <span>{source.scope || "scope"} · {source.format || "formato"} · loaded {formatInt(source.last_loaded)}</span>
                <StaticRouteStatusPill value={{ className: sourceStatusClass(source.state), label: source.state || "sin estado" }} />
                {source.default_url ? <StaticRouteLink href={source.default_url}>Origen</StaticRouteLink> : null}
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Bloqueos y remates del tracker." title="Siguientes acciones">
          <StaticRouteList
            items={actions.slice(0, 10)}
            renderItem={(action) => (
              <>
                <strong>{action.priority || "P"} · {action.title}</strong>
                <span>{compactText(action.details, 160)}</span>
                <span className="staticRouteList__meta">{(action.source_ids || []).join(", ") || action.kind}</span>
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="North star de fuentes, no solo lo cargado hoy." title="Ideal de cobertura">
          <StaticRouteList
            items={idealSources.slice(0, 10)}
            renderItem={(source) => (
              <>
                <strong>{source.name || source.id}</strong>
                <span>{(source.domains || []).join(", ") || source.scope} · confianza {source.confidence}/5</span>
                {source.url ? <StaticRouteLink href={source.url}>Referencia</StaticRouteLink> : null}
              </>
            )}
          />
        </StaticRoutePanel>
      </StaticRoutePanelGrid>
    </main>
  );
}
