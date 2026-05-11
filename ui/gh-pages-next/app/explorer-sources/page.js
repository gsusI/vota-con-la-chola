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

const REPO_URL = "https://github.com/gsusI/vota-con-la-chola";

export const metadata = {
  title: "Fuentes | Vota Con La Chola",
  description: "Seguimiento estático de fuentes, cobertura de adquisición y acciones pendientes.",
};

function readSourceCatalog() {
  const legacyCatalog = readPublicJson("legacy/explorer-sources/data/catalog.json", { summary: {}, sources: [], actions: [] });
  return readPublicJson("explorer-sources/data/catalog.json", legacyCatalog);
}

function readSourceQueue() {
  return readPublicJson("explorer-sources/data/scrape-queue.json", { summary: {}, items: [], batches: [] });
}

function sampleSearchHref(sourceId) {
  return `https://github.com/search?q=repo%3AgsusI%2Fvota-con-la-chola+path%3Aetl%2Fdata%2Fraw%2Fsamples+${encodeURIComponent(
    `${sourceId}_sample`,
  )}&type=code`;
}

function claimSourceHref(sourceId) {
  return `${REPO_URL}/issues/new?template=data_source_request.yml&title=Claim%20${encodeURIComponent(sourceId || "source")}`;
}

function queueBySourceId(queueItems) {
  return new Map(queueItems.map((item) => [item.source_id, item]));
}

function sourceFrontDoorState(source, queueItem) {
  const queueReason = String(queueItem?.queue_reason || "").toLowerCase();
  const opsState = String(source.ops_state || queueItem?.ops_state || "").toLowerCase();
  const sqlStatus = String(source.sql_status || queueItem?.sql_status || "").toUpperCase();
  const mismatchState = String(source.mismatch_state || queueItem?.mismatch_state || "").toUpperCase();
  if (queueReason === "blocked_upstream" || (source.flags?.blocked_note && Number(source.max_loaded_network || 0) <= 0)) {
    return "blocked";
  }
  if (!source.in_db || opsState === "missing" || sqlStatus === "TODO") {
    return "missing";
  }
  if (mismatchState === "MISMATCH" || opsState === "not_run" || Number(source.max_loaded_network || 0) <= 0) {
    return "stale";
  }
  return "available";
}

function stateLabel(state) {
  const labels = {
    available: "available",
    blocked: "blocked",
    stale: "stale",
    missing: "missing",
  };
  return labels[state] || "unknown";
}

function stateRank(state) {
  return { blocked: 0, missing: 1, stale: 2, available: 3 }[state] ?? 9;
}

function blockerReason(source, queueItem) {
  return queueItem?.tracker_block_note || source.tracker_block_note || source.last_message || "";
}

function sourceSnapshotLabel(catalog, source) {
  return source.last_seen_at || catalog.snapshot_date || catalog.generated_at || "";
}

function decorateSource(source, queueItem, catalog) {
  const state = sourceFrontDoorState(source, queueItem);
  return {
    ...source,
    front_door_state: state,
    front_door_label: stateLabel(state),
    front_door_blocker: blockerReason(source, queueItem),
    front_door_snapshot: sourceSnapshotLabel(catalog, source),
    front_door_queue: queueItem || null,
  };
}

function stateCounts(sources) {
  return sources.reduce(
    (counts, source) => {
      counts[source.front_door_state] = (counts[source.front_door_state] || 0) + 1;
      return counts;
    },
    { available: 0, blocked: 0, stale: 0, missing: 0 },
  );
}

function sourceSort(left, right) {
  return (
    stateRank(left.front_door_state) - stateRank(right.front_door_state) ||
    Number(right.front_door_queue?.priority_score || 0) - Number(left.front_door_queue?.priority_score || 0) ||
    String(left.source_id || "").localeCompare(String(right.source_id || ""))
  );
}

