import fs from "node:fs";
import path from "node:path";
import { notFound } from "next/navigation";

const KIND_META = {
  party: {
    label: "Partido",
    description: "Personas vinculadas a cada partido por sus mandatos.",
    itemLabel: "Partido",
  },
  institution: {
    label: "Institución",
    description: "Personas con mandatos en cada institución.",
    itemLabel: "Institución",
  },
  ambito: {
    label: "Ámbito",
    description: "Personas agrupadas por ámbito territorial-administrativo.",
    itemLabel: "Ámbito",
  },
  territorio: {
    label: "Territorio",
    description: "Personas vinculadas a cada territorio.",
    itemLabel: "Territorio",
  },
  cargo: {
    label: "Cargo",
    description: "Personas con cada tipo de cargo en mandatos.",
    itemLabel: "Cargo",
  },
};

function resolveBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || (process.env.NODE_ENV === "production" ? "/vota-con-la-chola" : "");
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

function resolveDataPath() {
  return path.resolve(process.cwd(), "public", "people", "data", "xray.json");
}

function loadXrayPayload() {
  const dataPath = resolveDataPath();
  if (!fs.existsSync(dataPath)) {
    return null;
  }
  const raw = fs.readFileSync(dataPath, "utf-8");
  return JSON.parse(raw);
}

export async function generateStaticParams() {
  return Object.keys(KIND_META).map((kind) => ({ kind }));
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

export default function XrayKindIndexPage({ params, searchParams }) {
  const payload = loadXrayPayload();
  const kind = String(params?.kind || "").toLowerCase();
  const meta = KIND_META[kind];

  if (!meta || !payload || !payload.groups) {
    return notFound();
  }

  const groups = Array.isArray(payload.groups[kind]) ? payload.groups[kind] : [];
  const { query, mode, limit, group: groupSlug } = parseFilters(searchParams);
  const filtered = filterGroups(groups, query, mode);
  const sorted = filtered.sort((a, b) => b.person_count - a.person_count || normalize(a.label).localeCompare(normalize(b.label)));
  const displayed = limit > 0 ? sorted.slice(0, limit) : sorted;
  const selectedGroup = findGroup(groups, groupSlug);

  const queryParams = new URLSearchParams();
  if (query) queryParams.set("q", query);
  if (mode !== "all") queryParams.set("mode", mode);
  if (limit > 0) queryParams.set("limit", String(limit));
  const queryString = queryParams.toString();
  const listPath = withBasePath(`/people/xray/${encodeURIComponent(kind)}/`);
  const listLink = (item) =>
    `${listPath}?group=${encodeURIComponent(item?.slug || "")}`;
  const groupExplainer = (
    <p className="sub">
      <a href={listPath}>Volver al listado de {meta.label.toLowerCase()}</a>
    </p>
  );
  const explorerLink = selectedGroup && String(selectedGroup.explorer_wc || "") && String(selectedGroup.explorer_wv || "")
    ? `${withBasePath("/explorer/")}?t=mandates&wc=${encodeURIComponent(
        String(selectedGroup.explorer_wc),
      )}&wv=${encodeURIComponent(String(selectedGroup.explorer_wv))}`
    : "";

  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">X-ray de personas</p>
        <h1>
          {meta.label}: exploración por agrupación
        </h1>
        <p className="sub">{meta.description}</p>
        <div className="chips">
          <span className="chip">Tipo: {kind}</span>
          <span className="chip">Grupos: {formatInt(sorted.length)}</span>
          <span className="chip">Snapshot: {payload?.meta?.snapshot_date || "—"}</span>
        </div>
        <p className="sub">
          <a href={withBasePath("/people/")}>Volver a Directorio</a>
          <span style={{ marginLeft: "10px", color: "var(--ink-soft)" }}>
            Tip: usa <code>q</code> y <code>mode</code> en query string para filtrar.
          </span>
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
            {groupExplainer}
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
                        <a className="tableButton" href={listLink(group)}>
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
