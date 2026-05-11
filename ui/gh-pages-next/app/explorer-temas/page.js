import {
  compactText,
  explorerRows,
  explorerTableMeta,
  formatDate,
  formatInt,
  readPublicJson,
  rowIdentityValue,
  rowPreviewValue,
} from "../static-snapshot.mjs";
import {
  StaticRouteHero,
  StaticRouteLink,
  StaticRouteList,
  StaticRouteMetrics,
  StaticRoutePanel,
  StaticRoutePanelGrid,
} from "../static-route-components";

export const metadata = {
  title: "Temas | Vota Con La Chola",
  description: "Vista estática de temas, posiciones y evidencias del corte público.",
};

export default function ExplorerTemasPage() {
  const snapshot = readPublicJson("legacy/explorer-temas/data/temas-preview.json", { tables: {} });
  const topicSets = explorerRows(snapshot, "topic_sets");
  const topics = explorerRows(snapshot, "topics");
  const positions = explorerRows(snapshot, "topic_positions");
  const evidence = explorerRows(snapshot, "topic_evidence");
  const tableNames = ["topic_sets", "topics", "topic_set_topics", "topic_positions", "topic_evidence", "topic_evidence_reviews"];

  return (
    <main className="shell staticRoute staticRouteTopics">
      <StaticRouteHero
        actions={[
          { href: "/citizen/", label: "Abrir vista ciudadana" },
          { href: "/political-positions/", label: "Ver posiciones" },
        ]}
        eyebrow="Corte público"
        meta={[
          { label: "Generado", value: formatDate(snapshot?.meta?.generated_at) },
          { label: "Modo", value: "sin API runtime" },
        ]}
        summary="Temas, posiciones y evidencias ya materializadas. Esta página no llama a /api: lo que ves sale del JSON estático publicado."
        title="Temas y evidencia"
      />

      <StaticRouteMetrics
        metrics={[
          { label: "Conjuntos de temas", value: formatInt(explorerTableMeta(snapshot, "topic_sets").total) },
          { label: "Temas", value: formatInt(explorerTableMeta(snapshot, "topics").total) },
          { label: "Posiciones", value: formatInt(explorerTableMeta(snapshot, "topic_positions").total) },
          { label: "Evidencias", value: formatInt(explorerTableMeta(snapshot, "topic_evidence").total) },
        ]}
      />

      <StaticRoutePanelGrid>
        <StaticRoutePanel note="Universos de temas publicados." title="Conjuntos activos">
          <StaticRouteList
            items={topicSets.slice(0, 6)}
            renderItem={(row) => (
              <>
                <strong>{row.label || rowPreviewValue(row, "name")}</strong>
                <span>{compactText(rowPreviewValue(row, "description"), 140)}</span>
                <span className="staticRouteList__meta">ID {rowIdentityValue(row)} · {rowPreviewValue(row, "institution_id")}</span>
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Primeras etiquetas canónicas disponibles." title="Temas">
          <StaticRouteList
            items={topics.slice(0, 8)}
            renderItem={(row) => (
              <>
                <strong>{row.label || rowPreviewValue(row, "label")}</strong>
                <span>{compactText(rowPreviewValue(row, "canonical_key"), 120)}</span>
                <span className="staticRouteList__meta">Tema {rowIdentityValue(row)}</span>
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Últimos registros exportados del corte." title="Evidencia trazable">
          <StaticRouteList
            items={evidence.slice(0, 8)}
            renderItem={(row) => (
              <>
                <strong>{rowPreviewValue(row, "title") || row.label}</strong>
                <span>{rowPreviewValue(row, "person_id")} · {formatDate(rowPreviewValue(row, "evidence_date"))}</span>
                {rowPreviewValue(row, "source_url") ? <StaticRouteLink href={rowPreviewValue(row, "source_url")}>Fuente oficial</StaticRouteLink> : null}
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Tablas listas para inspección estática." title="Cobertura de tablas">
          <StaticRouteList
            items={tableNames.map((name) => ({ id: name, name, meta: explorerTableMeta(snapshot, name) }))}
            renderItem={(row) => (
              <>
                <strong>{row.name}</strong>
                <span>Total {formatInt(row.meta.total)} · exportado {formatInt(row.meta.returned)}</span>
              </>
            )}
          />
        </StaticRoutePanel>

        <StaticRoutePanel note="Muestra de posiciones calculadas." title="Posiciones">
          <StaticRouteList
            items={positions.slice(0, 8)}
            renderItem={(row) => (
              <>
                <strong>{row.label || rowPreviewValue(row, "person_id")}</strong>
                <span>{rowPreviewValue(row, "computed_method")} · última evidencia {formatDate(rowPreviewValue(row, "last_evidence_date"))}</span>
                <span className="staticRouteList__meta">Posición {rowIdentityValue(row)} · {rowPreviewValue(row, "territory_id")}</span>
              </>
            )}
          />
        </StaticRoutePanel>
      </StaticRoutePanelGrid>
    </main>
  );
}