function SourceFrontDoorCard({ source }) {
  const queue = source.front_door_queue;
  const reason = source.front_door_blocker;
  return (
    <article className="sourceFrontDoorCard">
      <div className="sourceFrontDoorCard__header">
        <strong className="sourceFrontDoorCard__title">{source.source_name || source.source_id}</strong>
        <StaticRouteStatusPill
          value={{
            className: sourceStatusClass(source.front_door_state),
            label: source.front_door_label,
          }}
        />
      </div>
      <dl className="sourceFrontDoorCard__facts">
        <div className="sourceFrontDoorCard__fact">
          <dt>ID</dt>
          <dd>{source.source_id}</dd>
        </div>
        <div className="sourceFrontDoorCard__fact">
          <dt>Scope</dt>
          <dd>{source.scope || "sin scope"}</dd>
        </div>
        <div className="sourceFrontDoorCard__fact">
          <dt>Snapshot</dt>
          <dd>{formatDate(source.front_door_snapshot)}</dd>
        </div>
        <div className="sourceFrontDoorCard__fact">
          <dt>Registros</dt>
          <dd>{formatInt(source.last_loaded || source.max_loaded_any)}</dd>
        </div>
      </dl>
      {reason ? <p className="sourceFrontDoorCard__blocker">{compactText(reason, 220)}</p> : null}
      {queue?.queue_reason ? <p className="sourceFrontDoorCard__queueReason">Queue: {queue.priority_band || "P"} · {queue.queue_reason}</p> : null}
      <div className="sourceFrontDoorCard__links">
        {source.default_url ? <StaticRouteLink href={source.default_url}>Fuente</StaticRouteLink> : null}
        <StaticRouteLink href={sampleSearchHref(source.source_id)}>Muestra</StaticRouteLink>
        <StaticRouteLink href={claimSourceHref(source.source_id)}>Claim this source</StaticRouteLink>
      </div>
    </article>
  );
}

function StateBucket({ title, state, sources }) {
  const bucketAll = sources.filter((source) => source.front_door_state === state);
  const bucketSources = bucketAll.slice(0, 6);
  return (
    <section className="sourceStateBucket">
      <div className="sourceStateBucket__header">
        <h3 className="sourceStateBucket__title">{title}</h3>
        <StaticRouteStatusPill value={{ className: sourceStatusClass(state), label: formatInt(bucketAll.length) }} />
      </div>
      <StaticRouteList
        empty="Sin fuentes en este estado."
        items={bucketSources}
        renderItem={(source) => (
          <>
            <strong className="sourceStateBucket__sourceTitle">{source.source_name || source.source_id}</strong>
            <span className="sourceStateBucket__sourceMeta">
              {source.source_id} · {source.scope || "scope"} · {formatDate(source.front_door_snapshot)}
            </span>
            <div className="sourceStateBucket__sourceLinks">
              <StaticRouteLink href={claimSourceHref(source.source_id)}>Claim</StaticRouteLink>
              <StaticRouteLink href={sampleSearchHref(source.source_id)}>Sample</StaticRouteLink>
            </div>
          </>
        )}
      />
    </section>
  );
}

