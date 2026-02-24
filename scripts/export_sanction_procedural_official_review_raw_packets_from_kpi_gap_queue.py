#!/usr/bin/env python3
"""Export per-source raw capture packets from KPI gap queue."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.export_sanction_procedural_official_review_kpi_gap_queue import build_kpi_gap_queue_report
from scripts.export_sanction_procedural_official_review_raw_template import (
    DEFAULT_PERIOD_GRANULARITY,
    DEFAULT_SOURCE_ID,
    RAW_FIELDNAMES,
    build_raw_template,
)

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_STATUSES = ("missing_metric",)


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


def _parse_statuses(token: str) -> set[str]:
    out: set[str] = set()
    for raw in str(token or "").split(","):
        item = _norm(raw)
        if item:
            out.add(item)
    return out


def _packet_filename(*, sanction_source_id: str, period_date: str, period_granularity: str) -> str:
    return f"{_slug(sanction_source_id)}__{_slug(period_date)}__{_slug(period_granularity)}.csv"


def build_raw_packets_from_gap_queue(
    conn: Any,
    *,
    period_date: str,
    period_granularity: str,
    statuses: set[str] | None = None,
    queue_limit: int = 0,
    include_ready: bool = False,
    default_source_id: str = DEFAULT_SOURCE_ID,
) -> dict[str, Any]:
    status_set = set(statuses or DEFAULT_STATUSES)
    gap_report = build_kpi_gap_queue_report(
        conn,
        period_date=_norm(period_date),
        period_granularity=_norm(period_granularity),
        queue_limit=int(queue_limit),
        include_ready=bool(include_ready),
    )

    raw_template = build_raw_template(
        conn,
        period_date=_norm(period_date),
        period_granularity=_norm(period_granularity) or DEFAULT_PERIOD_GRANULARITY,
        default_source_id=_norm(default_source_id) or DEFAULT_SOURCE_ID,
        only_missing=False,
    )
    template_rows = list(raw_template.pop("rows", []))
    template_map = {str(row["sanction_source_id"]): row for row in template_rows}

    queue_rows = list(gap_report.get("queue_rows") or [])
    actionable_by_source: dict[str, set[str]] = {}
    skipped_by_status: dict[str, int] = {}
    for row in queue_rows:
        status = _norm(row.get("status"))
        source_id = _norm(row.get("sanction_source_id"))
        kpi_id = _norm(row.get("kpi_id"))
        if status_set and status not in status_set:
            skipped_by_status[status] = int(skipped_by_status.get(status, 0)) + 1
            continue
        if not source_id or not kpi_id:
            continue
        actionable_by_source.setdefault(source_id, set()).add(kpi_id)

    packets: list[dict[str, Any]] = []
    sources_skipped_missing_template_total = 0
    for source_id, kpis_missing in sorted(actionable_by_source.items()):
        template = template_map.get(source_id)
        if template is None:
            sources_skipped_missing_template_total += 1
            continue
        packet_name = _packet_filename(
            sanction_source_id=source_id,
            period_date=_norm(period_date),
            period_granularity=_norm(period_granularity) or DEFAULT_PERIOD_GRANULARITY,
        )
        packets.append(
            {
                "sanction_source_id": source_id,
                "kpis_missing_total": len(kpis_missing),
                "kpis_missing": sorted(kpis_missing),
                "packet_filename": packet_name,
                "row": dict(template),
            }
        )

    counts = {
        "queue_rows_seen_total": len(queue_rows),
        "sources_actionable_total": len(actionable_by_source),
        "packets_emitted_total": len(packets),
        "sources_skipped_missing_template_total": sources_skipped_missing_template_total,
        "rows_skipped_filtered_status_total": sum(int(v) for v in skipped_by_status.values()),
    }
    checks = {
        "gap_queue_not_failed": str(gap_report.get("status")) != "failed",
        "statuses_filter_valid": len(status_set) > 0,
        "packets_complete_for_actionable_sources": len(packets) == (len(actionable_by_source) - sources_skipped_missing_template_total),
    }
    if str(gap_report.get("status")) == "failed":
        status = "failed"
    elif len(actionable_by_source) > 0 and len(packets) == 0:
        status = "degraded"
    elif sources_skipped_missing_template_total > 0:
        status = "degraded"
    else:
        status = "ok"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "default_source_id": _norm(default_source_id) or DEFAULT_SOURCE_ID,
        "metric_scope": dict(gap_report.get("metric_scope") or {}),
        "statuses_filter": sorted(status_set),
        "include_ready": bool(include_ready),
        "queue_report_status": gap_report.get("status"),
        "queue_totals": dict(gap_report.get("totals") or {}),
        "totals": {
            **counts,
            "rows_skipped_by_status": skipped_by_status,
        },
        "checks": checks,
        "packets_preview": [
            {
                "sanction_source_id": p["sanction_source_id"],
                "kpis_missing_total": p["kpis_missing_total"],
                "kpis_missing": p["kpis_missing"],
                "packet_filename": p["packet_filename"],
            }
            for p in packets[:20]
        ],
        "packets": packets,
    }


def _write_packet_csv(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(RAW_FIELDNAMES))
        writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in RAW_FIELDNAMES})


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Export per-source raw capture packets from KPI gap queue"
    )
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--period-date", required=True)
    ap.add_argument("--period-granularity", default=DEFAULT_PERIOD_GRANULARITY)
    ap.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    ap.add_argument("--statuses", default=",".join(DEFAULT_STATUSES))
    ap.add_argument("--queue-limit", type=int, default=0)
    ap.add_argument("--include-ready", action="store_true")
    ap.add_argument("--strict-actionable", action="store_true", help="Exit non-zero when no packets are emitted")
    ap.add_argument("--out-dir", required=True, help="Directory where per-source CSV packets are written")
    ap.add_argument("--summary-out", default="", help="Optional JSON summary output")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = build_raw_packets_from_gap_queue(
            conn,
            period_date=_norm(args.period_date),
            period_granularity=_norm(args.period_granularity) or DEFAULT_PERIOD_GRANULARITY,
            statuses=_parse_statuses(args.statuses),
            queue_limit=int(args.queue_limit),
            include_ready=bool(args.include_ready),
            default_source_id=_norm(args.source_id) or DEFAULT_SOURCE_ID,
        )
    finally:
        conn.close()

    packets = list(report.pop("packets", []))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    packet_files: list[str] = []
    for packet in packets:
        packet_path = out_dir / _norm(packet.get("packet_filename"))
        _write_packet_csv(packet_path, dict(packet.get("row") or {}))
        packet_files.append(str(packet_path))

    payload = {
        **report,
        "db_path": str(args.db),
        "output_dir": str(out_dir),
        "packet_files": packet_files,
        "packets_emitted_total": len(packet_files),
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if _norm(args.summary_out):
        summary_path = Path(args.summary_out)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if bool(args.strict_actionable) and int(payload.get("packets_emitted_total") or 0) <= 0:
        return 4
    return 0 if str(payload.get("status")) != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
