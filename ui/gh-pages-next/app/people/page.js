"use client";

import { useEffect, useMemo, useRef, useState } from "react";

function resolveBasePath() {
  return process.env.NEXT_PUBLIC_BASE_PATH || (process.env.NODE_ENV === "production" ? "/vota-con-la-chola" : "");
}

function withBasePath(path) {
  return `${resolveBasePath()}${path}`;
}

function formatInt(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "0";
  }
  return Number(value).toLocaleString("es-ES");
}

function parsePipe(value) {
  return String(value || "")
    .split("|")
    .map((item) => item.trim())
    .filter(Boolean);
}

function normalizeLabel(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function normalizeSearchText(value) {
  return normalizeLabel(value).replace(/[\s-]+/g, " ").trim();
}

function slugify(value) {
  const normalized = normalizeLabel(value)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return normalized || "sin-valor";
}

function resolveXraySlugFromGroups(groupsByKind, kind, payload, label) {
  if (!kind || !label) {
    return "";
  }
  const list = Array.isArray(groupsByKind?.[kind]) ? groupsByKind[kind] : [];
  const target = normalizeLabel(label);
  const exact = list.find((item) => normalizeLabel(item?.label || "") === target);
  if (exact?.slug) {
    return String(exact.slug);
  }
  const fallback = slugify(label);
  const direct = payload?.group_index?.[kind]?.[fallback];
  if (direct) {
    return fallback;
  }
  return "";
}

function asInt(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function readUrlState() {
  if (typeof window === "undefined") {
    return {
      personId: 0,
      bucket: "",
      query: "",
      mode: "all",
    };
  }
  const url = new URL(window.location.href);
  const personId = Number(url.searchParams.get("person_id") || 0);
  const bucket = String(url.searchParams.get("bucket") || "").trim().toUpperCase();
  const query = String(url.searchParams.get("q") || "").trim();
  const modeRaw = String(url.searchParams.get("mode") || "all");
  const mode = ["all", "queue", "active", "votes"].includes(modeRaw) ? modeRaw : "all";
  return {
    personId: Number.isFinite(personId) ? personId : 0,
    bucket,
    query,
    mode,
  };
}

function useManifest() {
  const [state, setState] = useState({ loading: true, error: null, data: null });

  useEffect(() => {
    const controller = new AbortController();
    const url = `${resolveBasePath()}/people/data/profiles.json`;

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

function useRowsData(filePath) {
  const [state, setState] = useState({ loading: true, error: null, data: null, filePath: "" });

  useEffect(() => {
    if (!filePath) {
      setState({ loading: false, error: null, data: null, filePath: "" });
      return;
    }

    const controller = new AbortController();
    const url = `${resolveBasePath()}/people/data/${filePath}`;

    setState((prev) => ({ ...prev, loading: true, error: null, filePath }));

    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Respuesta no válida: ${response.status}`);
        }
        return response.json();
      })
      .then((payload) => {
        setState({ loading: false, error: null, data: payload, filePath });
      })
      .catch((error) => {
        if (error.name === "AbortError") {
          return;
        }
        setState({ loading: false, error: error.message || String(error), data: null, filePath });
      });

    return () => controller.abort();
  }, [filePath]);

  return state;
}

const XRAY_KIND_LINKS = [
  { kind: "party", label: "Partidos", href: "/people/xray/party/" },
  { kind: "institution", label: "Instituciones", href: "/people/xray/institution/" },
  { kind: "ambito", label: "Ámbitos", href: "/people/xray/ambito/" },
  { kind: "territorio", label: "Territorios", href: "/people/xray/territorio/" },
  { kind: "cargo", label: "Cargos", href: "/people/xray/cargo/" },
];

function rowGetter(columns) {
  const map = {};
  for (let i = 0; i < columns.length; i += 1) {
    map[columns[i]] = i;
  }
  return (row, col) => row?.[map[col]];
}

function profilePositions(row, getValue) {
  const raw = String(getValue(row, "positions_ever_json") || "[]");
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function filterRows(rows, getValue, query, mode, limit) {
  const q = normalizeSearchText(query);
  const maxRows = Math.max(20, Number(limit) || 250);
  const shown = [];
  let total = 0;

  for (const row of rows) {
    const pending = asInt(getValue(row, "queue_pending_total"));
    const inProgress = asInt(getValue(row, "queue_in_progress_total"));
    const active = asInt(getValue(row, "active_mandates"));
    const votes = asInt(getValue(row, "votes_total"));

    if (mode === "queue" && pending + inProgress <= 0) {
      continue;
    }
    if (mode === "active" && active <= 0) {
      continue;
    }
    if (mode === "votes" && votes <= 0) {
      continue;
    }

    if (q) {
      const personId = asInt(getValue(row, "person_id"));
      const qContainsId = String(personId) && String(personId).includes(q);
      const haystack = [
        getValue(row, "full_name"),
        getValue(row, "canonical_key"),
        getValue(row, "territory_name"),
        getValue(row, "roles_ever"),
        getValue(row, "parties_ever"),
      ]
        .map((value) => String(value || ""))
        .join(" ")
        .replace(/["'[\]{}]/g, " ");

      if (!qContainsId && !normalizeSearchText(haystack).includes(q)) {
        continue;
      }
    }

    total += 1;
    if (shown.length < maxRows) {
      shown.push(row);
    }
  }

  return { shown, total };
}

export default function PeoplePage() {
  const { loading: manifestLoading, error: manifestError, data: manifest } = useManifest();
  const { data: xrayPayload } = useRowsData("xray.json");
  const initialUrlState = useMemo(() => readUrlState(), []);
  const [bucket, setBucket] = useState("top");
  const [query, setQuery] = useState(initialUrlState.query || "");
  const [mode, setMode] = useState(initialUrlState.mode || "all");
  const [rowsLimit, setRowsLimit] = useState(250);
  const [selectedPersonId, setSelectedPersonId] = useState(0);

  const personBucketFromInitialUrl = useMemo(() => {
    if (!manifest || initialUrlState.personId <= 0) {
      return "";
    }
    return String(manifest.person_bucket_index?.[String(initialUrlState.personId)] || "").toUpperCase();
  }, [manifest, initialUrlState.personId]);

  const initializedFromUrlRef = useRef(false);
  useEffect(() => {
    if (initializedFromUrlRef.current) {
      return;
    }
    if (initialUrlState.personId > 0) {
      setSelectedPersonId(initialUrlState.personId);
    }
    if (initialUrlState.bucket) {
      setBucket(initialUrlState.bucket === "TOP" ? "top" : initialUrlState.bucket);
      initializedFromUrlRef.current = true;
      return;
    }

    if (!manifest) {
      return;
    }
    if (!initialUrlState.personId || !personBucketFromInitialUrl) {
      initializedFromUrlRef.current = true;
      return;
    }
    if (personBucketFromInitialUrl !== "TOP" && personBucketFromInitialUrl !== bucket) {
      setBucket(personBucketFromInitialUrl);
    }
    initializedFromUrlRef.current = true;
  }, [manifest, initialUrlState, personBucketFromInitialUrl, bucket]);

  useEffect(() => {
    if (!manifest || selectedPersonId <= 0) {
      return;
    }
    const bucketFromIndex = String(manifest.person_bucket_index?.[String(selectedPersonId)] || "").toUpperCase();
    if (!bucketFromIndex) {
      return;
    }
    const expectedBucket = bucketFromIndex === "TOP" ? "top" : bucketFromIndex;
    if (bucket !== expectedBucket) {
      setBucket(expectedBucket);
    }
  }, [manifest, selectedPersonId, bucket]);

  const bucketFileMap = useMemo(() => {
    const map = new Map();
    for (const item of manifest?.buckets || []) {
      map.set(String(item.bucket || "").toUpperCase(), item.file);
    }
    return map;
  }, [manifest]);

  const personBucketFromIndex = useMemo(() => {
    if (!manifest || selectedPersonId <= 0) {
      return "";
    }
    const bucket = String(manifest.person_bucket_index?.[String(selectedPersonId)] || "").toUpperCase();
    if (!bucket) {
      return "";
    }
    return bucket === "TOP" ? "top" : bucket;
  }, [manifest, selectedPersonId]);

  const selectedPersonFile = useMemo(() => {
    if (!manifest || !personBucketFromIndex) {
      return "";
    }
    if (personBucketFromIndex === "top") {
      return String(manifest.top?.file || "");
    }
    return String(bucketFileMap.get(personBucketFromIndex) || manifest.top?.file || "");
  }, [manifest, personBucketFromIndex, bucketFileMap]);

  const activeFile = useMemo(() => {
    if (!manifest) {
      return "";
    }
    if (bucket === "top") {
      return String(manifest.top?.file || "");
    }
    const file = bucketFileMap.get(String(bucket || "").toUpperCase());
    return file || String(manifest.top?.file || "");
  }, [bucket, bucketFileMap, manifest]);

  const { loading: rowsLoading, error: rowsError, data: rowsPayload } = useRowsData(activeFile);
  const {
    loading: selectedBucketLoading,
    data: selectedBucketPayload,
  } = useRowsData(selectedPersonFile || activeFile);

  const columns = rowsPayload?.columns || manifest?.columns || [];
  const rows = rowsPayload?.rows || [];
  const selectedBucketRows = useMemo(() => {
    if (selectedPersonFile && selectedPersonId > 0 && selectedPersonFile === activeFile) {
      return rows;
    }
    return selectedBucketPayload?.rows || [];
  }, [selectedPersonFile, selectedPersonId, activeFile, rows, selectedBucketPayload]);

  const getValue = useMemo(() => rowGetter(columns), [columns]);
  const getSelectedValue = useMemo(
    () => rowGetter(selectedBucketPayload?.columns || columns || manifest?.columns || []),
    [selectedBucketPayload?.columns, columns, manifest?.columns],
  );

  const filtered = useMemo(() => {
    if (!rows.length || !columns.length) {
      return { shown: [], total: 0 };
    }
    return filterRows(rows, getValue, query, mode, rowsLimit);
  }, [rows, columns, getValue, query, mode, rowsLimit]);

  const rowById = useMemo(() => {
    const map = new Map();
    for (const row of rows) {
      const personId = asInt(getValue(row, "person_id"));
      if (personId > 0) {
        map.set(personId, row);
      }
    }
    return map;
  }, [rows, getValue]);

  const selectedRow = useMemo(() => {
    if (selectedPersonId <= 0) {
      return filtered.shown[0] || null;
    }
    if (rowById.has(selectedPersonId)) {
      return rowById.get(selectedPersonId);
    }
    if (selectedPersonId > 0 && selectedBucketRows.length) {
      for (const row of selectedBucketRows) {
        const personId = asInt(getSelectedValue(row, "person_id"));
        if (personId === selectedPersonId) {
          return row;
        }
      }
    }
    return null;
  }, [selectedPersonId, rowById, filtered.shown, selectedBucketRows, getSelectedValue]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const url = new URL(window.location.href);
    if (selectedPersonId > 0) {
      url.searchParams.set("person_id", String(selectedPersonId));
    } else {
      url.searchParams.delete("person_id");
    }
    if (bucket && bucket !== "top") {
      url.searchParams.set("bucket", String(bucket).toUpperCase());
    } else {
      url.searchParams.delete("bucket");
    }
    if (query.trim()) {
      url.searchParams.set("q", query.trim());
    } else {
      url.searchParams.delete("q");
    }
    if (mode && mode !== "all") {
      url.searchParams.set("mode", mode);
    } else {
      url.searchParams.delete("mode");
    }
    window.history.replaceState({}, "", url.toString());
  }, [selectedPersonId, bucket, query, mode]);

  const profile = useMemo(() => {
    if (!selectedRow) {
      return null;
    }

    const personId = asInt(getValue(selectedRow, "person_id"));
    const positions = profilePositions(selectedRow, getValue);
    const pending = asInt(getValue(selectedRow, "queue_pending_total"));
    const inProgress = asInt(getValue(selectedRow, "queue_in_progress_total"));

    return {
      personId,
      fullName: String(getValue(selectedRow, "full_name") || ""),
      canonicalKey: String(getValue(selectedRow, "canonical_key") || ""),
      birthDate: String(getValue(selectedRow, "birth_date") || ""),
      genderLabel: String(getValue(selectedRow, "gender_label") || ""),
      territoryName: String(getValue(selectedRow, "territory_name") || ""),
      mandatesTotal: asInt(getValue(selectedRow, "mandates_total")),
      activeMandates: asInt(getValue(selectedRow, "active_mandates")),
      institutionsTotal: asInt(getValue(selectedRow, "institutions_total")),
      partiesTotal: asInt(getValue(selectedRow, "parties_total")),
      votesTotal: asInt(getValue(selectedRow, "votes_total")),
      voteEventsTotal: asInt(getValue(selectedRow, "vote_events_total")),
      declaredEvidenceTotal: asInt(getValue(selectedRow, "declared_evidence_total")),
      revealedVoteEvidenceTotal: asInt(getValue(selectedRow, "revealed_vote_evidence_total")),
      topicPositionsTotal: asInt(getValue(selectedRow, "topic_positions_total")),
      aliasesTotal: asInt(getValue(selectedRow, "aliases_total")),
      identifiersTotal: asInt(getValue(selectedRow, "identifiers_total")),
      firstMandateStart: String(getValue(selectedRow, "first_mandate_start") || ""),
      lastMandateDate: String(getValue(selectedRow, "last_mandate_date") || ""),
      lastVoteDate: String(getValue(selectedRow, "last_vote_date") || ""),
      lastEvidenceDate: String(getValue(selectedRow, "last_evidence_date") || ""),
      lastActionDate: String(getValue(selectedRow, "last_action_date") || ""),
      rolesEver: parsePipe(getValue(selectedRow, "roles_ever")),
      institutionsEver: parsePipe(getValue(selectedRow, "institutions_ever")),
      partiesEver: parsePipe(getValue(selectedRow, "parties_ever")),
      queuePendingTotal: pending,
      queueInProgressTotal: inProgress,
      queueOpenTotal: pending + inProgress,
      queuePriorityMax: asInt(getValue(selectedRow, "queue_priority_max")),
      queueGapCodes: parsePipe(getValue(selectedRow, "queue_gap_codes")),
      queueNextActions: parsePipe(getValue(selectedRow, "queue_next_actions")),
      positions,
      };
  }, [selectedRow, getValue]);

  const xrayProfiles = useMemo(() => {
    const groups = xrayPayload?.groups || {};
    const makeLinks = (kind, values) => {
      const out = new Map();
      for (const value of values) {
        const label = String(value || "").trim();
        const slug = resolveXraySlugFromGroups(groups, kind, xrayPayload, label);
        if (!label || !slug) {
          continue;
        }
        const key = `${kind}:${slug}`;
        if (!out.has(key)) {
          out.set(key, {
            kind,
            label,
            href: `${resolveBasePath()}/people/xray/${kind}/?group=${encodeURIComponent(slug)}`,
          });
        }
      }
      return [...out.values()];
    };

    if (!profile) {
      return { roles: [], institutions: [], parties: [], territory: [] };
    }
    return {
      roles: makeLinks("cargo", profile.rolesEver),
      institutions: makeLinks("institution", profile.institutionsEver),
      parties: makeLinks("party", profile.partiesEver),
      territory: profile.territoryName ? makeLinks("territorio", [profile.territoryName]) : [],
    };
  }, [xrayPayload, profile]);

  const bucketOptions = useMemo(() => {
    const options = [{ value: "top", label: `Top (${formatInt(manifest?.top?.rows_total || 0)})` }];
    for (const item of manifest?.buckets || []) {
      options.push({
        value: String(item.bucket || "").toUpperCase(),
        label: `${String(item.bucket || "").toUpperCase()} (${formatInt(item.rows_total || 0)})`,
      });
    }
    return options;
  }, [manifest]);

  if (manifestLoading) {
    return (
      <main className="shell">
        <section className="card block">
          <p className="sub">Cargando directorio de personas…</p>
        </section>
      </main>
    );
  }

  if (manifestError || !manifest) {
    return (
      <main className="shell">
        <section className="card block">
          <h2>Directorio no disponible</h2>
          <p className="sub">No pude cargar el manifiesto estático de perfiles.</p>
          <p className="sub">Error: {manifestError || "sin datos"}</p>
          <p className="sub">
            Asegura regenerar <code>docs/gh-pages/people/data/profiles.json</code> con{" "}
            <code>just explorer-gh-pages-build</code> o con{" "}
            <code>GH_PAGES_NEXT_PRIME_EXPORT=1 just gh-pages-next</code>.
          </p>
        </section>
      </main>
    );
  }

  const explorerBase = withBasePath("/explorer/");
  const profileSection = (
      <section className="card block">
        <div className="blockHead"><h2>Perfil seleccionado</h2></div>
        {!profile ? (
          <p className="sub">
              {selectedPersonId > 0 && (rowsLoading || (selectedPersonFile && selectedPersonFile !== activeFile && selectedBucketLoading))
                ? `Cargando el perfil ${selectedPersonId}…`
                : selectedPersonId > 0
                ? `No se encontró el perfil ${selectedPersonId} en esta vista.`
                : "Selecciona una persona para ver su xray."}
          </p>
        ) : (
        <>
          <h3 style={{ margin: "8px 0 4px" }}>{profile.fullName}</h3>
          <p className="sub">Clave canónica: <code>{profile.canonicalKey || "—"}</code></p>
          <div className="chips">
            <span className="chip">Mandatos: {formatInt(profile.mandatesTotal)}</span>
            <span className="chip">Activos: {formatInt(profile.activeMandates)}</span>
            <span className="chip">Votos: {formatInt(profile.votesTotal)}</span>
            <span className="chip">Cola abierta: {formatInt(profile.queueOpenTotal)}</span>
          </div>

          <div className="twoCols" style={{ marginTop: 12 }}>
            <article className="kpiCard">
              <span className="kpiLabel">Identidad</span>
              <p className="sub">Nacimiento: {profile.birthDate || "—"}</p>
              <p className="sub">Género: {profile.genderLabel || "—"}</p>
              <p className="sub">Territorio: {profile.territoryName || "—"}</p>
              <p className="sub">Identificadores: {formatInt(profile.identifiersTotal)}</p>
              <p className="sub">Alias: {formatInt(profile.aliasesTotal)}</p>
            </article>

            <article className="kpiCard">
              <span className="kpiLabel">Actividad</span>
              <p className="sub">Instituciones: {formatInt(profile.institutionsTotal)}</p>
              <p className="sub">Partidos: {formatInt(profile.partiesTotal)}</p>
              <p className="sub">Eventos de voto: {formatInt(profile.voteEventsTotal)}</p>
              <p className="sub">Evidencia declarada: {formatInt(profile.declaredEvidenceTotal)}</p>
              <p className="sub">Posiciones temáticas: {formatInt(profile.topicPositionsTotal)}</p>
            </article>
          </div>

          <div className="twoCols" style={{ marginTop: 12 }}>
            <article className="kpiCard">
              <span className="kpiLabel">Ventana temporal</span>
              <p className="sub">Primer mandato: {profile.firstMandateStart || "—"}</p>
              <p className="sub">Último mandato: {profile.lastMandateDate || "—"}</p>
              <p className="sub">Último voto: {profile.lastVoteDate || "—"}</p>
              <p className="sub">Última evidencia: {profile.lastEvidenceDate || "—"}</p>
              <p className="sub">Última acción: {profile.lastActionDate || "—"}</p>
            </article>

            <article className="kpiCard">
              <span className="kpiLabel">Datos faltantes públicos</span>
              <p className="sub">Pendientes: {formatInt(profile.queuePendingTotal)}</p>
              <p className="sub">En progreso: {formatInt(profile.queueInProgressTotal)}</p>
              <p className="sub">Prioridad max: {formatInt(profile.queuePriorityMax)}</p>
              <p className="sub">Gaps: {profile.queueGapCodes.length ? profile.queueGapCodes.join(", ") : "—"}</p>
              <p className="sub">Siguiente acción: {profile.queueNextActions.length ? profile.queueNextActions.join(", ") : "—"}</p>
            </article>
          </div>

          <div style={{ marginTop: 12 }}>
            <h3 style={{ margin: "0 0 8px" }}>Posiciones que ha ocupado</h3>
            {profile.positions.length ? (
              <div className="tableWrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Cargo</th>
                      <th>Institución</th>
                      <th>Partido</th>
                      <th>Ámbito</th>
                      <th>Territorio</th>
                      <th>Inicio</th>
                      <th>Fin</th>
                      <th>Activo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {profile.positions.map((position, idx) => (
                      <tr key={`${profile.personId}-${idx}`}>
                        <td>{position.role_title || "—"}</td>
                        <td>{position.institution_name || "—"}</td>
                        <td>{position.party || "—"}</td>
                        <td>{position.admin_level || "—"}</td>
                        <td>{position.territory_name || "—"}</td>
                        <td>{position.first_start_date || "—"}</td>
                        <td>{position.last_end_date || "—"}</td>
                        <td>{position.currently_active ? "sí" : "no"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="sub">Sin posiciones históricas registradas en el snapshot.</p>
            )}
          </div>

          <div style={{ marginTop: 12 }}>
            <h3 style={{ margin: "0 0 8px" }}>Etiquetas del perfil</h3>
            <p className="sub" style={{ marginBottom: 8 }}>
              Roles, instituciones y partidos (enlace a x-ray de entidad).
            </p>
            <div className="profileTags">
              {xrayProfiles.roles.length ? (
                xrayProfiles.roles.map((link) => (
                  <a className="chip" href={link.href} key={link.href}>
                    {link.label}
                  </a>
                ))
              ) : (
                profile.rolesEver.map((role) => <span className="chip" key={`role-${role}`}>{role}</span>)
              )}
              {xrayProfiles.institutions.length ? (
                xrayProfiles.institutions.map((link) => (
                  <a className="chip" href={link.href} key={link.href}>
                    {link.label}
                  </a>
                ))
              ) : (
                profile.institutionsEver.map((institution) => (
                  <span className="chip" key={`institution-${institution}`}>{institution}</span>
                ))
              )}
              {xrayProfiles.parties.length ? (
                xrayProfiles.parties.map((link) => (
                  <a className="chip" href={link.href} key={link.href}>
                    {link.label}
                  </a>
                  ))
              ) : (
                profile.partiesEver.map((party) => <span className="chip" key={`party-${party}`}>{party}</span>)
              )}
              {xrayProfiles.territory.length ? (
                xrayProfiles.territory.map((link) => (
                  <a className="chip" href={link.href} key={link.href}>
                    {link.label}
                  </a>
                ))
              ) : (
                profile.territoryName ? <span className="chip">Territorio: {profile.territoryName}</span> : null
              )}
            </div>
          </div>

          <ul className="artifactList" style={{ marginTop: 12 }}>
            <li>
              <a href={`${explorerBase}?t=mandates&wc=person_id&wv=${profile.personId}`}>Explorer: mandatos</a>
              <span>drill-down directo</span>
            </li>
            <li>
              <a href={`${explorerBase}?t=parl_vote_member_votes&wc=person_id&wv=${profile.personId}`}>Explorer: votos persona</a>
              <span>histórico de voto</span>
            </li>
            <li>
              <a href={`${explorerBase}?t=topic_evidence&wc=person_id&wv=${profile.personId}`}>Explorer: evidencia temática</a>
              <span>trazabilidad de postura</span>
            </li>
            <li>
              <a href={`${explorerBase}?t=person_public_data_queue&wc=person_id&wv=${profile.personId}`}>Explorer: cola de datos faltantes</a>
              <span>backlog por persona</span>
            </li>
          </ul>
        </>
      )}
    </section>
  );

  return (
    <main className="shell">
      <section className="hero card">
        <p className="eyebrow">Directory + Xray</p>
        <h1>Personas y trayectoria pública</h1>
        <p className="sub">
          Directorio navegable de personas con resumen de actividad, posiciones que han ocupado y cola de datos públicos faltantes.
        </p>
        <div className="chips">
          <span className="chip">Snapshot: {manifest.meta?.snapshot_date || "—"}</span>
          <span className="chip">Personas: {formatInt(manifest.meta?.people_total || 0)}</span>
          <span className="chip">Buckets: {formatInt((manifest.buckets || []).length)}</span>
        </div>
      </section>

      {profileSection}

      <section className="card block">
        <div className="blockHead"><h2>Directorio</h2></div>
        <p className="sub">
          Carga inicial con top; para buscar en todo el padrón usa bucket por inicial.</p>
        {selectedPersonId > 0 ? (
          <p className="sub" style={{ marginTop: 6 }}>
            Perfil seleccionado arriba. Esta tabla es el directorio navegable completo.
          </p>
        ) : null}
        <div className="filterGrid">
          <label className="field">
            Bucket
            <select value={bucket} onChange={(e) => setBucket(e.target.value)}>
              {bucketOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Modo
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="all">Todos</option>
              <option value="queue">Con cola abierta</option>
              <option value="active">Con mandato activo</option>
              <option value="votes">Con votos registrados</option>
            </select>
          </label>
          <label className="field">
            Máx. filas en tabla
            <select value={rowsLimit} onChange={(e) => setRowsLimit(Number(e.target.value) || 250)}>
              <option value={100}>100</option>
              <option value={250}>250</option>
              <option value={500}>500</option>
              <option value={1000}>1000</option>
            </select>
          </label>
          <label className="field">
            Buscar
            <input
              className="textInput"
              type="search"
              placeholder="Nombre, clave, territorio, rol, partido"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </div>

        <div className="chips" style={{ marginTop: 10 }}>
          <span className="chip">Coincidencias: {formatInt(filtered.total)}</span>
          <span className="chip">Mostrando: {formatInt(filtered.shown.length)}</span>
          <span className="chip">Archivo: {activeFile || "—"}</span>
        </div>

        <div className="blockHead" style={{ marginTop: 10 }}>
          <h2>X-ray por dimensión</h2>
        </div>
        <p className="sub">
          Perfiles agregados por partido, institución, ámbito, territorio y cargo.
        </p>
        <div className="chips" style={{ marginTop: 6 }}>
          {XRAY_KIND_LINKS.map((item) => (
            <a key={item.kind} className="chip" href={withBasePath(item.href)}>
              {item.label}
            </a>
          ))}
        </div>

        {rowsLoading ? (
          <p className="sub" style={{ marginTop: 10 }}>Cargando filas del bucket…</p>
        ) : null}
        {rowsError ? <p className="sub" style={{ marginTop: 10 }}>Error de bucket: {rowsError}</p> : null}

        <div className="tableWrap">
          <table className="table">
            <thead>
              <tr>
                <th>Persona</th>
                <th>Territorio</th>
                <th>Mandatos activos</th>
                <th>Votos</th>
                <th>Última acción</th>
                <th>Cola abierta</th>
              </tr>
            </thead>
            <tbody>
              {filtered.shown.map((row) => {
                const personId = asInt(getValue(row, "person_id"));
                const openQueue = asInt(getValue(row, "queue_pending_total")) + asInt(getValue(row, "queue_in_progress_total"));
                const selected = profile?.personId === personId;

                return (
                  <tr key={personId} className={selected ? "rowSelected" : ""}>
                    <td>
                      <button className="tableButton" onClick={() => setSelectedPersonId(personId)}>
                        {String(getValue(row, "full_name") || `Persona ${personId}`)}
                      </button>
                    </td>
                    <td>{String(getValue(row, "territory_name") || "—")}</td>
                    <td>{formatInt(getValue(row, "active_mandates"))}</td>
                    <td>{formatInt(getValue(row, "votes_total"))}</td>
                    <td>{String(getValue(row, "last_action_date") || "—")}</td>
                    <td>{formatInt(openQueue)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