export default function ExplorerSourcesPage() {
  const status = readPublicJson("explorer-sources/data/status.json", { summary: {}, sources: [], actions: [] });
  const catalog = readSourceCatalog();
  const scrapeQueue = readSourceQueue();
  const ideal = readPublicJson("legacy/explorer-sources/data/ideal.json", { sources: [] });
  const queueItems = Array.isArray(scrapeQueue.items) ? scrapeQueue.items : [];
  const catalogSources = Array.isArray(catalog.sources) ? catalog.sources : [];
  const actions = Array.isArray(catalog.actions) ? catalog.actions : Array.isArray(status.actions) ? status.actions : [];
  const idealSources = Array.isArray(ideal.sources) ? ideal.sources : [];
  const queueMap = queueBySourceId(queueItems);
  const decoratedSources = catalogSources.map((source) => decorateSource(source, queueMap.get(source.source_id), catalog)).sort(sourceSort);
  const counts = stateCounts(decoratedSources);
  const claimSources = decoratedSources.filter((source) => source.front_door_state !== "available").slice(0, 12);
  const catalogSummary = catalog.summary || {};

  return (
    <main className="shell staticRoute staticRouteSources">
      <StaticRouteHero
        actions={[
          { href: "/explorer-politico/", label: "Ver políticos" },
          { href: "/explorer-votaciones/", label: "Ver votaciones" },
          { href: `${REPO_URL}/blob/main/docs/etl/source-onboarding.md`, label: "Guía contributor" },
        ]}
        eyebrow="Operaciones de datos"
        meta={[
          { label: "Generado", value: formatDate(status.generated_at || catalog.generated_at) },
          { label: "Snapshot", value: formatDate(catalog.snapshot_date || scrapeQueue.snapshot_date) },
          { label: "Contrato", value: catalog.catalog_version || "source catalog" },
        ]}
        summary="Front door público para datasets: qué está disponible, qué está bloqueado, qué está stale o missing, y dónde reclamar ownership para sumar una fuente."
        title="Source catalog"
      />

      <StaticRouteMetrics
        metrics={[
          { label: "Available", value: formatInt(counts.available), note: "network clean/current" },
          { label: "Blocked", value: formatInt(counts.blocked), note: "upstream blocker" },
          { label: "Stale", value: formatInt(counts.stale), note: "needs fresh run" },
          { label: "Missing", value: formatInt(counts.missing), note: "not in live DB" },
          { label: "Queue", value: formatInt(scrapeQueue.summary?.queue_items_total || queueItems.length), note: "claimable tasks" },
        ]}
      />

      <StaticRoutePanelGrid>
        <StaticRoutePanel note="Start here: pick a source, inspect sample/evidence, claim the task, then add or fix the connector." title="Claim this source">
          <StaticRouteList
            empty="Sin fuentes reclamables en este corte."
            items={claimSources}
            renderItem={(source) => <SourceFrontDoorCard source={source} />}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Same catalog grouped for scanning by contribution state." title="Available / blocked / stale / missing">
          <div className="sourceStateBucketGrid">
            <StateBucket title="Available" state="available" sources={decoratedSources} />
            <StateBucket title="Blocked" state="blocked" sources={decoratedSources} />
            <StateBucket title="Stale" state="stale" sources={decoratedSources} />
            <StateBucket title="Missing" state="missing" sources={decoratedSources} />
          </div>
        </StaticRoutePanel>

        <StaticRoutePanel note="Generated from the same catalog/queue contract." title="Source queue">
          <StaticRouteList
            items={queueItems.slice(0, 10)}
            renderItem={(item) => (
              <>
                <strong className="sourceQueueItem__title">{item.priority_band || "P"} · {item.source_name || item.source_id}</strong>
                <span className="sourceQueueItem__meta">
                  {item.source_id} · {item.queue_reason} · score {formatInt(item.priority_score)}
                </span>
                {item.tracker_block_note ? <span className="sourceQueueItem__blocker">{compactText(item.tracker_block_note, 180)}</span> : null}
                <div className="sourceQueueItem__links">
                  {item.default_url ? <StaticRouteLink href={item.default_url}>Fuente</StaticRouteLink> : null}
                  <StaticRouteLink href={sampleSearchHref(item.source_id)}>Muestra</StaticRouteLink>
                  <StaticRouteLink href={claimSourceHref(item.source_id)}>Claim</StaticRouteLink>
                </div>
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Bloqueos y remates del tracker." title="Next actions">
          <StaticRouteList
            items={actions.slice(0, 10)}
            renderItem={(action) => (
              <>
                <strong className="sourceActionItem__title">{action.priority || "P"} · {action.title}</strong>
                <span className="sourceActionItem__details">{compactText(action.details, 160)}</span>
                <span className="staticRouteList__meta sourceActionItem__meta">{(action.source_ids || []).join(", ") || action.kind}</span>
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Full public contract for downstream users and contributors." title="Download catalog">
          <StaticRouteList
            items={[
              { id: "catalog", title: "Source catalog JSON", href: "/explorer-sources/data/catalog.json", note: `${formatInt(catalogSummary.sources_total)} sources` },
              { id: "queue", title: "Source scrape queue JSON", href: "/explorer-sources/data/scrape-queue.json", note: `${formatInt(queueItems.length)} queue items` },
              { id: "onboarding", title: "Source onboarding guide", href: `${REPO_URL}/blob/main/docs/etl/source-onboarding.md`, note: "just add-source + gates" },
            ]}
            renderItem={(item) => (
              <>
                <strong className="sourceDownloadItem__title">{item.title}</strong>
                <span className="sourceDownloadItem__meta">{item.note}</span>
                <StaticRouteLink href={item.href}>Abrir</StaticRouteLink>
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="North star de fuentes, no solo lo cargado hoy." title="Ideal coverage">
          <StaticRouteList
            items={idealSources.slice(0, 10)}
            renderItem={(source) => (
              <>
                <strong className="sourceIdealItem__title">{source.name || source.id}</strong>
                <span className="sourceIdealItem__meta">
                  {(source.domains || []).join(", ") || source.scope} · confianza {source.confidence}/5
                </span>
                {source.url ? <StaticRouteLink href={source.url}>Referencia</StaticRouteLink> : null}
              </>
            )}
          />
        </StaticRoutePanel>
      </StaticRoutePanelGrid>
    </main>
  );
}
