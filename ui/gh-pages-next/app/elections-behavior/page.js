"use client";

import { useEffect, useMemo, useState } from "react";

function resolveBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || (process.env.NODE_ENV === "production" ? "/vota-con-la-chola" : "");
}

function asInt(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function asFloat(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatInt(value) {
  return asInt(value).toLocaleString("es-ES");
}

function formatPct(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return "—";
  }
  return `${parsed.toFixed(1)}%`;
}

function formatDelta(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return "—";
  }
  const prefix = parsed > 0 ? "+" : "";
  return `${prefix}${parsed.toFixed(1)}pp`;
}

function deltaClass(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
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

function toBucketLabel(bucket) {
  if (bucket === "congreso") {
    return "Congreso";
  }
  if (bucket === "senado") {
    return "Senado";
  }
  return bucket || "—";
}

function readUrlState() {
  if (typeof window === "undefined") {
    return {
      bucket: "all",
      election: "",
      party: "",
      topic: "",
      territory: "",
      sortParty: "delta_abs_desc",
      sortTopic: "delta_abs_desc",
      sortDistrict: "seats_desc",
    };
  }

  const params = new URLSearchParams(window.location.search);
  return {
    bucket: String(params.get("bucket") || "all"),
    election: String(params.get("election") || ""),
    party: String(params.get("party") || ""),
    topic: String(params.get("topic") || ""),
    territory: String(params.get("territory") || ""),
    sortParty: String(params.get("sortParty") || "delta_abs_desc"),
    sortTopic: String(params.get("sortTopic") || "delta_abs_desc"),
    sortDistrict: String(params.get("sortDistrict") || "seats_desc"),
  };
}

function useElectionsPayload() {
  const [state, setState] = useState({
    loading: true,
    error: null,
    data: null,
  });

  useEffect(() => {
    const controller = new AbortController();
    const url = `${resolveBasePath()}/elections-behavior/data/elections-behavior.json`;
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

function renderElectionWindow(row) {
  const preWindow = `${row.pre_window_from || "—"} → ${row.pre_window_to || "—"}`;
  const postWindow = `${row.post_window_from || "—"} → ${row.post_window_to || "—"}`;
  return `${preWindow} / ${postWindow}`;
}

export default function ElectionsBehaviorPage() {
  const { loading, error, data } = useElectionsPayload();
  const [state, setState] = useState(() => readUrlState());

  useEffect(() => {
    setState(readUrlState());
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const params = new URLSearchParams();
    if (state.bucket && state.bucket !== "all") params.set("bucket", state.bucket);
    if (state.election) params.set("election", state.election);
    if (state.party) params.set("party", state.party);
    if (state.topic) params.set("topic", state.topic);
    if (state.territory) params.set("territory", state.territory);
    if (state.sortParty !== "delta_abs_desc") params.set("sortParty", state.sortParty);
    if (state.sortTopic !== "delta_abs_desc") params.set("sortTopic", state.sortTopic);
    if (state.sortDistrict !== "seats_desc") params.set("sortDistrict", state.sortDistrict);

    const nextUrl = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}`;
    window.history.replaceState({}, "", nextUrl);
  }, [state]);

  const elections = useMemo(() => data?.elections || [], [data?.elections]);
  const partyShiftsRaw = useMemo(() => data?.party_shifts || [], [data?.party_shifts]);
  const topicShiftsRaw = useMemo(() => data?.topic_shifts || [], [data?.topic_shifts]);
  const districtsRaw = useMemo(() => data?.district_representation || [], [data?.district_representation]);
  const meta = data?.meta || {};
  const institutions = (data?.institutions || []).map((item) => item?.bucket || "");

  const electionOptions = useMemo(() => {
    const filtered = elections
      .filter((row) => state.bucket === "all" || !state.bucket || row.bucket === state.bucket)
      .sort((left, right) => String(right.election_date || "").localeCompare(String(left.election_date || "")));

    return filtered.map((item) => ({
      election_id: String(item.election_id || ""),
      label: `${String(item.label || item.election_id || "")} (${item.election_date || "—"})`,
      bucket: item.bucket,
    }));
  }, [elections, state.bucket]);

  const filteredElections = useMemo(() => {
    const q = state.party.trim().toLowerCase();
    return elections
      .filter((row) => state.bucket === "all" || row.bucket === state.bucket)
      .filter((row) => (state.election ? row.election_id === state.election : true))
      .filter((row) => {
        const payload = q;
        if (!payload) {
          return true;
        }
        return String(row.label || row.election_id || "")
          .toLowerCase()
          .includes(payload);
      });
  }, [elections, state.bucket, state.election, state.party]);

  const filteredPartyShifts = useMemo(() => {
    const partyQuery = state.party.trim().toLowerCase();
    const rows = partyShiftsRaw.filter((row) => {
      if (state.bucket !== "all" && row.bucket !== state.bucket) return false;
      if (state.election && row.election_id !== state.election) return false;
      if (partyQuery && !String(row.party_label || "").toLowerCase().includes(partyQuery)) return false;
      return true;
    });

    rows.sort((left, right) => {
      const direction = state.sortParty;
      if (direction === "delta_desc") {
        return asFloat(right.delta_cohesion_pct) - asFloat(left.delta_cohesion_pct);
      }
      if (direction === "delta_asc") {
        return asFloat(left.delta_cohesion_pct) - asFloat(right.delta_cohesion_pct);
      }
      if (direction === "post_desc") {
        return asInt(right.post_directional_votes) - asInt(left.post_directional_votes);
      }
      if (direction === "post_asc") {
        return asInt(left.post_directional_votes) - asInt(right.post_directional_votes);
      }
      return Math.abs(asFloat(right.delta_cohesion_pct)) - Math.abs(asFloat(left.delta_cohesion_pct));
    });

    return rows;
  }, [partyShiftsRaw, state.bucket, state.election, state.party, state.sortParty]);

  const filteredTopicShifts = useMemo(() => {
    const topicQuery = state.topic.trim().toLowerCase();
    const rows = topicShiftsRaw.filter((row) => {
      if (state.bucket !== "all" && row.bucket !== state.bucket) return false;
      if (state.election && row.election_id !== state.election) return false;
      if (topicQuery && !String(row.topic || "").toLowerCase().includes(topicQuery)) return false;
      return true;
    });

    rows.sort((left, right) => {
      const direction = state.sortTopic;
      if (direction === "delta_desc") {
        return asFloat(right.delta_cohesion_pct) - asFloat(left.delta_cohesion_pct);
      }
      if (direction === "delta_asc") {
        return asFloat(left.delta_cohesion_pct) - asFloat(right.delta_cohesion_pct);
      }
      if (direction === "pre_desc") {
        return asFloat(right.pre_directional_votes || 0) - asFloat(left.pre_directional_votes || 0);
      }
      if (direction === "pre_asc") {
        return asFloat(left.pre_directional_votes || 0) - asFloat(right.pre_directional_votes || 0);
      }
      return Math.abs(asFloat(right.delta_cohesion_pct)) - Math.abs(asFloat(left.delta_cohesion_pct));
    });

    return rows;
  }, [topicShiftsRaw, state.bucket, state.election, state.topic, state.sortTopic]);

  const filteredDistrictRows = useMemo(() => {
    const territoryQuery = state.territory.trim().toLowerCase();
    const rows = districtsRaw.filter((row) => {
      if (state.bucket !== "all" && row.bucket !== state.bucket) return false;
      if (state.election && row.election_id !== state.election) return false;
      if (state.party && !String(row.party_label || "").toLowerCase().includes(state.party.toLowerCase())) return false;
      if (territoryQuery && !String(row.territory_label || "").toLowerCase().includes(territoryQuery)) return false;
      return true;
    });

    rows.sort((left, right) => {
      const direction = state.sortDistrict;
      if (direction === "seats_desc") {
        return asInt(right.seats) - asInt(left.seats);
      }
      if (direction === "seats_asc") {
        return asInt(left.seats) - asInt(right.seats);
      }
      if (direction === "cohesion_desc") {
        return asFloat(right.behavior_cohesion_pct) - asFloat(left.behavior_cohesion_pct);
      }
      if (direction === "cohesion_asc") {
        return asFloat(left.behavior_cohesion_pct) - asFloat(right.behavior_cohesion_pct);
      }
      return asInt(right.seats) - asInt(left.seats);
    });

    return rows;
  }, [districtsRaw, state.bucket, state.election, state.party, state.territory, state.sortDistrict]);

  if (loading) {
    return (
      <main className="shell">
        <section className="hero card">
          <p className="eyebrow">Conexión electoral</p>
          <h1>Cargando conexiones elecciones-comportamiento</h1>
          <p className="sub">Esperando el snapshot estático de GH Pages...</p>
        </section>
      </main>
    );
  }

  if (error) {
    return (
      <main className="shell">
        <section className="hero card">
          <p className="eyebrow">Conexión electoral</p>
          <h1>No se pudo cargar el snapshot</h1>
          <p className="sub">{error}</p>
        </section>
      </main>
    );
  }

  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">Conexión elecciones-comportamiento</p>
        <h1>Análisis: antes y después de cada elección</h1>
        <p className="sub">
          Relaciona elección nacional (Congreso / Senado) con cambios de cohesión partidaria, cambios temáticos y representación territorial
          del periodo pre/post.
        </p>
        <div className="chips" style={{ marginTop: 10 }}>
          <span className="chip">Snapshot: {meta.generated_at || "sin fecha"}</span>
          <span className="chip">Elecciones: {formatInt(elections.length)}</span>
          <span className="chip">Partidos con cambios: {formatInt(filteredPartyShifts.length)}</span>
          <span className="chip">Temas con cambios: {formatInt(filteredTopicShifts.length)}</span>
          <span className="chip">Territorios analizados: {formatInt(filteredDistrictRows.length)}</span>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Filtros globales</h2>
        </div>
        <div className="filterGrid">
          <div className="field">
            <label htmlFor="eb-bucket">Camara</label>
            <select
              id="eb-bucket"
              className="tableFilterSelect"
              value={state.bucket}
              onChange={(event) => setState((prev) => ({ ...prev, bucket: event.target.value }))}
            >
              <option value="all">Todas</option>
              {institutions.map((item) => (
                <option key={item} value={item}>
                  {toBucketLabel(item)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="eb-election">Elección</label>
            <select
              id="eb-election"
              className="tableFilterSelect"
              value={state.election}
              onChange={(event) => setState((prev) => ({ ...prev, election: event.target.value }))}
            >
              <option value="">Todas</option>
              {electionOptions.map((item) => (
                <option key={item.election_id} value={item.election_id}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="eb-party">Partido</label>
            <input
              id="eb-party"
              type="text"
              className="textInput"
              value={state.party}
              onChange={(event) => setState((prev) => ({ ...prev, party: event.target.value }))}
            />
          </div>
          <div className="field">
            <label htmlFor="eb-topic">Tema</label>
            <input
              id="eb-topic"
              type="text"
              className="textInput"
              value={state.topic}
              onChange={(event) => setState((prev) => ({ ...prev, topic: event.target.value }))}
            />
          </div>
          <div className="field">
            <label htmlFor="eb-territory">Territorio</label>
            <input
              id="eb-territory"
              type="text"
              className="textInput"
              value={state.territory}
              onChange={(event) => setState((prev) => ({ ...prev, territory: event.target.value }))}
            />
          </div>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Elections</h2>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Camara</th>
                <th>Elección</th>
                <th>Fecha</th>
                <th>Tipo</th>
                <th>Ventana pre/post</th>
                <th>Votaciones ventana pre</th>
                <th>Votaciones ventana post</th>
                <th>Resultado oficial</th>
              </tr>
            </thead>
            <tbody>
              {filteredElections.map((row) => (
                <tr key={row.election_id}>
                  <td>{toBucketLabel(row.bucket)}</td>
                  <td>{String(row.label || row.election_id || "—")}</td>
                  <td>{String(row.election_date || "—")}</td>
                  <td>{String(row.type || "—")}</td>
                  <td>{renderElectionWindow(row)}</td>
                  <td>{formatInt(row.pre_events || 0)}</td>
                  <td>{formatInt(row.post_events || 0)}</td>
                  <td>{row.has_result_payload ? `Cobertura ${formatInt(row.result_rows || 0)}` : "Sin cobertura"}</td>
                </tr>
              ))}
              {!filteredElections.length && (
                <tr>
                  <td colSpan={8} className="sub">
                    No hay elecciones para el filtro aplicado.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Cambios de cohesión por partido (pre/post)</h2>
          <div className="filterGrid" style={{ marginTop: 8 }}>
            <div className="field">
              <label htmlFor="eb-sort-party">Orden</label>
              <select
                id="eb-sort-party"
                className="tableFilterSelect"
                value={state.sortParty}
                onChange={(event) => setState((prev) => ({ ...prev, sortParty: event.target.value }))}
              >
                <option value="delta_abs_desc">Δ Cohesión | abs descendente</option>
                <option value="delta_desc">Δ Cohesión descendente</option>
                <option value="delta_asc">Δ Cohesión ascendente</option>
                <option value="post_desc">Votaciones post descendente</option>
                <option value="post_asc">Votaciones post ascendente</option>
              </select>
            </div>
          </div>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Camara</th>
                <th>Elección</th>
                <th>Partido</th>
                <th>Pre</th>
                <th>Post</th>
                <th>Δ Cohesión</th>
                <th>Pre vs elección anterior</th>
              </tr>
            </thead>
            <tbody>
              {filteredPartyShifts.map((row) => (
                <tr key={`${row.bucket}-${row.election_id}-${row.party_id}`}>
                  <td>{toBucketLabel(row.bucket)}</td>
                  <td>{String(row.label || row.election_id || "—")}</td>
                  <td>{String(row.party_label || "")}</td>
                  <td>
                    {formatPct(row.pre_cohesion_pct)}
                    <span className="sub" style={{ marginLeft: 6, display: "inline-block" }}>
                      ({formatInt(row.pre_directional_votes)} votos direccionales)
                    </span>
                  </td>
                  <td>
                    {formatPct(row.post_cohesion_pct)}
                    <span className="sub" style={{ marginLeft: 6, display: "inline-block" }}>
                      ({formatInt(row.post_directional_votes)} votos direccionales)
                    </span>
                  </td>
                  <td>
                    <span className={`pill ${deltaClass(row.delta_cohesion_pct)}`}>{formatDelta(row.delta_cohesion_pct)}</span>
                  </td>
                  <td>
                    {row.pre_vs_prev_election_delta_pct === null || row.pre_vs_prev_election_delta_pct === undefined
                      ? "—"
                      : `${String(row.pre_vs_prev_election || "—")} (${formatDelta(row.pre_vs_prev_election_delta_pct)})`}
                  </td>
                </tr>
              ))}
              {!filteredPartyShifts.length && (
                <tr>
                  <td colSpan={7} className="sub">
                    No hay cambios para el filtro aplicado.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Cambios por tema (pre/post)</h2>
          <div className="filterGrid" style={{ marginTop: 8 }}>
            <div className="field">
              <label htmlFor="eb-sort-topic">Orden</label>
              <select
                id="eb-sort-topic"
                className="tableFilterSelect"
                value={state.sortTopic}
                onChange={(event) => setState((prev) => ({ ...prev, sortTopic: event.target.value }))}
              >
                <option value="delta_abs_desc">Δ Cohesión | abs descendente</option>
                <option value="delta_desc">Δ Cohesión descendente</option>
                <option value="delta_asc">Δ Cohesión ascendente</option>
                <option value="pre_desc">Votaciones pre descendente</option>
                <option value="pre_asc">Votaciones pre ascendente</option>
              </select>
            </div>
          </div>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Camara</th>
                <th>Elección</th>
                <th>Partido</th>
                <th>Tema</th>
                <th>Pre</th>
                <th>Post</th>
                <th>Δ Cohesión</th>
              </tr>
            </thead>
            <tbody>
              {filteredTopicShifts.map((row) => (
                <tr key={`${row.bucket}-${row.election_id}-${row.party_id}-${row.topic}`}>
                  <td>{toBucketLabel(row.bucket)}</td>
                  <td>{String(row.label || row.election_id || "—")}</td>
                  <td>{String(row.party_label || "")}</td>
                  <td>{String(row.topic || "—")}</td>
                  <td>
                    {formatPct(row.pre_cohesion_pct)}
                    <span className="sub" style={{ marginLeft: 6, display: "inline-block" }}>
                      ({formatInt(row.pre_directional_votes)} direccionales)
                    </span>
                  </td>
                  <td>
                    {formatPct(row.post_cohesion_pct)}
                    <span className="sub" style={{ marginLeft: 6, display: "inline-block" }}>
                      ({formatInt(row.post_directional_votes)} direccionales)
                    </span>
                  </td>
                  <td>
                    <span className={`pill ${deltaClass(row.delta_cohesion_pct)}`}>{formatDelta(row.delta_cohesion_pct)}</span>
                  </td>
                </tr>
              ))}
              {!filteredTopicShifts.length && (
                <tr>
                  <td colSpan={7} className="sub">
                    No hay cambios temáticos para el filtro aplicado.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>Representación territorial y comportamiento post-elección</h2>
          <div className="filterGrid" style={{ marginTop: 8 }}>
            <div className="field">
              <label htmlFor="eb-sort-district">Orden</label>
              <select
                id="eb-sort-district"
                className="tableFilterSelect"
                value={state.sortDistrict}
                onChange={(event) => setState((prev) => ({ ...prev, sortDistrict: event.target.value }))}
              >
                <option value="seats_desc">Escaños (desc)</option>
                <option value="seats_asc">Escaños (asc)</option>
                <option value="cohesion_desc">Cohesión post (desc)</option>
                <option value="cohesion_asc">Cohesión post (asc)</option>
              </select>
            </div>
          </div>
        </div>
        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Camara</th>
                <th>Elección</th>
                <th>Partido</th>
                <th>Territorio</th>
                <th>Escaños</th>
                <th>Cuota escaños</th>
                <th>Comportamiento post</th>
              </tr>
            </thead>
            <tbody>
              {filteredDistrictRows.map((row) => (
                <tr key={`${row.bucket}-${row.election_id}-${row.party_id}-${row.territory_id}`}>
                  <td>{toBucketLabel(row.bucket)}</td>
                  <td>{String(row.label || row.election_id || "—")}</td>
                  <td>{String(row.party_label || "—")}</td>
                  <td>{String(row.territory_label || "—")}</td>
                  <td>{formatInt(row.seats || 0)}</td>
                  <td>{formatPct(row.seat_share_pct || 0)}</td>
                  <td>
                    {formatPct(row.behavior_cohesion_pct || 0)} <span className="sub">({formatInt(row.behavior_directional_votes || 0)} direccionales)</span>
                  </td>
                </tr>
              ))}
              {!filteredDistrictRows.length && (
                <tr>
                  <td colSpan={7} className="sub">
                    No hay filas de representación para el filtro aplicado.
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
