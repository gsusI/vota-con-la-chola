#!/usr/bin/env python3
"""Backfill execution evidence via normative lineage bridges."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from etl.politicos_es.util import normalize_ws

EXECUTION_EVIDENCE_TYPE = "other"
EXECUTION_RECORD_KIND = "sanction_norm_execution_lineage_bridge_backfill"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


def _parse_roles(raw: str) -> list[str]:
    allowed = {"propose", "approve", "delegate", "enforce", "audit"}
    out: list[str] = []
    for token in str(raw or "").split(","):
        role = _norm(token).lower()
        if role and role in allowed and role not in out:
            out.append(role)
    return out


def _source_exists(conn: sqlite3.Connection, source_id: str) -> bool:
    sid = _norm(source_id)
    if not sid:
        return False
    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (sid,)).fetchone()
    return row is not None


def _iter_responsibilities(conn: sqlite3.Connection, *, roles: list[str], limit: int) -> list[sqlite3.Row]:
    placeholders = ",".join(["?"] * len(roles))
    sql = f"""
        SELECT
          r.responsibility_id,
          r.role,
          r.fragment_id,
          f.norm_id AS delegate_norm_id,
          n.boe_id AS delegate_boe_id
        FROM legal_fragment_responsibilities r
        JOIN legal_norm_fragments f ON f.fragment_id = r.fragment_id
        JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
        LEFT JOIN legal_norms n ON n.norm_id = f.norm_id
        WHERE r.role IN ({placeholders})
        ORDER BY r.responsibility_id
    """
    params: list[Any] = [*roles]
    if int(limit) > 0:
        sql += " LIMIT ?"
        params.append(int(limit))
    return conn.execute(sql, tuple(params)).fetchall()


def _iter_observations(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
          o.observation_id,
          o.observation_key,
          o.sanction_source_id,
          o.period_date,
          o.period_granularity,
          o.norm_id,
          o.fragment_id,
          o.infraction_type_id,
          o.expediente_count,
          o.importe_total_eur,
          o.importe_medio_eur,
          o.recurso_presentado_count,
          o.recurso_estimado_count,
          o.recurso_desestimado_count,
          o.source_id,
          o.source_url,
          o.source_record_pk,
          n.boe_id AS observed_boe_id
        FROM sanction_volume_observations o
        JOIN sanction_norm_fragment_links l ON l.fragment_id = o.fragment_id
        LEFT JOIN legal_norms n ON n.norm_id = o.norm_id
        WHERE TRIM(COALESCE(o.norm_id, '')) <> ''
          AND TRIM(COALESCE(o.fragment_id, '')) <> ''
          AND (
            COALESCE(o.expediente_count, 0) > 0
            OR COALESCE(o.importe_total_eur, 0) > 0
            OR COALESCE(o.recurso_presentado_count, 0) > 0
            OR COALESCE(o.recurso_estimado_count, 0) > 0
            OR COALESCE(o.recurso_desestimado_count, 0) > 0
          )
        ORDER BY o.observation_id
        """
    ).fetchall()


def _load_related_map(conn: sqlite3.Connection) -> dict[str, set[str]]:
    rows = conn.execute(
        """
        SELECT norm_id, related_norm_id
        FROM legal_norm_lineage_edges
        WHERE TRIM(COALESCE(norm_id, '')) <> ''
          AND TRIM(COALESCE(related_norm_id, '')) <> ''
        """
    ).fetchall()
    out: dict[str, set[str]] = {}
    for row in rows:
        norm_id = _norm(row["norm_id"])
        related = _norm(row["related_norm_id"])
        if not norm_id or not related:
            continue
        out.setdefault(norm_id, set()).add(related)
    return out


def _match_lineage(
    *,
    delegate_norm_id: str,
    observed_norm_id: str,
    related_map: dict[str, set[str]],
) -> tuple[bool, str, str]:
    d = _norm(delegate_norm_id)
    o = _norm(observed_norm_id)
    if not d or not o:
        return False, "", ""
    if d == o:
        return True, "direct_norm_match", d

    d_related = related_map.get(d, set())
    o_related = related_map.get(o, set())

    if o in d_related:
        return True, "delegate_to_observed_direct", o
    if d in o_related:
        return True, "observed_to_delegate_direct", d

    common = sorted(d_related.intersection(o_related))
    if common:
        return True, "shared_related_norm", common[0]

    return False, "", ""


