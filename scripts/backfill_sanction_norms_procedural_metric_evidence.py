#!/usr/bin/env python3
"""Backfill procedural-metric evidence for sanction responsibilities."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from etl.politicos_es.util import normalize_ws

PROCEDURAL_EVIDENCE_TYPE = "other"
PROCEDURAL_RECORD_KIND = "sanction_norm_procedural_metric_evidence_backfill"


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


def _iter_metrics(conn: sqlite3.Connection, *, limit: int) -> list[sqlite3.Row]:
    sql = """
        SELECT
          m.metric_observation_id,
          m.metric_key,
          m.kpi_id,
          m.sanction_source_id,
          m.period_date,
          m.period_granularity,
          m.value,
          m.numerator,
          m.denominator,
          m.source_id,
          m.source_url,
          m.source_record_pk,
          m.raw_payload
        FROM sanction_procedural_metrics m
        WHERE TRIM(COALESCE(m.sanction_source_id, '')) <> ''
        ORDER BY m.metric_observation_id
    """
    params: list[Any] = []
    if int(limit) > 0:
        sql += " LIMIT ?"
        params.append(int(limit))
    return conn.execute(sql, tuple(params)).fetchall()


def _resolve_fragment_candidates(
    conn: sqlite3.Connection,
    *,
    sanction_source_id: str,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
          o.fragment_id,
          o.norm_id,
          n.boe_id,
          COUNT(*) AS obs_count
        FROM sanction_volume_observations o
        JOIN legal_norm_fragments f ON f.fragment_id = o.fragment_id
        JOIN sanction_norm_fragment_links l ON l.fragment_id = o.fragment_id
        LEFT JOIN legal_norms n ON n.norm_id = o.norm_id
        WHERE o.sanction_source_id = ?
          AND TRIM(COALESCE(o.fragment_id, '')) <> ''
        GROUP BY o.fragment_id, o.norm_id, n.boe_id
        ORDER BY COUNT(*) DESC, o.fragment_id ASC
        """,
        (sanction_source_id,),
    ).fetchall()


def _resolve_responsibilities(
    conn: sqlite3.Connection,
    *,
    fragment_id: str,
    roles: list[str],
) -> list[sqlite3.Row]:
    if not roles:
        return []
    placeholders = ",".join(["?"] * len(roles))
    params: list[Any] = [fragment_id, *roles]
    sql = f"""
        SELECT
          r.responsibility_id,
          r.role,
          r.fragment_id,
          f.norm_id
        FROM legal_fragment_responsibilities r
        JOIN legal_norm_fragments f ON f.fragment_id = r.fragment_id
        JOIN sanction_norm_fragment_links l ON l.fragment_id = r.fragment_id
        WHERE r.fragment_id = ?
          AND r.role IN ({placeholders})
        ORDER BY r.responsibility_id
    """
    return conn.execute(sql, tuple(params)).fetchall()


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


