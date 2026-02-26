"use client";

import { useEffect, useMemo, useState } from "react";

function resolveBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || (process.env.NODE_ENV === "production" ? "/vota-con-la-chola" : "");
}

function normalize(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function toInt(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function toPercent(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return "—";
  }
  return `${(num * 100).toFixed(1)}%`;
}

function toScore(value) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return "—";
  }
  return num.toFixed(2);
}

function clamp01(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) {
    return 0;
  }
  return Math.max(0, Math.min(1, num));
}

function formatDate(value) {
  return String(value || "—");
}

function stancePillClass(stance) {
  switch (String(stance || "").toLowerCase()) {
    case "support":
    case "supportive":
      return "pill-success";
    case "oppose":
      return "pill-danger";
    case "mixed":
      return "pill-warning";
    case "unclear":
      return "pill-muted";
    default:
      return "pill-muted";
  }
}

function methodPriority(method) {
  const m = String(method || "").toLowerCase();
  if (m === "combined") {
    return 0;
  }
  if (m === "votes") {
    return 1;
  }
  if (m === "declared") {
    return 2;
  }
  return 3;
}

function defaultStateFromUrl() {
  if (typeof window === "undefined") {
    return {
      mode: "person",
      q: "",
      method: "all",
      stance: "all",
      topic: "",
      party: "",
      sort: "person",
      limit: 180,
    };
  }

  const params = new URLSearchParams(window.location.search);
  return {
    mode: String(params.get("mode") || "person"),
    q: String(params.get("q") || ""),
    method: String(params.get("method") || "all"),
    stance: String(params.get("stance") || "all"),
    topic: String(params.get("topic") || ""),
    party: String(params.get("party") || ""),
    sort: String(params.get("sort") || "person"),
    limit: Number(params.get("limit") || 180),
  };
}

