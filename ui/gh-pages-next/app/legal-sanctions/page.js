"use client";

import { useEffect, useMemo, useState } from "react";

function resolveBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || (process.env.NODE_ENV === "production" ? "/vota-con-la-chola" : "");
}

function withBasePath(path) {
  return `${resolveBasePath()}${path}`;
}

function toInt(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.trunc(parsed) : 0;
}

function toFloat(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatInt(value) {
  return toInt(value).toLocaleString("es-ES");
}

function formatMoney(value) {
  return toFloat(value).toLocaleString("es-ES", { style: "currency", currency: "EUR", maximumFractionDigits: 2 });
}

function formatFloat(value, digits = 2) {
  return toFloat(value).toLocaleString("es-ES", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatDelta(value, asPercent = false) {
  if (!Number.isFinite(Number(value))) {
    return "—";
  }
  const n = Number(value);
  const sign = n > 0 ? "+" : "";
  return `${sign}${formatFloat(n, asPercent ? 2 : 2)}${asPercent ? "%" : ""}`;
}

function formatPercent(value) {
  if (!Number.isFinite(Number(value))) {
    return "—";
  }
  return `${formatFloat(Number(value), 2)}%`;
}

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\\u0300-\\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function normalizeQuery(value) {
  return normalize(value).replace(/\\s+/g, " ").trim();
}

function readUrlState() {
  if (typeof window === "undefined") {
    return {
      q: "",
      relation: "",
      infractionType: "",
      sanctionSource: "",
      sourceSystem: "",
      kpi: "",
      periodGranularity: "",
      periodDate: "",
      municipalStatus: "",
      municipalQ: "",
    };
  }
  const params = new URLSearchParams(window.location.search);
  return {
    q: String(params.get("q") || ""),
    relation: String(params.get("relation") || ""),
    infractionType: String(params.get("infraction_type") || ""),
    sanctionSource: String(params.get("source") || ""),
    sourceSystem: String(params.get("source_system") || ""),
    kpi: String(params.get("kpi") || ""),
    periodGranularity: String(params.get("granularity") || ""),
    periodDate: String(params.get("period_date") || ""),
    municipalStatus: String(params.get("municipal_status") || ""),
    municipalQ: String(params.get("municipal_q") || ""),
  };
}

function useLegalSanctionsPayload() {
  const [state, setState] = useState({ loading: true, error: null, data: null });

  useEffect(() => {
    const controller = new AbortController();
    const url = `${resolveBasePath()}/legal-sanctions/data/legal-sanctions.json`;

    setState({ loading: true, error: null, data: null });
    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Respuesta no válida: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        setState({ loading: false, error: null, data: payload });
      })
      .catch((error) => {
        if (error.name === "AbortError") {
          return;
        }
        setState({ loading: false, error: error.message || String(error), data: null });
      });

    return () => controller.abort();
  }, []);

  return state;
}

function matchesSearch(row, fields, query) {
  if (!query) {
    return true;
  }
  const haystack = fields
    .map((value) => normalize(value))
    .filter(Boolean)
    .join(" ");
  return haystack.includes(query);
}

function setUrlState(state) {
  if (typeof window === "undefined") {
    return;
  }
  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.relation) params.set("relation", state.relation);
  if (state.infractionType) params.set("infraction_type", state.infractionType);
  if (state.sanctionSource) params.set("source", state.sanctionSource);
  if (state.sourceSystem) params.set("source_system", state.sourceSystem);
  if (state.kpi) params.set("kpi", state.kpi);
  if (state.periodGranularity) params.set("granularity", state.periodGranularity);
  if (state.periodDate) params.set("period_date", state.periodDate);
  if (state.municipalStatus) params.set("municipal_status", state.municipalStatus);
  if (state.municipalQ) params.set("municipal_q", state.municipalQ);
  const nextUrl = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}`;
  window.history.replaceState({}, "", nextUrl);
}

export default function LegalSanctionsPage() {
  const { loading, error, data } = useLegalSanctionsPayload();
  const [state, setState] = useState(() => readUrlState());

  useEffect(() => {
    setState(readUrlState());
  }, []);

  useEffect(() => {
    setUrlState(state);
  }, [state]);

  if (loading) {
    return (
      <main className="shell">
        <section className="card block">
          <h1>Cargando legal + sanciones…</h1>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main className="shell">
        <section className="card block">
          <h1>No se pudo cargar el snapshot</h1>
          <p className="sub">{error}</p>
          <p className="sub">
            <a href={withBasePath("/legal-sanctions/?")}>Reintentar</a>
          </p>
        </section>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="shell">
        <section className="card block">
          <h1>Sin datos</h1>
          <p className="sub">No se encontró el snapshot de monitorización jurídica.</p>
        </section>
      </main>
    );
  }

  const query = normalizeQuery(state.q);
  const legalGraph = data.legal_graph || {};
  const infractionNetwork = data.infraction_network || {};
  const volume = data.sanction_volume_monitoring || {};
  const kpiRows = data.procedural_kpi_drift || [];
  const municipal = data.municipal_monitoring || {};
  const municipalSummary = municipal.summary || {};
  const citySummary = municipal.city_summary || [];
  const ordinanceRows = municipal.ordinance_rows || [];
  const responsibility = data.responsibility_summary || {};
  const liberty = data.liberty_restriction_monitoring || {};
  const sourceFilters = data.filters || {};

  const legalNodes = useMemo(() => (Array.isArray(legalGraph.nodes) ? legalGraph.nodes : []), [legalGraph.nodes]);
  const legalEdges = useMemo(() => (Array.isArray(legalGraph.edges) ? legalGraph.edges : []), [legalGraph.edges]);
  const infractionTypes = useMemo(
    () => (Array.isArray(infractionNetwork.infraction_types) ? infractionNetwork.infraction_types : []),
    [infractionNetwork.infraction_types],
  );
  const infractionMappings = useMemo(
    () => (Array.isArray(infractionNetwork.mappings) ? infractionNetwork.mappings : []),
    [infractionNetwork.mappings],
  );
  const volumeSeries = useMemo(
    () => (Array.isArray(volume.series) ? volume.series : []),
    [volume.series],
  );
  const sourceVolumeRows = useMemo(
    () => (Array.isArray(volume.source_totals) ? volume.source_totals : []),
    [volume.source_totals],
  );
  const volumeSources = useMemo(() => (Array.isArray(volume.sources) ? volume.sources : []), [volume.sources]);
  const volumePeriods = useMemo(() => (Array.isArray(volume.periods) ? volume.periods : []), [volume.periods]);
  const kpiRowsTotal = useMemo(() => (Array.isArray(kpiRows) ? kpiRows : []), [kpiRows]);

  const relationOptions = useMemo(() => legalGraph.relation_types || sourceFilters.relation_types || [], [legalGraph.relation_types, sourceFilters.relation_types]);
  const sourceSystemOptions = useMemo(() => sourceFilters.source_ids || [], [sourceFilters.source_ids]);
  const infractionTypeOptions = useMemo(() => sourceFilters.infraction_type_ids || [], [sourceFilters.infraction_type_ids]);
  const kpiOptions = useMemo(() => sourceFilters.kpi_ids || [], [sourceFilters.kpi_ids]);

  const filteredNodes = useMemo(
    () =>
      legalNodes.filter((row) =>
        matchesSearch(
          row,
          [row.norm_id, row.boe_id, row.title, row.scope, row.topic_hint, row.effective_date, row.published_date],
          query,
        ),
      ),
    [legalNodes, query],
  );

  const filteredEdges = useMemo(() => {
    return legalEdges.filter((row) => {
      if (state.relation && normalize(row.relation_type) !== normalize(state.relation)) {
        return false;
      }
      return matchesSearch(
        row,
        [
          row.source_norm_id,
          row.source_norm_boe_id,
          row.related_norm_id,
          row.related_norm_boe_id,
          row.source_norm_title,
          row.related_norm_title,
          row.relation_type,
          row.relation_scope,
          row.evidence_quote,
        ],
        query,
      );
    });
  }, [legalEdges, state.relation, query]);

  const filteredInfractionTypes = useMemo(
    () =>
      infractionTypes.filter((row) => {
        if (state.infractionType && String(row.infraction_type_id || row.infraction_label) !== state.infractionType) {
          return false;
        }
        return matchesSearch(
          row,
          [row.infraction_type_id, row.infraction_label, row.infraction_domain, row.canonical_unit],
          query,
        );
      }),
    [infractionTypes, state.infractionType, query],
  );

  const filteredMappings = useMemo(
    () =>
      infractionMappings.filter((row) => {
        const infMatch = state.infractionType ? String(row.infraction_type_id) === state.infractionType : true;
        const sourceMatch = state.sourceSystem ? normalize(row.source_system) === normalize(state.sourceSystem) : true;
        if (!infMatch || !sourceMatch) {
          return false;
        }
        return matchesSearch(
          row,
          [row.mapping_key, row.norm_id, row.fragment_id, row.source_code, row.source_label, row.source_system],
          query,
        );
      }),
    [infractionMappings, state.infractionType, state.sourceSystem, query],
  );

  const filteredVolumeSeries = useMemo(
    () =>
      volumeSeries.filter((row) => {
        if (state.sanctionSource && row.sanction_source_id !== state.sanctionSource) return false;
        if (state.periodGranularity && row.period_granularity !== state.periodGranularity) return false;
        if (state.periodDate && row.period_date !== state.periodDate) return false;
        return matchesSearch(
          row,
          [row.sanction_source_id, row.source_label, row.admin_scope, row.territory_scope, row.territory_name],
          query,
        );
      }),
    [volumeSeries, state.sanctionSource, state.periodGranularity, state.periodDate, query],
  );

  const filteredKpiRows = useMemo(
    () =>
      kpiRowsTotal.filter((row) => {
        if (state.kpi && row.kpi_id !== state.kpi) return false;
        if (state.sanctionSource && row.sanction_source_id !== state.sanctionSource) return false;
        return matchesSearch(row, [row.kpi_id, row.kpi_label, row.territory_name, row.source_label], query);
      }),
    [kpiRowsTotal, state.kpi, state.sanctionSource, query],
  );

  const filteredMunicipalRows = useMemo(
    () =>
      ordinanceRows.filter((row) => {
        if (state.municipalStatus && normalize(row.ordinance_status) !== normalize(state.municipalStatus)) {
          return false;
        }
        return matchesSearch(
          row,
          [row.city_name, row.province_name, row.ordinance_label, row.ordinance_status, row.publication_date],
          normalizeQuery(state.municipalQ),
        );
      }),
    [ordinanceRows, state.municipalStatus, state.municipalQ],
  );

  const periodOptions = useMemo(() => {
    const map = new Map();
    for (const item of volumePeriods) {
      const gran = String(item.period_granularity || "");
      const date = String(item.period_date || "");
      if (!gran || !date) {
        continue;
      }
      map.set(`${gran}::${date}`, true);
    }
    return Array.from(map.keys())
      .map((value) => {
        const [granularity, periodDate] = value.split("::");
        return { granularity, periodDate, label: `${granularity} · ${periodDate}` };
      })
      .sort((a, b) => `${a.granularity} ${a.periodDate}`.localeCompare(`${b.granularity} ${b.periodDate}`));
  }, [volumePeriods]);

  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">Legal + sanciones</p>
        <h1>Monitor jurídico y de ejecución sancionadora</h1>
        <p className="sub">
          Conecta normas, vínculos de texto, tipos de infracción, volúmenes de sanciones y evolución de KPIs
          procedimentales. También incluye monitor municipal y restricciones de derechos con trazabilidad pública.
        </p>
        <div className="chips">
          <span className="chip">Snapshot: {data.snapshot_date || "—"}</span>
          <span className="chip">Nodos normativos: {formatInt(legalGraph.node_count || 0)}</span>
          <span className="chip">Aristas de línea: {formatInt(legalGraph.edge_count || 0)}</span>
          <span className="chip">Tipos de infracción: {formatInt(filteredInfractionTypes.length)}</span>
          <span className="chip">Total asignaciones: {formatInt(filteredMappings.length)}</span>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Resumen ejecutivo</h2>
        </div>
        <div className="kpiGrid">
          <div className="kpiCard">
            <span className="kpiLabel">Responsabilidad (filas con evidencia principal)</span>
            <span className="kpiValue">
              {formatInt(responsibility.rows_with_primary_evidence || 0)} / {formatInt(responsibility.rows_total || 0)}
            </span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Observaciones de sanción</span>
            <span className="kpiValue">{formatInt(volumeSeries.length)}</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">KPIs procedimentales</span>
            <span className="kpiValue">{formatInt(kpiRowsTotal.length)}</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Ordenanzas municipales</span>
            <span className="kpiValue">{formatInt(ordinanceRows.length)}</span>
            <span className="tileNote">
              Normalizadas: {formatInt(municipalSummary.normalized_ordinances || 0)} / Bloqueadas:{" "}
              {formatInt(municipalSummary.blocked_ordinances || 0)}
            </span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Libertad restringida</span>
            <span className="kpiValue">
              {liberty.enabled ? "Disponibilidad" : "No activa"}
            </span>
            <span className="tileNote">Filas: {formatInt(liberty.rows || 0)}</span>
          </div>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Filtros</h2>
        </div>
        <div className="filterGrid">
          <div className="field">
            <label>Buscar</label>
            <input
              className="textInput"
              value={state.q}
              onChange={(event) => setState((prev) => ({ ...prev, q: event.target.value }))}
              placeholder="BOE, título, relación, infracción, ámbito..."
            />
          </div>
          <div className="field">
            <label>Tipo de relación legal</label>
            <select
              className="textInput"
              value={state.relation}
              onChange={(event) => setState((prev) => ({ ...prev, relation: event.target.value }))}
            >
              <option value="">Todas</option>
              {relationOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Tipo de infracción</label>
            <select
              className="textInput"
              value={state.infractionType}
              onChange={(event) => setState((prev) => ({ ...prev, infractionType: event.target.value }))}
            >
              <option value="">Todos</option>
              {infractionTypeOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Fuente de sanción</label>
            <select
              className="textInput"
              value={state.sanctionSource}
              onChange={(event) => setState((prev) => ({ ...prev, sanctionSource: event.target.value }))}
            >
              <option value="">Todos</option>
              {sourceFilters.source_ids?.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>KPIs (ID)</label>
            <select
              className="textInput"
              value={state.kpi}
              onChange={(event) => setState((prev) => ({ ...prev, kpi: event.target.value }))}
            >
              <option value="">Todos</option>
              {kpiOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Sistema de origen (mapeo)</label>
            <select
              className="textInput"
              value={state.sourceSystem}
              onChange={(event) => setState((prev) => ({ ...prev, sourceSystem: event.target.value }))}
            >
              <option value="">Todos</option>
              {sourceSystemOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Granularidad temporal</label>
            <select
              className="textInput"
              value={state.periodGranularity}
              onChange={(event) =>
                setState((prev) => ({
                  ...prev,
                  periodGranularity: event.target.value,
                  periodDate: "",
                }))
              }
            >
              <option value="">Todas</option>
              {Array.from(new Set(volumePeriods.map((row) => row.period_granularity || "")))
                .filter(Boolean)
                .sort()
                .map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
            </select>
          </div>
          <div className="field">
            <label>Periodo</label>
            <select
              className="textInput"
              value={state.periodDate}
              onChange={(event) => setState((prev) => ({ ...prev, periodDate: event.target.value }))}
            >
              <option value="">Todos</option>
              {periodOptions
                .filter((item) => !state.periodGranularity || item.granularity === state.periodGranularity)
                .map((item) => (
                  <option key={`${item.granularity}::${item.periodDate}`} value={item.periodDate}>
                    {item.label}
                  </option>
                ))}
            </select>
          </div>
          <div className="field">
            <label>Estado municipal</label>
            <select
              className="textInput"
              value={state.municipalStatus}
              onChange={(event) => setState((prev) => ({ ...prev, municipalStatus: event.target.value }))}
            >
              <option value="">Todos</option>
              {(municipalSummary.status_counts || []).map((row) => (
                <option key={row.status} value={row.status}>
                  {row.status} ({row.total || 0})
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Buscar ordenanzas</label>
            <input
              className="textInput"
              value={state.municipalQ}
              onChange={(event) => setState((prev) => ({ ...prev, municipalQ: event.target.value }))}
              placeholder="Ciudad, provincia, etiqueta..."
            />
          </div>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Grafo jurídico</h2>
        </div>
        <div className="kpiGrid">
          <div className="kpiCard">
            <span className="kpiLabel">Nodos mostrados</span>
            <span className="kpiValue">{formatInt(filteredNodes.length)}</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Relaciones mostradas</span>
            <span className="kpiValue">{formatInt(filteredEdges.length)}</span>
          </div>
        </div>
        <div className="twoCols" style={{ marginTop: "12px" }}>
          <div className="tableWrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Norma origen</th>
                  <th>BOE</th>
                  <th>Relación</th>
                  <th>Norma destino</th>
                  <th>BOE destino</th>
                  <th>Fecha evidencia</th>
                </tr>
              </thead>
              <tbody>
                {filteredEdges.length === 0 ? (
                  <tr>
                    <td colSpan={6}>No hay aristas con los filtros actuales.</td>
                  </tr>
                ) : (
                  filteredEdges.map((row) => (
                    <tr key={`${row.lineage_edge_id}-${row.source_norm_id}-${row.related_norm_id}`}>
                      <td>{row.source_norm_id}</td>
                      <td>{row.source_norm_boe_id || "—"}</td>
                      <td>
                        <span className="pill pill-muted">{row.relation_type || "—"}</span>
                      </td>
                      <td>{row.related_norm_id || "—"}</td>
                      <td>{row.related_norm_boe_id || "—"}</td>
                      <td>{row.evidence_date || "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          <div className="tableWrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Norma</th>
                  <th>BOE</th>
                  <th>Ámbito</th>
                  <th>Publicada</th>
                  <th>Fragmentos</th>
                </tr>
              </thead>
              <tbody>
                {filteredNodes.length === 0 ? (
                  <tr>
                    <td colSpan={5}>No hay normas con los filtros actuales.</td>
                  </tr>
                ) : (
                  filteredNodes.map((row) => (
                    <tr key={row.norm_id}>
                      <td>{row.title || row.norm_id}</td>
                      <td>{row.boe_id || "—"}</td>
                      <td>{row.scope || "—"}</td>
                      <td>{row.published_date || "—"}</td>
                      <td>{toInt(row.fragments_total)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Red de infracciones y responsabilidades</h2>
        </div>
        <div className="tableWrap" style={{ marginBottom: "12px" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Tipo de infracción</th>
                <th>Dominio</th>
                <th>Unidades</th>
                <th>Mapeos</th>
                <th>Normas cubiertas</th>
                <th>Fragmentos</th>
                <th>Expedientes</th>
                <th>Importe</th>
              </tr>
            </thead>
            <tbody>
              {filteredInfractionTypes.length === 0 ? (
                <tr>
                  <td colSpan={8}>Sin tipos de infracción para los filtros.</td>
                </tr>
              ) : (
                filteredInfractionTypes.map((row) => (
                  <tr key={row.infraction_type_id}>
                    <td>{row.infraction_label || row.infraction_type_id}</td>
                    <td>{row.infraction_domain || "—"}</td>
                    <td>{row.canonical_unit || "—"}</td>
                    <td>{formatInt(row.mapping_rows || 0)}</td>
                    <td>{formatInt(row.norms_covered || 0)}</td>
                    <td>{formatInt(row.fragments_covered || 0)}</td>
                    <td>{formatInt(row.obs_expediente_total || 0)}</td>
                    <td>{formatMoney(row.obs_importe_total_eur || 0)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Tipo</th>
                <th>Fuente/sistema</th>
                <th>Código</th>
                <th>Norma</th>
                <th>Fragmento</th>
                <th>Conf.</th>
                <th>Vía</th>
              </tr>
            </thead>
            <tbody>
              {filteredMappings.length === 0 ? (
                <tr>
                  <td colSpan={7}>Sin mapeos con los filtros actuales.</td>
                </tr>
              ) : (
                filteredMappings.map((row) => (
                  <tr key={row.mapping_id}>
                    <td>{row.infraction_label || row.infraction_type_id}</td>
                    <td>{row.source_system || row.source_label || "—"}</td>
                    <td>{row.source_code || "—"}</td>
                    <td>{row.norm_id || "—"}</td>
                    <td>{row.fragment_id || "—"}</td>
                    <td>{formatFloat(row.confidence, 4)}</td>
                    <td>
                      {row.source_url ? (
                        <a href={row.source_url} target="_blank" rel="noreferrer">
                          evidencia
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Monitoreo de volumen por período</h2>
          <p className="tileNote">Deltas calculadas frente al punto anterior de la misma serie territorial-fuente.</p>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Fuente</th>
                <th>Ámbito / Territorio</th>
                <th>Periodo</th>
                <th>Expedientes</th>
                <th>Importe total</th>
                <th>Delta exped.</th>
                <th>Delta importe %</th>
                <th>Recurso presentado</th>
                <th>Recurso desestimado</th>
              </tr>
            </thead>
            <tbody>
              {filteredVolumeSeries.length === 0 ? (
                <tr>
                  <td colSpan={9}>Sin observaciones de volumen para los filtros.</td>
                </tr>
              ) : (
                filteredVolumeSeries.map((row) => (
                  <tr key={`${row.sanction_source_id}-${row.period_granularity}-${row.period_date}-${row.territory_name}`}>
                    <td>{row.source_label || row.sanction_source_id}</td>
                    <td>
                      {row.admin_scope || "—"}
                      {row.territory_name ? ` · ${row.territory_name}` : ""}
                    </td>
                    <td>
                      {row.period_granularity} {row.period_date}
                    </td>
                    <td>{formatInt(row.expediente_count || 0)}</td>
                    <td>{formatMoney(row.importe_total_eur || 0)}</td>
                    <td>{formatDelta(row.delta_expediente_count)}</td>
                    <td>{formatDelta(row.delta_importe_total_pct, true)}</td>
                    <td>{formatInt(row.recurso_presentado_count || 0)}</td>
                    <td>{formatInt(row.recurso_desestimado_count || 0)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Derivas de KPIs procesales</h2>
          <p className="tileNote">Variación temporal por norma organizativa y fuente.</p>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>KPI</th>
                <th>Dirección objetivo</th>
                <th>Fuente</th>
                <th>Territorio</th>
                <th>Periodo</th>
                <th>Valor</th>
                <th>Delta</th>
                <th>Delta %</th>
                <th>Numerador</th>
                <th>Denominador</th>
              </tr>
            </thead>
            <tbody>
              {filteredKpiRows.length === 0 ? (
                <tr>
                  <td colSpan={10}>Sin KPIs con los filtros actuales.</td>
                </tr>
              ) : (
                filteredKpiRows.map((row) => (
                  <tr key={`${row.kpi_id}-${row.sanction_source_id}-${row.territory_id}-${row.period_granularity}-${row.period_date}`}>
                    <td>
                      {row.kpi_label || row.kpi_id}
                      <br />
                      <span className="tileNote">{row.kpi_id}</span>
                    </td>
                    <td>{row.target_direction || "—"}</td>
                    <td>{row.source_label || row.sanction_source_id}</td>
                    <td>{row.territory_name || "—"}</td>
                    <td>{row.period_granularity} {row.period_date}</td>
                    <td>{formatFloat(row.value, 4)}</td>
                    <td>{formatDelta(row.delta_value, false)}</td>
                    <td>{formatDelta(row.delta_value_pct, true)}</td>
                    <td>{formatFloat(row.numerator, 4)}</td>
                    <td>{formatFloat(row.denominator, 4)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Órdenes y régimen municipal</h2>
        </div>
        <div className="kpiGrid">
          <div className="kpiCard">
            <span className="kpiLabel">Órdenes totales</span>
            <span className="kpiValue">{formatInt(municipalSummary.total_ordinances || 0)}</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Normalizadas</span>
            <span className="kpiValue">{formatInt(municipalSummary.normalized_ordinances || 0)}</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Identificadas</span>
            <span className="kpiValue">{formatInt(municipalSummary.identified_ordinances || 0)}</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Bloqueadas</span>
            <span className="kpiValue">{formatInt(municipalSummary.blocked_ordinances || 0)}</span>
          </div>
        </div>
        <div className="tableWrap" style={{ marginTop: "12px" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Ciudad</th>
                <th>Provincia</th>
                <th>Órdenes</th>
                <th>Normalizadas</th>
                <th>Identificadas</th>
                <th>Bloqueadas</th>
              </tr>
            </thead>
            <tbody>
              {citySummary.length === 0 ? (
                <tr>
                  <td colSpan={6}>No hay resumen territorial.</td>
                </tr>
              ) : (
                citySummary.map((row) => (
                  <tr key={`${row.city_name}-${row.province_name}`}>
                    <td>{row.city_name || "—"}</td>
                    <td>{row.province_name || "—"}</td>
                    <td>{formatInt(row.ordinances_total || 0)}</td>
                    <td>{formatInt(row.normalized_total || 0)}</td>
                    <td>{formatInt(row.identified_total || 0)}</td>
                    <td>{formatInt(row.blocked_total || 0)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="tableWrap" style={{ marginTop: "12px" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Ciudad</th>
                <th>Provincia</th>
                <th>Ordenanza</th>
                <th>Estado</th>
                <th>Fecha publicación</th>
                <th>Frags</th>
                <th>Mapeadas</th>
                <th>URL</th>
              </tr>
            </thead>
            <tbody>
              {filteredMunicipalRows.length === 0 ? (
                <tr>
                  <td colSpan={8}>Sin ordenanzas con filtros actuales.</td>
                </tr>
              ) : (
                filteredMunicipalRows.map((row) => (
                  <tr key={row.ordinance_id}>
                    <td>{row.city_name || "—"}</td>
                    <td>{row.province_name || "—"}</td>
                    <td>{row.ordinance_label || "—"}</td>
                    <td>{row.ordinance_status || "—"}</td>
                    <td>{row.publication_date || "—"}</td>
                    <td>{formatInt(row.fragments_total || 0)}</td>
                    <td>{formatInt(row.mapped_fragment_rows || 0)} / {formatInt(row.mapped_norm_fragments || 0)}</td>
                    <td>
                      {row.ordinance_url ? (
                        <a href={row.ordinance_url} target="_blank" rel="noreferrer">
                          abrir
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Restricción de libertades: señal</h2>
          <p className="tileNote">Vista mínima para enlazar cambios normativos con observaciones de impacto en derechos.</p>
        </div>
        <div className="kpiGrid">
          <div className="kpiCard">
            <span className="kpiLabel">Activo</span>
            <span className="kpiValue">{liberty.enabled ? "Sí" : "No"}</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Observaciones</span>
            <span className="kpiValue">{formatInt(liberty.rows || 0)}</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">IRLC medio</span>
            <span className="kpiValue">
              {typeof liberty.avg_irlc_score === "number" ? formatFloat(liberty.avg_irlc_score, 4) : "—"}
            </span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Confianza media</span>
            <span className="kpiValue">
              {typeof liberty.avg_confidence === "number" ? formatFloat(liberty.avg_confidence, 4) : "—"}
            </span>
          </div>
        </div>
      </section>
    </main>
  );
}
