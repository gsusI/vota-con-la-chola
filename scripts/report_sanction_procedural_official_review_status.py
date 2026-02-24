#!/usr/bin/env python3
"""Report status for official procedural-review sources (TEAR/TEAC/contencioso/defensor)."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db

OFFICIAL_REVIEW_SOURCE_IDS: tuple[str, ...] = (
    "es:sanctions:tear_resolutions",
    "es:sanctions:teac_resolutions",
    "es:sanctions:contencioso_sentencias",
    "es:sanctions:defensor_pueblo_quejas",
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {str(row["name"]) for row in rows if row is not None}


def _source_priority(status: str) -> int:
    if status == "missing_source":
        return 100
    if status == "no_metrics":
        return 80
    if status == "no_source_record_chain":
        return 60
    if status == "no_evidence_chain":
        return 50
    if status == "partial_kpi_coverage":
        return 40
    return 10


def _source_next_action(status: str) -> str:
    if status == "missing_source":
        return "add_source_to_sanction_data_catalog_seed"
    if status == "no_metrics":
        return "ingest_official_review_procedural_metrics"
    if status == "no_source_record_chain":
        return "backfill_source_record_pk_for_official_review_metrics"
    if status == "no_evidence_chain":
        return "backfill_evidence_date_quote_for_official_review_metrics"
    if status == "partial_kpi_coverage":
        return "ingest_missing_kpis_for_source_scope"
    return "monitor_refresh"


def _queue_status(
    *,
    source_seeded: bool,
    metric_rows_total: int,
    kpis_covered_total: int,
    kpis_expected_total: int,
    source_record_rows_total: int,
    evidence_rows_total: int,
) -> str:
    if not source_seeded:
        return "missing_source"
    if metric_rows_total <= 0:
        return "no_metrics"
    if source_record_rows_total < metric_rows_total:
        return "no_source_record_chain"
    if evidence_rows_total < metric_rows_total:
        return "no_evidence_chain"
    if int(kpis_expected_total) > 0 and int(kpis_covered_total) < int(kpis_expected_total):
        return "partial_kpi_coverage"
    return "ready"


def _source_expected_metrics(row: sqlite3.Row | None) -> list[str]:
    if row is None:
        return []
    raw = _norm(row["data_contract_json"])
    if not raw:
        return []
    try:
        doc = json.loads(raw)
    except Exception:  # noqa: BLE001
        return []
    vals = doc.get("expected_metrics")
    if not isinstance(vals, list):
        return []
    out: list[str] = []
    for value in vals:
        txt = _norm(value)
        if txt:
            out.append(txt)
    return out


def build_status_report(
    conn: sqlite3.Connection,
    *,
    queue_limit: int = 0,
    period_date: str = "",
    period_granularity: str = "",
) -> dict[str, Any]:
    placeholders = ",".join(["?"] * len(OFFICIAL_REVIEW_SOURCE_IDS))
    period_date_token = _norm(period_date)
    period_granularity_token = _norm(period_granularity)
    metric_columns = _table_columns(conn, "sanction_procedural_metrics")
    has_evidence_columns = "evidence_date" in metric_columns and "evidence_quote" in metric_columns
    evidence_rows_expr = (
        """
          SUM(
            CASE
              WHEN evidence_date IS NOT NULL
               AND TRIM(COALESCE(evidence_date, '')) <> ''
               AND evidence_quote IS NOT NULL
               AND TRIM(COALESCE(evidence_quote, '')) <> ''
              THEN 1 ELSE 0
            END
          )
        """
        if has_evidence_columns
        else "0"
    )

    source_rows = conn.execute(
        f"""
        SELECT
          sanction_source_id,
          label,
          organismo,
          admin_scope,
          territory_scope,
          publication_frequency,
          source_url,
          data_contract_json
        FROM sanction_volume_sources
        WHERE sanction_source_id IN ({placeholders})
        """,
        OFFICIAL_REVIEW_SOURCE_IDS,
    ).fetchall()
    source_map: dict[str, sqlite3.Row] = {str(row["sanction_source_id"]): row for row in source_rows}

    expected_kpis_total = int(
        conn.execute("SELECT COUNT(*) AS n FROM sanction_procedural_kpi_definitions").fetchone()["n"] or 0
    )

    metric_where = [f"sanction_source_id IN ({placeholders})"]
    metric_params: list[Any] = list(OFFICIAL_REVIEW_SOURCE_IDS)
    if period_date_token:
        metric_where.append("period_date = ?")
        metric_params.append(period_date_token)
    if period_granularity_token:
        metric_where.append("period_granularity = ?")
        metric_params.append(period_granularity_token)
    metric_where_sql = " AND ".join(metric_where)

    metric_rows = conn.execute(
        f"""
        SELECT
          sanction_source_id,
          COUNT(*) AS metric_rows_total,
          COUNT(DISTINCT kpi_id) AS kpis_covered_total,
          SUM(CASE WHEN source_record_pk IS NOT NULL THEN 1 ELSE 0 END) AS source_record_rows_total,
          {evidence_rows_expr} AS evidence_rows_total
        FROM sanction_procedural_metrics
        WHERE {metric_where_sql}
        GROUP BY sanction_source_id
        """,
        tuple(metric_params),
    ).fetchall()
    metric_map = {
        str(row["sanction_source_id"]): {
            "metric_rows_total": int(row["metric_rows_total"] or 0),
            "kpis_covered_total": int(row["kpis_covered_total"] or 0),
            "source_record_rows_total": int(row["source_record_rows_total"] or 0),
            "evidence_rows_total": int(row["evidence_rows_total"] or 0),
        }
        for row in metric_rows
    }

    expected_total = len(OFFICIAL_REVIEW_SOURCE_IDS)
    seeded_total = len(source_map)
    missing_total = max(0, expected_total - seeded_total)

    sources_with_metrics_total = 0
    sources_with_all_kpis_total = 0
    metrics_total = 0
    source_record_total = 0
    evidence_total = 0
    missing_kpi_pairs_total = 0
    all_kpis: set[str] = set()
    queue_rows: list[dict[str, Any]] = []

    for source_id in OFFICIAL_REVIEW_SOURCE_IDS:
        src = source_map.get(source_id)
        counts = metric_map.get(source_id, {})
        metric_rows_total = int(counts.get("metric_rows_total", 0))
        kpis_covered_total = int(counts.get("kpis_covered_total", 0))
        source_record_rows_total = int(counts.get("source_record_rows_total", 0))
        evidence_rows_total = int(counts.get("evidence_rows_total", 0))
        kpis_missing_total = max(0, int(expected_kpis_total) - int(kpis_covered_total))

        if metric_rows_total > 0:
            sources_with_metrics_total += 1
        if metric_rows_total > 0 and kpis_missing_total == 0:
            sources_with_all_kpis_total += 1
        metrics_total += metric_rows_total
        source_record_total += source_record_rows_total
        evidence_total += evidence_rows_total
        missing_kpi_pairs_total += kpis_missing_total

        status = _queue_status(
            source_seeded=src is not None,
            metric_rows_total=metric_rows_total,
            kpis_covered_total=kpis_covered_total,
            kpis_expected_total=expected_kpis_total,
            source_record_rows_total=source_record_rows_total,
            evidence_rows_total=evidence_rows_total,
        )
        queue_rows.append(
            {
                "sanction_source_id": source_id,
                "label": _norm(src["label"]) if src is not None else "",
                "organismo": _norm(src["organismo"]) if src is not None else "",
                "admin_scope": _norm(src["admin_scope"]) if src is not None else "",
                "territory_scope": _norm(src["territory_scope"]) if src is not None else "",
                "publication_frequency": _norm(src["publication_frequency"]) if src is not None else "",
                "source_url": _norm(src["source_url"]) if src is not None else "",
                "expected_metrics": _source_expected_metrics(src),
                "source_seeded": src is not None,
                "procedural_metric_rows_total": metric_rows_total,
                "kpis_covered_total": kpis_covered_total,
                "kpis_expected_total": expected_kpis_total,
                "kpis_missing_total": kpis_missing_total,
                "source_record_rows_total": source_record_rows_total,
                "evidence_rows_total": evidence_rows_total,
                "status": status,
                "priority": _source_priority(status),
                "next_action": _source_next_action(status),
            }
        )

        if src is not None:
            kpi_where = ["sanction_source_id = ?"]
            kpi_params: list[Any] = [source_id]
            if period_date_token:
                kpi_where.append("period_date = ?")
                kpi_params.append(period_date_token)
            if period_granularity_token:
                kpi_where.append("period_granularity = ?")
                kpi_params.append(period_granularity_token)
            kpi_rows = conn.execute(
                """
                SELECT DISTINCT kpi_id
                FROM sanction_procedural_metrics
                WHERE """
                + " AND ".join(kpi_where)
                + """
                """,
                tuple(kpi_params),
            ).fetchall()
            for row in kpi_rows:
                all_kpis.add(_norm(row["kpi_id"]))

    queue_rows.sort(key=lambda row: (-int(row["priority"]), _norm(row["sanction_source_id"])))
    if int(queue_limit) > 0:
        queue_rows = queue_rows[: int(queue_limit)]

    seeded_without_metrics_total = sum(
        1
        for source_id in OFFICIAL_REVIEW_SOURCE_IDS
        if source_id in source_map and int(metric_map.get(source_id, {}).get("metric_rows_total", 0)) == 0
    )
    sources_with_missing_kpis_total = max(0, sources_with_metrics_total - sources_with_all_kpis_total)
    metric_rows_missing_source_record_total = max(0, metrics_total - source_record_total)
    metric_rows_missing_evidence_total = max(0, metrics_total - evidence_total)

    checks = {
        "official_review_sources_seeded": seeded_total == expected_total,
        "official_review_metrics_started": metrics_total > 0,
        "official_review_kpi_coverage_started": len(all_kpis) > 0,
        "official_review_all_seeded_have_all_kpis": seeded_total > 0 and sources_with_all_kpis_total == expected_total,
        "official_review_source_record_chain_started": source_record_total > 0,
        "official_review_evidence_chain_started": evidence_total > 0,
        "official_review_all_seeded_have_metrics": seeded_total > 0 and seeded_without_metrics_total == 0,
    }

    if seeded_total == 0:
        status = "failed"
    elif (
        seeded_total < expected_total
        or sources_with_metrics_total < expected_total
        or sources_with_all_kpis_total < expected_total
        or metric_rows_missing_source_record_total > 0
        or metric_rows_missing_evidence_total > 0
    ):
        status = "degraded"
    else:
        status = "ok"

    coverage = {
        "official_review_source_seed_coverage_pct": round((seeded_total / expected_total) if expected_total else 0.0, 6),
        "official_review_source_metric_coverage_pct": round((sources_with_metrics_total / expected_total) if expected_total else 0.0, 6),
        "official_review_source_full_kpi_coverage_pct": round((sources_with_all_kpis_total / expected_total) if expected_total else 0.0, 6),
        "official_review_source_record_coverage_pct": round((source_record_total / metrics_total) if metrics_total else 0.0, 6),
        "official_review_evidence_coverage_pct": round((evidence_total / metrics_total) if metrics_total else 0.0, 6),
    }

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "official_review_source_ids": list(OFFICIAL_REVIEW_SOURCE_IDS),
        "totals": {
            "official_review_sources_expected_total": expected_total,
            "official_review_sources_seeded_total": seeded_total,
            "official_review_sources_missing_total": missing_total,
            "official_review_sources_with_metrics_total": sources_with_metrics_total,
            "official_review_sources_with_all_kpis_total": sources_with_all_kpis_total,
            "official_review_sources_with_missing_kpis_total": sources_with_missing_kpis_total,
            "official_review_sources_seeded_without_metrics_total": seeded_without_metrics_total,
            "official_review_procedural_metrics_total": metrics_total,
            "official_review_metric_rows_with_source_record_total": source_record_total,
            "official_review_metric_rows_missing_source_record_total": metric_rows_missing_source_record_total,
            "official_review_metric_rows_with_evidence_total": evidence_total,
            "official_review_metric_rows_missing_evidence_total": metric_rows_missing_evidence_total,
            "official_review_kpis_expected_total": expected_kpis_total,
            "official_review_kpis_covered_total": len(all_kpis),
            "official_review_missing_kpi_pairs_total": missing_kpi_pairs_total,
        },
        "metric_scope": {
            "period_date": period_date_token or None,
            "period_granularity": period_granularity_token or None,
            "label": "period" if (period_date_token or period_granularity_token) else "all_time",
        },
        "coverage": coverage,
        "checks": checks,
        "queue": queue_rows,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Report status for TEAR/TEAC/contencioso/defensor procedural-review sources"
    )
    ap.add_argument("--db", required=True)
    ap.add_argument("--period-date", default="", help="Optional period_date filter for metric scope")
    ap.add_argument("--period-granularity", default="", help="Optional period_granularity filter for metric scope")
    ap.add_argument("--queue-limit", type=int, default=0)
    ap.add_argument("--csv-out", default="")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sanction_source_id",
        "label",
        "organismo",
        "admin_scope",
        "territory_scope",
        "publication_frequency",
        "source_url",
        "expected_metrics",
        "source_seeded",
        "procedural_metric_rows_total",
        "kpis_covered_total",
        "kpis_expected_total",
        "kpis_missing_total",
        "source_record_rows_total",
        "evidence_rows_total",
        "status",
        "priority",
        "next_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["expected_metrics"] = ",".join(str(v) for v in row.get("expected_metrics", []))
            writer.writerow(out)


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = build_status_report(
            conn,
            queue_limit=int(args.queue_limit),
            period_date=_norm(args.period_date),
            period_granularity=_norm(args.period_granularity),
        )
    finally:
        conn.close()

    if _norm(args.csv_out):
        _write_csv(Path(args.csv_out), list(report.get("queue") or []))

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")

    print(rendered)
    return 0 if str(report.get("status")) != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
