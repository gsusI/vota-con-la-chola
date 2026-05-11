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
  description: "Seguimiento estático de fuentes, cobertura de adquisición y acciones pendientes.",
};

export default function ExplorerSourcesPage() {
  const status = readPublicJson("legacy/explorer-sources/data/status.json", { summary: {}, sources: [], actions: [] });
  const catalog = readPublicJson("legacy/explorer-sources/data/catalog.json", { sources: [] });
  const ideal = readPublicJson("legacy/explorer-sources/data/ideal.json", { sources: [] });
  const sources = Array.isArray(status.sources) ? status.sources : [];
  const catalogSources = Array.isArray(catalog.sources) ? catalog.sources : [];
  const actions = Array.isArray(status.actions) ? status.actions : [];
  const idealSources = Array.isArray(ideal.sources) ? ideal.sources : [];
  const catalogClaimSources = catalogSources.filter((source) => source.catalog_state);
  const sourceClaimPool = catalogClaimSources.length
    ? catalogClaimSources
    : sources.map((source) => ({
        ...source,
        catalog_state: source.state || source.sql_status || "missing",
        sample_url: source.fallback_file || source.sample_url,
      }));
  const sourceClaims = sourceClaimPool
    .filter((source) => ["missing", "blocked", "stale"].includes(String(source.catalog_state || "").toLowerCase()))
    .sort((left, right) => {
      const stateOrder = { missing: 0, blocked: 1, stale: 2, available: 3 };
      const leftState = stateOrder[String(left.catalog_state || "").toLowerCase()] ?? 9;
      const rightState = stateOrder[String(right.catalog_state || "").toLowerCase()] ?? 9;
      return leftState - rightState || String(left.source_id || "").localeCompare(String(right.source_id || ""));
    });
  const catalogSummary = catalog.summary || {};

  return (
    <main className="shell staticRoute staticRouteSources">
      <StaticRouteHero
        actions={[
          { href: "/explorer-politico/", label: "Ver políticos" },
          { href: "/explorer-votaciones/", label: "Ver votaciones" },
        ]}
        eyebrow="Operaciones de datos"
        meta={[
          { label: "Generado", value: formatDate(status.generated_at || catalog.generated_at) },
          { label: "Contrato", value: "corte estático" },
        ]}
        summary="Estado público de fuentes, ejecuciones y bloqueos. Esta ruta usa los JSON publicados; no intenta consultar endpoints privados desde el navegador."
        title="Fuentes y cobertura"
      />

      <StaticRouteMetrics
        metrics={[
          { label: "Fuentes deseadas", value: formatInt(status.summary?.desired) },
          { label: "Presentes", value: formatInt(status.summary?.present) },
          { label: "Disponibles", value: formatInt(catalogSummary.available_total), note: "catálogo" },
          { label: "Bloqueadas", value: formatInt(catalogSummary.blocked_total), note: "catálogo" },
          { label: "Acciones", value: formatInt(actions.length), note: "priorizadas" },
        ]}
      />

      <StaticRoutePanelGrid>
        <StaticRoutePanel note="Front door para nuevas fuentes: escoger fila, abrir issue y reclamar ownership." title="Fuentes reclamables">
          <StaticRouteList
            empty="Sin fuentes reclamables en este corte."
            items={sourceClaims.slice(0, 12)}
            renderItem={(source) => (
              <div className="sourceClaimCard">
                <div className="sourceClaimCard__header">
                  <strong className="sourceClaimCard__title">{source.name || source.source_name || source.source_id}</strong>
                  <StaticRouteStatusPill
                    value={{
                      className: sourceStatusClass(source.catalog_state),
                      label: source.catalog_state || "missing",
                    }}
                  />
                </div>
                <span className="sourceClaimCard__meta">
                  {source.source_id} · {source.scope || "ámbito"} · snapshot {formatDate(source.latest_snapshot || source.last_seen_at)}
                </span>
                {source.blocker_reason ? <span className="sourceClaimCard__blocker">{compactText(source.blocker_reason, 180)}</span> : null}
                <div className="sourceClaimCard__links">
                  {source.default_url ? <StaticRouteLink href={source.default_url}>Fuente</StaticRouteLink> : null}
                  {source.sample_url ? (
                    <StaticRouteLink href={`https://github.com/gsusI/vota-con-la-chola/blob/main/${source.sample_url}`}>
                      Muestra
                    </StaticRouteLink>
                  ) : null}
                  <StaticRouteLink
                    href={`https://github.com/gsusI/vota-con-la-chola/issues/new?template=data_source_request.yml&title=Claim%20${encodeURIComponent(source.source_id || "source")}`}
                  >
                    Reclamar fuente
                  </StaticRouteLink>
                </div>
              </div>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Estado operativo actual por fuente." title="Fuentes publicadas">
          <StaticRouteList
            items={sources.slice(0, 14)}
            renderItem={(source) => (
              <>
                <strong>{source.source_name || source.source_id}</strong>
                <span>{source.scope || "ámbito"} · {source.format || "formato"} · cargados {formatInt(source.last_loaded)}</span>
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
