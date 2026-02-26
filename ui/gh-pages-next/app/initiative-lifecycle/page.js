"use client";

import { useEffect, useMemo, useState } from "react";

function resolveBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || (process.env.NODE_ENV === "production" ? "/vota-con-la-chola" : "");
}

function toInt(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function formatInt(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return Number(value).toLocaleString("es-ES");
}

function formatDate(value) {
  return value ? String(value) : "—";
}

function formatDays(value) {
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return "—";
  }
  return Number.isFinite(parsed) ? String(Math.round(parsed)) : "—";
}

function toPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${Number(value).toFixed(2)}%`;
}

function confidenceClass(bucket) {
  if (bucket === "alta") {
    return "pill-success";
  }
  if (bucket === "media") {
    return "pill-warning";
  }
  if (bucket === "baja") {
    return "pill-danger";
  }
  return "pill-muted";
}

function outcomeClass(outcome) {
  if (outcome === "aprobada") {
    return "pill-success";
  }
  if (outcome === "rechazada") {
    return "pill-danger";
  }
  if (outcome === "empate") {
    return "pill-warning";
  }
  return "pill-muted";
}

function readUrlState() {
  if (typeof window === "undefined") {
    return { initiativeId: "", sort: "votes_desc", source: "", committee: "", legislature: "", status: "", confidence: "", method: "", q: "", confidenceMode: "all" };
  }

  const query = new URLSearchParams(window.location.search);
  return {
    initiativeId: String(query.get("initiative") || ""),
    sort: String(query.get("sort") || "votes_desc"),
    source: String(query.get("source") || ""),
    committee: String(query.get("committee") || ""),
    legislature: String(query.get("legislature") || ""),
    status: String(query.get("status") || ""),
    confidence: String(query.get("confidence") || ""),
    method: String(query.get("method") || ""),
    q: String(query.get("q") || ""),
    confidenceMode: String(query.get("confidenceMode") || "all"),
  };
}

function useLifecyclePayload() {
  const [state, setState] = useState({ loading: true, error: null, data: null });

  useEffect(() => {
    const controller = new AbortController();
    const url = `${resolveBasePath()}/initiative-lifecycle/data/lifecycle.json`;

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

function filterInitiatives(rows, state) {
  const q = String(state.q || "").trim().toLowerCase();
  const source = String(state.source || "").trim().toLowerCase();
  const committee = String(state.committee || "").trim().toLowerCase();
  const legislature = String(state.legislature || "").trim().toLowerCase();
  const status = String(state.status || "").trim().toLowerCase();
  const confidence = String(state.confidence || "").trim().toLowerCase();
  const method = String(state.method || "").trim().toLowerCase();
  const onlyLowConfidence = state.confidenceMode === "uncertain";

  const out = [];
  for (const row of rows) {
    if (source && String(row.source_id || "").toLowerCase() !== source) {
      continue;
    }
    if (committee && String(row.competent_committee || "").toLowerCase() !== committee) {
      continue;
    }
    if (legislature && String(row.legislature || "").toLowerCase() !== legislature) {
      continue;
    }
    if (status && String(row.current_status || "").toLowerCase() !== status) {
      continue;
    }
    if (confidence && String(row.link_summary?.link_confidence_bucket || "").toLowerCase() !== confidence) {
      continue;
    }
    if (method) {
      if (String(row.link_summary?.dominant_method || "").toLowerCase() !== method) {
        continue;
      }
    }
    if (onlyLowConfidence) {
      const ratio = Number(row.link_summary?.low_confidence_ratio || 0);
      if (!(ratio > 0.15)) {
        continue;
      }
    }
    if (q) {
      const haystack = [
        row.initiative_id,
        row.expediente,
        row.title,
        row.author_text,
        row.competent_committee,
        row.current_status,
      ]
        .map((value) => String(value || "").toLowerCase())
        .join(" ");
      if (!haystack.includes(q)) {
        continue;
      }
    }
    out.push(row);
  }
  return out;
}

export default function InitiativeLifecyclePage() {
  const { loading, error, data } = useLifecyclePayload();
  const [state, setState] = useState(readUrlState());
  const [selectedInitiativeId, setSelectedInitiativeId] = useState("");

  useEffect(() => {
    const initial = readUrlState();
    setState(initial);
    setSelectedInitiativeId(initial.initiativeId);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const params = new URLSearchParams();
    if (state.sort) params.set("sort", state.sort);
    if (state.source) params.set("source", state.source);
    if (state.committee) params.set("committee", state.committee);
    if (state.legislature) params.set("legislature", state.legislature);
    if (state.status) params.set("status", state.status);
    if (state.confidence) params.set("confidence", state.confidence);
    if (state.method) params.set("method", state.method);
    if (state.q) params.set("q", state.q);
    if (state.confidenceMode && state.confidenceMode !== "all") params.set("confidenceMode", state.confidenceMode);
    if (selectedInitiativeId) params.set("initiative", selectedInitiativeId);

    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}`;
    window.history.replaceState({}, "", nextUrl);
  }, [
    state.sort,
    state.source,
    state.committee,
    state.legislature,
    state.status,
    state.confidence,
    state.method,
    state.q,
    state.confidenceMode,
    selectedInitiativeId,
  ]);

  const initiatives = data?.initiatives || [];
  const filters = data?.filters || {};
  const overview = data?.initiative_overview || {};
  const bottlenecks = data?.bottlenecks || {};
  const committeeThroughput = bottlenecks.committee_by_throughput || [];

  const filtered = useMemo(() => {
    const base = filterInitiatives(initiatives, state);
    const sorted = [...base];
    const key = state.sort || "votes_desc";

    sorted.sort((left, right) => {
      const l = left || {};
      const r = right || {};
      if (key === "first_vote_asc") {
        return String(l.first_vote_date || "").localeCompare(String(r.first_vote_date || ""));
      }
      if (key === "first_vote_desc") {
        return String(r.first_vote_date || "").localeCompare(String(l.first_vote_date || ""));
      }
      if (key === "status_delay_desc") {
        return toInt(r.timeline_days?.presented_to_status_days) - toInt(l.timeline_days?.presented_to_status_days);
      }
      if (key === "status_delay_asc") {
        return toInt(l.timeline_days?.presented_to_status_days) - toInt(r.timeline_days?.presented_to_status_days);
      }
      if (key === "confidence_desc") {
        return toInt(r.link_summary?.low_confidence_links || 0) - toInt(l.link_summary?.low_confidence_links || 0);
      }
      return toInt(r.vote_count || 0) - toInt(l.vote_count || 0);
    });

    return sorted;
  }, [initiatives, state.sort, state.source, state.committee, state.legislature, state.status, state.confidence, state.method, state.confidenceMode, state.q]);

  const selectedInitiative = useMemo(() => {
    if (selectedInitiativeId) {
      const hit = initiatives.find((item) => item.initiative_id === selectedInitiativeId);
      if (hit) {
        return hit;
      }
    }
    return filtered[0] || null;
  }, [initiatives, filtered, selectedInitiativeId]);

  useEffect(() => {
    if (!selectedInitiative) {
      setSelectedInitiativeId("");
      return;
    }
    if (selectedInitiative.initiative_id !== selectedInitiativeId) {
      setSelectedInitiativeId(selectedInitiative.initiative_id);
    }
  }, [selectedInitiative, selectedInitiativeId]);

  const setFilter = (field, value) => setState((prev) => ({ ...prev, [field]: String(value || "") }));

  if (loading) {
    return (
      <main className="shell">
        <section className="card block">
          <h1>Cargando ciclo de vida de iniciativas…</h1>
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
        </section>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="shell">
        <section className="card block">
          <h1>Sin datos</h1>
          <p className="sub">No se encontraron métricas de iniciativas para esta publicación.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">Iniciativas</p>
        <h1>Lifecycle + Throughput legislativo</h1>
        <p className="sub">
          Analiza tiempo de tramitación por iniciativa, cuellos de botella por comisión y la secuencia de votos con
          transparencia de confianza en el enlace iniciativa-votación.
        </p>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Resumen rápido</h2>
        </div>
        <div className="kpiGrid">
          <div className="kpiCard">
            <span className="kpiLabel">Iniciativas expuestas</span>
            <span className="kpiValue">{formatInt(data.meta.total_initiatives)}</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Con votación vinculada</span>
            <span className="kpiValue">{formatInt(overview.linked_initiatives || 0)}</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Sin enlace de voto</span>
            <span className="kpiValue">{formatInt(overview.unlinked_initiatives || 0)}</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Total enlaces votos</span>
            <span className="kpiValue">{formatInt(data.meta.total_vote_links)}</span>
          </div>
          <div className="kpiCard">
            <span className="kpiLabel">Confianza alta / media / baja</span>
            <span className="kpiValue">
              {toInt(overview.confidence_distribution?.high || 0)} / {toInt(overview.confidence_distribution?.medium || 0)} /{" "}
              {toInt(overview.confidence_distribution?.low || 0)}
            </span>
            <span className="tileNote">sin enlace: {toInt(overview.confidence_distribution?.none || 0)}</span>
          </div>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Cuellos de botella por comité</h2>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Comité</th>
                <th>Iniciativas</th>
                <th>Sin voto</th>
                <th>Median días (presentado→1ª votación)</th>
                <th>Median días (presentado→estado)</th>
                <th>Confiabilidad muestra</th>
              </tr>
            </thead>
            <tbody>
              {committeeThroughput.length === 0 ? (
                <tr>
                  <td colSpan={6}>Sin datos de comité suficiente para este snapshot.</td>
                </tr>
              ) : (
                committeeThroughput.slice(0, 12).map((row) => (
                  <tr key={row.committee}>
                    <td>{row.committee}</td>
                    <td>{formatInt(row.initiatives_total)}</td>
                    <td>
                      {formatInt(row.no_vote_initiatives)} ({toPercent(row.no_vote_pct)})
                    </td>
                    <td>{formatDays(row.stages?.presented_to_first_vote_days?.median)}</td>
                    <td>{formatDays(row.stages?.presented_to_status_days?.median)}</td>
                    <td>{formatInt(row.reliability?.sampled_initiatives)}</td>
                  </tr>
                ))
              )}
            </tbody>
            </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Filtros y timeline</h2>
        </div>
        <div className="filterGrid">
          <div className="field">
            <label>Buscar</label>
            <input
              className="textInput"
              value={state.q}
              onChange={(event) => setFilter("q", event.target.value)}
              placeholder="Expediente, título, autor, comité..."
            />
          </div>
          <div className="field">
            <label>Origen</label>
            <select className="textInput" value={state.source} onChange={(event) => setFilter("source", event.target.value)}>
              <option value="">Todos</option>
              {(filters.source_ids || []).map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Comité</label>
            <select
              className="textInput"
              value={state.committee}
              onChange={(event) => setFilter("committee", event.target.value)}
            >
              <option value="">Todos</option>
              {(filters.committees || []).map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Legislatura</label>
            <select
              className="textInput"
              value={state.legislature}
              onChange={(event) => setFilter("legislature", event.target.value)}
            >
              <option value="">Todas</option>
              {(filters.legislatures || []).map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Estado actual</label>
            <select className="textInput" value={state.status} onChange={(event) => setFilter("status", event.target.value)}>
              <option value="">Todos</option>
              {(filters.status_buckets || []).map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Confianza del enlace</label>
            <select
              className="textInput"
              value={state.confidence}
              onChange={(event) => setFilter("confidence", event.target.value)}
            >
              <option value="">Todas</option>
              <option value="alta">Alta</option>
              <option value="media">Media</option>
              <option value="baja">Baja</option>
              <option value="sin_enlace">Sin enlace</option>
            </select>
          </div>
          <div className="field">
            <label>Método dominante</label>
              <select className="textInput" value={state.method} onChange={(event) => setFilter("method", event.target.value)}>
              <option value="">Todos</option>
              {(filters.link_methods || []).map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Orden</label>
            <select className="textInput" value={state.sort} onChange={(event) => setFilter("sort", event.target.value)}>
              <option value="votes_desc">Más votos</option>
              <option value="first_vote_desc">1ª votación (más reciente)</option>
              <option value="first_vote_asc">1ª votación (más antigua)</option>
              <option value="status_delay_desc">Tiempo a estado (lento primero)</option>
              <option value="status_delay_asc">Tiempo a estado (rápido primero)</option>
              <option value="confidence_desc">Más vínculos inciertos</option>
            </select>
          </div>
          <div className="field">
            <label>Enlace incierto</label>
            <select
              className="textInput"
              value={state.confidenceMode}
              onChange={(event) => setFilter("confidenceMode", event.target.value)}
            >
              <option value="all">Cualquier iniciativa</option>
              <option value="uncertain">&ge; 15% baja confianza</option>
            </select>
          </div>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Timeline de iniciativas</h2>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Iniciativa</th>
                <th>Comité / órgano</th>
                <th>Votos vinculados</th>
                <th>1ª votación</th>
                <th>Días (presentado→1ª)</th>
                <th>Estado</th>
                <th>Confianza del vínculo</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7}>No hay iniciativas con los filtros actuales.</td>
                </tr>
              ) : (
                filtered.slice(0, 240).map((initiative) => (
                  <tr
                    key={initiative.initiative_id}
                    className={selectedInitiativeId === initiative.initiative_id ? "rowSelected" : ""}
                  >
                    <td>
                      <button
                        className="tableButton"
                        onClick={() => setSelectedInitiativeId(initiative.initiative_id)}
                        type="button"
                      >
                        <div>
                          <strong>{initiative.expediente || initiative.initiative_id}</strong>
                        </div>
                        <div className="tileNote">
                          {initiative.title || "Sin título"} ({formatInt(initiative.vote_count)} votos)
                        </div>
                      </button>
                    </td>
                    <td>{initiative.competent_committee || "—"}</td>
                    <td>{formatInt(initiative.vote_count)} </td>
                    <td>{formatDate(initiative.first_vote_date)}</td>
                    <td>{formatDays(initiative.timeline_days?.presented_to_first_vote_days)}</td>
                    <td>{formatDate(initiative.current_status)} </td>
                    <td>
                      <span className={`pill ${confidenceClass(initiative.link_summary?.link_confidence_bucket)}`}>
                        {initiative.link_summary?.link_confidence_bucket || "sin enlace"}
                      </span>
                      <span className="tileNote">
                        links: {formatInt(initiative.link_summary?.low_confidence_links || 0)} ·
                        ratio: {toPercent((initiative.link_summary?.low_confidence_ratio || 0) * 100)}
                      </span>
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
          <h2>Votaciones alrededor de la iniciativa</h2>
        </div>
        {selectedInitiative ? (
          <div className="twoCols">
            <div>
              <p className="tileNote">Iniciativa: {selectedInitiative.initiative_id}</p>
              <p className="sub">
                {selectedInitiative.title || "Sin título"} · {selectedInitiative.author_text || "Sin autor"}
              </p>
              <p className="tileNote">
                Estado: {selectedInitiative.current_status || "—"} · Confianza enlace dominante: {selectedInitiative.link_summary?.link_confidence_bucket || "—"}
                · Votos vinculados: {formatInt(selectedInitiative.vote_count)}
                {selectedInitiative.vote_truncated ? ` (corte: ${formatInt(selectedInitiative.vote_truncated_count)})` : ""}
              </p>
              <p className="tileNote">
                Tiempos clave (días): registrado→calificado {formatDays(selectedInitiative.timeline_days?.presented_to_qualified_days)} ·
                registrado→1ª votación {formatDays(selectedInitiative.timeline_days?.presented_to_first_vote_days)} ·
                1ª→última votación {formatDays(selectedInitiative.timeline_days?.first_to_last_vote_days)} ·
                registrado→estado {formatDays(selectedInitiative.timeline_days?.presented_to_status_days)}
              </p>
            </div>
            <div className="tile">
              <strong>Métodos de vínculo</strong>
              <ul className="artifactList">
                {Object.entries(selectedInitiative.link_summary || {}).length === 0 ? (
                  <li>
                    <span>Sin evidencia de vínculo</span>
                  </li>
                ) : (
                  <li>
                    <span>Método dominante</span>
                    <span>{selectedInitiative.link_summary?.dominant_method || "—"}</span>
                  </li>
                )}
                <li>
                  <span>Confianza promedio</span>
                  <span>{toPercent((selectedInitiative.link_summary?.link_confidence_avg || 0) * 100)}</span>
                </li>
                <li>
                  <span>Baja confianza</span>
                  <span>{toPercent((selectedInitiative.link_summary?.low_confidence_ratio || 0) * 100)}</span>
                </li>
              </ul>
            </div>
          </div>
        ) : null}

        {selectedInitiative ? (
          <div className="tableWrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Evento</th>
                  <th>Contexto</th>
                  <th>Resultado</th>
                  <th>Margen</th>
                  <th>Método de enlace</th>
                  <th>Confianza</th>
                  <th>Fuente</th>
                </tr>
              </thead>
              <tbody>
                {(selectedInitiative.votes || []).map((vote) => (
                  <tr key={vote.vote_event_id}>
                    <td>{formatDate(vote.vote_date)}</td>
                    <td>
                      <div>{vote.vote_title || "—"}</div>
                      <div className="tileNote">
                        {vote.subgroup_title || vote.subgroup_text || vote.expediente_text || ""}
                      </div>
                    </td>
                    <td>{vote.context || "otro"}</td>
                    <td>
                      <span className={`pill ${outcomeClass(vote.outcome)}`}>{vote.outcome}</span>
                    </td>
                    <td>{vote.outcome_margin}</td>
                    <td>{vote.link_method || "sin método"}</td>
                    <td>
                      <span className={`pill ${confidenceClass(vote.link_confidence_band)}`}>
                        {vote.link_confidence === null || vote.link_confidence === undefined
                          ? "—"
                          : `${(vote.link_confidence * 100).toFixed(2)}%`}{" "}
                        {vote.link_confidence_band}
                      </span>
                    </td>
                    <td>
                      {vote.source_url ? (
                        <a className="tableButton" href={vote.source_url} target="_blank" rel="noreferrer">
                          Ver evidencia
                        </a>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="sub">Selecciona una iniciativa para ver su ruta de votaciones.</p>
        )}
      </section>
    </main>
  );
}
