#!/usr/bin/env python3
"""Export remediation apply CSV from official-review KPI gap queue."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.export_sanction_procedural_official_review_kpi_gap_queue import build_kpi_gap_queue_report
from scripts.report_sanction_procedural_official_review_status import OFFICIAL_REVIEW_SOURCE_IDS

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_SOURCE_ID = "boe_api_legal"
DEFAULT_STATUSES = ("missing_metric", "missing_source_record", "missing_evidence")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _slug(value: str) -> str:
    out: list[str] = []
    prev_dash = False
    for ch in _norm(value).lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    token = "".join(out).strip("-")
    return token or "na"


def _default_source_record_id(
    *,
    sanction_source_id: str,
    kpi_id: str,
    period_date: str,
    period_granularity: str,
) -> str:
    return ":".join(
        [
            "official_review",
            _slug(sanction_source_id),
            _slug(kpi_id),
            _slug(period_date),
            _slug(period_granularity),
        ]
    )


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return {str(row["name"]) for row in rows if row is not None}


def _load_source_map(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    placeholders = ",".join(["?"] * len(OFFICIAL_REVIEW_SOURCE_IDS))
    rows = conn.execute(
        f"""
        SELECT sanction_source_id, label, organismo, data_contract_json
        FROM sanction_volume_sources
        WHERE sanction_source_id IN ({placeholders})
        """,
        OFFICIAL_REVIEW_SOURCE_IDS,
    ).fetchall()
    return {str(row["sanction_source_id"]): row for row in rows}


def _load_kpi_map(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT kpi_id, label, metric_formula, target_direction
        FROM sanction_procedural_kpi_definitions
        """
    ).fetchall()
    return {str(row["kpi_id"]): row for row in rows if _norm(row["kpi_id"])}


def _load_metric_map(
    conn: sqlite3.Connection,
    *,
    period_date: str,
    period_granularity: str,
) -> dict[str, sqlite3.Row]:
    placeholders = ",".join(["?"] * len(OFFICIAL_REVIEW_SOURCE_IDS))
    where = [f"sanction_source_id IN ({placeholders})"]
    params: list[Any] = list(OFFICIAL_REVIEW_SOURCE_IDS)
    if _norm(period_date):
        where.append("period_date = ?")
        params.append(_norm(period_date))
    if _norm(period_granularity):
        where.append("period_granularity = ?")
        params.append(_norm(period_granularity))

    metric_cols = _table_columns(conn, "sanction_procedural_metrics")
    evidence_date_expr = "evidence_date" if "evidence_date" in metric_cols else "NULL AS evidence_date"
    evidence_quote_expr = "evidence_quote" if "evidence_quote" in metric_cols else "NULL AS evidence_quote"
    rows = conn.execute(
        f"""
        SELECT
          metric_key,
          kpi_id,
          sanction_source_id,
          period_date,
          period_granularity,
          value,
          numerator,
          denominator,
          source_id,
          source_url,
          source_record_pk,
          {evidence_date_expr},
          {evidence_quote_expr}
        FROM sanction_procedural_metrics
        WHERE {" AND ".join(where)}
        """,
        tuple(params),
    ).fetchall()
    return {str(row["metric_key"]): row for row in rows if _norm(row["metric_key"])}


def _load_source_record_map(conn: sqlite3.Connection, pks: list[int]) -> dict[int, sqlite3.Row]:
    if not pks:
        return {}
    placeholders = ",".join(["?"] * len(pks))
    rows = conn.execute(
        f"""
        SELECT source_record_pk, source_id, source_record_id
        FROM source_records
        WHERE source_record_pk IN ({placeholders})
        """,
        tuple(pks),
    ).fetchall()
    return {int(row["source_record_pk"]): row for row in rows}


def _expected_metrics(source_row: sqlite3.Row | None) -> str:
    if source_row is None:
        return ""
    raw = _norm(source_row["data_contract_json"])
    if not raw:
        return ""
    try:
        doc = json.loads(raw)
    except Exception:  # noqa: BLE001
        return ""
    vals = doc.get("expected_metrics")
    if not isinstance(vals, list):
        return ""
    return ",".join(_norm(v) for v in vals if _norm(v))


