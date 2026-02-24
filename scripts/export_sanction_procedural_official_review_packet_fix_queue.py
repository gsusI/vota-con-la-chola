#!/usr/bin/env python3
"""Export prioritized fix queue for non-ready official procedural raw packets."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.export_sanction_procedural_official_review_raw_template import (
    DEFAULT_PERIOD_GRANULARITY,
    DEFAULT_SOURCE_ID,
)
from scripts.report_sanction_procedural_official_review_raw_packets_progress import (
    build_raw_packets_progress_report,
)

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_STATUSES = "missing_metric"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _parse_statuses(token: str) -> set[str]:
    out: set[str] = set()
    for raw in str(token or "").split(","):
        item = _norm(raw)
        if item:
            out.add(item)
    return out


def _priority(packet_status: str) -> int:
    status = _norm(packet_status)
    if status == "missing_packet_file":
        return 100
    if status == "invalid_headers":
        return 90
    if status == "multiple_rows":
        return 85
    if status == "empty_packet":
        return 80
    if status == "invalid_row":
        return 70
    return 20


def _next_action(row: dict[str, Any]) -> str:
    status = _norm(row.get("packet_status"))
    if status == "missing_packet_file":
        return "export_packet_template_for_source_and_fill_required_fields"
    if status == "invalid_headers":
        return "restore_required_packet_headers_from_raw_template_contract"
    if status == "multiple_rows":
        return "keep_single_row_per_source_period_packet"
    if status == "empty_packet":
        return "fill_required_raw_counts_and_evidence_fields_in_packet"
    if status == "invalid_row":
        missing = _norm(row.get("missing_required_fields"))
        reasons = _norm(row.get("row_reject_reasons"))
        if "missing_required_metadata" in reasons or missing:
            return "complete_evidence_and_raw_count_fields_then_recheck"
        return "fix_packet_row_validation_errors_then_recheck"
    return "review_packet_and_recheck_progress"


def _queue_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            _norm(row.get("sanction_source_id")),
            _norm(row.get("packet_filename")),
            _norm(row.get("packet_status")),
        ]
    )


def _write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    token = _norm(path)
    if not token:
        return
    headers = [
        "queue_key",
        "priority",
        "next_action",
        "sanction_source_id",
        "packet_filename",
        "packet_path",
        "packet_status",
        "missing_required_fields",
        "row_reject_reasons",
        "row_reject_priority",
        "kpis_missing_total",
        "kpis_missing",
    ]
    out_path = Path(token)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def _write_json(path: str, payload: dict[str, Any]) -> None:
    token = _norm(path)
    if not token:
        return
    out_path = Path(token)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_packet_fix_queue_report(
    conn: Any,
    *,
    packets_dir: Path,
    period_date: str,
    period_granularity: str,
    statuses: set[str] | None = None,
    queue_limit: int = 0,
    include_ready: bool = False,
    default_source_id: str = DEFAULT_SOURCE_ID,
) -> dict[str, Any]:
    progress = build_raw_packets_progress_report(
        conn,
        packets_dir=packets_dir,
        period_date=_norm(period_date),
        period_granularity=_norm(period_granularity) or DEFAULT_PERIOD_GRANULARITY,
        statuses=set(statuses or _parse_statuses(DEFAULT_STATUSES)),
        queue_limit=int(queue_limit),
        include_ready=bool(include_ready),
        default_source_id=_norm(default_source_id) or DEFAULT_SOURCE_ID,
    )

    progress_rows = list(progress.pop("packets_rows", []))
    queue_rows: list[dict[str, Any]] = []
    counts_by_status: dict[str, int] = {}
    for row in progress_rows:
        if bool(row.get("ready_for_transform")):
            continue
        packet_status = _norm(row.get("packet_status")) or "unknown"
        counts_by_status[packet_status] = int(counts_by_status.get(packet_status, 0)) + 1
        queue_rows.append(
            {
                "queue_key": _queue_key(row),
                "priority": _priority(packet_status),
                "next_action": _next_action(row),
                "sanction_source_id": _norm(row.get("sanction_source_id")),
                "packet_filename": _norm(row.get("packet_filename")),
                "packet_path": _norm(row.get("packet_path")),
                "packet_status": packet_status,
                "missing_required_fields": _norm(row.get("missing_required_fields")),
                "row_reject_reasons": _norm(row.get("row_reject_reasons")),
                "row_reject_priority": _norm(row.get("row_reject_priority")),
                "kpis_missing_total": int(row.get("kpis_missing_total") or 0),
                "kpis_missing": _norm(row.get("kpis_missing")),
            }
        )

    queue_rows_sorted = sorted(
        queue_rows,
        key=lambda item: (
            -int(item.get("priority") or 0),
            _norm(item.get("sanction_source_id")),
            _norm(item.get("packet_filename")),
        ),
    )

    totals = {
        "queue_rows_total": len(queue_rows_sorted),
        "queue_rows_by_packet_status": counts_by_status,
        "packets_expected_total": int((progress.get("totals") or {}).get("packets_expected_total") or 0),
        "packets_ready_total": int((progress.get("totals") or {}).get("packets_ready_total") or 0),
        "packets_not_ready_total": int((progress.get("totals") or {}).get("packets_not_ready_total") or 0),
    }
    checks = {
        "progress_report_not_failed": str(progress.get("status")) != "failed",
        "fix_queue_empty": len(queue_rows_sorted) == 0,
    }

    if str(progress.get("status")) == "failed":
        status = "failed"
    elif len(queue_rows_sorted) > 0:
        status = "degraded"
    else:
        status = "ok"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "packets_dir": str(packets_dir),
        "metric_scope": dict(progress.get("metric_scope") or {}),
        "statuses_filter": list(progress.get("statuses_filter") or []),
        "progress_status": progress.get("status"),
        "progress_totals": dict(progress.get("totals") or {}),
        "totals": totals,
        "checks": checks,
        "queue_preview": queue_rows_sorted[:20],
        "queue_rows": queue_rows_sorted,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Export prioritized fix queue for non-ready official procedural raw packets"
    )
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--packets-dir", required=True)
    ap.add_argument("--period-date", required=True)
    ap.add_argument("--period-granularity", default=DEFAULT_PERIOD_GRANULARITY)
    ap.add_argument("--statuses", default=DEFAULT_STATUSES)
    ap.add_argument("--queue-limit", type=int, default=0)
    ap.add_argument("--include-ready", action="store_true")
    ap.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    ap.add_argument("--strict-empty", action="store_true")
    ap.add_argument("--csv-out", required=True)
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    packets_dir = Path(args.packets_dir)
    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2
    if not packets_dir.exists() or not packets_dir.is_dir():
        print(json.dumps({"error": f"packets dir not found: {packets_dir}"}, ensure_ascii=False))
        return 2

    conn = open_db(db_path)
    try:
        payload = build_packet_fix_queue_report(
            conn,
            packets_dir=packets_dir,
            period_date=_norm(args.period_date),
            period_granularity=_norm(args.period_granularity) or DEFAULT_PERIOD_GRANULARITY,
            statuses=_parse_statuses(args.statuses),
            queue_limit=int(args.queue_limit),
            include_ready=bool(args.include_ready),
            default_source_id=_norm(args.source_id) or DEFAULT_SOURCE_ID,
        )
    finally:
        conn.close()

    rows = list(payload.pop("queue_rows", []))
    payload["db_path"] = str(db_path)
    _write_csv(args.csv_out, rows)
    _write_json(args.out, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if bool(args.strict_empty) and int((payload.get("totals") or {}).get("queue_rows_total") or 0) > 0:
        return 4
    return 0 if str(payload.get("status")) != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
