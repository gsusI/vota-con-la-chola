"use client";

import { useEffect, useMemo, useState } from "react";
import { resolveBasePath, withBasePath } from "../path-utils.mjs";

function readUrlState() {
  if (typeof window === "undefined") {
    return {
      level: "all",
      territory: "all",
      status: "all",
    };
  }
  const params = new URLSearchParams(window.location.search);
  return {
    level: params.get("level") || "all",
    territory: params.get("territory") || "all",
    status: params.get("status") || "all",
  };
}

function useElectionCalendarPayload() {
  const [state, setState] = useState({ loading: true, error: null, data: null });

  useEffect(() => {
    const controller = new AbortController();
    const url = `${resolveBasePath()}/calendario-electoral/data/election-calendar.json`;
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

function formatMonth(value) {
  if (!value) {
    return "Sin fecha";
  }
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return "Sin fecha";
  }
  return new Intl.DateTimeFormat("es-ES", { month: "long", year: "numeric" }).format(parsed);
}

function formatDay(value, precision) {
  if (!value) {
    return "Sin fecha";
  }
  if (precision === "year") {
    return value.slice(0, 4);
  }
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("es-ES", { day: "2-digit", month: "short" }).format(parsed);
}

function dateRangeLabel(event) {
  if (event.date_label) {
    return event.date_label;
  }
  if (event.date && event.date_end) {
    return `${event.date} a ${event.date_end}`;
  }
  return event.date || "sin fecha fijada";
}

function sourceLabel(event) {
  if (event.source_kind === "official_calendar") {
    return event.source_verified ? "Oficial verificada" : "Oficial pendiente";
  }
  if (event.certainty === "condicional") {
    return "Condicional";
  }
  return "Ciclo legal";
}

function sourceClass(event) {
  if (event.source_kind === "official_calendar" && event.source_verified) {
    return "electionCalendarSourcePill--official";
  }
  if (event.certainty === "condicional" || event.date_precision === "unknown") {
    return "electionCalendarSourcePill--conditional";
  }
  return "electionCalendarSourcePill--computed";
}

function uniqueValues(rows, field) {
  return Array.from(new Set(rows.map((row) => row[field]).filter(Boolean))).sort((a, b) =>
    String(a).localeCompare(String(b), "es"),
  );
}

function groupByMonth(rows) {
  const groups = new Map();
  for (const row of rows) {
    const key = row.date ? row.date.slice(0, 7) : "sin-fecha";
    const label = row.date ? formatMonth(row.date) : "Sin fecha";
    if (!groups.has(key)) {
      groups.set(key, { key, label, rows: [] });
    }
    groups.get(key).rows.push(row);
  }
  return Array.from(groups.values());
}

function updateUrlState(state) {
  if (typeof window === "undefined") {
    return;
  }
  const params = new URLSearchParams();
  if (state.level !== "all") params.set("level", state.level);
  if (state.territory !== "all") params.set("territory", state.territory);
  if (state.status !== "all") params.set("status", state.status);
  const nextUrl = `${window.location.pathname}${params.toString() ? `?${params.toString()}` : ""}`;
  window.history.replaceState({}, "", nextUrl);
}

function CalendarFilter({ label, value, values, onChange }) {
  return (
    <label className="electionCalendarFilter">
      <span className="electionCalendarFilter__label">{label}</span>
      <select
        className="electionCalendarFilter__select"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="all">Todo</option>
        {values.map((item) => (
          <option value={item} key={item}>
            {item}
          </option>
        ))}
      </select>
    </label>
  );
}

function TimelineEvent({ event }) {
  return (
    <article className="electionCalendarEvent">
      <div className="electionCalendarEvent__date">
        <span className="electionCalendarEvent__day">{formatDay(event.date, event.date_precision)}</span>
        <span className="electionCalendarEvent__range">{dateRangeLabel(event)}</span>
      </div>
      <div className="electionCalendarEvent__body">
        <div className="electionCalendarEvent__header">
          <h3 className="electionCalendarEvent__title">{event.election}</h3>
          <span className={`electionCalendarSourcePill ${sourceClass(event)}`}>{sourceLabel(event)}</span>
        </div>
        <div className="electionCalendarEvent__meta">
          <span className="electionCalendarEvent__metaItem">{event.level}</span>
          <span className="electionCalendarEvent__metaItem">{event.territory}</span>
          <span className="electionCalendarEvent__metaItem">{event.status}</span>
        </div>
        <p className="electionCalendarEvent__notes">{event.notes}</p>
        <a className="electionCalendarEvent__sourceLink" href={event.source_url} target="_blank" rel="noreferrer">
          Fuente
        </a>
      </div>
    </article>
  );
}

export default function ElectionCalendarPage() {
  const { loading, error, data } = useElectionCalendarPayload();
  const [filters, setFilters] = useState(() => readUrlState());

  useEffect(() => {
    setFilters(readUrlState());
  }, []);

  useEffect(() => {
    updateUrlState(filters);
  }, [filters]);

  const events = useMemo(() => data?.events || [], [data?.events]);
  const filteredEvents = useMemo(
    () =>
      events.filter((event) => {
        if (filters.level !== "all" && event.level !== filters.level) return false;
        if (filters.territory !== "all" && event.territory !== filters.territory) return false;
        if (filters.status !== "all" && event.status !== filters.status) return false;
        return true;
      }),
    [events, filters],
  );
  const timelineEvents = useMemo(() => filteredEvents.filter((event) => event.date), [filteredEvents]);
  const undatedEvents = useMemo(() => filteredEvents.filter((event) => !event.date), [filteredEvents]);
  const grouped = useMemo(() => groupByMonth(timelineEvents), [timelineEvents]);
  const levels = useMemo(() => uniqueValues(events, "level"), [events]);
  const territories = useMemo(() => uniqueValues(events, "territory"), [events]);
  const statuses = useMemo(() => uniqueValues(events, "status"), [events]);
  const nextOfficial = timelineEvents.find((event) => event.source_kind === "official_calendar") || timelineEvents[0];

  return (
    <main className="shell electionCalendarPage">
      <section className="electionCalendarHero card" aria-labelledby="election-calendar-title">
        <div className="electionCalendarHero__copy">
          <p className="electionCalendarHero__eyebrow eyebrow">Calendario electoral</p>
          <h1 className="electionCalendarHero__title" id="election-calendar-title">
            Próximas elecciones
          </h1>
          <p className="electionCalendarHero__summary sub">
            Convocatorias oficiales, ciclos legales y fechas condicionales en una sola línea temporal.
          </p>
        </div>
        <div className="electionCalendarHero__metrics" aria-label="Resumen del calendario">
          <div className="electionCalendarMetric">
            <span className="electionCalendarMetric__label">Eventos</span>
            <strong className="electionCalendarMetric__value">{data?.totales?.events ?? "-"}</strong>
          </div>
          <div className="electionCalendarMetric">
            <span className="electionCalendarMetric__label">Oficiales</span>
            <strong className="electionCalendarMetric__value">
              {data?.totales?.official_calendar_events ?? "-"}
            </strong>
          </div>
          <div className="electionCalendarMetric">
            <span className="electionCalendarMetric__label">Referencia</span>
            <strong className="electionCalendarMetric__value electionCalendarMetric__value--date">
              {data?.fecha_referencia || "-"}
            </strong>
          </div>
        </div>
      </section>

      <section className="electionCalendarControls card" aria-label="Filtros del calendario electoral">
        <CalendarFilter
          label="Ámbito"
          value={filters.level}
          values={levels}
          onChange={(level) => setFilters((current) => ({ ...current, level }))}
        />
        <CalendarFilter
          label="Territorio"
          value={filters.territory}
          values={territories}
          onChange={(territory) => setFilters((current) => ({ ...current, territory }))}
        />
        <CalendarFilter
          label="Estado"
          value={filters.status}
          values={statuses}
          onChange={(status) => setFilters((current) => ({ ...current, status }))}
        />
      </section>

      {loading ? <p className="electionCalendarState card">Cargando calendario...</p> : null}
      {error ? <p className="electionCalendarState electionCalendarState--error card">{error}</p> : null}

      {!loading && !error ? (
        <section className="electionCalendarContent">
          <aside className="electionCalendarNextPanel card" aria-label="Siguiente cita">
            <span className="electionCalendarNextPanel__label">Siguiente</span>
            <strong className="electionCalendarNextPanel__date">
              {nextOfficial ? dateRangeLabel(nextOfficial) : "Sin datos"}
            </strong>
            <span className="electionCalendarNextPanel__title">
              {nextOfficial ? nextOfficial.election : "Sin eventos"}
            </span>
            <span className="electionCalendarNextPanel__territory">
              {nextOfficial ? nextOfficial.territory : ""}
            </span>
            <a className="electionCalendarNextPanel__methodLink" href={withBasePath("/explorer-sources/")}>
              Fuentes
            </a>
          </aside>

          <div className="electionCalendarTimeline" aria-label="Timeline electoral">
            {grouped.length ? (
              grouped.map((group) => (
                <section className="electionCalendarMonthGroup" key={group.key} aria-label={group.label}>
                  <h2 className="electionCalendarMonthGroup__title">{group.label}</h2>
                  <div className="electionCalendarMonthGroup__events">
                    {group.rows.map((event) => (
                      <TimelineEvent event={event} key={event.event_id} />
                    ))}
                  </div>
                </section>
              ))
            ) : (
              <p className="electionCalendarState card">Sin eventos con estos filtros.</p>
            )}

            {undatedEvents.length ? (
              <section className="electionCalendarUndated card" aria-label="Fechas sin fijar">
                <h2 className="electionCalendarUndated__title">Sin fecha cerrada</h2>
                <div className="electionCalendarUndated__list">
                  {undatedEvents.map((event) => (
                    <TimelineEvent event={event} key={event.event_id} />
                  ))}
                </div>
              </section>
            ) : null}
          </div>
        </section>
      ) : null}
    </main>
  );
}
