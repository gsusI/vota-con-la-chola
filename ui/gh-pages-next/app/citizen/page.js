import { formatDate, formatInt, formatPct, readPublicJson } from "../static-snapshot.mjs";
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
  title: "Ciudadania | Vota Con La Chola",
  description: "Vista ciudadana estatica de preocupaciones, partidos y evidencias.",
};

export default function CitizenPage() {
  const citizen = readPublicJson("legacy/citizen/data/citizen.json", { meta: {}, topics: [], parties: [], party_topic_positions: [] });
  const quality = readPublicJson("legacy/citizen/data/concern_pack_quality.json", { summary: {}, packs: [] });
  const topics = Array.isArray(citizen.topics) ? citizen.topics : [];
  const parties = Array.isArray(citizen.parties) ? citizen.parties : [];
  const positions = Array.isArray(citizen.party_topic_positions) ? citizen.party_topic_positions : [];
  const packs = Array.isArray(quality.packs) ? quality.packs : [];
  const clearPositions = positions.filter((row) => !["unclear", "no_signal", ""].includes(String(row.stance || "")));

  return (
    <main className="shell staticRoute staticRouteCitizen">
      <StaticRouteHero
        actions={[
          { href: "/explorer-temas/", label: "Auditar evidencia" },
          { href: "/citizen/leaderboards/", label: "Leaderboards" },
        ]}
        eyebrow="Vista ciudadana"
        meta={[
          { label: "As of", value: formatDate(citizen.meta?.as_of_date) },
          { label: "Metodo", value: citizen.meta?.computed_method || "combined" },
        ]}
        summary="Mapa de preocupaciones, partidos y senales con honestidad visible sobre incertidumbre. Render estatico: no iframe, no API runtime."
        title="Ciudadania"
      />

      <StaticRouteMetrics
        metrics={[
          { label: "Temas", value: formatInt(topics.length) },
          { label: "Partidos", value: formatInt(parties.length) },
          { label: "Senales claras", value: formatInt(clearPositions.length), note: formatPct(citizen.meta?.quality?.clear_pct) },
          { label: "Unknown", value: formatPct(citizen.meta?.quality?.unknown_pct), note: citizen.meta?.freshness?.freshness_label || "" },
        ]}
      />

      <StaticRoutePanelGrid>
        <StaticRoutePanel note="Paquetes de preocupaciones publicados." title="Packs ciudadanos">
          <StaticRouteList
            items={packs}
            renderItem={(pack) => (
              <>
                <strong>{pack.pack_label || pack.pack_id}</strong>
                <span>{formatInt(pack.topics_total)} temas · {formatInt(pack.high_stakes_topics_total)} high stakes</span>
                <StaticRouteStatusPill value={{ className: pack.weak ? "staticRouteStatusPill--warn" : "staticRouteStatusPill--ok", label: pack.weak ? "debil" : "ok" }} />
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Temas con prioridad alta." title="Temas principales">
          <StaticRouteList
            items={topics.slice(0, 10)}
            renderItem={(topic) => (
              <>
                <strong>{topic.label}</strong>
                <span>{(topic.concern_ids || []).join(", ") || "sin pack"} · rank {topic.stakes_rank}</span>
                {topic.links?.explorer_temas ? <StaticRouteLink href="/explorer-temas/">Abrir evidencia</StaticRouteLink> : null}
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Partidos disponibles en el snapshot." title="Partidos">
          <StaticRouteList
            items={parties.slice(0, 16)}
            renderItem={(party) => (
              <>
                <strong>{party.name || party.acronym || party.party_id}</strong>
                <span>Party ID {party.party_id}</span>
                <StaticRouteLink href="/explorer-politico/">Abrir arena</StaticRouteLink>
              </>
            )}
          />
        </StaticRoutePanel>
      </StaticRoutePanelGrid>
    </main>
  );
}
