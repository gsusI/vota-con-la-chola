from __future__ import annotations

import json
import re
from typing import Any, Iterable, Sequence

from etl.politicos_es.util import normalize_key_part, normalize_ws, now_utc_iso, sha256_bytes, stable_json


SAFE_SLUG_RE = re.compile(r"[^a-z0-9]+")
TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
HIGH_RISK_EFFECTS = {"tax", "restriction", "sanction", "rights"}
MEDIUM_RISK_EFFECTS = {"obligation", "competence"}
EFFECT_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tax", ("impuesto", "gravamen", "tribut", "iva", "ibi", "irpf", "cotiz", "tasa", "bonificacion fiscal")),
    ("benefit", ("ayuda", "bono", "subvencion", "prestacion", "ingreso minimo", "deduccion", "reduccion", "descuento", "moratoria")),
    ("obligation", ("oblig", "deber", "requisito", "debe", "debera", "exig", "registro obligatorio")),
    (
        "restriction",
        ("prohib", "restricc", "restring", "limita", "limite de acceso", "no podra", "no se podra", "zona de bajas emisiones"),
    ),
    ("sanction", ("sanc", "multa", "pena", "infracci", "recargo", "retirada de puntos")),
    ("rights", ("derecho", "proteccion", "reclamacion", "garantia", "defensa", "transparencia", "acceso a la informacion")),
    ("competence", ("competenc", "autoridad", "policia", "inspeccion", "organismo competente")),
    ("institutional", ("comision", "procedimiento", "convenio", "tratado", "nombramiento", "organizacion interna")),
)


def _norm(value: Any) -> str:
    return normalize_ws(str(value or ""))


def _table_exists(conn: Any, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (_norm(table_name),),
    ).fetchone()
    return row is not None