def _parse_statuses(token: str) -> set[str]:
    out: set[str] = set()
    for raw in str(token or "").split(","):
        item = _norm(raw)
        if item:
            out.add(item)
    return out


def build_apply_rows_from_gap_queue(
    conn: sqlite3.Connection,
    *,
    period_date: str = "",
    period_granularity: str = "",
    queue_limit: int = 0,
    include_ready: bool = False,
    statuses: set[str] | None = None,
    default_source_id: str = DEFAULT_SOURCE_ID,
) -> dict[str, Any]:
    status_set = set(statuses or DEFAULT_STATUSES)
    queue_report = build_kpi_gap_queue_report(
        conn,
        period_date=_norm(period_date),
        period_granularity=_norm(period_granularity),
        queue_limit=int(queue_limit),
        include_ready=bool(include_ready),
    )
    source_map = _load_source_map(conn)
    kpi_map = _load_kpi_map(conn)
    metric_map = _load_metric_map(
        conn,
        period_date=_norm(period_date),
        period_granularity=_norm(period_granularity),
    )
    pks = sorted(
        {
            int(row["source_record_pk"])
            for row in metric_map.values()
            if row["source_record_pk"] is not None
        }
    )
    source_record_map = _load_source_record_map(conn, pks)

    queue_rows = list(queue_report.get("queue_rows") or [])
    counts = {
        "queue_rows_seen_total": len(queue_rows),
        "rows_emitted_total": 0,
        "rows_skipped_missing_source_total": 0,
        "rows_skipped_filtered_status_total": 0,
    }
    emitted_by_status: dict[str, int] = {}
    skipped_by_status: dict[str, int] = {}
    rows_out: list[dict[str, Any]] = []

    for qrow in queue_rows:
        status = _norm(qrow.get("status"))
        if status == "missing_source":
            counts["rows_skipped_missing_source_total"] += 1
            skipped_by_status[status] = int(skipped_by_status.get(status, 0)) + 1
            continue
        if status_set and status not in status_set:
            counts["rows_skipped_filtered_status_total"] += 1
            skipped_by_status[status] = int(skipped_by_status.get(status, 0)) + 1
            continue

        sanction_source_id = _norm(qrow.get("sanction_source_id"))
        kpi_id = _norm(qrow.get("kpi_id"))
        period_date_token = _norm(qrow.get("period_date"))
        period_granularity_token = _norm(qrow.get("period_granularity")) or "year"
        metric_key_expected = _norm(qrow.get("metric_key_expected"))
        metric_key = _norm(qrow.get("metric_key")) or metric_key_expected
        metric = metric_map.get(metric_key) or metric_map.get(metric_key_expected)

        src = source_map.get(sanction_source_id)
        kpi = kpi_map.get(kpi_id)
        source_record_pk = int(metric["source_record_pk"]) if metric is not None and metric["source_record_pk"] is not None else None
        source_record_row = source_record_map.get(source_record_pk) if source_record_pk is not None else None

        source_id = (
            _norm(metric["source_id"]) if metric is not None and _norm(metric["source_id"]) else _norm(default_source_id)
        )
        source_record_id = (
            _norm(source_record_row["source_record_id"])
            if source_record_row is not None and _norm(source_record_row["source_record_id"])
            else _default_source_record_id(
                sanction_source_id=sanction_source_id,
                kpi_id=kpi_id,
                period_date=period_date_token,
                period_granularity=period_granularity_token,
            )
        )
        source_url = (
            _norm(metric["source_url"]) if metric is not None and _norm(metric["source_url"]) else _norm(qrow.get("source_url"))
        )
        row = {
            "sanction_source_id": sanction_source_id,
            "kpi_id": kpi_id,
            "period_date": period_date_token,
            "period_granularity": period_granularity_token,
            "value": _norm(metric["value"]) if metric is not None and metric["value"] is not None else "",
            "numerator": _norm(metric["numerator"]) if metric is not None and metric["numerator"] is not None else "",
            "denominator": _norm(metric["denominator"]) if metric is not None and metric["denominator"] is not None else "",
            "source_url": source_url,
            "evidence_date": _norm(metric["evidence_date"]) if metric is not None and metric["evidence_date"] is not None else "",
            "evidence_quote": _norm(metric["evidence_quote"]) if metric is not None and metric["evidence_quote"] is not None else "",
            "source_id": source_id,
            "source_record_id": source_record_id,
            "source_record_pk": source_record_pk if source_record_pk is not None else "",
            "metric_key": metric_key_expected or metric_key,
            "source_label": _norm(src["label"]) if src is not None else "",
            "organismo": _norm(src["organismo"]) if src is not None else "",
            "kpi_label": _norm(kpi["label"]) if kpi is not None else _norm(qrow.get("kpi_label")),
            "metric_formula": _norm(kpi["metric_formula"]) if kpi is not None else "",
            "target_direction": _norm(kpi["target_direction"]) if kpi is not None else "",
            "expected_metrics": _expected_metrics(src),
            "queue_key": _norm(qrow.get("queue_key")),
            "queue_status": status,
            "queue_priority": int(qrow.get("priority") or 0),
            "queue_next_action": _norm(qrow.get("next_action")),
        }
        rows_out.append(row)
        emitted_by_status[status] = int(emitted_by_status.get(status, 0)) + 1

    counts["rows_emitted_total"] = len(rows_out)
    actionable_pairs_total = int(queue_report.get("totals", {}).get("actionable_pairs_total") or 0)
    checks = {
        "gap_queue_not_failed": str(queue_report.get("status")) != "failed",
        "rows_emitted_present": len(rows_out) > 0,
        "filtered_statuses_valid": len(status_set) > 0,
    }
    if str(queue_report.get("status")) == "failed":
        status = "failed"
    elif len(rows_out) == 0 and actionable_pairs_total > 0:
        status = "degraded"
    else:
        status = "ok"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "default_source_id": _norm(default_source_id),
        "metric_scope": dict(queue_report.get("metric_scope") or {}),
        "statuses_filter": sorted(status_set),
        "include_ready": bool(include_ready),
        "queue_report_status": queue_report.get("status"),
        "queue_totals": dict(queue_report.get("totals") or {}),
        "totals": {
            **counts,
            "rows_emitted_by_status": emitted_by_status,
            "rows_skipped_by_status": skipped_by_status,
        },
        "checks": checks,
        "rows_preview": rows_out[:20],
        "rows": rows_out,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sanction_source_id",
        "kpi_id",
        "period_date",
        "period_granularity",
        "value",
        "numerator",
        "denominator",
        "source_url",
        "evidence_date",
        "evidence_quote",
        "source_id",
        "source_record_id",
        "source_record_pk",
        "metric_key",
        "source_label",
        "organismo",
        "kpi_label",
        "metric_formula",
        "target_direction",
        "expected_metrics",
        "queue_key",
        "queue_status",
        "queue_priority",
        "queue_next_action",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Export apply-ready remediation CSV from official-review KPI gap queue"
    )
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--period-date", default="")
    ap.add_argument("--period-granularity", default="")
    ap.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    ap.add_argument("--queue-limit", type=int, default=0)
    ap.add_argument(
        "--statuses",
        default=",".join(DEFAULT_STATUSES),
        help="Comma-separated queue statuses to include",
    )
    ap.add_argument("--include-ready", action="store_true")
    ap.add_argument(
        "--strict-actionable",
        action="store_true",
        help="Exit non-zero when no actionable rows are emitted",
    )
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument("--summary-out", default="", help="Optional JSON summary output")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = build_apply_rows_from_gap_queue(
            conn,
            period_date=_norm(args.period_date),
            period_granularity=_norm(args.period_granularity),
            queue_limit=int(args.queue_limit),
            include_ready=bool(args.include_ready),
            statuses=_parse_statuses(args.statuses),
            default_source_id=_norm(args.source_id) or DEFAULT_SOURCE_ID,
        )
    finally:
        conn.close()

    rows = list(report.pop("rows", []))
    out_path = Path(args.out)
    _write_csv(out_path, rows)

    payload = {
        **report,
        "db_path": str(args.db),
        "output_csv": str(out_path),
        "rows_emitted_total": len(rows),
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if _norm(args.summary_out):
        summary_path = Path(args.summary_out)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if bool(args.strict_actionable) and int(payload.get("rows_emitted_total") or 0) <= 0:
        return 4
    return 0 if str(payload.get("status")) != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
