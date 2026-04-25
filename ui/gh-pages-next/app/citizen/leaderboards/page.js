import { formatDate, formatInt, formatPct, readPublicJson } from "../../static-snapshot.mjs";
import {
  StaticRouteHero,
  StaticRouteLink,
  StaticRouteList,
  StaticRouteMetrics,
  StaticRoutePanel,
  StaticRoutePanelGrid,
  StaticRouteStatusPill,
} from "../../static-route-components";

export const metadata = {
  title: "Leaderboards | Vota Con La Chola",
  description: "Tablero estatico de senales, incertidumbre y cobertura por partido.",
};

function buildPartyRows(parties, positions) {
  const partyMap = new Map((parties || []).map((party) => [party.party_id, party]));
  const rows = new Map();
  for (const position of positions || []) {
    const partyId = position.party_id;
    if (!rows.has(partyId)) {
      const party = partyMap.get(partyId) || {};
      rows.set(partyId, {
        id: partyId,
        name: party.name || party.acronym || `Party ${partyId}`,
        clear: 0,
        noSignal: 0,
        unclear: 0,
        support: 0,
        oppose: 0,
        mixed: 0,
        confidenceTotal: 0,
        confidenceRows: 0,
      });
    }
    const row = rows.get(partyId);
    const stance = String(position.stance || "");
    if (stance === "support" || stance === "oppose" || stance === "mixed") {
      row.clear += 1;
      row[stance] += 1;
    } else if (stance === "no_signal") {
      row.noSignal += 1;
    } else {
      row.unclear += 1;
    }
    const confidence = Number(position.confidence);
    if (Number.isFinite(confidence)) {
      row.confidenceTotal += confidence;
      row.confidenceRows += 1;
    }
  }
  return [...rows.values()]
    .map((row) => ({
      ...row,
      confidenceAvg: row.confidenceRows ? row.confidenceTotal / row.confidenceRows : 0,
    }))
    .sort((left, right) => right.clear - left.clear || right.confidenceAvg - left.confidenceAvg || left.name.localeCompare(right.name));
}

export default function CitizenLeaderboardPage() {
  const citizen = readPublicJson("legacy/citizen/data/citizen.json", { meta: {}, parties: [], party_topic_positions: [] });
  const quality = readPublicJson("legacy/citizen/data/concern_pack_quality.json", { summary: {}, packs: [] });
  const parties = Array.isArray(citizen.parties) ? citizen.parties : [];
  const positions = Array.isArray(citizen.party_topic_positions) ? citizen.party_topic_positions : [];
  const partyRows = buildPartyRows(parties, positions);
  const packs = Array.isArray(quality.packs) ? quality.packs : [];

  return (
    <main className="shell staticRoute staticRouteCitizenLeaderboard">
      <StaticRouteHero
        actions={[
          { href: "/citizen/", label: "Vista ciudadana" },
          { href: "/explorer-temas/", label: "Auditar evidencia" },
        ]}
        eyebrow="Leaderboards"
        meta={[
          { label: "As of", value: formatDate(citizen.meta?.as_of_date) },
          { label: "Metodo", value: citizen.meta?.computed_method || "combined" },
        ]}
        summary="Ranking estatico por partido y calidad de packs. Muestra senal clara y unknown sin inventar certezas."
        title="Leaderboards"
      />

      <StaticRouteMetrics
        metrics={[
          { label: "Partidos", value: formatInt(parties.length) },
          { label: "Celdas", value: formatInt(positions.length) },
          { label: "Senal clara", value: formatPct(citizen.meta?.quality?.clear_pct) },
          { label: "Unknown", value: formatPct(citizen.meta?.quality?.unknown_pct) },
        ]}
      />

      <StaticRoutePanelGrid>
        <StaticRoutePanel note="Ordenado por numero de posturas claras." title="Partidos">
          <StaticRouteList
            items={partyRows.slice(0, 16)}
            renderItem={(party) => (
              <>
                <strong>{party.name}</strong>
                <span>Claras {formatInt(party.clear)} · support {formatInt(party.support)} · oppose {formatInt(party.oppose)} · mixed {formatInt(party.mixed)}</span>
                <span className="staticRouteList__meta">Unknown/no signal {formatInt(party.noSignal + party.unclear)} · confianza media {formatPct(party.confidenceAvg)}</span>
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Calidad de cada pack ciudadano." title="Packs">
          <StaticRouteList
            items={packs}
            renderItem={(pack) => (
              <>
                <strong>{pack.pack_label || pack.pack_id}</strong>
                <span>Clear {formatPct(pack.clear_cells_pct)} · unknown {formatPct(pack.unknown_cells_pct)}</span>
                <StaticRouteStatusPill value={{ className: pack.weak ? "staticRouteStatusPill--warn" : "staticRouteStatusPill--ok", label: pack.weak ? "debil" : "ok" }} />
                <StaticRouteLink href="/citizen/">Ver contexto</StaticRouteLink>
              </>
            )}
          />
        </StaticRoutePanel>
      </StaticRoutePanelGrid>
    </main>
  );
}
