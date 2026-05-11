import { formatDate, formatInt, formatMethod, formatPct, readPublicJson } from "../static-snapshot.mjs";
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
  title: "Ciudadanía | Vota Con La Chola",
  description: "Vista ciudadana estática de preocupaciones, partidos y evidencias.",
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
          { href: "/citizen/leaderboards/", label: "Clasificaciones" },
        ]}
        eyebrow="Vista ciudadana"
        meta={[
          { label: "Corte", value: formatDate(citizen.meta?.as_of_date) },
          { label: "Método", value: formatMethod(citizen.meta?.computed_method || "combined") },
        ]}
        summary="Mapa de preocupaciones, partidos y señales con honestidad visible sobre incertidumbre. Página estática: sin marco incrustado ni API en tiempo de ejecución."
        title="Ciudadanía"
      />

      <StaticRouteMetrics
        metrics={[
          { label: "Temas", value: formatInt(topics.length) },
          { label: "Partidos", value: formatInt(parties.length) },
          { label: "Señales claras", value: formatInt(clearPositions.length), note: formatPct(citizen.meta?.quality?.clear_pct) },
          { label: "Sin clasificar", value: formatPct(citizen.meta?.quality?.unknown_pct), note: citizen.meta?.freshness?.freshness_label || "" },
        ]}
      />

      <StaticRoutePanelGrid>
        <StaticRoutePanel note="Paquetes de preocupaciones publicados." title="Paquetes ciudadanos">
          <StaticRouteList
            items={packs}
            renderItem={(pack) => (
              <>
                <strong>{pack.pack_label || pack.pack_id}</strong>
                <span>{formatInt(pack.topics_total)} temas · {formatInt(pack.high_stakes_topics_total)} de alta relevancia</span>
                <StaticRouteStatusPill value={{ className: pack.weak ? "staticRouteStatusPill--warn" : "staticRouteStatusPill--ok", label: pack.weak ? "débil" : "ok" }} />
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
                <span>{(topic.concern_ids || []).join(", ") || "sin paquete"} · prioridad {topic.stakes_rank}</span>
                {topic.links?.explorer_temas ? <StaticRouteLink href="/explorer-temas/">Abrir evidencia</StaticRouteLink> : null}
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Partidos disponibles en el corte." title="Partidos">
          <StaticRouteList
            items={parties.slice(0, 16)}
            renderItem={(party) => (
              <>
                <strong>{party.name || party.acronym || party.party_id}</strong>
                <span>ID de partido {party.party_id}</span>
                <StaticRouteLink href="/explorer-politico/">Abrir políticos</StaticRouteLink>
              </>
            )}
          />
        </StaticRoutePanel>
      </StaticRoutePanelGrid>
    </main>
  );
}
