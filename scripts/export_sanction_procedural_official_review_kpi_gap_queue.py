#!/usr/bin/env python3
"""Export KPI-level actionable gap queue for official procedural-review sources."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.report_sanction_procedural_official_review_status import OFFICIAL_REVIEW_SOURCE_IDS


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _source_priority(status: str) -> int:
    if status == "missing_source":
        return 100
    if status == "missing_metric":
        return 90
    if status == "missing_source_record":
        return 70
    if status == "missing_evidence":
        return 60
    return 10


def _source_next_action(status: str) -> str:
    if status == "missing_source":
        return "add_source_to_sanction_data_catalog_seed"
    if status == "missing_metric":
        return "ingest_official_review_kpi_metric"
    if status == "missing_source_record":
        return "backfill_source_record_pk_for_official_review_metric"
    if status == "missing_evidence":
        return "backfill_evidence_date_quote_for_official_review_metric"
    return "monitor_refresh"


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {str(row["name"]) for row in rows if row is not None}


def _queue_status(
    *,
    source_seeded: bool,
    metric_exists: bool,
    source_record_present: bool,
    evidence_present: bool,
) -> str:
    if not source_seeded:
        return "missing_source"
    if not metric_exists:
        return "missing_metric"
    if not source_record_present:
        return "missing_source_record"
    if not evidence_present:
        return "missing_evidence"
    return "ready"


def build_kpi_gap_queue_report(
    conn: sqlite3.Connection,
    *,
    period_date: str = "",
    period_granularity: str = "",
    queue_limit: int = 0,
    include_ready: bool = False,
) -> dict[str, Any]:
    period_date_token = _norm(period_date)
    period_granularity_token = _norm(period_granularity)

    source_placeholders = ",".join(["?"] * len(OFFICIAL_REVIEW_SOURCE_IDS))
    source_rows = conn.execute(
        f"""
        SELECT sanction_source_id, label, organismo, source_url
        FROM sanction_volume_sources
        WHERE sanction_source_id IN ({source_placeholders})
        """,
        OFFICIAL_REVIEW_SOURCE_IDS,
    ).fetchall()
    source_map = {str(row["sanction_source_id"]): row for row in source_rows}

    kpi_rows = conn.execute(
        """
        SELECT kpi_id, label
        FROM sanction_procedural_kpi_definitions
        ORDER BY kpi_id
        """
    ).fetchall()
    kpi_pairs = [(str(row["kpi_id"]), _norm(row["label"])) for row in kpi_rows if _norm(row["kpi_id"])]

    metric_where = [f"sanction_source_id IN ({source_placeholders})"]
    metric_params: list[Any] = list(OFFICIAL_REVIEW_SOURCE_IDS)
    if period_date_token:
        metric_where.append("period_date = ?")
        metric_params.append(period_date_token)
    if period_granularity_token:
        metric_where.append("period_granularity = ?")
        metric_params.append(period_granularity_token)

    metric_columns = _table_columns(conn, "sanction_procedural_metrics")
    has_evidence_columns = "evidence_date" in metric_columns and "evidence_quote" in metric_columns
    evidence_expr = (
        "CASE WHEN TRIM(COALESCE(evidence_date,'')) <> '' AND TRIM(COALESCE(evidence_quote,'')) <> '' THEN 1 ELSE 0 END"
        if has_evidence_columns
        else "0"
    )

    metric_rows = conn.execute(
        f"""
        SELECT
          sanction_source_id,
          kpi_id,
          metric_key,
          period_date,
          period_granularity,
          source_record_pk,
          {evidence_expr} AS evidence_present
        FROM sanction_procedural_metrics
        WHERE {' AND '.join(metric_where)}
        """,
        tuple(metric_params),
    ).fetchall()
    metric_map: dict[tuple[str, str], sqlite3.Row] = {
        (str(row["sanction_source_id"]), str(row["kpi_id"])): row for row in metric_rows
    }

    expected_pairs_total = len(OFFICIAL_REVIEW_SOURCE_IDS) * len(kpi_pairs)
    totals = {
        "official_review_sources_expected_total": len(OFFICIAL_REVIEW_SOURCE_IDS),
        "official_review_sources_seeded_total": len(source_rows),
        "official_review_kpis_expected_total": len(kpi_pairs),
        "expected_pairs_total": expected_pairs_total,
        "pairs_ready_total": 0,
        "pairs_missing_source_total": 0,
        "pairs_missing_metric_total": 0,
        "pairs_missing_source_record_total": 0,
        "pairs_missing_evidence_total": 0,
    }

    queue_rows: list[dict[str, Any]] = []
    for source_id in OFFICIAL_REVIEW_SOURCE_IDS:
        src = source_map.get(source_id)
        for kpi_id, kpi_label in kpi_pairs:
            metric_row = metric_map.get((source_id, kpi_id))
            metric_exists = metric_row is not None
            source_record_present = bool(metric_row is not None and metric_row["source_record_pk"] is not None)
            evidence_present = bool(metric_row is not None and int(metric_row["evidence_present"] or 0) == 1)
            status = _queue_status(
                source_seeded=src is not None,
                metric_exists=metric_exists,
                source_record_present=source_record_present,
                evidence_present=evidence_present,
            )

            if status == "ready":
                totals["pairs_ready_total"] += 1
            elif status == "missing_source":
                totals["pairs_missing_source_total"] += 1
            elif status == "missing_metric":
                totals["pairs_missing_metric_total"] += 1
            elif status == "missing_source_record":
                totals["pairs_missing_source_record_total"] += 1
            elif status == "missing_evidence":
                totals["pairs_missing_evidence_total"] += 1

            if not include_ready and status == "ready":
                continue

            metric_key_expected = "|".join(
                [
                    _norm(kpi_id),
                    _norm(source_id),
                    period_date_token or "",
                    period_granularity_token or "",
                ]
            ).strip("|")
            queue_rows.append(
                {
                    "queue_key": f"{source_id}|{kpi_id}|{period_date_token or 'all'}|{period_granularity_token or 'all'}",
                    "sanction_source_id": source_id,
                    "kpi_id": kpi_id,
                    "kpi_label": _norm(kpi_label),
                    "period_date": period_date_token or "",
                    "period_granularity": period_granularity_token or "",
                    "label": _norm(src["label"]) if src is not None else "",
                    "organismo": _norm(src["organismo"]) if src is not None else "",
                    "source_url": _norm(src["source_url"]) if src is not None else "",
                    "metric_exists": bool(metric_exists),
                    "source_record_present": bool(source_record_present),
                    "evidence_present": bool(evidence_present),
                    "metric_key": _norm(metric_row["metric_key"]) if metric_row is not None else "",
                    "metric_key_expected": metric_key_expected,
                    "status": status,
                    "priority": _source_priority(status),
                    "next_action": _source_next_action(status),
                }
            )

    queue_rows.sort(
        key=lambda row: (
            -int(row["priority"]),
            _norm(row["sanction_source_id"]),
            _norm(row["kpi_id"]),
            _norm(row["period_date"]),
            _norm(row["period_granularity"]),
        )
    )
    if int(queue_limit) > 0:
        queue_rows = queue_rows[: int(queue_limit)]

    queue_rows_total = len(queue_rows)
    actionable_pairs_total = (
        totals["pairs_missing_source_total"]
        + totals["pairs_missing_metric_total"]
        + totals["pairs_missing_source_record_total"]
        + totals["pairs_missing_evidence_total"]
    )

    checks = {
        "sources_seeded": totals["official_review_sources_seeded_total"] == totals["official_review_sources_expected_total"],
        "kpis_defined": totals["official_review_kpis_expected_total"] > 0,
        "pairs_complete": actionable_pairs_total == 0,
        "queue_visible": queue_rows_total > 0,
        "queue_empty": queue_rows_total == 0,
    }

    if totals["official_review_sources_seeded_total"] == 0 or totals["official_review_kpis_expected_total"] == 0:
        status = "failed"
    elif actionable_pairs_total > 0:
        status = "degraded"
    else:
        status = "ok"

    coverage = {
        "pairs_ready_pct": round((totals["pairs_ready_total"] / expected_pairs_total) if expected_pairs_total else 0.0, 6),
        "pairs_missing_metric_pct": round(
            (totals["pairs_missing_metric_total"] / expected_pairs_total) if expected_pairs_total else 0.0, 6
        ),
        "pairs_missing_source_record_pct": round(
            (totals["pairs_missing_source_record_total"] / expected_pairs_total) if expected_pairs_total else 0.0, 6
        ),
        "pairs_missing_evidence_pct": round(
            (totals["pairs_missing_evidence_total"] / expected_pairs_total) if expected_pairs_total else 0.0, 6
        ),
    }

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "metric_scope": {
            "period_date": period_date_token or None,
            "period_granularity": period_granularity_token or None,
            "label": "period" if (period_date_token or period_granularity_token) else "all_time",
        },
        "include_ready": bool(include_ready),
        "totals": {
            **totals,
            "actionable_pairs_total": actionable_pairs_total,
            "queue_rows_total": queue_rows_total,
        },
        "coverage": coverage,
        "checks": checks,
        "queue_rows": queue_rows,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "queue_key",
        "sanction_source_id",
        "kpi_id",
        "kpi_label",
        "period_date",
        "period_granularity",
        "label",
        "organismo",
        "source_url",
        "metric_exists",
        "source_record_present",
        "evidence_present",
        "metric_key",
        "metric_key_expected",
        "status",
        "priority",
        "next_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Export KPI-level gap queue for official procedural-review sources"
    )
    ap.add_argument("--db", required=True)
    ap.add_argument("--period-date", default="", help="Optional period_date filter")
    ap.add_argument("--period-granularity", default="", help="Optional period_granularity filter")
    ap.add_argument("--queue-limit", type=int, default=0)
    ap.add_argument("--include-ready", action="store_true")
    ap.add_argument("--strict-empty", action="store_true", help="Exit non-zero when queue is not empty")
    ap.add_argument("--csv-out", default="")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = build_kpi_gap_queue_report(
            conn,
            period_date=_norm(args.period_date),
            period_granularity=_norm(args.period_granularity),
            queue_limit=int(args.queue_limit),
            include_ready=bool(args.include_ready),
        )
    finally:
        conn.close()

    if _norm(args.csv_out):
        _write_csv(Path(args.csv_out), list(report.get("queue_rows") or []))

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if bool(args.strict_empty) and int(report.get("totals", {}).get("queue_rows_total") or 0) > 0:
        return 4
    return 0 if str(report.get("status")) != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