def _resolve_source_record_pk(
    conn: sqlite3.Connection,
    *,
    source_id: str,
    source_record_pk: int | None,
    boe_id: str,
) -> tuple[int | None, str]:
    if source_record_pk is not None and int(source_record_pk) > 0:
        return int(source_record_pk), "existing"

    sid = _norm(source_id)
    boe = _norm(boe_id).upper()
    if not sid or not boe:
        return None, "missing_lookup_key"

    for record_id in (f"boe_ref:{boe}", boe):
        row = conn.execute(
            """
            SELECT source_record_pk
            FROM source_records
            WHERE source_id = ? AND source_record_id = ?
            ORDER BY source_record_pk DESC
            LIMIT 1
            """,
            (sid, record_id),
        ).fetchone()
        if row is not None and row["source_record_pk"] is not None:
            return int(row["source_record_pk"]), f"resolved:{record_id}"

    return None, "lookup_miss"


def _observation_quote(row: sqlite3.Row) -> str:
    parts: list[str] = []
    if row["expediente_count"] is not None:
        parts.append(f"expedientes={int(row['expediente_count'])}")
    if row["importe_total_eur"] is not None:
        parts.append(f"importe_total_eur={float(row['importe_total_eur']):.2f}")
    if row["recurso_presentado_count"] is not None:
        parts.append(f"recursos_presentados={int(row['recurso_presentado_count'])}")
    if row["recurso_estimado_count"] is not None:
        parts.append(f"recursos_estimados={int(row['recurso_estimado_count'])}")
    if row["recurso_desestimado_count"] is not None:
        parts.append(f"recursos_desestimados={int(row['recurso_desestimado_count'])}")
    if not parts:
        return "observacion sancionadora con señal cuantitativa"
    return _norm("; ".join(parts))


