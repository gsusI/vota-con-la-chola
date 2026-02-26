"use client";

import { useEffect, useMemo, useState } from "react";

function resolveBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || (process.env.NODE_ENV === "production" ? "/vota-con-la-chola" : "");
}

function withBasePath(path) {
  return `${resolveBasePath()}${path}`;
}

function safeInt(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function safeFloat(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalize(value) {
  return String(value || "").trim().toLowerCase();
}

function normalizeQuery(value) {
  return normalize(value).replace(/\s+/g, " ");
}

function formatInt(value) {
  return safeInt(value).toLocaleString("es-ES");
}

function formatFloat(value) {
  const parsed = safeFloat(value);
  if (parsed === null) {
    return "—";
  }
  return parsed.toLocaleString("es-ES", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });
}

function formatPct(value) {
  const parsed = safeFloat(value);
  if (parsed === null) {
    return "—";
  }
  const sign = parsed > 0 ? "+" : "";
  return `${sign}${parsed.toFixed(2)}%`;
}

function formatDate(value) {
  return String(value || "—");
}

function looksLikeUrl(value) {
  const text = String(value || "").trim().toLowerCase();
  return text.startsWith("http://") || text.startsWith("https://");
}

function deltaClass(value) {
  const parsed = safeFloat(value);
  if (parsed === null) {
    return "pill-muted";
  }
  if (parsed > 0) {
    return "pill-success";
  }
  if (parsed < 0) {
    return "pill-danger";
  }
  return "pill-muted";
}

function formatDelta(value) {
  const parsed = safeFloat(value);
  if (parsed === null) {
    return "—";
  }
  const sign = parsed > 0 ? "+" : "";
  return `${sign}${formatFloat(parsed)}`;
}

function readUrlState() {
  if (typeof window === "undefined") {
    return {
      q: "",
      seriesSource: "",
      eventSource: "",
      domain: "",
      sortSeries: "delta_abs_desc",
      sortAssoc: "delta_abs_desc",
      minAbsDelta: "",
      mode: "series",
    };
  }

  const params = new URLSearchParams(window.location.search);
  return {
    q: String(params.get("q") || ""),
    seriesSource: String(params.get("series_source") || ""),
    eventSource: String(params.get("event_source") || ""),
    domain: String(params.get("domain") || ""),
    sortSeries: String(params.get("sortSeries") || "delta_abs_desc"),
    sortAssoc: String(params.get("sortAssoc") || "delta_abs_desc"),
    minAbsDelta: String(params.get("minAbsDelta") || ""),
    mode: String(params.get("mode") || "series"),
  };
}

function setUrlState(state) {
  if (typeof window === "undefined") {
    return;
  }

  const params = new URLSearchParams();
  if (state.q) params.set("q", state.q);
  if (state.seriesSource) params.set("series_source", state.seriesSource);
  if (state.eventSource) params.set("event_source", state.eventSource);
  if (state.domain) params.set("domain", state.domain);
  if (state.sortSeries !== "delta_abs_desc") params.set("sortSeries", state.sortSeries);
  if (state.sortAssoc !== "delta_abs_desc") params.set("sortAssoc", state.sortAssoc);
  if (state.minAbsDelta) params.set("minAbsDelta", state.minAbsDelta);
  if (state.mode !== "series") params.set("mode", state.mode);

  const nextUrl = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}`;
  window.history.replaceState({}, "", nextUrl);
}

function renderSourceUrl(sourceUrl) {
  const normalized = String(sourceUrl || "").trim();
  if (!normalized) {
    return "—";
  }
  return (
    <a className="tableButton" href={normalized} rel="noopener noreferrer" target="_blank">
      Ver fuente
    </a>
  );
}

function renderSourceCell(source) {
  const sourceUrl = String(source?.url || "").trim();
  const sourceLabel = String(source?.label || "").trim();
  if (looksLikeUrl(sourceUrl)) {
    return (
      <a className="tableButton" href={sourceUrl} rel="noopener noreferrer" target="_blank">
        Ver fuente
      </a>
    );
  }
  if (sourceLabel) {
    return <span className="tileNote">{sourceLabel}</span>;
  }
  return "—";
}

function usePolicyOutcomesPayload() {
  const [state, setState] = useState({
    loading: true,
    error: null,
    data: null,
  });

  useEffect(() => {
    const controller = new AbortController();
    const url = `${resolveBasePath()}/policy-outcomes/data/policy-outcomes.json`;
    setState({ loading: true, error: null, data: null });

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Respuesta no válida: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => setState({ loading: false, error: null, data: payload }))
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

function sortSeriesRows(rows, sortKey, minAbsDelta) {
  const minThreshold = safeFloat(minAbsDelta);
  const filtered = rows.filter((row) => {
    if (minThreshold === null) {
      return true;
    }
    const absDelta = Math.abs(safeFloat(row?.latest_delta) || 0);
    return absDelta >= minThreshold;
  });

  const ordered = [...filtered];
  ordered.sort((left, right) => {
    if (sortKey === "points_desc") {
      return safeInt(right.point_count) - safeInt(left.point_count);
    }
    if (sortKey === "label_asc") {
      return normalize(left.label || "").localeCompare(normalize(right.label || ""));
    }
    if (sortKey === "delta_desc") {
      return (safeFloat(right.latest_delta) || 0) - (safeFloat(left.latest_delta) || 0);
    }
    if (sortKey === "delta_asc") {
      return (safeFloat(left.latest_delta) || 0) - (safeFloat(right.latest_delta) || 0);
    }
    if (sortKey === "recent") {
      return normalize(right.latest_date).localeCompare(normalize(left.latest_date));
    }
    return Math.abs(safeFloat(right.latest_delta) || 0) - Math.abs(safeFloat(left.latest_delta) || 0);
  });
  return ordered;
}

function sortAssociations(rows, sortKey) {
  const ordered = [...rows];
  ordered.sort((left, right) => {
    if (sortKey === "delta_desc") {
      return (safeFloat(right.delta) || 0) - (safeFloat(left.delta) || 0);
    }
    if (sortKey === "delta_asc") {
      return (safeFloat(left.delta) || 0) - (safeFloat(right.delta) || 0);
    }
    if (sortKey === "event_date_desc") {
      return normalize(right.policy_event_date).localeCompare(normalize(left.policy_event_date));
    }
    if (sortKey === "event_date_asc") {
      return normalize(left.policy_event_date).localeCompare(normalize(right.policy_event_date));
    }
    if (sortKey === "series_asc") {
      return normalize(left.indicator_series_label).localeCompare(normalize(right.indicator_series_label));
    }
    return Math.abs(safeFloat(right.delta) || 0) - Math.abs(safeFloat(left.delta) || 0);
  });
  return ordered;
}

export default function PolicyOutcomesPage() {
  const { loading, error, data } = usePolicyOutcomesPayload();
  const [state, setState] = useState(() => readUrlState());

  useEffect(() => {
    setState(readUrlState());
  }, []);

  useEffect(() => {
    setUrlState(state);
  }, [state]);

  const coverage = data?.coverage || {};
  const limitations = data?.limitations || {};
  const seriesSourceOptions = Array.isArray(data?.filters?.series_source_ids) ? data.filters.series_source_ids : [];
  const eventSourceOptions = Array.isArray(data?.filters?.event_source_ids) ? data.filters.event_source_ids : [];
  const domainOptions = Array.isArray(data?.filters?.domains) ? data.filters.domains : [];
  const domainFilter = normalize(state.domain);
  const q = normalizeQuery(state.q);

  const allSeries = useMemo(() => (Array.isArray(data?.series) ? data.series : []), [data?.series]);
  const allAssociations = useMemo(() => (Array.isArray(data?.associations) ? data.associations : []), [data?.associations]);

  const filteredSeries = useMemo(() => {
    const sourceFilter = normalize(state.seriesSource);
    const output = allSeries.filter((row) => {
      const text = normalize(`${row.label} ${row.canonical_key} ${row.domain_label} ${row.domain_key} ${row.territory_label}`);
      if (q && !text.includes(q)) {
        return false;
      }
      if (sourceFilter && normalize(row.source_id) !== sourceFilter) {
        return false;
      }
      if (domainFilter) {
        const rowDomain = normalize(`${row.domain_label} ${row.domain_key}`);
        if (!rowDomain.includes(domainFilter)) {
          return false;
        }
      }
      return true;
    });
    return sortSeriesRows(output, state.sortSeries, state.minAbsDelta);
  }, [allSeries, q, state.seriesSource, state.sortSeries, state.minAbsDelta, domainFilter]);

  const filteredAssociations = useMemo(() => {
    const eventSourceFilter = normalize(state.eventSource);
    const out = allAssociations.filter((row) => {
      const text = normalize(
        `${row.indicator_series_label} ${row.indicator_series_canonical_key} ${row.policy_event_title} ${row.policy_event_id}`,
      );
      if (q && !text.includes(q)) {
        return false;
      }
      if (eventSourceFilter && normalize(row.policy_event_source_id) !== eventSourceFilter) {
        return false;
      }
      if (domainFilter) {
        const rowDomain = normalize(
          `${row.policy_event_domain_label} ${row.policy_event_domain_key} ${row.indicator_domain_label}`,
        );
        if (!rowDomain.includes(domainFilter)) {
          return false;
        }
      }
      if (safeFloat(state.minAbsDelta) !== null) {
        return Math.abs(safeFloat(row.delta) || 0) >= safeFloat(state.minAbsDelta);
      }
      return true;
    });
    return sortAssociations(out, state.sortAssoc);
  }, [allAssociations, q, state.eventSource, state.sortAssoc, state.minAbsDelta, domainFilter]);

  const eventRows = useMemo(() => {
    const eventSourceFilter = normalize(state.eventSource);
    if (!q) {
      return (Array.isArray(data?.policy_events) ? data.policy_events : []).filter((event) => {
        if (!eventSourceFilter) {
          return true;
        }
        return normalize(event.source_id) === eventSourceFilter;
      });
    }
    return (Array.isArray(data?.policy_events) ? data.policy_events : []).filter((event) =>
      (eventSourceFilter ? normalize(event.source_id) === eventSourceFilter : true) &&
      normalize(`${event.policy_event_id} ${event.title} ${event.summary} ${event.domain_label}`).includes(q),
    );
  }, [data?.policy_events, q, state.eventSource]);

  const correlationStatement = [
    "Estas señales son descriptivas y comparables solo como evidencia de co-movimiento temporal.",
    "No se reporta inferencia causal en esta fase por ausencia de vínculos `interventions` y `causal_estimates`.",
    "Sin un diseño de identificación explícito (p. ej. placebo, panel, diferencias en diferencias), no se infiere impacto causal.",
  ];

  if (loading) {
    return (
      <main className="shell">
        <section className="card block">
          <h1>Cargando resultados de política…</h1>
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
            <a href={withBasePath("/policy-outcomes/")}>Reintentar</a>
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
          <p className="sub">No hay snapshot de resultados e indicadores disponible.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">Resultados de políticas</p>
        <h1>Indicadores de resultados e impacto</h1>
        <p className="sub">
          Seguimiento temprano de series de indicadores (Eurostat/INE, BDE, AEMET), con cruces descriptivos
          frente a eventos de política pública.
        </p>
        <div className="chips">
          <span className="chip">Snapshot: {coverage.snapshot_date || data.meta?.snapshot_date || "—"}</span>
          <span className="chip">Series exportadas: {formatInt(coverage.series_loaded || 0)}</span>
          <span className="chip">Puntos: {formatInt(coverage.indicator_points_total || 0)}</span>
          <span className="chip">Eventos: {formatInt(coverage.events_loaded || 0)}</span>
          <span className="chip">Asociaciones: {formatInt(coverage.associations_total || 0)}</span>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Resumen ejecutivo</h2>
        </div>
        <div className="kpiGrid">
          <div className="kpiCard">
            <span className="kpiLabel">Intervenciones</span>
            <span className="kpiValue">{formatInt(coverage.interventions_total || 0)}</span>
            <span className="tileNote">No hay tabla de intervenciones en esta ventana útil.</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Eventos vinculados</span>
            <span className="kpiValue">{formatInt(coverage.events_in_association || 0)}</span>
            <span className="tileNote">Eventos con al menos una asociación.</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Series con asociación</span>
            <span className="kpiValue">{formatInt(coverage.series_in_association || 0)}</span>
            <span className="tileNote">Series incluidas en asociaciones descriptivas.</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Series totales</span>
            <span className="kpiValue">{formatInt(coverage.indicator_series_total || 0)}</span>
            <span className="tileNote">Cobertura total en BD.</span>
          </div>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Guía de interpretación</h2>
        </div>
        <ul className="artifactList">
          {correlationStatement.map((line) => (
            <li key={line}>
              <span>{line}</span>
            </li>
          ))}
        </ul>
        <p className="sub" style={{ marginTop: "10px" }}>
          Estado causal:
          <span className="chip" style={{ marginLeft: "8px" }}>
            {limitations.causal_estimates_available ? "estimación disponible" : "sin estimaciones causales"}
          </span>
        </p>
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
              placeholder="Serie o evento..."
            />
          </div>
          <div className="field">
            <label>Fuente (series)</label>
            <select
              className="textInput"
              value={state.seriesSource}
              onChange={(event) => setState((prev) => ({ ...prev, seriesSource: event.target.value }))}
            >
              <option value="">Todas</option>
              {seriesSourceOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Fuente (eventos)</label>
            <select
              className="textInput"
              value={state.eventSource}
              onChange={(event) => setState((prev) => ({ ...prev, eventSource: event.target.value }))}
            >
              <option value="">Todas</option>
              {eventSourceOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Dominio</label>
            <select
              className="textInput"
              value={state.domain}
              onChange={(event) => setState((prev) => ({ ...prev, domain: event.target.value }))}
            >
              <option value="">Todos</option>
              {domainOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Orden (series)</label>
            <select
              className="textInput"
              value={state.sortSeries}
              onChange={(event) => setState((prev) => ({ ...prev, sortSeries: event.target.value }))}
            >
              <option value="delta_abs_desc">Variación absoluta (desc)</option>
              <option value="delta_desc">Variación (desc)</option>
              <option value="delta_asc">Variación (asc)</option>
              <option value="points_desc">Puntos</option>
              <option value="recent">Último punto</option>
              <option value="label_asc">Etiqueta</option>
            </select>
          </div>
          <div className="field">
            <label>Orden (asociaciones)</label>
            <select
              className="textInput"
              value={state.sortAssoc}
              onChange={(event) => setState((prev) => ({ ...prev, sortAssoc: event.target.value }))}
            >
              <option value="delta_abs_desc">Variación absoluta (desc)</option>
              <option value="delta_desc">Variación (desc)</option>
              <option value="delta_asc">Variación (asc)</option>
              <option value="event_date_desc">Evento (reciente)</option>
              <option value="event_date_asc">Evento (antiguo)</option>
              <option value="series_asc">Serie</option>
            </select>
          </div>
          <div className="field">
            <label>Umbral cambio mínimo (abs)</label>
            <input
              className="textInput"
              value={state.minAbsDelta}
              onChange={(event) => setState((prev) => ({ ...prev, minAbsDelta: event.target.value }))}
              placeholder="0"
              inputMode="decimal"
            />
          </div>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>1) Series de indicadores (outcomes)</h2>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Serie</th>
                <th>Fuente</th>
                <th>Dominio</th>
                <th>Territorio / ámbito</th>
                <th>Último punto</th>
                <th>Cambio reciente</th>
                <th>Último cambio %</th>
                <th>Fuente</th>
              </tr>
            </thead>
            <tbody>
              {filteredSeries.map((row) => {
                const labelParts = [row.domain_label, row.frequency, row.unit].filter(Boolean).join(" · ");
                const latestValue = row.latest_value_text || formatFloat(row.latest_value);
                return (
                  <tr key={row.indicator_series_id}>
                    <td>
                      <strong>{row.label || row.canonical_key}</strong>
                      <div className="tileNote">{labelParts || row.canonical_key}</div>
                    </td>
                    <td>{row.source_id || "—"}</td>
                    <td>{row.domain_label || row.domain_key || "—"}</td>
                    <td>{row.territory_label || row.admin_level_label || "—"}</td>
                    <td>
                      {formatFloat(row.latest_value)} {row.unit ? `(${row.unit})` : ""} · {formatDate(row.latest_date)}
                      <div className="tileNote">
                        {formatDate(row.previous_date)} → {formatDate(row.latest_date)}
                      </div>
                    </td>
                    <td>
                      <span className={`pill ${deltaClass(row.latest_delta)}`}>{formatDelta(row.latest_delta)}</span>
                    </td>
                    <td>{formatPct(row.latest_delta_pct)}</td>
                    <td>{renderSourceCell({ label: row.source_id, url: row.source_url })}</td>
                  </tr>
                );
              })}
              {!filteredSeries.length && (
                <tr>
                  <td className="sub" colSpan={8}>
                    No hay series que cumplan el filtro actual.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>2) Eventos vinculados (descriptivo)</h2>
          <p className="sub">
            "Evento → indicador": compara el último punto previo y el siguiente punto posterior al evento.
          </p>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Evento</th>
                <th>Indicador</th>
                <th>Delta previo/posterior</th>
                <th>Cambio relativo</th>
                <th>Distancia temporal</th>
                <th>Fuente evento</th>
              </tr>
            </thead>
            <tbody>
              {filteredAssociations.map((row) => (
                <tr key={`${row.policy_event_id}-${row.indicator_series_id}-${row.pre_point_date}`}>
                  <td>
                    <div>
                      <strong>{formatDate(row.policy_event_date)}</strong>
                    </div>
                    <div className="tileNote">{row.policy_event_title || row.policy_event_id}</div>
                    <div className="tileNote">{row.policy_event_domain_label || row.policy_event_domain_key || "—"}</div>
                  </td>
                  <td>
                    <div>{row.indicator_series_label || row.indicator_series_canonical_key}</div>
                    <div className="tileNote">{row.indicator_unit ? `Unidad: ${row.indicator_unit}` : "—"}</div>
                  </td>
                  <td>
                    <div>
                      {formatDate(row.pre_point_date)}: {formatFloat(row.pre_value)}
                    </div>
                    <div>
                      {formatDate(row.post_point_date)}: {formatFloat(row.post_value)}
                    </div>
                    <div>
                      Cambio:
                      <span className={`pill ${deltaClass(row.delta)}`} style={{ marginLeft: "6px" }}>
                        {formatDelta(row.delta)}
                      </span>
                    </div>
                  </td>
                  <td>{formatPct(row.delta_pct)}</td>
                  <td>
                    <div>Antes: {formatInt(row.pre_gap_days)} días</div>
                    <div>Después: {formatInt(row.post_gap_days)} días</div>
                  </td>
                  <td>{renderSourceCell({ label: row.policy_event_source_id, url: row.policy_event_source_url })}</td>
                </tr>
              ))}
              {!filteredAssociations.length && (
                <tr>
                  <td className="sub" colSpan={6}>
                    No hay asociaciones descriptivas para los filtros seleccionados.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>3) Eventos de política más recientes</h2>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Evento</th>
                <th>Resumen</th>
                <th>Fuente</th>
                <th>Territorio</th>
                <th>Series asociadas</th>
              </tr>
            </thead>
            <tbody>
              {eventRows.slice(0, 120).map((event) => (
                <tr key={event.policy_event_id}>
                  <td>
                    <div>
                      <strong>{formatDate(event.event_date)}</strong>
                    </div>
                    <div className="tileNote">{event.policy_event_id}</div>
                    <div className="tileNote">{event.title ? event.title : event.summary || "—"}</div>
                  </td>
                  <td className="tileNote">{event.summary || "—"}</td>
                  <td>{renderSourceUrl(event.source_url)}</td>
                  <td>{event.territory_label || event.institution_name || event.admin_level_label || "—"}</td>
                  <td>{formatInt(event.associated_series_count || 0)}</td>
                </tr>
              ))}
              {!eventRows.length && (
                <tr>
                  <td className="sub" colSpan={5}>
                    No hay eventos en el rango del snapshot.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
