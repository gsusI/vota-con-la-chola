"use client";

import { useEffect, useMemo, useState } from "react";

function resolveBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || "";
}

function formatInt(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0) {
    return "0";
  }
  return parsed.toLocaleString("es-ES");
}

function withBasePath(pathname) {
  return `${resolveBasePath()}${pathname}`;
}

function normalize(value) {
  return String(value || "").trim().toLowerCase();
}

function parseFilters(searchParams) {
  const query = normalize(searchParams?.q || "");
  const mode = String(searchParams?.mode || "all");
  const group = normalize(searchParams?.group || searchParams?.slug || "");
  const limitRaw = Number(searchParams?.limit || 0);
  const limit = Number.isFinite(limitRaw) && limitRaw > 0 ? Math.min(limitRaw, 200) : 0;
  return {
    query,
    mode,
    group,
    limit,
  };
}

function filterGroups(groups, query, mode) {
  const out = [];
  for (const item of groups || []) {
    if (!item || typeof item !== "object") {
      continue;
    }
    if (mode === "active" && Number(item.active_person_count || 0) <= 0) {
      continue;
    }
    if (mode === "active-mandates" && Number(item.active_mandates_total || 0) <= 0) {
      continue;
    }
    if (query) {
      const haystack = `${item.label || ""} ${item.slug || ""}`.toLowerCase();
      if (!haystack.includes(query)) {
        continue;
      }
    }
    out.push(item);
  }
  return out;
}

function findGroup(groups, groupKey) {
  if (!groupKey) {
    return null;
  }
  const target = normalize(groupKey);
  for (const group of groups || []) {
    if (normalize(group?.slug || "") === target || normalize(group?.group_key || "") === target) {
      return group;
    }
  }
  return null;
}

function readUrlState() {
  if (typeof window === "undefined") {
    return parseFilters({});
  }
  const url = new URL(window.location.href);
  return parseFilters({
    q: url.searchParams.get("q") || "",
    mode: url.searchParams.get("mode") || "",
    group: url.searchParams.get("group") || url.searchParams.get("slug") || "",
    limit: url.searchParams.get("limit") || "",
  });
}