function usePositionsPayload() {
  const [state, setState] = useState({
    loading: true,
    error: null,
    data: null,
  });

  useEffect(() => {
    const controller = new AbortController();
    const url = `${resolveBasePath()}/political-positions/data/stances.json`;

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

function formatEvidenceSummary(item) {
  const breakdown = item?.evidence_breakdown || {};
  const total = toInt(item?.evidence_count || 0);
  if (!total) {
    return "Sin evidencia agregada";
  }
  const entries = [];
  if (toInt(breakdown.declared)) {
    entries.push(`declarada:${toInt(breakdown.declared)}`);
  }
  if (toInt(breakdown.revealed)) {
    entries.push(`votos:${toInt(breakdown.revealed)}`);
  }
  if (toInt(breakdown.other)) {
    entries.push(`otra:${toInt(breakdown.other)}`);
  }
  return entries.length ? entries.join(" · ") : `Total ${total}`;
}

function compactReviewLabel(item) {
  const pending = toInt(item?.review_summary?.pending || 0);
  const resolved = toInt(item?.review_summary?.resolved || 0);
  const ignored = toInt(item?.review_summary?.ignored || 0);

  if (!pending && !resolved && !ignored) {
    return "Sin revisión registrada";
  }
  return `Pendiente ${pending} · Aprobada ${resolved} · Ignorada ${ignored}`;
}

export default function PoliticalPositionsPage() {
  const { loading, error, data } = usePositionsPayload();
  const [state, setState] = useState(() => defaultStateFromUrl());
  const [selectedPoint, setSelectedPoint] = useState(null);

  useEffect(() => {
    const initial = defaultStateFromUrl();
    setState({
      ...initial,
      limit: Number.isFinite(initial.limit) && initial.limit > 0 ? Math.min(initial.limit, 400) : 180,
    });
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const params = new URLSearchParams();
    if (state.mode && state.mode !== "person") params.set("mode", state.mode);
    if (state.q) params.set("q", state.q);
    if (state.method && state.method !== "all") params.set("method", state.method);
    if (state.stance && state.stance !== "all") params.set("stance", state.stance);
    if (state.topic) params.set("topic", state.topic);
    if (state.party) params.set("party", state.party);
    if (state.sort && state.sort !== "person") params.set("sort", state.sort);
    if (toInt(state.limit || 0) > 0 && toInt(state.limit) !== 180) params.set("limit", String(toInt(state.limit)));

    const query = params.toString();
    const nextUrl = `${window.location.pathname}${query ? `?${query}` : ""}`;
    window.history.replaceState({}, "", nextUrl);
  }, [state.mode, state.q, state.method, state.stance, state.topic, state.party, state.sort, state.limit]);

  const topicsById = useMemo(() => {
    const out = new Map();
    for (const topic of data?.topics || []) {
      out.set(toInt(topic.topic_id), {
        topic_id: toInt(topic.topic_id),
        label: String(topic.topic_label || topic.label || "").trim(),
        key: String(topic.topic_key || "").trim(),
      });
    }
    return out;
  }, [data?.topics]);

  const personsById = useMemo(() => {
    const out = new Map();
    for (const person of data?.persons || []) {
      out.set(toInt(person.person_id), {
        person_id: toInt(person.person_id),
        full_name: String(person.full_name || person.name || "").trim(),
        canonical_key: String(person.canonical_key || "").trim(),
        point_count: toInt(person.point_count || 0),
        latest_as_of: String(person.latest_as_of || ""),
      });
    }
    return out;
  }, [data?.persons]);

  const partiesById = useMemo(() => {
    const out = new Map();
    for (const party of data?.parties || []) {
      out.set(toInt(party.party_id), {
        party_id: toInt(party.party_id),
        name: String(party.name || party.party || "").trim(),
        acronym: String(party.acronym || "").trim(),
      });
    }
    return out;
  }, [data?.parties]);

  const rows = useMemo(() => {
    const mode = String(state.mode || "person");
    const query = normalize(state.q);
    const methodFilter = String(state.method || "all").trim().toLowerCase();
    const stanceFilter = String(state.stance || "all").trim().toLowerCase();
    const topicFilter = normalize(state.topic);
    const partyFilter = normalize(state.party);

    const out = [];

    if (!data?.person_trajectories || typeof data.person_trajectories !== "object") {
      return out;
    }

    if (mode === "party") {
      const partySeries = data?.party_trajectories || {};
      const entries = Object.entries(partySeries);
      for (const [partyIdRaw, points] of entries) {
        const party = partiesById.get(toInt(partyIdRaw));
        if (!party) {
          continue;
        }
        const partyLabel = `${party.name || `Partido ${party.party_id}`}` + (party.acronym ? ` (${party.acronym})` : "");
        if (partyFilter && !normalize(partyLabel).includes(partyFilter)) {
          continue;
        }
        for (const point of Array.isArray(points) ? points : []) {
          const topic = topicsById.get(toInt(point.topic_id)) || {};
          const topicLabel = String(point.topic_label || topic.label || "").trim();
          const topicKey = normalize(state.topic ? point.topic_key || topic.key : topicLabel);
          if (topicFilter && !topicKey.includes(topicFilter)) {
            continue;
          }
          const method = String(point.computed_method || "").toLowerCase();
          if (methodFilter !== "all" && method !== methodFilter) {
            continue;
          }
          const stance = String(point.stance || "").toLowerCase();
          if (stanceFilter !== "all" && stance !== stanceFilter) {
            continue;
          }
          if (query && ![topicLabel, partyLabel, String(point.as_of_date || ""), String(point.computed_version || ""), point.party_label || ""].map(normalize).some((value) => value.includes(query))) {
            continue;
          }
          out.push({
            scope: "party",
            key: `p-${party.party_id}-${topic.topic_id || 0}-${point.as_of_date || ""}-${method}`,
            partyId: party.party_id,
            partyLabel,
            party,
            personId: 0,
            personName: "",
            topicId: toInt(point.topic_id || 0),
            topicLabel,
            topicKey: String(topic.key || point.topic_key || ""),
            asOf: String(point.as_of_date || ""),
            windowDays: toInt(point.window_days),
            method,
            stance,
            score: clamp01(point.score),
            confidence: clamp01(point.confidence),
            evidenceCount: toInt(point.evidence_count || 0),
            lastEvidenceDate: String(point.last_evidence_date || ""),
            coverage: point.coverage || point,
            evidenceBreakdown: point.evidence_breakdown || {},
            reviewSummary: point.review_summary || {},
            samples: Array.isArray(point.evidence_samples) ? point.evidence_samples : [],
            raw: point,
          });
        }
      }
    } else {
      for (const [personIdRaw, points] of Object.entries(data.person_trajectories || {})) {
        const person = personsById.get(toInt(personIdRaw));
        if (!person) {
          continue;
        }
        for (const point of Array.isArray(points) ? points : []) {
          const topic = topicsById.get(toInt(point.topic_id)) || {};
          const topicLabel = String(point.topic_label || topic.label || "").trim();
          const topicKey = normalize(state.topic ? point.topic_key || topic.key : topicLabel);
          if (topicFilter && !topicKey.includes(topicFilter)) {
            continue;
          }
          const method = String(point.computed_method || "").toLowerCase();
          if (methodFilter !== "all" && method !== methodFilter) {
            continue;
          }
          const stance = String(point.stance || "").toLowerCase();
          if (stanceFilter !== "all" && stance !== stanceFilter) {
            continue;
          }
          const rowHaystack = [
            String(person.full_name || ""),
            String(person.canonical_key || ""),
            String(topicLabel || ""),
            String(point.party_label || ""),
            String(point.as_of_date || ""),
            String(method || ""),
            String(point.topic_key || ""),
          ].map(normalize).join(" ");
          if (query && !rowHaystack.includes(query)) {
            continue;
          }
          if (partyFilter) {
            const partyLabel = normalize(point.party_label || "");
            if (!partyLabel.includes(partyFilter)) {
              continue;
            }
          }
          out.push({
            scope: "person",
            key: `i-${personIdRaw}-${topic.topic_id || 0}-${point.as_of_date || ""}-${method}`,
            personId: toInt(person.person_id || personIdRaw),
            personName: String(person.full_name || ""),
            person,
            partyId: toInt(point.party_id || 0),
            partyLabel: String(point.party_label || ""),
            topicId: toInt(point.topic_id || 0),
            topicLabel,
            topicKey: String(point.topic_key || topic.key || ""),
            asOf: String(point.as_of_date || ""),
            windowDays: toInt(point.window_days),
            method,
            stance,
            score: clamp01(point.score),
            confidence: clamp01(point.confidence),
            evidenceCount: toInt(point.evidence_count || 0),
            lastEvidenceDate: String(point.last_evidence_date || ""),
            coverage: point.coverage || point,
            evidenceBreakdown: point.evidence_breakdown || {},
            reviewSummary: point.review_summary || {},
            samples: Array.isArray(point.evidence_samples) ? point.evidence_samples : [],
            raw: point,
          });
        }
      }
    }

    const sortMode = String(state.sort || "person");
    out.sort((a, b) => {
      if (sortMode === "confidence_desc") {
        return clamp01(b.confidence) - clamp01(a.confidence) || b.score - a.score || b.evidenceCount - a.evidenceCount;
      }
      if (sortMode === "confidence_asc") {
        return clamp01(a.confidence) - clamp01(b.confidence) || a.score - b.score;
      }
      if (sortMode === "method") {
        if (a.method !== b.method) {
          return methodPriority(a.method) - methodPriority(b.method);
        }
      }
      if (sortMode === "stance") {
        if (a.stance !== b.stance) {
          return String(a.stance).localeCompare(String(b.stance));
        }
      }
      if (sortMode === "as_of") {
        return String(b.asOf || "").localeCompare(String(a.asOf || ""));
      }
      if (sortMode === "topic") {
        return String(a.topicLabel || "").localeCompare(String(b.topicLabel || "")) || String(a.asOf || "").localeCompare(String(b.asOf || ""));
      }
      if (sortMode === "party") {
        const ap = normalize(a.partyLabel || "");
        const bp = normalize(b.partyLabel || "");
        if (ap !== bp) {
          return ap.localeCompare(bp);
        }
      }

      if (a.scope === b.scope) {
        if (a.scope === "person") {
          return String(a.personName || "").localeCompare(String(b.personName || ""))
            || String(a.topicLabel || "").localeCompare(String(b.topicLabel || ""))
            || String(b.asOf || "").localeCompare(String(a.asOf || ""))
            || methodPriority(a.method) - methodPriority(b.method);
        }
        return String(a.partyLabel || "").localeCompare(String(b.partyLabel || ""))
          || String(a.topicLabel || "").localeCompare(String(b.topicLabel || ""))
          || String(b.asOf || "").localeCompare(String(a.asOf || ""))
          || methodPriority(a.method) - methodPriority(b.method);
      }

      return String(a.scope).localeCompare(String(b.scope));
    });

    const maxRows = Math.max(10, Number(state.limit || 180));
    return out.slice(0, maxRows);
  }, [data, partiesById, personsById, topicsById, state]);

  const selectedPersonCard = useMemo(() => {
    if (!selectedPoint || selectedPoint.scope !== "person") {
      return null;
    }
    const person = personsById.get(selectedPoint.personId);
    if (!person) {
      return null;
    }
    return person;
  }, [selectedPoint, personsById]);

  const selectedPartyCard = useMemo(() => {
    if (!selectedPoint || selectedPoint.scope !== "party") {
      return null;
    }
    return partiesById.get(selectedPoint.partyId);
  }, [selectedPoint, partiesById]);

  const selectionSummary = useMemo(() => {
    if (!selectedPoint) {
      return "Sin selección";
    }
    const core = [
      selectedPoint.scope === "person" ? `Persona: ${selectedPoint.personName || selectedPoint.personId}` : `Partido: ${selectedPoint.partyLabel || selectedPoint.partyId}`,
      `Tema: ${selectedPoint.topicLabel || selectedPoint.topicId}`,
      `Método: ${selectedPoint.method || "—"}`,
      `As of: ${selectedPoint.asOf || "—"}`,
    ];
    return core.join(" · ");
  }, [selectedPoint]);

  if (loading) {
    return (
      <main className="shell">
        <section className="card block">
          <p className="sub">Cargando posturas trazables…</p>
        </section>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="shell">
        <section className="card block">
          <h2>Error de publicación</h2>
          <p className="sub">No pude cargar <code>political-positions/data/stances.json</code>.</p>
          <p className="sub">Error: {error || "sin datos"}</p>
          <p className="sub">Genera el snapshot con: <code>python3 scripts/export_political_positions_snapshot.py --db etl/data/staging/politicos-es.db --snapshot-date 2026-02-12</code>.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">Postura política explicable</p>
        <h1>Topic stance scoring (por persona y partido)</h1>
        <p className="sub">
          Vistas explicables de posición por tema con evidencia rastreable y estado de revisión para auditoría.
        </p>
        <div className="chips" style={{ marginTop: 12 }}>
          <span className="chip">Snapshot: {data.meta?.snapshot_date || "—"}</span>
          <span className="chip">Personas: {toInt((data.persons || []).length)}</span>
          <span className="chip">Partidos: {toInt((data.parties || []).length)}</span>
          <span className="chip">Topics: {toInt((data.topics || []).length)}</span>
          <span className="chip">Pendientes de revisión: {toInt(data.meta?.review_pending || 0)}</span>
        </div>
      </section>

      <section className="card block">
        <div className="filterGrid">
          <label className="field">
            Vista
            <select value={state.mode} onChange={(e) => setState((prev) => ({ ...prev, mode: e.target.value }))}>
              <option value="person">Personas</option>
              <option value="party">Partidos</option>
            </select>
          </label>
          <label className="field">
            Buscar
            <input
              className="textInput"
              type="search"
              value={state.q}
              placeholder="Persona, partido, tema, método"
              onChange={(e) => setState((prev) => ({ ...prev, q: e.target.value }))}
            />
          </label>
          <label className="field">
            Método
            <select value={state.method} onChange={(e) => setState((prev) => ({ ...prev, method: e.target.value }))}>
              <option value="all">Todos</option>
              <option value="combined">Combined</option>
              <option value="votes">Votos</option>
              <option value="declared">Declarado</option>
            </select>
          </label>
          <label className="field">
            Postura
            <select value={state.stance} onChange={(e) => setState((prev) => ({ ...prev, stance: e.target.value }))}>
              <option value="all">Todas</option>
              <option value="support">Support</option>
              <option value="oppose">Oppose</option>
              <option value="mixed">Mixto</option>
              <option value="unclear">Poco claro</option>
              <option value="no_signal">Sin señal</option>
            </select>
          </label>
          <label className="field">
            Tema
            <input
              className="textInput"
              value={state.topic}
              placeholder="Buscar por tema (texto o clave)"
              onChange={(e) => setState((prev) => ({ ...prev, topic: e.target.value }))}
            />
          </label>
          <label className="field">
            Partido
            <input
              className="textInput"
              value={state.party}
              placeholder="Filtrar por partido"
              onChange={(e) => setState((prev) => ({ ...prev, party: e.target.value }))}
            />
          </label>
          <label className="field">
            Ordenar
            <select value={state.sort} onChange={(e) => setState((prev) => ({ ...prev, sort: e.target.value }))}>
              <option value="person">Persona/Partido + Tema</option>
              <option value="topic">Tema</option>
              <option value="party">Partido</option>
              <option value="as_of">Fecha (más reciente)</option>
              <option value="confidence_desc">Confianza (alta)</option>
              <option value="confidence_asc">Confianza (baja)</option>
              <option value="method">Método</option>
              <option value="stance">Postura</option>
            </select>
          </label>
          <label className="field">
            Límite filas
            <select
              value={String(state.limit || 180)}
              onChange={(e) => setState((prev) => ({ ...prev, limit: Number(e.target.value) || 180 }))}
            >
              <option value={120}>120</option>
              <option value={180}>180</option>
              <option value={240}>240</option>
              <option value={320}>320</option>
              <option value={400}>400</option>
            </select>
          </label>
        </div>

        <div className="chips" style={{ marginTop: 10 }}>
          <span className="chip">Filas mostradas: {rows.length}</span>
          <span className="chip">Filas calculadas: {rows.length}</span>
          {state.mode === "person" ? (
            <span className="chip">Modo: comparación persona · tema · método</span>
          ) : (
            <span className="chip">Modo: agregación por grupo parlamentario</span>
          )}
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Trayectorias y evidencia</h2>
          <p className="sub">Selecciona una fila para ver muestra de evidencia + estado de revisión.</p>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Ámbito</th>
                <th>Entidad</th>
                <th>Tema</th>
                <th>Método</th>
                <th>As Of</th>
                <th>Postura</th>
                <th>Score</th>
                <th>Confianza</th>
                <th>Evidencia</th>
                <th>Revisión</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const isSelected = selectedPoint?.key === row.key;
                const rowLabel = row.scope === "person"
                  ? `${row.personName || row.personId} · ${row.partyLabel || "Sin partido"}`
                  : `${row.partyLabel || row.partyId}`;
                const rowText = `/${row.scope}/`;
                return (
                  <tr
                    key={row.key}
                    className={isSelected ? "rowSelected" : ""}
                    onClick={() => setSelectedPoint(row)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        setSelectedPoint(row);
                      }
                    }}
                    style={{ cursor: "pointer" }}
                  >
                    <td>{rowText}</td>
                    <td>{rowLabel}</td>
                    <td>{row.topicLabel || "Sin tema"}</td>
                    <td>{row.method || "—"}</td>
                    <td>{formatDate(row.asOf)}{row.windowDays ? ` (${row.windowDays}d)` : ""}</td>
                    <td>
                      <span className={`pill ${stancePillClass(row.stance)}`}>
                        {row.stance || "no_signal"}
                      </span>
                    </td>
                    <td>{toScore(row.score)}</td>
                    <td>{toPercent(row.confidence)}</td>
                    <td>{formatEvidenceSummary(row)}</td>
                    <td>{compactReviewLabel(row)}</td>
                  </tr>
                );
              })}
              {!rows.length && (
                <tr>
                  <td colSpan={9} className="sub">
                    No hay datos para los filtros actuales.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Detalle de evidencia</h2>
          <p className="sub">{selectionSummary}</p>
        </div>
        {!selectedPoint ? (
          <p className="sub">Selecciona una fila para mostrar las evidencias puntuales y su estado de revisión.</p>
        ) : (
          <div className="twoCols" style={{ marginTop: 12 }}>
            <article className="kpiCard">
              <span className="kpiLabel">Entidad activa</span>
              <p className="sub">
                {selectedPoint.scope === "person"
                  ? selectedPersonCard
                    ? `${selectedPersonCard.full_name || "Persona"} (ID ${selectedPersonCard.person_id || selectedPoint.personId})`
                    : "Persona"
                  : selectedPartyCard
                    ? `${selectedPartyCard.name || selectedPartyCard.acronym || "Partido"} (ID ${selectedPoint.partyId})`
                    : "Partido"}
              </p>
              <p className="sub">Tema: {selectedPoint.topicLabel || `#${selectedPoint.topicId}`}</p>
              <p className="sub">Postura: <span className={`pill ${stancePillClass(selectedPoint.stance)}`}>{selectedPoint.stance || "no_signal"}</span></p>
              <p className="sub">Score: {toScore(selectedPoint.score)} · Confianza: {toPercent(selectedPoint.confidence)}</p>
              <p className="sub">Evidencias: {selectedPoint.evidenceCount || 0}</p>
              <p className="sub">Última evidencia: {formatDate(selectedPoint.lastEvidenceDate || "")}</p>
            </article>

            <article className="kpiCard">
              <span className="kpiLabel">Links de exploración</span>
              <p className="sub" style={{ marginBottom: 4 }}>
                {selectedPoint.scope === "person" ? (
                  <a href={`${resolveBasePath()}/explorer/?t=topic_evidence&wc=person_id&wv=${selectedPoint.personId}&wc=topic_id&wv=${selectedPoint.topicId}&wc=topic_set_id&wv=${data.meta?.topic_set_id || 1}`}>Explorer: evidencia tema</a>
                ) : (
                  <a href={`${resolveBasePath()}/explorer/?t=topic_positions&wc=party_id&wv=${selectedPoint.partyId}&wc=topic_id&wv=${selectedPoint.topicId}&wc=topic_set_id&wv=${data.meta?.topic_set_id || 1}`}>Explorer: posiciones de grupo</a>
                )}
              </p>
              <p className="sub">
                {selectedPoint.scope === "person"
                  ? <a href={`${resolveBasePath()}/explorer/?t=parl_vote_member_votes&wc=person_id&wv=${selectedPoint.personId}&wc=topic_id&wv=${selectedPoint.topicId}`}>Explorer: votos persona</a>
                  : <a href={`${resolveBasePath()}/explorer/?t=topic_positions&wc=party_id&wv=${selectedPoint.partyId}&wc=topic_set_id&wv=${data.meta?.topic_set_id || 1}`}>Explorer: partido y tema</a>
                }
              </p>
              <p className="sub">Revisión: {compactReviewLabel(selectedPoint)}</p>
            </article>
          </div>
        )}

        {selectedPoint ? (
          <div className="tableWrap" style={{ marginTop: 12 }}>
            <table className="table">
              <thead>
                <tr>
                  <th>Fuente</th>
                  <th>Fecha</th>
                  <th>Tipo</th>
                  <th>Postura</th>
                  <th>Confianza</th>
                  <th>Extracto</th>
                  <th>Revisión</th>
                </tr>
              </thead>
              <tbody>
                {(selectedPoint.samples || []).slice(0, 6).map((sample) => {
                  const sourceUrl = String(sample.source_url || "");
                  return (
                    <tr key={`${sample.source_id || "src"}-${sample.evidence_id || sample.evidence_record_id || ""}-${sample.evidence_type || ""}`}>
                      <td>
                        {sourceUrl ? (
                          <a href={sourceUrl} target="_blank" rel="noreferrer">
                            {sample.source_id || "fuente"}
                          </a>
                        ) : (
                          sample.source_id || "—"
                        )}
                      </td>
                      <td>{formatDate(sample.evidence_date || "")}</td>
                      <td>{sample.evidence_type || "—"}</td>
                      <td>{sample.stance || "—"}</td>
                      <td>{toPercent(sample.confidence || 0)}</td>
                      <td>{String(sample.excerpt || sample.title || "—").slice(0, 280)}</td>
                      <td>
                        <span className="sub">
                          {sample.review && sample.review.status ? sample.review.status : "sin revisión"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
                {(!selectedPoint.samples || !selectedPoint.samples.length) ? (
                  <tr>
                    <td colSpan={7} className="sub">
                      Esta postura no tiene evidencia puntual listada para su rastro.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </main>
  );
}
