#!/usr/bin/env python3
"""Run gap->apply cycle for official procedural-review metrics."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.export_sanction_procedural_official_review_apply_from_kpi_gap_queue import (
    DEFAULT_SOURCE_ID,
    build_apply_rows_from_gap_queue,
)
from scripts.report_sanction_procedural_official_review_status import (
    build_status_report as build_official_review_status_report,
)
from scripts.run_sanction_procedural_official_review_apply_cycle import (
    DEFAULT_DB,
    run_cycle,
    today_utc_date,
)

DEFAULT_STATUSES = "missing_source_record"


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


def _write_json(path: str, payload: dict[str, Any]) -> None:
    token = _norm(path)
    if not token:
        return
    out_path = Path(token)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def _build_skipped_cycle_payload(
    *,
    db_path: Path,
    status_queue_limit: int,
    strict_readiness: bool,
    dry_run: bool,
    skip_reason: str,
) -> dict[str, Any]:
    conn = open_db(db_path)
    try:
        status_snapshot = build_official_review_status_report(conn, queue_limit=int(status_queue_limit))
    finally:
        conn.close()
    return {
        "generated_at": now_utc_iso(),
        "db_path": str(db_path),
        "input_csv": "",
        "strict_readiness": bool(strict_readiness),
        "dry_run": bool(dry_run),
        "readiness": {},
        "status_before": status_snapshot,
        "apply": {
            "skipped": True,
            "skip_reason": _norm(skip_reason) or "no_actionable_rows",
            "dry_run": bool(dry_run),
            "counts": {
                "rows_seen": 0,
                "rows_ready": 0,
                "rows_upserted": 0,
            },
        },
        "status_after": status_snapshot,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Run KPI-gap remediation cycle (gap export -> readiness/apply/status)"
    )
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--period-date", default="")
    ap.add_argument("--period-granularity", default="")
    ap.add_argument("--statuses", default=DEFAULT_STATUSES)
    ap.add_argument("--include-ready", action="store_true")
    ap.add_argument("--queue-limit", type=int, default=0)
    ap.add_argument("--strict-actionable", action="store_true")
    ap.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    ap.add_argument("--snapshot-date", default=today_utc_date())
    ap.add_argument("--readiness-tolerance", type=float, default=0.01)
    ap.add_argument("--readiness-queue-limit", type=int, default=0)
    ap.add_argument("--readiness-csv-out", default="")
    ap.add_argument("--readiness-out", default="")
    ap.add_argument("--strict-readiness", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status-queue-limit", type=int, default=0)
    ap.add_argument("--status-out", default="")
    ap.add_argument("--apply-out", default="", help="Apply CSV output path")
    ap.add_argument("--gap-out", default="", help="Gap export summary JSON output")
    ap.add_argument("--cycle-out", default="", help="Nested cycle JSON output")
    ap.add_argument("--out", default="", help="Combined payload JSON output")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2

    conn = open_db(db_path)
    try:
        gap_report = build_apply_rows_from_gap_queue(
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

    rows = list(gap_report.pop("rows", []))

    apply_csv_path: Path
    temp_dir_apply: TemporaryDirectory[str] | None = None
    if _norm(args.apply_out):
        apply_csv_path = Path(_norm(args.apply_out))
    else:
        temp_dir_apply = TemporaryDirectory(prefix="sanction_proc_gap_apply_")
        apply_csv_path = Path(temp_dir_apply.name) / "apply_from_gap.csv"
    _write_csv(apply_csv_path, rows)

    gap_payload = {
        **gap_report,
        "db_path": str(db_path),
        "output_apply_csv": str(apply_csv_path),
        "rows_emitted_total": len(rows),
    }
    _write_json(args.gap_out, gap_payload)

    cycle_exit_code = 0
    if str(gap_payload.get("status")) == "failed":
        cycle_payload = _build_skipped_cycle_payload(
            db_path=db_path,
            status_queue_limit=int(args.status_queue_limit),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
            skip_reason="gap_export_failed",
        )
        cycle_exit_code = 1
    elif int(gap_payload.get("rows_emitted_total") or 0) <= 0:
        cycle_payload = _build_skipped_cycle_payload(
            db_path=db_path,
            status_queue_limit=int(args.status_queue_limit),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
            skip_reason="no_actionable_rows",
        )
        cycle_exit_code = 4 if bool(args.strict_actionable) else 0
    else:
        cycle_exit_code, cycle_payload = run_cycle(
            db_path=db_path,
            in_path=apply_csv_path,
            source_id=_norm(args.source_id) or DEFAULT_SOURCE_ID,
            snapshot_date=_norm(args.snapshot_date) or today_utc_date(),
            readiness_tolerance=float(args.readiness_tolerance),
            readiness_queue_limit=int(args.readiness_queue_limit),
            readiness_csv_out=_norm(args.readiness_csv_out),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
            status_queue_limit=int(args.status_queue_limit),
        )

    _write_json(args.readiness_out, dict(cycle_payload.get("readiness") or {}))
    _write_json(args.status_out, dict(cycle_payload.get("status_after") or {}))
    _write_json(args.cycle_out, cycle_payload)

    payload = {
        "generated_at": now_utc_iso(),
        "db_path": str(db_path),
        "strict_actionable": bool(args.strict_actionable),
        "strict_readiness": bool(args.strict_readiness),
        "dry_run": bool(args.dry_run),
        "gap_export": gap_payload,
        "cycle": cycle_payload,
    }
    _write_json(args.out, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if temp_dir_apply is not None:
        temp_dir_apply.cleanup()
    return int(cycle_exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
