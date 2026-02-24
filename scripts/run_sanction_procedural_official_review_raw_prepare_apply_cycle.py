#!/usr/bin/env python3
"""Run strict raw->prepare->apply cycle for official procedural-review metrics."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.export_sanction_procedural_official_review_apply_from_raw_metrics import (
    _APPLY_FIELDNAMES,
    DEFAULT_PERIOD_GRANULARITY,
    DEFAULT_SOURCE_ID,
    build_apply_rows,
)
from scripts.prepare_sanction_procedural_official_review_apply_input import (
    build_prepare_report,
)
from scripts.run_sanction_procedural_official_review_apply_cycle import (
    DEFAULT_DB,
    run_cycle,
    today_utc_date,
)
from scripts.report_sanction_procedural_official_review_status import (
    build_status_report as build_official_review_status_report,
)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _write_json(path: str, payload: dict[str, Any]) -> None:
    token = _norm(path)
    if not token:
        return
    out_path = Path(token)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = [str(h or "") for h in (reader.fieldnames or [])]
        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append({str(k or ""): str(v or "") for k, v in row.items()})
    return headers, rows


def _write_csv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in headers})


def _build_raw_payload(
    *,
    report: dict[str, Any],
    raw_input_csv: Path,
    apply_csv: Path,
    strict_raw: bool,
    apply_rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        **report,
        "raw_input_csv": str(raw_input_csv),
        "output_apply_csv": str(apply_csv),
        "strict_raw": bool(strict_raw),
        "apply_rows_preview": apply_rows[:20],
        "rejected_rows_preview": rejected_rows[:20],
    }


def _build_prepare_payload(
    *,
    report: dict[str, Any],
    input_csv: Path,
    prepared_csv: Path,
    strict_prepare: bool,
    kept_rows: list[dict[str, Any]],
    rejected_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        **report,
        "input_csv": str(input_csv),
        "prepared_csv": str(prepared_csv),
        "strict_prepare": bool(strict_prepare),
        "rows_kept_preview": kept_rows[:20],
        "rows_rejected_preview": rejected_rows[:20],
    }


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
            "skip_reason": _norm(skip_reason) or "raw_not_ok",
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
        description="Run raw->prepare->readiness->apply->status cycle for official procedural-review metrics"
    )
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--raw-in", required=True, help="Raw input CSV path")
    ap.add_argument("--apply-out", default="", help="Apply-ready CSV path generated from raw input")
    ap.add_argument("--raw-rejected-csv-out", default="", help="Optional raw rejection queue CSV")
    ap.add_argument("--raw-out-json", default="", help="Optional raw transformation summary JSON")
    ap.add_argument("--strict-raw", action="store_true", help="Require raw transform status=ok before continue")
    ap.add_argument("--default-source-id", default=DEFAULT_SOURCE_ID)
    ap.add_argument("--default-period-granularity", default=DEFAULT_PERIOD_GRANULARITY)
    ap.add_argument("--prepare-out", default="", help="Prepared CSV path")
    ap.add_argument("--prepare-rejected-csv-out", default="", help="Optional prepare rejection queue CSV")
    ap.add_argument("--prepare-out-json", default="", help="Optional prepare summary JSON")
    ap.add_argument("--strict-prepare", action="store_true", help="Require prepare status=ok before cycle")
    ap.add_argument("--snapshot-date", default=today_utc_date())
    ap.add_argument("--readiness-tolerance", type=float, default=0.01)
    ap.add_argument("--readiness-queue-limit", type=int, default=0)
    ap.add_argument("--readiness-csv-out", default="")
    ap.add_argument("--readiness-out", default="")
    ap.add_argument("--strict-readiness", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status-queue-limit", type=int, default=0)
    ap.add_argument("--status-out", default="")
    ap.add_argument("--cycle-out", default="", help="Optional nested cycle payload JSON output")
    ap.add_argument("--out", default="", help="Optional full payload JSON output")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    raw_in_path = Path(args.raw_in)

    if not db_path.exists():
        print(json.dumps({"error": f"db not found: {db_path}"}, ensure_ascii=False))
        return 2
    if not raw_in_path.exists():
        print(json.dumps({"error": f"raw input csv not found: {raw_in_path}"}, ensure_ascii=False))
        return 2

    raw_headers, raw_rows = _read_csv(raw_in_path)
    raw_report = build_apply_rows(
        headers=raw_headers,
        rows=raw_rows,
        default_source_id=_norm(args.default_source_id) or DEFAULT_SOURCE_ID,
        default_period_granularity=_norm(args.default_period_granularity) or DEFAULT_PERIOD_GRANULARITY,
    )
    apply_rows = list(raw_report.pop("apply_rows", []))
    raw_rejected_rows = list(raw_report.pop("rejected_rows", []))

    apply_csv_path: Path
    temp_dir_apply: TemporaryDirectory[str] | None = None
    if _norm(args.apply_out):
        apply_csv_path = Path(_norm(args.apply_out))
    else:
        temp_dir_apply = TemporaryDirectory(prefix="sanction_proc_raw_apply_")
        apply_csv_path = Path(temp_dir_apply.name) / "apply_ready.csv"
    _write_csv(apply_csv_path, list(_APPLY_FIELDNAMES), apply_rows)

    if _norm(args.raw_rejected_csv_out):
        raw_rejected_headers = list(raw_headers) + ["_csv_line", "_reason", "_priority"]
        _write_csv(Path(_norm(args.raw_rejected_csv_out)), raw_rejected_headers, raw_rejected_rows)

    raw_payload = _build_raw_payload(
        report=raw_report,
        raw_input_csv=raw_in_path,
        apply_csv=apply_csv_path,
        strict_raw=bool(args.strict_raw),
        apply_rows=apply_rows,
        rejected_rows=raw_rejected_rows,
    )
    _write_json(args.raw_out_json, raw_payload)

    if bool(args.strict_raw) and str(raw_payload.get("status")) != "ok":
        cycle_payload = _build_skipped_cycle_payload(
            db_path=db_path,
            status_queue_limit=int(args.status_queue_limit),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
            skip_reason="raw_not_ok",
        )
        payload = {
            "generated_at": now_utc_iso(),
            "db_path": str(db_path),
            "raw_input_csv": str(raw_in_path),
            "strict_raw": bool(args.strict_raw),
            "strict_prepare": bool(args.strict_prepare),
            "strict_readiness": bool(args.strict_readiness),
            "dry_run": bool(args.dry_run),
            "raw": raw_payload,
            "prepare": {},
            "cycle": cycle_payload,
        }
        _write_json(args.readiness_out, dict(cycle_payload.get("readiness") or {}))
        _write_json(args.status_out, dict(cycle_payload.get("status_after") or {}))
        _write_json(args.cycle_out, cycle_payload)
        _write_json(args.out, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if temp_dir_apply is not None:
            temp_dir_apply.cleanup()
        return 4

    apply_headers, apply_input_rows = _read_csv(apply_csv_path)
    prepare_report = build_prepare_report(headers=apply_headers, rows=apply_input_rows)
    prepare_kept_rows = list(prepare_report.pop("kept_rows", []))
    prepare_rejected_rows = list(prepare_report.pop("rejected_rows", []))

    prepared_csv_path: Path
    temp_dir_prepared: TemporaryDirectory[str] | None = None
    if _norm(args.prepare_out):
        prepared_csv_path = Path(_norm(args.prepare_out))
    else:
        temp_dir_prepared = TemporaryDirectory(prefix="sanction_proc_prepare_")
        prepared_csv_path = Path(temp_dir_prepared.name) / "prepared.csv"

    _write_csv(prepared_csv_path, apply_headers, prepare_kept_rows)
    if _norm(args.prepare_rejected_csv_out):
        prepare_rejected_headers = list(apply_headers) + ["_csv_line", "_reason"]
        _write_csv(Path(_norm(args.prepare_rejected_csv_out)), prepare_rejected_headers, prepare_rejected_rows)

    prepare_payload = _build_prepare_payload(
        report=prepare_report,
        input_csv=apply_csv_path,
        prepared_csv=prepared_csv_path,
        strict_prepare=bool(args.strict_prepare),
        kept_rows=prepare_kept_rows,
        rejected_rows=prepare_rejected_rows,
    )
    _write_json(args.prepare_out_json, prepare_payload)

    cycle_exit_code = 0
    if bool(args.strict_prepare) and str(prepare_payload.get("status")) != "ok":
        cycle_payload = _build_skipped_cycle_payload(
            db_path=db_path,
            status_queue_limit=int(args.status_queue_limit),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
            skip_reason="prepare_not_ok",
        )
        cycle_exit_code = 4
    else:
        cycle_exit_code, cycle_payload = run_cycle(
            db_path=db_path,
            in_path=prepared_csv_path,
            source_id=_norm(args.default_source_id) or DEFAULT_SOURCE_ID,
            snapshot_date=args.snapshot_date,
            readiness_tolerance=float(args.readiness_tolerance),
            readiness_queue_limit=int(args.readiness_queue_limit),
            readiness_csv_out=args.readiness_csv_out,
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
        "raw_input_csv": str(raw_in_path),
        "strict_raw": bool(args.strict_raw),
        "strict_prepare": bool(args.strict_prepare),
        "strict_readiness": bool(args.strict_readiness),
        "dry_run": bool(args.dry_run),
        "raw": raw_payload,
        "prepare": prepare_payload,
        "cycle": cycle_payload,
    }
    _write_json(args.out, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if temp_dir_prepared is not None:
        temp_dir_prepared.cleanup()
    if temp_dir_apply is not None:
        temp_dir_apply.cleanup()
    return int(cycle_exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
