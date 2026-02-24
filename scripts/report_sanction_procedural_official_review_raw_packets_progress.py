#!/usr/bin/env python3
"""Report readiness/progress of raw packet files for official procedural-review metrics."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.export_sanction_procedural_official_review_apply_from_raw_metrics import (
    DEFAULT_PERIOD_GRANULARITY,
    DEFAULT_SOURCE_ID,
    _REQUIRED_HEADERS,
    build_apply_rows,
)
from scripts.export_sanction_procedural_official_review_raw_packets_from_kpi_gap_queue import (
    build_raw_packets_from_gap_queue,
)
from scripts.export_sanction_procedural_official_review_raw_template import RAW_FIELDNAMES

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


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = [str(h or "") for h in (reader.fieldnames or [])]
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({str(k or ""): str(v or "") for k, v in row.items()})
    return headers, rows


def _write_json(path: str, payload: dict[str, Any]) -> None:
    token = _norm(path)
    if not token:
        return
    out_path = Path(token)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    token = _norm(path)
    if not token:
        return
    headers = [
        "sanction_source_id",
        "packet_filename",
        "packet_path",
        "packet_exists",
        "packet_status",
        "rows_found",
        "missing_headers",
        "missing_required_fields",
        "row_reject_reasons",
        "row_reject_priority",
        "kpis_missing_total",
        "kpis_missing",
        "ready_for_transform",
    ]
    out_path = Path(token)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in headers})


def _expected_raw_headers() -> list[str]:
    return [_norm(h) for h in RAW_FIELDNAMES if _norm(h)]


def _missing_required_fields(row: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for header in _REQUIRED_HEADERS:
        if not _norm(row.get(header)):
            out.append(str(header))
    return out


def build_raw_packets_progress_report(
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
    packet_plan = build_raw_packets_from_gap_queue(
        conn,
        period_date=_norm(period_date),
        period_granularity=_norm(period_granularity) or DEFAULT_PERIOD_GRANULARITY,
        statuses=set(statuses or _parse_statuses(DEFAULT_STATUSES)),
        queue_limit=int(queue_limit),
        include_ready=bool(include_ready),
        default_source_id=_norm(default_source_id) or DEFAULT_SOURCE_ID,
    )

    packets = list(packet_plan.pop("packets", []))
    expected_headers = _expected_raw_headers()
    expected_set = {_norm(p.get("packet_filename")) for p in packets if _norm(p.get("packet_filename"))}
    packet_by_name = {_norm(p.get("packet_filename")): p for p in packets if _norm(p.get("packet_filename"))}

    available = {path.name: path for path in packets_dir.glob("*.csv") if path.is_file()}
    missing_packet_files = sorted([name for name in expected_set if name not in available])
    extra_packet_files = sorted([name for name in available.keys() if name not in expected_set])

    rows: list[dict[str, Any]] = []
    for packet_name in sorted(expected_set):
        packet = packet_by_name.get(packet_name) or {}
        packet_path = available.get(packet_name)
        source_id = _norm(packet.get("sanction_source_id"))
        kpis_missing = list(packet.get("kpis_missing") or [])
        base_row: dict[str, Any] = {
            "sanction_source_id": source_id,
            "packet_filename": packet_name,
            "packet_path": str(packet_path) if packet_path else "",
            "packet_exists": bool(packet_path is not None),
            "packet_status": "missing_packet_file",
            "rows_found": 0,
            "missing_headers": "|".join(expected_headers),
            "missing_required_fields": "",
            "row_reject_reasons": "",
            "row_reject_priority": "",
            "kpis_missing_total": int(packet.get("kpis_missing_total") or len(kpis_missing)),
            "kpis_missing": "|".join([_norm(kpi) for kpi in kpis_missing if _norm(kpi)]),
            "ready_for_transform": False,
        }

        if packet_path is None:
            rows.append(base_row)
            continue

        headers, packet_rows = _read_csv(packet_path)
        header_set = {_norm(h) for h in headers if _norm(h)}
        missing_headers = [h for h in expected_headers if h not in header_set]
        base_row["rows_found"] = len(packet_rows)
        base_row["missing_headers"] = "|".join(missing_headers)

        if missing_headers:
            base_row["packet_status"] = "invalid_headers"
            rows.append(base_row)
            continue

        if len(packet_rows) <= 0:
            base_row["packet_status"] = "empty_packet"
            base_row["missing_headers"] = ""
            rows.append(base_row)
            continue

        first_row = dict(packet_rows[0])
        missing_required = _missing_required_fields(first_row)
        base_row["missing_required_fields"] = "|".join(missing_required)
        base_row["missing_headers"] = ""

        apply_report = build_apply_rows(
            headers=headers,
            rows=[first_row],
            default_source_id=_norm(default_source_id) or DEFAULT_SOURCE_ID,
            default_period_granularity=_norm(period_granularity) or DEFAULT_PERIOD_GRANULARITY,
        )
        rejected_rows = list(apply_report.get("rejected_rows") or [])
        if len(packet_rows) > 1:
            base_row["packet_status"] = "multiple_rows"
            base_row["row_reject_reasons"] = "multiple_rows"
            base_row["row_reject_priority"] = "95"
            rows.append(base_row)
            continue
        if rejected_rows:
            rejected = rejected_rows[0]
            base_row["packet_status"] = "invalid_row"
            base_row["row_reject_reasons"] = _norm(rejected.get("_reason"))
            base_row["row_reject_priority"] = _norm(rejected.get("_priority"))
            rows.append(base_row)
            continue

        base_row["packet_status"] = "ready"
        base_row["ready_for_transform"] = True
        rows.append(base_row)

    status_counts: dict[str, int] = {}
    ready_total = 0
    for row in rows:
        status = _norm(row.get("packet_status")) or "unknown"
        status_counts[status] = int(status_counts.get(status, 0)) + 1
        if bool(row.get("ready_for_transform")):
            ready_total += 1

    expected_total = len(expected_set)
    totals = {
        "queue_rows_seen_total": int((packet_plan.get("totals") or {}).get("queue_rows_seen_total") or 0),
        "sources_actionable_total": int((packet_plan.get("totals") or {}).get("sources_actionable_total") or 0),
        "packets_expected_total": expected_total,
        "packets_found_total": expected_total - len(missing_packet_files),
        "packets_missing_total": len(missing_packet_files),
        "packets_extra_total": len(extra_packet_files),
        "packets_ready_total": ready_total,
        "packets_not_ready_total": expected_total - ready_total,
        "packets_status_counts": status_counts,
    }
    checks = {
        "packet_directory_exists": packets_dir.exists() and packets_dir.is_dir(),
        "queue_report_not_failed": str(packet_plan.get("status")) != "failed",
        "packet_coverage_complete": len(missing_packet_files) == 0,
        "all_expected_packets_ready": expected_total > 0 and ready_total == expected_total,
    }

    if str(packet_plan.get("status")) == "failed":
        status = "failed"
    elif expected_total <= 0:
        status = "degraded"
    elif ready_total == expected_total:
        status = "ok"
    else:
        status = "degraded"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "db_path": "",
        "packets_dir": str(packets_dir),
        "metric_scope": dict(packet_plan.get("metric_scope") or {}),
        "statuses_filter": list(packet_plan.get("statuses_filter") or []),
        "include_ready": bool(packet_plan.get("include_ready")),
        "queue_report_status": packet_plan.get("status"),
        "queue_totals": dict(packet_plan.get("queue_totals") or {}),
        "totals": totals,
        "checks": checks,
        "missing_packet_files": missing_packet_files,
        "extra_packet_files": extra_packet_files,
        "packets_preview": rows[:20],
        "packets_rows": rows,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Report readiness/progress of raw packet files for official procedural-review metrics"
    )
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--packets-dir", required=True)
    ap.add_argument("--period-date", required=True)
    ap.add_argument("--period-granularity", default=DEFAULT_PERIOD_GRANULARITY)
    ap.add_argument("--statuses", default=DEFAULT_STATUSES)
    ap.add_argument("--queue-limit", type=int, default=0)
    ap.add_argument("--include-ready", action="store_true")
    ap.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    ap.add_argument("--strict-actionable", action="store_true")
    ap.add_argument("--strict-ready", action="store_true")
    ap.add_argument("--csv-out", default="")
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
        payload = build_raw_packets_progress_report(
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

    payload["db_path"] = str(db_path)
    payload["strict_actionable"] = bool(args.strict_actionable)
    payload["strict_ready"] = bool(args.strict_ready)

    rows = list(payload.pop("packets_rows", []))
    _write_csv(args.csv_out, rows)
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    _write_json(args.out, payload)
    print(rendered)

    expected_total = int((payload.get("totals") or {}).get("packets_expected_total") or 0)
    ready_total = int((payload.get("totals") or {}).get("packets_ready_total") or 0)
    if bool(args.strict_actionable) and expected_total <= 0:
        return 4
    if bool(args.strict_ready) and expected_total > 0 and ready_total < expected_total:
        return 4
    return 0 if str(payload.get("status")) != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
