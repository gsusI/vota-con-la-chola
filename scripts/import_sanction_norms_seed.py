#!/usr/bin/env python3
"""Import sanction_norms_seed_v1 into normative/accountability tables."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws
from scripts.validate_sanction_norms_seed import validate_seed


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


def _slug(value: str) -> str:
    out = []
    prev_dash = False
    for ch in value.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        else:
            if not prev_dash:
                out.append("-")
                prev_dash = True
    token = "".join(out).strip("-")
    return token or "fragment"


def _fragment_id(norm_id: str, fragment_type: str, fragment_label: str, provided: str) -> str:
    token = _norm(provided)
    if token:
        return token
    return f"{norm_id}:fragment:{_slug(fragment_type)}:{_slug(fragment_label)}"


def _to_float_or_none(v: Any) -> float | None:
    token = _norm(v)
    if not token:
        return None
    try:
        return float(token)
    except Exception:
        return None


def _to_int_or_none(v: Any) -> int | None:
    token = _norm(v)
    if not token:
        return None
    try:
        return int(token)
    except Exception:
        return None


def _boe_id_to_norm_id(boe_id: Any) -> str:
    token = _norm(boe_id).lower()
    if token.startswith("boe-a-"):
        return f"es:{token}"
    return ""


def _source_exists(conn: sqlite3.Connection, source_id: str) -> bool:
    sid = _norm(source_id)
    if not sid:
        return False
    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (sid,)).fetchone()
    return row is not None


def _resolve_source_record_pk(
    conn: sqlite3.Connection,
    *,
    source_record_cache: dict[tuple[str, str], int | None],
    source_id: str,
    source_record_id: str,
) -> int | None:
    sid = _norm(source_id)
    srid = _norm(source_record_id)
    if not sid or not srid:
        return None
    key = (sid, srid)
    cached = source_record_cache.get(key)
    if cached is not None:
        return int(cached)
    row = conn.execute(
        """
        SELECT source_record_pk
        FROM source_records
        WHERE source_id = ? AND source_record_id = ?
        """,
        (sid, srid),
    ).fetchone()
    if row is None:
        return None
    pk = int(row["source_record_pk"])
    source_record_cache[key] = pk
    return pk


def _ensure_source_record(
    conn: sqlite3.Connection,
    *,
    source_record_cache: dict[tuple[str, str], int | None],
    source_id: str,
    source_record_id: str,
    source_snapshot_date: str,
    raw_payload: dict[str, Any],
    now_ts: str,
) -> tuple[int | None, bool]:
    sid = _norm(source_id)
    srid = _norm(source_record_id)
    if not sid or not srid:
        return None, False
    if not _source_exists(conn, sid):
        return None, False
    key = (sid, srid)

    existing = conn.execute(
        """
        SELECT source_record_pk
        FROM source_records
        WHERE source_id = ? AND source_record_id = ?
        """,
        (sid, srid),
    ).fetchone()
    if existing is not None:
        pk_existing = int(existing["source_record_pk"])
        source_record_cache[key] = pk_existing
        return pk_existing, False

    payload_text = json.dumps(raw_payload, ensure_ascii=False, sort_keys=True)
    payload_sha = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    conn.execute(
        """
        INSERT INTO source_records (
          source_id, source_record_id, source_snapshot_date,
          raw_payload, content_sha256, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sid,
            srid,
            _norm(source_snapshot_date) or None,
            payload_text,
            payload_sha,
            now_ts,
            now_ts,
        ),
    )
    inserted = conn.execute(
        """
        SELECT source_record_pk
        FROM source_records
        WHERE source_id = ? AND source_record_id = ?
        """,
        (sid, srid),
    ).fetchone()
    if inserted is None:
        return None, False
    pk_inserted = int(inserted["source_record_pk"])
    source_record_cache[key] = pk_inserted
    return pk_inserted, True