def backfill(
    conn: sqlite3.Connection,
    *,
    roles: list[str],
    limit: int,
) -> dict[str, Any]:
    roles_norm = [r for r in roles if r]
    if not roles_norm:
        raise ValueError("at least one role is required")

    now_iso = now_utc_iso()
    responsibilities = _iter_responsibilities(conn, roles=roles_norm, limit=int(limit))
    observations = _iter_observations(conn)
    related_map = _load_related_map(conn)

    counts: dict[str, int] = {
        "responsibilities_scanned_total": len(responsibilities),
        "observations_scanned_total": len(observations),
        "responsibilities_with_lineage_match_total": 0,
        "responsibilities_without_lineage_match_total": 0,
        "observation_links_total": 0,
        "source_record_pk_resolved_total": 0,
        "source_record_pk_missing_total": 0,
        "evidence_inserted": 0,
        "evidence_updated": 0,
    }
    by_role: dict[str, int] = {}
    by_delegate_norm: dict[str, int] = {}
    by_observed_norm: dict[str, int] = {}
    by_match_method: dict[str, int] = {}
    samples: list[dict[str, Any]] = []

    for resp in responsibilities:
        responsibility_id = int(resp["responsibility_id"])
        role = _norm(resp["role"])
        delegate_norm_id = _norm(resp["delegate_norm_id"])
        matched_any = False

        for obs in observations:
            observed_norm_id = _norm(obs["norm_id"])
            matched, match_method, anchor_norm_id = _match_lineage(
                delegate_norm_id=delegate_norm_id,
                observed_norm_id=observed_norm_id,
                related_map=related_map,
            )
            if not matched:
                continue

            matched_any = True
            counts["observation_links_total"] += 1
            by_role[role] = int(by_role.get(role, 0)) + 1
            by_delegate_norm[delegate_norm_id] = int(by_delegate_norm.get(delegate_norm_id, 0)) + 1
            by_observed_norm[observed_norm_id] = int(by_observed_norm.get(observed_norm_id, 0)) + 1
            by_match_method[match_method] = int(by_match_method.get(match_method, 0)) + 1

            source_id = _norm(obs["source_id"])
            if not _source_exists(conn, source_id):
                source_id = ""

            observation_id = int(obs["observation_id"])
            source_url_original = _norm(obs["source_url"])
            source_url = (
                f"{source_url_original}#observation_id={observation_id}&lineage_bridge=1"
                if source_url_original
                else f"observation:{observation_id}:lineage_bridge"
            )
            evidence_date = _norm(obs["period_date"]) or now_iso[:10]

            observed_boe_id = _norm(obs["observed_boe_id"]).upper()
            resolved_source_record_pk, resolve_status = _resolve_source_record_pk(
                conn,
                source_id=source_id,
                source_record_pk=(int(obs["source_record_pk"]) if obs["source_record_pk"] is not None else None),
                boe_id=observed_boe_id,
            )
            if resolved_source_record_pk is None:
                counts["source_record_pk_missing_total"] += 1
            else:
                counts["source_record_pk_resolved_total"] += 1

            exists = conn.execute(
                """
                SELECT responsibility_evidence_id
                FROM legal_fragment_responsibility_evidence
                WHERE responsibility_id = ?
                  AND evidence_type = ?
                  AND COALESCE(source_url, '') = ?
                  AND COALESCE(evidence_date, '') = ?
                """,
                (responsibility_id, EXECUTION_EVIDENCE_TYPE, source_url, evidence_date),
            ).fetchone()

            payload = {
                "record_kind": EXECUTION_RECORD_KIND,
                "match_method": match_method,
                "match_confidence": "low" if match_method == "shared_related_norm" else "medium",
                "delegate_norm_id": delegate_norm_id,
                "observed_norm_id": observed_norm_id,
                "anchor_norm_id": anchor_norm_id,
                "observation_id": observation_id,
                "observation_key": _norm(obs["observation_key"]),
                "sanction_source_id": _norm(obs["sanction_source_id"]),
                "period_granularity": _norm(obs["period_granularity"]),
                "fragment_id": _norm(obs["fragment_id"]),
                "boe_id": observed_boe_id,
                "responsibility_id": responsibility_id,
                "role": role,
                "infraction_type_id": _norm(obs["infraction_type_id"]),
                "expediente_count": int(obs["expediente_count"]) if obs["expediente_count"] is not None else None,
                "importe_total_eur": float(obs["importe_total_eur"]) if obs["importe_total_eur"] is not None else None,
                "importe_medio_eur": float(obs["importe_medio_eur"]) if obs["importe_medio_eur"] is not None else None,
                "recurso_presentado_count": int(obs["recurso_presentado_count"]) if obs["recurso_presentado_count"] is not None else None,
                "recurso_estimado_count": int(obs["recurso_estimado_count"]) if obs["recurso_estimado_count"] is not None else None,
                "recurso_desestimado_count": int(obs["recurso_desestimado_count"]) if obs["recurso_desestimado_count"] is not None else None,
                "evidence_type_hint": "sanction_volume_observation_lineage_bridge",
                "source_url_original": source_url_original,
                "source_record_pk_resolution": resolve_status,
            }
            raw_payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)

            if exists is None:
                conn.execute(
                    """
                    INSERT INTO legal_fragment_responsibility_evidence (
                      responsibility_id,
                      evidence_type,
                      source_id,
                      source_url,
                      source_record_pk,
                      evidence_date,
                      evidence_quote,
                      raw_payload,
                      created_at,
                      updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        responsibility_id,
                        EXECUTION_EVIDENCE_TYPE,
                        source_id or None,
                        source_url or None,
                        resolved_source_record_pk,
                        evidence_date or None,
                        _observation_quote(obs) or None,
                        raw_payload,
                        now_iso,
                        now_iso,
                    ),
                )
                counts["evidence_inserted"] += 1
            else:
                conn.execute(
                    """
                    UPDATE legal_fragment_responsibility_evidence
                    SET
                      source_id = ?,
                      source_url = ?,
                      source_record_pk = ?,
                      evidence_date = ?,
                      evidence_quote = ?,
                      raw_payload = ?,
                      updated_at = ?
                    WHERE responsibility_evidence_id = ?
                    """,
                    (
                        source_id or None,
                        source_url or None,
                        resolved_source_record_pk,
                        evidence_date or None,
                        _observation_quote(obs) or None,
                        raw_payload,
                        now_iso,
                        int(exists["responsibility_evidence_id"]),
                    ),
                )
                counts["evidence_updated"] += 1

            if len(samples) < 20:
                samples.append(
                    {
                        "responsibility_id": responsibility_id,
                        "role": role,
                        "delegate_norm_id": delegate_norm_id,
                        "observed_norm_id": observed_norm_id,
                        "anchor_norm_id": anchor_norm_id,
                        "match_method": match_method,
                        "observation_id": observation_id,
                        "source_record_pk_resolution": resolve_status,
                    }
                )

        if matched_any:
            counts["responsibilities_with_lineage_match_total"] += 1
        else:
            counts["responsibilities_without_lineage_match_total"] += 1
            if len(samples) < 20:
                samples.append(
                    {
                        "responsibility_id": responsibility_id,
                        "role": role,
                        "delegate_norm_id": delegate_norm_id,
                        "reason": "no_lineage_bridge_to_observed_norms",
                    }
                )

    conn.commit()
    return {
        "generated_at": now_iso,
        "roles": roles_norm,
        "limit": int(limit),
        "counts": counts,
        "by_role": by_role,
        "by_delegate_norm": by_delegate_norm,
        "by_observed_norm": by_observed_norm,
        "by_match_method": by_match_method,
        "samples": samples,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Backfill execution evidence for sanction responsibilities via norm lineage bridges"
    )
    ap.add_argument("--db", required=True)
    ap.add_argument("--roles", default="delegate")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    roles = _parse_roles(args.roles)
    conn = open_db(Path(args.db))
    try:
        report = backfill(conn, roles=roles, limit=int(args.limit))
    finally:
        conn.close()

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