export default function XrayKindPageClient({ kind, meta, groups, snapshotDate }) {
  const [state, setState] = useState(() => readUrlState());

  useEffect(() => {
    const syncFromLocation = () => setState(readUrlState());
    syncFromLocation();
    window.addEventListener("popstate", syncFromLocation);
    return () => window.removeEventListener("popstate", syncFromLocation);
  }, []);

  const { query, mode, limit, group: groupSlug } = state;

  const sorted = useMemo(() => {
    return filterGroups(groups, query, mode).sort(
      (a, b) => b.person_count - a.person_count || normalize(a.label).localeCompare(normalize(b.label)),
    );
  }, [groups, mode, query]);
  const displayed = useMemo(() => (limit > 0 ? sorted.slice(0, limit) : sorted), [limit, sorted]);
  const selectedGroup = useMemo(() => findGroup(groups, groupSlug), [groupSlug, groups]);

  const queryString = useMemo(() => {
    const queryParams = new URLSearchParams();
    if (query) queryParams.set("q", query);
    if (mode !== "all") queryParams.set("mode", mode);
    if (limit > 0) queryParams.set("limit", String(limit));
    return queryParams.toString();
  }, [limit, mode, query]);

  const listPath = withBasePath(`/people/xray/${encodeURIComponent(kind)}/`);
  const explorerLink = selectedGroup && String(selectedGroup.explorer_wc || "") && String(selectedGroup.explorer_wv || "")
    ? `${withBasePath("/explorer/")}?t=mandates&wc=${encodeURIComponent(
        String(selectedGroup.explorer_wc),
      )}&wv=${encodeURIComponent(String(selectedGroup.explorer_wv))}`
    : "";

  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">Personas</p>
        <h1>
          {meta.label}: grupos y personas
        </h1>
        <p className="sub">{meta.description}</p>
        <div className="chips">
          <span className="chip">Tipo: {kind}</span>
          <span className="chip">Grupos: {formatInt(sorted.length)}</span>
          <span className="chip">Publicación: {snapshotDate || "—"}</span>
        </div>
        <p className="sub">
          <a href={withBasePath("/people/")}>Volver a Directorio</a>
        </p>
      </section>

      <section className="card block">
        <div className="blockHead">
          <h2>{selectedGroup ? `Perfil ${meta.itemLabel}: ${selectedGroup.label}` : "Vínculo"}</h2>
          <p className="sub">
            {selectedGroup
              ? `Grupo "${selectedGroup.label}" con ${formatInt(selectedGroup.person_count || 0)} personas.`
              : `Mostrando ${formatInt(displayed.length)} de ${formatInt(sorted.length)} grupos.`}
          </p>
        </div>
        {selectedGroup ? (
          <>
            <p className="sub">
              <a href={listPath}>Volver al listado de {meta.label.toLowerCase()}</a>
            </p>
            <div className="chips" style={{ marginTop: 6 }}>
              <span className="chip">Personas: {formatInt(selectedGroup.person_count || 0)}</span>
              <span className="chip">Personas activas: {formatInt(selectedGroup.active_person_count || 0)}</span>
              <span className="chip">Mandatos activos: {formatInt(selectedGroup.active_mandates_total || 0)}</span>
              <span className="chip">Votos: {formatInt(selectedGroup.vote_events_total || selectedGroup.votes_total || 0)}</span>
              <span className="chip">Última acción: {String(selectedGroup.last_action_date || "—")}</span>
            </div>
            {explorerLink ? (
              <p className="sub" style={{ marginTop: 10 }}>
                <a href={explorerLink}>Abrir mandatos en Explorer</a>
              </p>
            ) : null}
            <div className="tableWrap" style={{ marginTop: 12 }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Persona</th>
                    <th>Mandatos</th>
                    <th>Mandatos activos</th>
                    <th>Votos</th>
                    <th>Última acción</th>
                  </tr>
                </thead>
                <tbody>
                  {(selectedGroup.top_people || []).map((person) => (
                    <tr key={person?.person_id}>
                      <td>
                        <a className="tableButton" href={withBasePath(`/people/?person_id=${encodeURIComponent(person?.person_id || 0)}`)}>
                          {String(person?.full_name || `Persona ${person?.person_id}`)}
                        </a>
                      </td>
                      <td>{formatInt(person?.mandates_total || 0)}</td>
                      <td>{formatInt(person?.active_mandates || 0)}</td>
                      <td>{formatInt(person?.votes_total || 0)}</td>
                      <td>{String(person?.last_action_date || "—")}</td>
                    </tr>
                  ))}
                  {!selectedGroup.top_people?.length && (
                    <tr>
                      <td colSpan={5} className="sub">
                        Sin personas destacadas para este grupo.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <>
            <div className="tableWrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>{meta.itemLabel}</th>
                    <th>Personas</th>
                    <th>Personas activas</th>
                    <th>Mandatos activos</th>
                    <th>Votos</th>
                    <th>Última acción</th>
                  </tr>
                </thead>
                <tbody>
                  {displayed.map((group) => (
                    <tr key={group.slug}>
                      <td>
                        <a className="tableButton" href={`${listPath}?group=${encodeURIComponent(group?.slug || "")}`}>
                          {group.label || "Sin nombre"}
                        </a>
                      </td>
                      <td>{formatInt(group.person_count || 0)}</td>
                      <td>{formatInt(group.active_person_count || 0)}</td>
                      <td>{formatInt(group.active_mandates_total || 0)}</td>
                      <td>{formatInt(group.vote_events_total || group.votes_total || 0)}</td>
                      <td>{String(group.last_action_date || "—")}</td>
                    </tr>
                  ))}
                  {!displayed.length && (
                    <tr>
                      <td colSpan={6} className="sub">
                        No hay resultados para el filtro aplicado.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {queryString ? <p className="sub" style={{ marginTop: 10 }}>Filtro activo: ?{queryString}</p> : null}
          </>
        )}
      </section>
    </main>
  );
}