def _unique_texts(values: Iterable[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _norm(value)
        if not item:
            continue
        marker = item.lower()
        if marker in seen:
            continue
        seen.add(marker)
        out.append(item)
    return out


def _load_json_list(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return _unique_texts(raw)
    text = _norm(raw)
    if not text:
        return []
    try:
        data = json.loads(text)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    return _unique_texts(data)


def _load_json_rows(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        data = raw
    else:
        text = _norm(raw)
        if not text:
            return []
        try:
            data = json.loads(text)
        except Exception:
            return []
    if not isinstance(data, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            rows.append(dict(item))
    return rows


def _slug(value: str, *, fallback: str = "measure") -> str:
    token = SAFE_SLUG_RE.sub("-", _norm(value).lower()).strip("-")
    return token or fallback


def _term_tokens(value: str) -> set[str]:
    return set(TOKEN_RE.findall(normalize_key_part(value)))


def candidate_id_from_measure_point_id(measure_point_id: str) -> str:
    token = _norm(measure_point_id)
    return "mcand:" + sha256_bytes(token.encode("utf-8"))[:32]


def build_measure_normalized_key(
    *,
    measure_title: str,
    effect_type: str,
    policy_area: str,
    measure_kind: str,
) -> str:
    parts = [
        normalize_key_part(measure_title),
        normalize_key_part(effect_type),
        normalize_key_part(policy_area),
        normalize_key_part(measure_kind),
    ]
    return "|".join(part for part in parts if part)


def cluster_id_from_normalized_key(normalized_key: str) -> str:
    token = _norm(normalized_key)
    return "mcluster:" + sha256_bytes(token.encode("utf-8"))[:32]


def cluster_slug_for_title(title: str, normalized_key: str) -> str:
    base = _slug(title, fallback="measure")
    suffix = sha256_bytes(_norm(normalized_key).encode("utf-8"))[:8]
    return f"{base}-{suffix}"


def infer_effect_type(
    *,
    measure_title: str,
    citizen_summary: str,
    policy_area: str,
    measure_kind: str,
) -> str:
    text = " ".join(
        part
        for part in (
            normalize_key_part(measure_title),
            normalize_key_part(citizen_summary),
            normalize_key_part(policy_area),
            normalize_key_part(measure_kind),
        )
        if part
    )
    if not text:
        return "unknown"
    for effect_type, terms in EFFECT_HINTS:
        if any(term in text for term in terms):
            return effect_type
    return "unknown"


def infer_risk_level(*, effect_type: str, measure_title: str, citizen_summary: str) -> str:
    effect = _norm(effect_type).lower()
    if effect in HIGH_RISK_EFFECTS:
        return "high"
    if effect in MEDIUM_RISK_EFFECTS:
        return "medium"
    text = " ".join((normalize_key_part(measure_title), normalize_key_part(citizen_summary)))
    if any(term in text for term in ("multa", "sanc", "prohib", "restricc", "impuesto", "derecho")):
        return "high"
    if any(term in text for term in ("oblig", "requisito", "competenc", "autoridad")):
        return "medium"
    return "low"


def _pick_version_metadata(conn: Any, initiative_id: str, primary_vote_event_ids: Sequence[str]) -> dict[str, Any]:
    if not _table_exists(conn, "parl_initiative_text_versions"):
        return {}
    initiative_token = _norm(initiative_id)
    if not initiative_token:
        return {}

    if primary_vote_event_ids and _table_exists(conn, "parl_vote_event_text_versions"):
        for vote_event_id in primary_vote_event_ids:
            row = conn.execute(
                """
                SELECT initiative_text_version_id, link_method, confidence
                FROM parl_vote_event_text_versions
                WHERE initiative_id = ? AND vote_event_id = ?
                ORDER BY is_primary DESC,
                         CASE WHEN confidence IS NULL THEN 1 ELSE 0 END ASC,
                         confidence DESC,
                         parl_vote_event_text_version_id ASC
                LIMIT 1
                """,
                (initiative_token, _norm(vote_event_id)),
            ).fetchone()
            if row is not None:
                return {
                    "initiative_text_version_id": _norm(row["initiative_text_version_id"]),
                    "version_link_method": _norm(row["link_method"]),
                    "version_confidence": row["confidence"],
                }

    row = conn.execute(
        """
        SELECT initiative_text_version_id
        FROM parl_initiative_text_versions
        WHERE initiative_id = ?
        ORDER BY CASE WHEN published_date IS NULL OR TRIM(published_date) = '' THEN 1 ELSE 0 END ASC,
                 published_date DESC,
                 COALESCE(version_order, 0) DESC,
                 initiative_text_version_id DESC
        LIMIT 1
        """,
        (initiative_token,),
    ).fetchone()
    if row is None:
        return {}
    return {
        "initiative_text_version_id": _norm(row["initiative_text_version_id"]),
        "version_link_method": "latest_available_version",
        "version_confidence": None,
    }


def _best_fragment_match(
    conn: Any,
    *,
    initiative_id: str,
    initiative_text_version_id: str,
    query_terms: Sequence[str],
) -> dict[str, Any]:
    if not _table_exists(conn, "parl_text_fragments"):
        return {}
    phrases = [normalize_key_part(term) for term in query_terms if normalize_key_part(term)]
    token_pool: set[str] = set()
    for phrase in phrases:
        token_pool.update(_term_tokens(phrase))

    def _score_rows(rows: Sequence[Any], *, match_scope: str) -> dict[str, Any]:
        best_row = None
        best_score = 0.0
        for row in rows:
            fragment_norm = normalize_key_part(str(row["fragment_text"] or ""))
            fragment_tokens = _term_tokens(fragment_norm)
            score = 0.0
            for phrase in phrases:
                if phrase and phrase in fragment_norm:
                    score += 12.0 + min(float(len(phrase.split())), 6.0)
            if token_pool:
                score += float(len(fragment_tokens & token_pool))
            if score > best_score:
                best_score = score
                best_row = row
        if best_row is None or best_score <= 0:
            return {}
        return {
            "fragment_id": _norm(best_row["fragment_id"]),
            "fragment_label": _norm(best_row["fragment_label"]),
            "match_score": round(best_score, 3),
            "fragment_initiative_text_version_id": _norm(best_row["initiative_text_version_id"]),
            "match_scope": match_scope,
        }

    preferred_version_id = _norm(initiative_text_version_id)
    if preferred_version_id:
        rows = conn.execute(
            """
            SELECT fragment_id, fragment_label, fragment_text, initiative_text_version_id
            FROM parl_text_fragments
            WHERE initiative_text_version_id = ?
            ORDER BY fragment_order ASC
            """,
            (preferred_version_id,),
        ).fetchall()
        matched = _score_rows(rows, match_scope="selected_version")
        if matched:
            return matched

    initiative_token = _norm(initiative_id)
    if not initiative_token:
        return {}
    rows = conn.execute(
        """
        SELECT fragment_id, fragment_label, fragment_text, initiative_text_version_id
        FROM parl_text_fragments
        WHERE initiative_id = ?
        ORDER BY CASE WHEN initiative_text_version_id = ? THEN 0 ELSE 1 END ASC,
                 initiative_text_version_id ASC,
                 fragment_order ASC
        """,
        (initiative_token, preferred_version_id),
    ).fetchall()
    return _score_rows(rows, match_scope="initiative_fallback")


def _parse_filter_values(values: Sequence[str] | None) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        item = _norm(value)
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return tuple(out)


def _cleanup_orphan_clusters(conn: Any) -> int:
    if not (_table_exists(conn, "parl_measure_candidate_cluster_links") and _table_exists(conn, "parl_measure_clusters")):
        return 0
    deleted_clusters = conn.execute(
        """
        DELETE FROM parl_measure_clusters
        WHERE NOT EXISTS (
          SELECT 1
          FROM parl_measure_candidate_cluster_links l
          WHERE l.measure_cluster_id = parl_measure_clusters.measure_cluster_id
        )
        """
    ).rowcount
    return max(int(deleted_clusters or 0), 0)


def _purge_candidate_ids(conn: Any, candidate_ids: Sequence[str]) -> int:
    candidate_tokens = _parse_filter_values(candidate_ids)
    if not candidate_tokens:
        return 0
    marks = ",".join("?" for _ in candidate_tokens)
    if _table_exists(conn, "parl_measure_candidate_reviews"):
        conn.execute(
            f"""
            DELETE FROM parl_measure_candidate_reviews
            WHERE measure_candidate_id IN ({marks})
            """,
            candidate_tokens,
        )
    if _table_exists(conn, "parl_measure_candidate_cluster_links"):
        conn.execute(
            f"""
            DELETE FROM parl_measure_candidate_cluster_links
            WHERE measure_candidate_id IN ({marks})
            """,
            candidate_tokens,
        )
    conn.execute(
        f"""
        DELETE FROM parl_measure_candidates
        WHERE measure_candidate_id IN ({marks})
        """,
        candidate_tokens,
    )
    return len(candidate_tokens)


def _build_measure_point_query(
    *,
    source_id: str,
    measure_point_ids: tuple[str, ...],
    task_ids: tuple[str, ...],
    initiative_ids: tuple[str, ...],
    only_missing: bool,
    limit: int,
) -> tuple[str, list[Any]]:
    params: list[Any] = []
    where = ["1=1"]
    if _norm(source_id):
        where.append("p.source_id = ?")
        params.append(_norm(source_id))
    if measure_point_ids:
        marks = ",".join("?" for _ in measure_point_ids)
        where.append(f"p.measure_point_id IN ({marks})")
        params.extend(measure_point_ids)
    if task_ids:
        marks = ",".join("?" for _ in task_ids)
        where.append(f"p.task_id IN ({marks})")
        params.extend(task_ids)
    if initiative_ids:
        marks = ",".join("?" for _ in initiative_ids)
        where.append(f"p.initiative_id IN ({marks})")
        params.extend(initiative_ids)
    if only_missing:
        where.append("c.measure_candidate_id IS NULL")

    limit_sql = ""
    if int(limit or 0) > 0:
        limit_sql = "LIMIT ?"
        params.append(int(limit))

    sql = f"""
    SELECT
      p.measure_point_id,
      p.task_id,
      p.initiative_id,
      p.source_id,
      p.measure_title,
      p.citizen_summary,
      p.affected_groups,
      p.policy_area,
      p.measure_kind,
      p.measure_status,
      p.search_terms_json,
      p.primary_vote_event_ids_json,
      p.support_side,
      p.support_explanation,
      p.evidence_json,
      p.note
    FROM parl_initiative_measure_points p
    LEFT JOIN parl_measure_candidates c
      ON c.source_measure_point_id = p.measure_point_id
    WHERE {" AND ".join(where)}
    ORDER BY p.initiative_id ASC, p.measure_rank ASC, p.measure_point_id ASC
    {limit_sql}
    """
    return sql, params


def purge_seeded_measure_scale_layer(
    conn: Any,
    *,
    measure_point_ids: Sequence[str] | None,
    dry_run: bool,
) -> dict[str, Any]:
    point_ids = _parse_filter_values(measure_point_ids)
    if not point_ids or not _table_exists(conn, "parl_measure_candidates"):
        return {
            "measure_point_ids_seen": len(point_ids),
            "candidates_deleted": 0,
            "clusters_deleted": 0,
        }

    marks = ",".join("?" for _ in point_ids)
    candidate_rows = conn.execute(
        f"""
        SELECT measure_candidate_id
        FROM parl_measure_candidates
        WHERE candidate_origin = 'reviewed_point'
          AND source_measure_point_id IN ({marks})
        """,
        point_ids,
    ).fetchall()
    candidate_ids = [_norm(row["measure_candidate_id"]) for row in candidate_rows if _norm(row["measure_candidate_id"])]
    if dry_run or not candidate_ids:
        return {
            "measure_point_ids_seen": len(point_ids),
            "candidates_deleted": len(candidate_ids),
            "clusters_deleted": 0,
        }

    deleted_candidates = _purge_candidate_ids(conn, candidate_ids)
    deleted_clusters = _cleanup_orphan_clusters(conn)
    return {
        "measure_point_ids_seen": len(point_ids),
        "candidates_deleted": deleted_candidates,
        "clusters_deleted": deleted_clusters,
    }


def purge_fragment_measure_scale_layer(
    conn: Any,
    *,
    fragment_ids: Sequence[str] | None,
    dry_run: bool,
) -> dict[str, Any]:
    tokens = _parse_filter_values(fragment_ids)
    if not tokens or not _table_exists(conn, "parl_measure_candidates"):
        return {
            "fragment_ids_seen": len(tokens),
            "candidates_deleted": 0,
            "clusters_deleted": 0,
        }

    marks = ",".join("?" for _ in tokens)
    rows = conn.execute(
        f"""
        SELECT measure_candidate_id
        FROM parl_measure_candidates
        WHERE candidate_origin = 'fragment_model'
          AND fragment_id IN ({marks})
        """,
        tokens,
    ).fetchall()
    candidate_ids = [_norm(row["measure_candidate_id"]) for row in rows if _norm(row["measure_candidate_id"])]
    if dry_run or not candidate_ids:
        return {
            "fragment_ids_seen": len(tokens),
            "candidates_deleted": len(candidate_ids),
            "clusters_deleted": 0,
        }

    deleted_candidates = _purge_candidate_ids(conn, candidate_ids)
    if _table_exists(conn, "parl_fragment_measure_reviews"):
        conn.execute(
            f"""
            DELETE FROM parl_fragment_measure_reviews
            WHERE fragment_id IN ({marks})
            """,
            tokens,
        )
    deleted_clusters = _cleanup_orphan_clusters(conn)
    return {
        "fragment_ids_seen": len(tokens),
        "candidates_deleted": deleted_candidates,
        "clusters_deleted": deleted_clusters,
    }


def seed_measure_scale_layer(
    conn: Any,
    *,
    source_id: str = "",
    measure_point_ids: Sequence[str] | None = None,
    task_ids: Sequence[str] | None = None,
    initiative_ids: Sequence[str] | None = None,
    only_missing: bool = False,
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    required_tables = (
        "parl_measure_candidates",
        "parl_measure_clusters",
        "parl_measure_candidate_cluster_links",
        "parl_initiative_measure_points",
    )
    missing_tables = [name for name in required_tables if not _table_exists(conn, name)]
    if missing_tables:
        return {
            "schema_ready": False,
            "missing_tables": missing_tables,
            "measure_points_seen": 0,
            "candidate_rows_written": 0,
            "cluster_rows_written": 0,
            "link_rows_written": 0,
            "versions_resolved": 0,
            "fragments_matched": 0,
            "missing_versions": 0,
            "missing_fragments": 0,
        }

    sql, params = _build_measure_point_query(
        source_id=_norm(source_id),
        measure_point_ids=_parse_filter_values(measure_point_ids),
        task_ids=_parse_filter_values(task_ids),
        initiative_ids=_parse_filter_values(initiative_ids),
        only_missing=bool(only_missing),
        limit=int(limit or 0),
    )
    rows = conn.execute(sql, params).fetchall()
    now_iso = now_utc_iso()

    candidates_inserted = 0
    candidates_updated = 0
    clusters_inserted = 0
    clusters_updated = 0
    links_inserted = 0
    links_updated = 0
    versions_resolved = 0
    fragments_matched = 0
    missing_versions = 0
    missing_fragments = 0

    for row in rows:
        measure_point_id = _norm(row["measure_point_id"])
        initiative_id = _norm(row["initiative_id"])
        measure_title = _norm(row["measure_title"])
        citizen_summary = _norm(row["citizen_summary"])
        policy_area = _norm(row["policy_area"])
        measure_kind = _norm(row["measure_kind"])
        search_terms = _load_json_list(row["search_terms_json"])
        primary_vote_event_ids = _load_json_list(row["primary_vote_event_ids_json"])
        evidence_rows = _load_json_rows(row["evidence_json"])
        affected_groups = _norm(row["affected_groups"])
        effect_type = infer_effect_type(
            measure_title=measure_title,
            citizen_summary=citizen_summary,
            policy_area=policy_area,
            measure_kind=measure_kind,
        )
        risk_level = infer_risk_level(
            effect_type=effect_type,
            measure_title=measure_title,
            citizen_summary=citizen_summary,
        )
        normalized_key = build_measure_normalized_key(
            measure_title=measure_title,
            effect_type=effect_type,
            policy_area=policy_area,
            measure_kind=measure_kind,
        )
        candidate_id = candidate_id_from_measure_point_id(measure_point_id)
        cluster_id = cluster_id_from_normalized_key(normalized_key)
        cluster_slug = cluster_slug_for_title(measure_title, normalized_key)

        version_meta = _pick_version_metadata(conn, initiative_id, primary_vote_event_ids)
        version_id = _norm(version_meta.get("initiative_text_version_id"))
        if version_id:
            versions_resolved += 1
        else:
            missing_versions += 1

        query_terms = _unique_texts(
            [
                measure_title,
                citizen_summary,
                *search_terms,
                *[_norm(item.get("quote")) for item in evidence_rows if isinstance(item, dict)],
                policy_area,
                measure_kind,
                affected_groups,
            ]
        )
        fragment_meta = _best_fragment_match(
            conn,
            initiative_id=initiative_id,
            initiative_text_version_id=version_id,
            query_terms=query_terms,
        )
        fragment_id = _norm(fragment_meta.get("fragment_id"))
        if fragment_id:
            fragments_matched += 1
        else:
            missing_fragments += 1

        candidate_payload = {
            "seed_method": "seed_reviewed_point_v1",
            "task_id": _norm(row["task_id"]),
            "measure_status": _norm(row["measure_status"]).lower() or "unknown",
            "support_explanation": _norm(row["support_explanation"]),
            "note": _norm(row["note"]),
            "version_link_method": _norm(version_meta.get("version_link_method")),
            "version_confidence": version_meta.get("version_confidence"),
            "fragment_match_score": fragment_meta.get("match_score"),
            "fragment_label": _norm(fragment_meta.get("fragment_label")),
            "fragment_match_scope": _norm(fragment_meta.get("match_scope")) or "unmatched",
            "fragment_initiative_text_version_id": _norm(fragment_meta.get("fragment_initiative_text_version_id")),
        }

        existing_candidate = conn.execute(
            """
            SELECT measure_candidate_id
            FROM parl_measure_candidates
            WHERE measure_candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()
        if existing_candidate is None:
            candidates_inserted += 1
        else:
            candidates_updated += 1

        existing_cluster = conn.execute(
            """
            SELECT canonical_title, canonical_summary, aliases_json, search_terms_json, raw_payload_json
            FROM parl_measure_clusters
            WHERE measure_cluster_id = ?
            """,
            (cluster_id,),
        ).fetchone()
        existing_aliases = _load_json_list(existing_cluster["aliases_json"]) if existing_cluster is not None else []
        existing_search_terms = _load_json_list(existing_cluster["search_terms_json"]) if existing_cluster is not None else []
        existing_cluster_payload: Any = {}
        if existing_cluster is not None and _norm(existing_cluster["raw_payload_json"]):
            try:
                existing_cluster_payload = json.loads(existing_cluster["raw_payload_json"])
            except Exception:
                existing_cluster_payload = {}
        if not isinstance(existing_cluster_payload, dict):
            existing_cluster_payload = {}
        existing_point_ids = _load_json_list(existing_cluster_payload.get("source_measure_point_ids"))
        existing_initiative_ids = _load_json_list(existing_cluster_payload.get("initiative_ids"))
        cluster_payload = dict(existing_cluster_payload)
        cluster_payload["seed_method"] = "seed_reviewed_point_v1"
        cluster_payload["source_measure_point_ids"] = _unique_texts([*existing_point_ids, measure_point_id])
        cluster_payload["initiative_ids"] = _unique_texts([*existing_initiative_ids, initiative_id])

        merged_aliases = _unique_texts([*existing_aliases, measure_title])
        merged_search_terms = _unique_texts([*existing_search_terms, *search_terms, measure_title])
        canonical_title = (
            _norm(existing_cluster["canonical_title"])
            if existing_cluster is not None and _norm(existing_cluster["canonical_title"])
            else measure_title
        )
        canonical_summary = (
            _norm(existing_cluster["canonical_summary"])
            if existing_cluster is not None and _norm(existing_cluster["canonical_summary"])
            else citizen_summary
        )
        if existing_cluster is None:
            clusters_inserted += 1
        else:
            clusters_updated += 1

        existing_link = conn.execute(
            """
            SELECT candidate_cluster_link_id
            FROM parl_measure_candidate_cluster_links
            WHERE measure_candidate_id = ? AND measure_cluster_id = ?
            """,
            (candidate_id, cluster_id),
        ).fetchone()
        if existing_link is None:
            links_inserted += 1
        else:
            links_updated += 1

        if dry_run:
            continue

        conn.execute(
            """
            INSERT INTO parl_measure_candidates (
              measure_candidate_id, initiative_id, source_id, initiative_text_version_id, fragment_id,
              source_measure_point_id, candidate_origin, extraction_method, effect_type, risk_level,
              measure_title, citizen_summary, normalized_key, affected_groups, policy_area, measure_kind,
              search_terms_json, primary_vote_event_ids_json, support_side, evidence_json, confidence,
              status, raw_payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(measure_candidate_id) DO UPDATE SET
              initiative_id = excluded.initiative_id,
              source_id = excluded.source_id,
              initiative_text_version_id = excluded.initiative_text_version_id,
              fragment_id = excluded.fragment_id,
              source_measure_point_id = excluded.source_measure_point_id,
              candidate_origin = excluded.candidate_origin,
              extraction_method = excluded.extraction_method,
              effect_type = excluded.effect_type,
              risk_level = excluded.risk_level,
              measure_title = excluded.measure_title,
              citizen_summary = excluded.citizen_summary,
              normalized_key = excluded.normalized_key,
              affected_groups = excluded.affected_groups,
              policy_area = excluded.policy_area,
              measure_kind = excluded.measure_kind,
              search_terms_json = excluded.search_terms_json,
              primary_vote_event_ids_json = excluded.primary_vote_event_ids_json,
              support_side = excluded.support_side,
              evidence_json = excluded.evidence_json,
              confidence = excluded.confidence,
              status = excluded.status,
              raw_payload_json = excluded.raw_payload_json,
              updated_at = excluded.updated_at
            """,
            (
                candidate_id,
                initiative_id,
                _norm(row["source_id"]),
                version_id or None,
                fragment_id or None,
                measure_point_id,
                "reviewed_point",
                "seed_reviewed_point_v1",
                effect_type,
                risk_level,
                measure_title,
                citizen_summary,
                normalized_key,
                affected_groups or None,
                policy_area or None,
                measure_kind or None,
                stable_json(search_terms),
                stable_json(primary_vote_event_ids),
                _norm(row["support_side"]).lower() or "unknown",
                stable_json(evidence_rows),
                1.0,
                "promoted",
                stable_json(candidate_payload),
                now_iso,
                now_iso,
            ),
        )
        conn.execute(
            """
            INSERT INTO parl_measure_clusters (
              measure_cluster_id, cluster_slug, canonical_title, canonical_summary, normalized_key,
              effect_type, risk_level, policy_area, measure_kind, aliases_json, search_terms_json,
              confidence, publish_status, raw_payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(measure_cluster_id) DO UPDATE SET
              cluster_slug = excluded.cluster_slug,
              canonical_title = excluded.canonical_title,
              canonical_summary = excluded.canonical_summary,
              normalized_key = excluded.normalized_key,
              effect_type = excluded.effect_type,
              risk_level = excluded.risk_level,
              policy_area = excluded.policy_area,
              measure_kind = excluded.measure_kind,
              aliases_json = excluded.aliases_json,
              search_terms_json = excluded.search_terms_json,
              confidence = excluded.confidence,
              publish_status = excluded.publish_status,
              raw_payload_json = excluded.raw_payload_json,
              updated_at = excluded.updated_at
            """,
            (
                cluster_id,
                cluster_slug,
                canonical_title,
                canonical_summary,
                normalized_key,
                effect_type,
                risk_level,
                policy_area or None,
                measure_kind or None,
                stable_json(merged_aliases),
                stable_json(merged_search_terms),
                1.0,
                "published",
                stable_json(cluster_payload),
                now_iso,
                now_iso,
            ),
        )
        conn.execute(
            """
            INSERT INTO parl_measure_candidate_cluster_links (
              measure_candidate_id, measure_cluster_id, link_method, confidence, is_primary,
              raw_payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(measure_candidate_id, measure_cluster_id) DO UPDATE SET
              link_method = excluded.link_method,
              confidence = excluded.confidence,
              is_primary = excluded.is_primary,
              raw_payload_json = excluded.raw_payload_json,
              updated_at = excluded.updated_at
            """,
            (
                candidate_id,
                cluster_id,
                "seed_exact",
                1.0,
                stable_json({"source_measure_point_id": measure_point_id}),
                now_iso,
                now_iso,
            ),
        )

    return {
        "schema_ready": True,
        "missing_tables": [],
        "measure_points_seen": len(rows),
        "candidate_rows_written": candidates_inserted + candidates_updated,
        "candidate_rows_inserted": candidates_inserted,
        "candidate_rows_updated": candidates_updated,
        "cluster_rows_written": clusters_inserted + clusters_updated,
        "cluster_rows_inserted": clusters_inserted,
        "cluster_rows_updated": clusters_updated,
        "link_rows_written": links_inserted + links_updated,
        "link_rows_inserted": links_inserted,
        "link_rows_updated": links_updated,
        "versions_resolved": versions_resolved,
        "fragments_matched": fragments_matched,
        "missing_versions": missing_versions,
        "missing_fragments": missing_fragments,
        "dry_run": bool(dry_run),
    }
