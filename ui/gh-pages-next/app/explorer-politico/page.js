import { formatDate, formatInt, readPublicJson, rowsAsObjects, tallyBy } from "../static-snapshot.mjs";
import {
  StaticRouteHero,
  StaticRouteLink,
  StaticRouteList,
  StaticRouteMetrics,
  StaticRoutePanel,
  StaticRoutePanelGrid,
} from "../static-route-components";

export const metadata = {
  title: "Explorer Político | Vota Con La Chola",
  description: "Radar territorial estatico de mandatos, instituciones, fuentes y partidos.",
};

export default function ExplorerPoliticoPage() {
  const mandatesPayload = readPublicJson("legacy/explorer-politico/data/arena-mandates.json", { meta: {}, columns: [], rows: [] });
  const sourcesPayload = readPublicJson("legacy/explorer-politico/data/sources.json", { sources: [] });
  const mandates = rowsAsObjects(mandatesPayload.columns, mandatesPayload.rows);
  const activeRows = mandates.filter((row) => Number(row.is_active) === 1);
  const scopeCounts = tallyBy(mandates, "level").slice(0, 6);
  const partyCounts = tallyBy(activeRows, "party_name").slice(0, 8);

  return (
    <main className="shell staticRoute staticRoutePeopleArena">
      <StaticRouteHero
        actions={[
          { href: "/people/", label: "Abrir perfiles" },
          { href: "/people/xray/", label: "Abrir X-Ray" },
        ]}
        eyebrow="Arena politica"
        meta={[
          { label: "Snapshot", value: formatDate(mandatesPayload.meta?.snapshot_date) },
          { label: "Fuentes", value: formatInt(sourcesPayload.sources?.length || 0) },
        ]}
        summary="Mandatos, partidos, instituciones y territorios renderizados desde el extracto estatico. No hay iframe ni dependencia de /api/graph."
        title="Explorer politico"
      />

      <StaticRouteMetrics
        metrics={[
          { label: "Mandatos", value: formatInt(mandatesPayload.meta?.rows || mandates.length) },
          { label: "Activos", value: formatInt(activeRows.length) },
          { label: "Fuentes", value: formatInt(sourcesPayload.sources?.length || 0) },
          { label: "Ambitos", value: formatInt(scopeCounts.length) },
        ]}
      />

      <StaticRoutePanelGrid>
        <StaticRoutePanel note="Muestra de mandatos activos." title="Personas e instituciones">
          <StaticRouteList
            items={activeRows.slice(0, 12)}
            renderItem={(row) => (
              <>
                <strong>{row.full_name || "Persona sin nombre"}</strong>
                <span>{row.role_title || "cargo"} · {row.institution_name || "institucion"}</span>
                <span className="staticRouteList__meta">{row.party_name || "sin partido"} · {row.mandate_territory_code || row.level}</span>
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Distribucion de la muestra por partido." title="Partidos con mas mandatos activos">
          <StaticRouteList
            items={partyCounts}
            renderItem={(row) => (
              <>
                <strong>{row.label}</strong>
                <span>{formatInt(row.count)} mandatos activos</span>
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Fuentes de representacion politica." title="Fuentes cargadas">
          <StaticRouteList
            items={(sourcesPayload.sources || []).slice(0, 10)}
            renderItem={(source) => (
              <>
                <strong>{source.name || source.source_id}</strong>
                <span>{source.scope || "scope"} · {source.source_id}</span>
                {source.default_url ? <StaticRouteLink href={source.default_url}>Origen</StaticRouteLink> : null}
              </>
            )}
          />
        </StaticRoutePanel>
      </StaticRoutePanelGrid>
    </main>
  );
}
