import { citizenMethodLabel, formatDayEs, formatInt, formatPct, readPublicJson } from "../static-snapshot.mjs";
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
  const clearByParty = new Map();
  for (const row of clearPositions) clearByParty.set(row.party_id, (clearByParty.get(row.party_id) || 0) + 1);
  const concernLabels = Object.fromEntries(
    (readPublicJson("legacy/citizen/data/concerns_v1.json", { concerns: [] }).concerns || []).map((c) => [c.id, c.label]),
  );

  return (
    <main className="shell staticRoute staticRouteCitizen">
      <StaticRouteHero
        actions={[
          { href: "/citizen/vota/", label: "¿Con quién coincides? (generales)" },
          { href: "/explorer-temas/", label: "Auditar evidencia" },
          { href: "/citizen/leaderboards/", label: "Clasificaciones" },
        ]}
        eyebrow="Vista ciudadana"
        meta={[
          { label: "Datos hasta", value: formatDayEs(citizen.meta?.as_of_date) },
          { label: "Basado en", value: citizenMethodLabel(citizen.meta?.computed_method || "combined") },
        ]}
        summary="Qué posición ha tomado cada partido en los temas que más preocupan. Cuando no hay una señal clara lo decimos, en vez de inventarla."
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
        <StaticRoutePanel note="Las preocupaciones agrupadas en bloques." title="Bloques de temas">
          <StaticRouteList
            items={packs}
            renderItem={(pack) => (
              <>
                <strong>{pack.pack_label || pack.pack_id}</strong>
                <span>{formatInt(pack.topics_total)} temas · {formatInt(pack.high_stakes_topics_total)} de alta relevancia</span>
                <StaticRouteStatusPill value={{ className: pack.weak ? "staticRouteStatusPill--warn" : "staticRouteStatusPill--ok", label: pack.weak ? "Datos escasos" : "Datos suficientes" }} />
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Temas con prioridad alta." title="Temas principales">
          <StaticRouteList
            items={topics.slice(0, 10)}
            renderItem={(topic) => (
              <>
                <strong className="staticRouteList__clamp" title={topic.label}>
                  {topic.label}
                </strong>
                <span>
                  {(topic.concern_ids || []).map((id) => concernLabels[id] || id).join(", ") || "Sin tema asignado"} · prioridad {topic.stakes_rank}
                </span>
                {topic.links?.explorer_temas ? <StaticRouteLink href="/explorer-temas/">Abrir evidencia</StaticRouteLink> : null}
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Siglas con datos en este corte; las federaciones del PSOE (PSC, PSdeG…) cuentan aparte." title="Partidos">
          <StaticRouteList
            items={parties.slice(0, 16)}
            renderItem={(party) => (
              <>
                <strong>{party.name || party.acronym || party.party_id}</strong>
                <span>{formatInt(clearByParty.get(party.party_id) || 0)} posiciones claras</span>
                <StaticRouteLink href="/explorer-politico/">Abrir políticos</StaticRouteLink>
              </>
            )}
          />
        </StaticRoutePanel>
      </StaticRoutePanelGrid>
    </main>
  );
}