def _metric_quote(row: sqlite3.Row) -> str:
    parts: list[str] = [f"kpi_id={_norm(row['kpi_id'])}"]
    if row["value"] is not None:
        parts.append(f"value={float(row['value']):.6f}")
    if row["numerator"] is not None:
        parts.append(f"numerator={float(row['numerator']):.6f}")
    if row["denominator"] is not None:
        parts.append(f"denominator={float(row['denominator']):.6f}")
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
    rows = _iter_metrics(conn, limit=int(limit))

    counts: dict[str, int] = {
        "metrics_scanned_total": len(rows),
        "metrics_with_fragment_candidates_total": 0,
        "metrics_without_fragment_candidates_total": 0,
        "metrics_with_responsibility_total": 0,
        "metrics_without_responsibility_total": 0,
        "source_record_pk_resolved_total": 0,
        "source_record_pk_missing_total": 0,
        "evidence_inserted": 0,
        "evidence_updated": 0,
    }
    by_norm: dict[str, int] = {}
    by_role: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_kpi: dict[str, int] = {}
    samples: list[dict[str, Any]] = []

    for row in rows:
        metric_observation_id = int(row["metric_observation_id"])
        sanction_source_id = _norm(row["sanction_source_id"])
        kpi_id = _norm(row["kpi_id"])
        by_kpi[kpi_id] = int(by_kpi.get(kpi_id, 0)) + 1

        source_id = _norm(row["source_id"])
        source_url_original = _norm(row["source_url"])
        source_url = (
            f"{source_url_original}#metric_observation_id={metric_observation_id}"
            if source_url_original
            else f"metric:{metric_observation_id}"
        )
        evidence_date = _norm(row["period_date"]) or now_iso[:10]

        if not _source_exists(conn, source_id):
            source_id = ""

        fragment_candidates = _resolve_fragment_candidates(conn, sanction_source_id=sanction_source_id)
        if not fragment_candidates:
            counts["metrics_without_fragment_candidates_total"] += 1
            counts["metrics_without_responsibility_total"] += 1
            if len(samples) < 20:
                samples.append(
                    {
                        "metric_observation_id": metric_observation_id,
                        "metric_key": _norm(row["metric_key"]),
                        "sanction_source_id": sanction_source_id,
                        "reason": "no_fragment_candidates_for_sanction_source",
                        "roles": roles_norm,
                    }
                )
            continue

        counts["metrics_with_fragment_candidates_total"] += 1

        metric_had_responsibility = False
        for rank, candidate in enumerate(fragment_candidates, start=1):
            fragment_id = _norm(candidate["fragment_id"])
            norm_id = _norm(candidate["norm_id"])
            boe_id = _norm(candidate["boe_id"]).upper()
            obs_count = int(candidate["obs_count"])

            responsibilities = _resolve_responsibilities(
                conn,
                fragment_id=fragment_id,
                roles=roles_norm,
            )
            if not responsibilities:
                continue

            metric_had_responsibility = True
            by_source[source_id or ""] = int(by_source.get(source_id or "", 0)) + len(responsibilities)

            for resp in responsibilities:
                responsibility_id = int(resp["responsibility_id"])
                role = _norm(resp["role"])
                by_role[role] = int(by_role.get(role, 0)) + 1
                by_norm[norm_id] = int(by_norm.get(norm_id, 0)) + 1

                resolved_source_record_pk, resolve_status = _resolve_source_record_pk(
                    conn,
                    source_id=source_id,
                    source_record_pk=(
                        int(row["source_record_pk"]) if row["source_record_pk"] is not None else None
                    ),
                    boe_id=boe_id,
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
                    (responsibility_id, PROCEDURAL_EVIDENCE_TYPE, source_url, evidence_date),
                ).fetchone()

                payload = {
                    "record_kind": PROCEDURAL_RECORD_KIND,
                    "match_method": "sanction_source_to_observed_fragment_set",
                    "match_confidence": (
                        "high" if len(fragment_candidates) == 1 else "medium"
                    ),
                    "fragment_candidate_rank": rank,
                    "fragment_candidates_total": len(fragment_candidates),
                    "fragment_candidate_obs_count": obs_count,
                    "metric_observation_id": metric_observation_id,
                    "metric_key": _norm(row["metric_key"]),
                    "kpi_id": kpi_id,
                    "sanction_source_id": sanction_source_id,
                    "period_granularity": _norm(row["period_granularity"]),
                    "norm_id": norm_id,
                    "fragment_id": fragment_id,
                    "boe_id": boe_id,
                    "responsibility_id": responsibility_id,
                    "role": role,
                    "value": float(row["value"]) if row["value"] is not None else None,
                    "numerator": float(row["numerator"]) if row["numerator"] is not None else None,
                    "denominator": float(row["denominator"]) if row["denominator"] is not None else None,
                    "evidence_type_hint": "sanction_procedural_metric",
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
                            PROCEDURAL_EVIDENCE_TYPE,
                            source_id or None,
                            source_url or None,
                            resolved_source_record_pk,
                            evidence_date or None,
                            _metric_quote(row) or None,
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
                            _metric_quote(row) or None,
                            raw_payload,
                            now_iso,
                            int(exists["responsibility_evidence_id"]),
                        ),
                    )
                    counts["evidence_updated"] += 1

                if len(samples) < 20:
                    samples.append(
                        {
                            "metric_observation_id": metric_observation_id,
                            "metric_key": _norm(row["metric_key"]),
                            "kpi_id": kpi_id,
                            "sanction_source_id": sanction_source_id,
                            "norm_id": norm_id,
                            "fragment_id": fragment_id,
                            "responsibility_id": responsibility_id,
                            "role": role,
                            "source_record_pk_resolution": resolve_status,
                        }
                    )

        if metric_had_responsibility:
            counts["metrics_with_responsibility_total"] += 1
        else:
            counts["metrics_without_responsibility_total"] += 1
            if len(samples) < 20:
                samples.append(
                    {
                        "metric_observation_id": metric_observation_id,
                        "metric_key": _norm(row["metric_key"]),
                        "sanction_source_id": sanction_source_id,
                        "reason": "no_matching_responsibility_for_roles",
                        "roles": roles_norm,
                    }
                )

    conn.commit()
    return {
        "generated_at": now_iso,
        "roles": roles_norm,
        "limit": int(limit),
        "counts": counts,
        "by_kpi": by_kpi,
        "by_norm": by_norm,
        "by_role": by_role,
        "by_source": by_source,
        "samples": samples,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Backfill sanction procedural-metric evidence from procedural metric observations"
    )
    ap.add_argument("--db", required=True)
    ap.add_argument("--roles", default="enforce,approve,propose,delegate")
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