def import_seed(
    conn: sqlite3.Connection,
    *,
    seed_doc: dict[str, Any],
    source_id: str,
    snapshot_date: str,
) -> dict[str, Any]:
    ts = now_utc_iso()
    sid = _norm(source_id)
    if sid and not _source_exists(conn, sid):
        sid = ""

    norms = seed_doc.get("norms") if isinstance(seed_doc, dict) else []
    if not isinstance(norms, list):
        norms = []

    counts: dict[str, int] = {
        "norms_inserted": 0,
        "norms_updated": 0,
        "catalog_inserted": 0,
        "catalog_updated": 0,
        "fragments_inserted": 0,
        "fragments_updated": 0,
        "fragment_links_inserted": 0,
        "fragment_links_updated": 0,
        "responsibilities_inserted": 0,
        "responsibilities_updated": 0,
        "responsibility_evidence_inserted": 0,
        "responsibility_evidence_updated": 0,
        "responsibility_evidence_source_record_pk_auto_resolved": 0,
        "responsibility_evidence_source_record_seed_rows_inserted": 0,
        "responsibility_evidence_source_record_pk_auto_resolve_missed": 0,
        "lineage_related_norms_inserted": 0,
        "lineage_edges_inserted": 0,
        "lineage_edges_updated": 0,
    }
    source_record_cache: dict[tuple[str, str], int | None] = {}

    seed_version = _norm(seed_doc.get("schema_version")) or "sanction_norms_seed_v1"

    for norm in norms:
        if not isinstance(norm, dict):
            continue
        norm_id = _norm(norm.get("norm_id"))
        if not norm_id:
            continue

        boe_id = _norm(norm.get("boe_id")) or None
        title = _norm(norm.get("title")) or norm_id
        scope = _norm(norm.get("scope")) or None
        organismo_competente = _norm(norm.get("organismo_competente")) or None
        incidence_hypothesis = _norm(norm.get("incidence_hypothesis")) or None
        source_url = _norm(norm.get("source_url")) or None
        norm_evidence_date = _norm(norm.get("evidence_date")) or None
        evidence_required = norm.get("evidence_required") if isinstance(norm.get("evidence_required"), list) else []

        norm_payload = json.dumps(norm, ensure_ascii=False, sort_keys=True)

        norm_exists = conn.execute("SELECT 1 FROM legal_norms WHERE norm_id = ?", (norm_id,)).fetchone() is not None
        conn.execute(
            """
            INSERT INTO legal_norms (
              norm_id, boe_id, title, scope, topic_hint,
              source_id, source_url, source_snapshot_date,
              raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(norm_id) DO UPDATE SET
              boe_id=excluded.boe_id,
              title=excluded.title,
              scope=excluded.scope,
              topic_hint=excluded.topic_hint,
              source_id=COALESCE(excluded.source_id, legal_norms.source_id),
              source_url=COALESCE(excluded.source_url, legal_norms.source_url),
              source_snapshot_date=COALESCE(excluded.source_snapshot_date, legal_norms.source_snapshot_date),
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                norm_id,
                boe_id,
                title,
                scope,
                "ciudadania_sanciones",
                sid or None,
                source_url,
                snapshot_date,
                norm_payload,
                ts,
                ts,
            ),
        )
        counts["norms_updated" if norm_exists else "norms_inserted"] += 1

        catalog_exists = conn.execute("SELECT 1 FROM sanction_norm_catalog WHERE norm_id = ?", (norm_id,)).fetchone() is not None
        conn.execute(
            """
            INSERT INTO sanction_norm_catalog (
              norm_id, scope, organismo_competente, incidence_hypothesis,
              evidence_required_json, seed_version,
              source_id, source_url, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(norm_id) DO UPDATE SET
              scope=excluded.scope,
              organismo_competente=excluded.organismo_competente,
              incidence_hypothesis=excluded.incidence_hypothesis,
              evidence_required_json=excluded.evidence_required_json,
              seed_version=excluded.seed_version,
              source_id=COALESCE(excluded.source_id, sanction_norm_catalog.source_id),
              source_url=COALESCE(excluded.source_url, sanction_norm_catalog.source_url),
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                norm_id,
                scope,
                organismo_competente,
                incidence_hypothesis,
                json.dumps(evidence_required, ensure_ascii=False, sort_keys=True),
                seed_version,
                sid or None,
                source_url,
                norm_payload,
                ts,
                ts,
            ),
        )
        counts["catalog_updated" if catalog_exists else "catalog_inserted"] += 1

        key_fragments = norm.get("key_fragments") if isinstance(norm.get("key_fragments"), list) else []
        responsibility_hints = norm.get("responsibility_hints") if isinstance(norm.get("responsibility_hints"), list) else []
        lineage_hints = norm.get("lineage_hints") if isinstance(norm.get("lineage_hints"), list) else []

        for pos, frag in enumerate(key_fragments, start=1):
            if not isinstance(frag, dict):
                continue
            fragment_type = _norm(frag.get("fragment_type")).lower() or "articulo"
            fragment_label = _norm(frag.get("fragment_label")) or f"fragment-{pos}"
            fragment_id = _fragment_id(norm_id, fragment_type, fragment_label, _norm(frag.get("fragment_id")))

            frag_payload = json.dumps(frag, ensure_ascii=False, sort_keys=True)
            frag_exists = conn.execute("SELECT 1 FROM legal_norm_fragments WHERE fragment_id = ?", (fragment_id,)).fetchone() is not None

            conn.execute(
                """
                INSERT INTO legal_norm_fragments (
                  fragment_id, norm_id, fragment_type, fragment_order,
                  fragment_label, fragment_title, fragment_text_excerpt,
                  sanction_conduct, sanction_amount_min_eur, sanction_amount_max_eur,
                  competent_body, appeal_path,
                  source_url, raw_payload, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fragment_id) DO UPDATE SET
                  norm_id=excluded.norm_id,
                  fragment_type=excluded.fragment_type,
                  fragment_order=excluded.fragment_order,
                  fragment_label=excluded.fragment_label,
                  fragment_title=excluded.fragment_title,
                  fragment_text_excerpt=excluded.fragment_text_excerpt,
                  sanction_conduct=excluded.sanction_conduct,
                  sanction_amount_min_eur=excluded.sanction_amount_min_eur,
                  sanction_amount_max_eur=excluded.sanction_amount_max_eur,
                  competent_body=excluded.competent_body,
                  appeal_path=excluded.appeal_path,
                  source_url=COALESCE(excluded.source_url, legal_norm_fragments.source_url),
                  raw_payload=excluded.raw_payload,
                  updated_at=excluded.updated_at
                """,
                (
                    fragment_id,
                    norm_id,
                    fragment_type,
                    pos,
                    fragment_label,
                    _norm(frag.get("fragment_title")) or None,
                    _norm(frag.get("fragment_text_excerpt")) or None,
                    _norm(frag.get("conducta_sancionada")) or None,
                    _to_float_or_none(frag.get("importe_min_eur")),
                    _to_float_or_none(frag.get("importe_max_eur")),
                    _norm(frag.get("organo_competente")) or organismo_competente,
                    _norm(frag.get("via_recurso")) or None,
                    _norm(frag.get("source_url")) or source_url,
                    frag_payload,
                    ts,
                    ts,
                ),
            )
            counts["fragments_updated" if frag_exists else "fragments_inserted"] += 1

            link_exists = (
                conn.execute(
                    "SELECT 1 FROM sanction_norm_fragment_links WHERE norm_id = ? AND fragment_id = ?",
                    (norm_id, fragment_id),
                ).fetchone()
                is not None
            )
            conn.execute(
                """
                INSERT INTO sanction_norm_fragment_links (
                  norm_id, fragment_id, link_reason, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(norm_id, fragment_id) DO UPDATE SET
                  link_reason=excluded.link_reason,
                  updated_at=excluded.updated_at
                """,
                (norm_id, fragment_id, "seed_key_fragment", ts, ts),
            )
            counts["fragment_links_updated" if link_exists else "fragment_links_inserted"] += 1

            for hint in responsibility_hints:
                if not isinstance(hint, dict):
                    continue
                role = _norm(hint.get("role")).lower()
                actor_label = _norm(hint.get("actor_label"))
                if not role or not actor_label:
                    continue
                resp_source_url = _norm(hint.get("source_url")) or source_url or ""
                resp_evidence_date = _norm(hint.get("evidence_date")) or norm_evidence_date or ""
                resp_evidence_quote = _norm(hint.get("evidence_quote")) or f"Publicacion oficial en BOE: {title}."
                existing = conn.execute(
                    """
                    SELECT responsibility_id
                    FROM legal_fragment_responsibilities
                    WHERE fragment_id = ? AND role = ? AND actor_label = ? AND COALESCE(source_url, '') = ?
                    """,
                    (fragment_id, role, actor_label, resp_source_url),
                ).fetchone()

                hint_payload = json.dumps(hint, ensure_ascii=False, sort_keys=True)
                responsibility_id: int
                if existing is None:
                    cur = conn.execute(
                        """
                        INSERT INTO legal_fragment_responsibilities (
                          fragment_id, role, actor_label,
                          evidence_date,
                          source_id, source_url,
                          evidence_quote,
                          raw_payload, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            fragment_id,
                            role,
                            actor_label,
                            resp_evidence_date or None,
                            sid or None,
                            resp_source_url or None,
                            resp_evidence_quote or None,
                            hint_payload,
                            ts,
                            ts,
                        ),
                    )
                    responsibility_id = int(cur.lastrowid)
                    counts["responsibilities_inserted"] += 1
                else:
                    conn.execute(
                        """
                        UPDATE legal_fragment_responsibilities
                        SET source_id = COALESCE(?, source_id),
                            source_url = COALESCE(?, source_url),
                            evidence_date = COALESCE(?, evidence_date),
                            evidence_quote = COALESCE(?, evidence_quote),
                            raw_payload = ?,
                            updated_at = ?
                        WHERE responsibility_id = ?
                        """,
                        (
                            sid or None,
                            resp_source_url or None,
                            resp_evidence_date or None,
                            resp_evidence_quote or None,
                            hint_payload,
                            ts,
                            int(existing["responsibility_id"]),
                        ),
                    )
                    responsibility_id = int(existing["responsibility_id"])
                    counts["responsibilities_updated"] += 1

                evidence_items = hint.get("evidence_items") if isinstance(hint.get("evidence_items"), list) else []
                if not evidence_items:
                    evidence_items = [
                        {
                            "evidence_type": "boe_publicacion",
                            "source_id": sid or None,
                            "source_url": resp_source_url or None,
                            "evidence_date": resp_evidence_date or None,
                            "evidence_quote": resp_evidence_quote or None,
                        }
                    ]

                for evidence_item in evidence_items:
                    if not isinstance(evidence_item, dict):
                        continue
                    evidence_type = _norm(evidence_item.get("evidence_type")).lower() or "boe_publicacion"
                    if evidence_type not in {
                        "boe_publicacion",
                        "congreso_diario",
                        "senado_diario",
                        "congreso_vote",
                        "senado_vote",
                        "other",
                    }:
                        evidence_type = "other"

                    ev_source_id = _norm(evidence_item.get("source_id")) or sid
                    if ev_source_id and not _source_exists(conn, ev_source_id):
                        ev_source_id = ""

                    ev_source_url = _norm(evidence_item.get("source_url")) or resp_source_url or ""
                    ev_evidence_date = _norm(evidence_item.get("evidence_date")) or resp_evidence_date or ""
                    ev_evidence_quote = _norm(evidence_item.get("evidence_quote")) or resp_evidence_quote or ""
                    ev_source_record_pk = _to_int_or_none(evidence_item.get("source_record_pk"))
                    ev_source_record_id = _norm(evidence_item.get("source_record_id"))
                    if ev_source_record_pk is None and ev_source_id and ev_source_record_id:
                        resolved_pk = _resolve_source_record_pk(
                            conn,
                            source_record_cache=source_record_cache,
                            source_id=ev_source_id,
                            source_record_id=ev_source_record_id,
                        )
                        if resolved_pk is not None:
                            ev_source_record_pk = int(resolved_pk)
                            counts["responsibility_evidence_source_record_pk_auto_resolved"] += 1
                        else:
                            ensure_payload = {
                                "seed_schema_version": seed_version,
                                "norm_id": norm_id,
                                "fragment_id": fragment_id,
                                "role": role,
                                "actor_label": actor_label,
                                "source_url": ev_source_url or None,
                                "evidence_date": ev_evidence_date or None,
                                "evidence_quote": ev_evidence_quote or None,
                                "evidence_item": evidence_item,
                            }
                            ensured_pk, was_inserted = _ensure_source_record(
                                conn,
                                source_record_cache=source_record_cache,
                                source_id=ev_source_id,
                                source_record_id=ev_source_record_id,
                                source_snapshot_date=snapshot_date,
                                raw_payload=ensure_payload,
                                now_ts=ts,
                            )
                            if ensured_pk is None:
                                counts["responsibility_evidence_source_record_pk_auto_resolve_missed"] += 1
                            else:
                                ev_source_record_pk = int(ensured_pk)
                                if was_inserted:
                                    counts["responsibility_evidence_source_record_seed_rows_inserted"] += 1
                                else:
                                    counts["responsibility_evidence_source_record_pk_auto_resolved"] += 1

                    existing_ev = conn.execute(
                        """
                        SELECT responsibility_evidence_id
                        FROM legal_fragment_responsibility_evidence
                        WHERE responsibility_id = ?
                          AND evidence_type = ?
                          AND COALESCE(source_url, '') = ?
                          AND COALESCE(evidence_date, '') = ?
                        """,
                        (responsibility_id, evidence_type, ev_source_url, ev_evidence_date),
                    ).fetchone()

                    ev_payload = json.dumps(evidence_item, ensure_ascii=False, sort_keys=True)
                    if existing_ev is None:
                        conn.execute(
                            """
                            INSERT INTO legal_fragment_responsibility_evidence (
                              responsibility_id, evidence_type, source_id, source_url,
                              source_record_pk, evidence_date, evidence_quote,
                              raw_payload, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                responsibility_id,
                                evidence_type,
                                ev_source_id or None,
                                ev_source_url or None,
                                ev_source_record_pk,
                                ev_evidence_date or None,
                                ev_evidence_quote or None,
                                ev_payload,
                                ts,
                                ts,
                            ),
                        )
                        counts["responsibility_evidence_inserted"] += 1
                    else:
                        conn.execute(
                            """
                            UPDATE legal_fragment_responsibility_evidence
                            SET source_id = COALESCE(?, source_id),
                                source_url = COALESCE(?, source_url),
                                source_record_pk = COALESCE(?, source_record_pk),
                                evidence_date = COALESCE(?, evidence_date),
                                evidence_quote = COALESCE(?, evidence_quote),
                                raw_payload = ?,
                                updated_at = ?
                            WHERE responsibility_evidence_id = ?
                            """,
                            (
                                ev_source_id or None,
                                ev_source_url or None,
                                ev_source_record_pk,
                                ev_evidence_date or None,
                                ev_evidence_quote or None,
                                ev_payload,
                                ts,
                                int(existing_ev["responsibility_evidence_id"]),
                            ),
                        )
                        counts["responsibility_evidence_updated"] += 1

        for hint in lineage_hints:
            if not isinstance(hint, dict):
                continue
            relation_type = _norm(hint.get("relation_type")).lower()
            if relation_type not in {"deroga", "modifica", "desarrolla"}:
                continue

            related_norm_id = _norm(hint.get("target_norm_id")) or _boe_id_to_norm_id(hint.get("target_boe_id"))
            if not related_norm_id:
                continue

            related_boe_id = _norm(hint.get("target_boe_id")) or None
            related_title = _norm(hint.get("target_title")) or related_boe_id or related_norm_id
            related_source_url = _norm(hint.get("target_source_url")) or _norm(hint.get("source_url")) or source_url or None

            related_exists = conn.execute(
                "SELECT 1 FROM legal_norms WHERE norm_id = ?",
                (related_norm_id,),
            ).fetchone()
            if related_exists is None:
                related_payload = json.dumps(
                    {
                        "lineage_ref_for": norm_id,
                        "target_norm_id": related_norm_id,
                        "target_boe_id": related_boe_id,
                        "target_title": related_title,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                conn.execute(
                    """
                    INSERT INTO legal_norms (
                      norm_id, boe_id, title, scope, topic_hint,
                      source_id, source_url, source_snapshot_date,
                      raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        related_norm_id,
                        related_boe_id,
                        related_title,
                        None,
                        "ciudadania_sanciones_lineage_ref",
                        sid or None,
                        related_source_url,
                        snapshot_date,
                        related_payload,
                        ts,
                        ts,
                    ),
                )
                counts["lineage_related_norms_inserted"] += 1

            lineage_source_url = _norm(hint.get("source_url")) or source_url or ""
            lineage_evidence_date = _norm(hint.get("evidence_date")) or norm_evidence_date or ""
            lineage_evidence_quote = _norm(hint.get("evidence_quote")) or (
                f"Relacion normativa ({relation_type}) documentada en BOE para {title}."
            )
            lineage_scope = _norm(hint.get("relation_scope")).lower() or None

            existing = conn.execute(
                """
                SELECT lineage_edge_id
                FROM legal_norm_lineage_edges
                WHERE norm_id = ?
                  AND related_norm_id = ?
                  AND relation_type = ?
                  AND COALESCE(source_url, '') = ?
                """,
                (norm_id, related_norm_id, relation_type, lineage_source_url),
            ).fetchone()

            hint_payload = json.dumps(hint, ensure_ascii=False, sort_keys=True)
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO legal_norm_lineage_edges (
                      norm_id, related_norm_id, relation_type, relation_scope,
                      evidence_date, source_id, source_url, evidence_quote,
                      raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        norm_id,
                        related_norm_id,
                        relation_type,
                        lineage_scope,
                        lineage_evidence_date or None,
                        sid or None,
                        lineage_source_url or None,
                        lineage_evidence_quote or None,
                        hint_payload,
                        ts,
                        ts,
                    ),
                )
                counts["lineage_edges_inserted"] += 1
            else:
                conn.execute(
                    """
                    UPDATE legal_norm_lineage_edges
                    SET relation_scope = COALESCE(?, relation_scope),
                        evidence_date = COALESCE(?, evidence_date),
                        source_id = COALESCE(?, source_id),
                        source_url = COALESCE(?, source_url),
                        evidence_quote = COALESCE(?, evidence_quote),
                        raw_payload = ?,
                        updated_at = ?
                    WHERE lineage_edge_id = ?
                    """,
                    (
                        lineage_scope,
                        lineage_evidence_date or None,
                        sid or None,
                        lineage_source_url or None,
                        lineage_evidence_quote or None,
                        hint_payload,
                        ts,
                        int(existing["lineage_edge_id"]),
                    ),
                )
                counts["lineage_edges_updated"] += 1

    conn.commit()

    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM legal_norms) AS legal_norms_total,
          (SELECT COUNT(*) FROM legal_norm_fragments) AS legal_norm_fragments_total,
          (SELECT COUNT(*) FROM legal_fragment_responsibilities) AS legal_fragment_responsibilities_total,
          (SELECT COUNT(*) FROM legal_fragment_responsibility_evidence) AS legal_fragment_responsibility_evidence_total,
          (SELECT COUNT(*) FROM sanction_norm_catalog) AS sanction_norm_catalog_total,
          (SELECT COUNT(*) FROM sanction_norm_fragment_links) AS sanction_norm_fragment_links_total,
          (SELECT COUNT(*) FROM legal_norm_lineage_edges) AS legal_norm_lineage_edges_total
        """
    ).fetchone()

    out = {
        "status": "ok",
        "snapshot_date": snapshot_date,
        "source_id_used": sid,
        "seed_schema_version": seed_version,
        "counts": counts,
        "totals": {
            "legal_norms_total": int(totals["legal_norms_total"]),
            "legal_norm_fragments_total": int(totals["legal_norm_fragments_total"]),
            "legal_fragment_responsibilities_total": int(totals["legal_fragment_responsibilities_total"]),
            "legal_fragment_responsibility_evidence_total": int(
                totals["legal_fragment_responsibility_evidence_total"]
            ),
            "sanction_norm_catalog_total": int(totals["sanction_norm_catalog_total"]),
            "sanction_norm_fragment_links_total": int(totals["sanction_norm_fragment_links_total"]),
            "legal_norm_lineage_edges_total": int(totals["legal_norm_lineage_edges_total"]),
        },
    }
    return out


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Import sanction_norms_seed_v1 into SQLite")
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed", default="etl/data/seeds/sanction_norms_seed_v1.json")
    ap.add_argument("--snapshot-date", default=today_utc_date())
    ap.add_argument("--source-id", default="boe_api_legal")
    ap.add_argument("--out", default="", help="optional output JSON path")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    seed_path = Path(args.seed)
    validation = validate_seed(seed_path)
    if not bool(validation.get("valid")):
        payload = {
            "status": "invalid_seed",
            "validation": validation,
        }
        rendered = json.dumps(payload, ensure_ascii=False, indent=2)
        if _norm(args.out):
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 1

    seed_doc = json.loads(seed_path.read_text(encoding="utf-8"))

    db_path = Path(args.db)
    schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
    conn = open_db(db_path)
    try:
        apply_schema(conn, schema_path)
        report = import_seed(
            conn,
            seed_doc=seed_doc,
            source_id=str(args.source_id or ""),
            snapshot_date=str(args.snapshot_date or ""),
        )
    finally:
        conn.close()

    payload = {
        "generated_at": now_utc_iso(),
        "db_path": str(db_path),
        "seed_path": str(seed_path),
        "validation": {
            "valid": bool(validation.get("valid")),
            "norms_total": int(validation.get("norms_total") or 0),
            "fragments_total": int(validation.get("fragments_total") or 0),
            "responsibility_hints_total": int(validation.get("responsibility_hints_total") or 0),
            "responsibility_evidence_items_total": int(validation.get("responsibility_evidence_items_total") or 0),
            "lineage_hints_total": int(validation.get("lineage_hints_total") or 0),
        },
        "import": report,
    }

    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
