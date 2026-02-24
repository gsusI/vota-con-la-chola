#!/usr/bin/env python3
"""Run packet-dir -> raw->prepare->apply cycle for official procedural-review metrics."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.export_sanction_procedural_official_review_raw_packets_from_kpi_gap_queue import (
    build_raw_packets_from_gap_queue,
)
from scripts.export_sanction_procedural_official_review_raw_template import (
    DEFAULT_PERIOD_GRANULARITY,
    DEFAULT_SOURCE_ID,
    RAW_FIELDNAMES,
)
from scripts.report_sanction_procedural_official_review_status import (
    build_status_report as build_official_review_status_report,
)
from scripts.run_sanction_procedural_official_review_apply_cycle import (
    DEFAULT_DB,
    today_utc_date,
)

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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(RAW_FIELDNAMES))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in RAW_FIELDNAMES})


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
        "raw_input_csv": "",
        "strict_readiness": bool(strict_readiness),
        "dry_run": bool(dry_run),
        "raw": {},
        "prepare": {},
        "cycle": {
            "generated_at": now_utc_iso(),
            "db_path": str(db_path),
            "input_csv": "",
            "strict_readiness": bool(strict_readiness),
            "dry_run": bool(dry_run),
            "readiness": {},
            "status_before": status_snapshot,
            "apply": {
                "skipped": True,
                "skip_reason": _norm(skip_reason) or "no_actionable_packets",
                "dry_run": bool(dry_run),
                "counts": {
                    "rows_seen": 0,
                    "rows_ready": 0,
                    "rows_upserted": 0,
                },
            },
            "status_after": status_snapshot,
        },
    }


def build_packets_input_payload(
    *,
    packets_dir: Path,
    packet_plan: dict[str, Any],
    packets: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    expected_names = {_norm(packet.get("packet_filename")) for packet in packets if _norm(packet.get("packet_filename"))}
    packet_by_name = {
        _norm(packet.get("packet_filename")): packet
        for packet in packets
        if _norm(packet.get("packet_filename"))
    }

    available = {path.name: path for path in packets_dir.glob("*.csv") if path.is_file()}
    missing_names = sorted([name for name in expected_names if name not in available])
    extra_names = sorted([name for name in available.keys() if name not in expected_names])

    merged_rows: list[dict[str, Any]] = []
    loaded_names: list[str] = []
    empty_names: list[str] = []
    invalid_header_rows: list[dict[str, Any]] = []

    expected_headers = [_norm(h) for h in RAW_FIELDNAMES if _norm(h)]

    for packet_name in sorted(expected_names):
        packet_path = available.get(packet_name)
        if packet_path is None:
            continue
        headers, rows = _read_csv(packet_path)
        header_set = {_norm(h) for h in headers if _norm(h)}
        missing_headers = [h for h in expected_headers if h not in header_set]
        if missing_headers:
            packet = packet_by_name.get(packet_name) or {}
            invalid_header_rows.append(
                {
                    "packet_filename": packet_name,
                    "sanction_source_id": _norm(packet.get("sanction_source_id")),
                    "missing_headers": missing_headers,
                }
            )
            continue

        if len(rows) <= 0:
            empty_names.append(packet_name)
        for row in rows:
            merged_rows.append({key: _norm(row.get(key)) for key in RAW_FIELDNAMES})
        loaded_names.append(packet_name)

    totals = {
        "queue_rows_seen_total": int((packet_plan.get("totals") or {}).get("queue_rows_seen_total") or 0),
        "sources_actionable_total": int((packet_plan.get("totals") or {}).get("sources_actionable_total") or 0),
        "packets_expected_total": len(expected_names),
        "packet_files_found_total": len(loaded_names),
        "packet_files_missing_total": len(missing_names),
        "packet_files_empty_total": len(empty_names),
        "packet_files_invalid_header_total": len(invalid_header_rows),
        "packet_files_extra_total": len(extra_names),
        "packet_rows_loaded_total": len(merged_rows),
    }

    checks = {
        "packet_directory_exists": packets_dir.exists() and packets_dir.is_dir(),
        "queue_report_not_failed": str(packet_plan.get("status")) != "failed",
        "packet_coverage_complete": len(missing_names) == 0,
        "packet_headers_valid": len(invalid_header_rows) == 0,
        "packet_rows_present": len(merged_rows) > 0,
    }

    if str(packet_plan.get("status")) == "failed":
        status = "failed"
    elif len(expected_names) <= 0:
        status = "degraded"
    elif len(missing_names) > 0 or len(invalid_header_rows) > 0:
        status = "degraded"
    elif len(merged_rows) <= 0:
        status = "degraded"
    else:
        status = "ok"

    payload = {
        "generated_at": now_utc_iso(),
        "status": status,
        "queue_report_status": packet_plan.get("status"),
        "metric_scope": dict(packet_plan.get("metric_scope") or {}),
        "statuses_filter": list(packet_plan.get("statuses_filter") or []),
        "include_ready": bool(packet_plan.get("include_ready")),
        "queue_totals": dict(packet_plan.get("queue_totals") or {}),
        "totals": totals,
        "checks": checks,
        "missing_packet_files": missing_names,
        "empty_packet_files": empty_names,
        "invalid_packet_headers": invalid_header_rows,
        "extra_packet_files": extra_names,
        "packet_files_loaded": loaded_names,
        "packets_preview": list(packet_plan.get("packets_preview") or []),
    }
    return payload, merged_rows


def _run_raw_cycle(
    *,
    db_path: Path,
    raw_input_csv: Path,
    nested_out: Path,
    source_id: str,
    default_period_granularity: str,
    snapshot_date: str,
    readiness_tolerance: float,
    readiness_queue_limit: int,
    status_queue_limit: int,
    strict_raw: bool,
    strict_prepare: bool,
    strict_readiness: bool,
    dry_run: bool,
) -> tuple[int, dict[str, Any], str, str]:
    script_path = Path(__file__).resolve().with_name(
        "run_sanction_procedural_official_review_raw_prepare_apply_cycle.py"
    )
    repo_root = script_path.resolve().parents[1]
    cmd = [
        sys.executable,
        str(script_path),
        "--db",
        str(db_path),
        "--raw-in",
        str(raw_input_csv),
        "--default-source-id",
        _norm(source_id) or DEFAULT_SOURCE_ID,
        "--default-period-granularity",
        _norm(default_period_granularity) or DEFAULT_PERIOD_GRANULARITY,
        "--snapshot-date",
        _norm(snapshot_date) or today_utc_date(),
        "--readiness-tolerance",
        str(float(readiness_tolerance)),
        "--readiness-queue-limit",
        str(int(readiness_queue_limit)),
        "--status-queue-limit",
        str(int(status_queue_limit)),
        "--out",
        str(nested_out),
    ]
    if bool(strict_raw):
        cmd.append("--strict-raw")
    if bool(strict_prepare):
        cmd.append("--strict-prepare")
    if bool(strict_readiness):
        cmd.append("--strict-readiness")
    if bool(dry_run):
        cmd.append("--dry-run")

    env = dict(os.environ)
    py_path = _norm(env.get("PYTHONPATH"))
    repo_root_str = str(repo_root)
    env["PYTHONPATH"] = f"{repo_root_str}:{py_path}" if py_path else repo_root_str
    run = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root_str, env=env)

    nested_payload: dict[str, Any] = {}
    if nested_out.exists():
        try:
            nested_payload = json.loads(nested_out.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            nested_payload = {}
    if not nested_payload:
        try:
            nested_payload = json.loads(_norm(run.stdout))
        except Exception:  # noqa: BLE001
            nested_payload = {
                "generated_at": now_utc_iso(),
                "status": "failed",
                "error": "raw_cycle_payload_unavailable",
            }

    return int(run.returncode), nested_payload, _norm(run.stdout), _norm(run.stderr)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Run packet-dir -> raw->prepare->apply cycle for official procedural-review metrics"
    )
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--packets-dir", required=True, help="Directory with per-source raw packet CSVs")
    ap.add_argument("--period-date", required=True)
    ap.add_argument("--period-granularity", default=DEFAULT_PERIOD_GRANULARITY)
    ap.add_argument("--statuses", default=DEFAULT_STATUSES)
    ap.add_argument("--queue-limit", type=int, default=0)
    ap.add_argument("--include-ready", action="store_true")
    ap.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    ap.add_argument("--strict-actionable", action="store_true")
    ap.add_argument(
        "--strict-packet-coverage",
        action="store_true",
        help="Exit non-zero when expected packet files are missing or invalid",
    )
    ap.add_argument("--raw-in-out", default="", help="Optional merged raw CSV path")
    ap.add_argument("--packets-out", default="", help="Optional packets-input summary JSON output")
    ap.add_argument("--snapshot-date", default=today_utc_date())
    ap.add_argument("--readiness-tolerance", type=float, default=0.01)
    ap.add_argument("--readiness-queue-limit", type=int, default=0)
    ap.add_argument("--status-queue-limit", type=int, default=0)
    ap.add_argument("--strict-raw", action="store_true")
    ap.add_argument("--strict-prepare", action="store_true")
    ap.add_argument("--strict-readiness", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cycle-out", default="", help="Optional nested raw-cycle JSON output")
    ap.add_argument("--out", default="", help="Optional combined payload JSON output")
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
        packet_plan = build_raw_packets_from_gap_queue(
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

    packets = list(packet_plan.pop("packets", []))
    packet_input_payload, raw_rows = build_packets_input_payload(
        packets_dir=packets_dir,
        packet_plan=packet_plan,
        packets=packets,
    )

    raw_in_path: Path
    tmp_raw_dir: TemporaryDirectory[str] | None = None
    if _norm(args.raw_in_out):
        raw_in_path = Path(_norm(args.raw_in_out))
    else:
        tmp_raw_dir = TemporaryDirectory(prefix="sanction_proc_raw_packets_")
        raw_in_path = Path(tmp_raw_dir.name) / "raw_from_packets.csv"
    _write_csv(raw_in_path, raw_rows)

    packet_input_payload = {
        **packet_input_payload,
        "db_path": str(db_path),
        "packets_dir": str(packets_dir),
        "raw_input_csv": str(raw_in_path),
    }
    _write_json(args.packets_out, packet_input_payload)

    cycle_exit_code = 0
    cycle_payload: dict[str, Any] = {}
    raw_cycle_stdout = ""
    raw_cycle_stderr = ""

    if str(packet_input_payload.get("status")) == "failed":
        cycle_payload = _build_skipped_cycle_payload(
            db_path=db_path,
            status_queue_limit=int(args.status_queue_limit),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
            skip_reason="packet_plan_failed",
        )
        cycle_exit_code = 1
    elif int((packet_input_payload.get("totals") or {}).get("packets_expected_total") or 0) <= 0:
        cycle_payload = _build_skipped_cycle_payload(
            db_path=db_path,
            status_queue_limit=int(args.status_queue_limit),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
            skip_reason="no_actionable_packets",
        )
        cycle_exit_code = 4 if bool(args.strict_actionable) else 0
    elif bool(args.strict_packet_coverage) and (
        int((packet_input_payload.get("totals") or {}).get("packet_files_missing_total") or 0) > 0
        or int((packet_input_payload.get("totals") or {}).get("packet_files_invalid_header_total") or 0) > 0
    ):
        skip_reason = "missing_packet_files"
        if int((packet_input_payload.get("totals") or {}).get("packet_files_invalid_header_total") or 0) > 0:
            skip_reason = "invalid_packet_headers"
        cycle_payload = _build_skipped_cycle_payload(
            db_path=db_path,
            status_queue_limit=int(args.status_queue_limit),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
            skip_reason=skip_reason,
        )
        cycle_exit_code = 4
    elif int((packet_input_payload.get("totals") or {}).get("packet_rows_loaded_total") or 0) <= 0:
        cycle_payload = _build_skipped_cycle_payload(
            db_path=db_path,
            status_queue_limit=int(args.status_queue_limit),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
            skip_reason="no_packet_rows",
        )
        cycle_exit_code = 4 if bool(args.strict_actionable) else 0
    else:
        nested_out_path: Path
        tmp_nested_out: TemporaryDirectory[str] | None = None
        if _norm(args.cycle_out):
            nested_out_path = Path(_norm(args.cycle_out))
            nested_out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            tmp_nested_out = TemporaryDirectory(prefix="sanction_proc_raw_packets_cycle_")
            nested_out_path = Path(tmp_nested_out.name) / "raw_cycle_payload.json"

        cycle_exit_code, cycle_payload, raw_cycle_stdout, raw_cycle_stderr = _run_raw_cycle(
            db_path=db_path,
            raw_input_csv=raw_in_path,
            nested_out=nested_out_path,
            source_id=_norm(args.source_id) or DEFAULT_SOURCE_ID,
            default_period_granularity=_norm(args.period_granularity) or DEFAULT_PERIOD_GRANULARITY,
            snapshot_date=_norm(args.snapshot_date) or today_utc_date(),
            readiness_tolerance=float(args.readiness_tolerance),
            readiness_queue_limit=int(args.readiness_queue_limit),
            status_queue_limit=int(args.status_queue_limit),
            strict_raw=bool(args.strict_raw),
            strict_prepare=bool(args.strict_prepare),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
        )
        if tmp_nested_out is not None:
            tmp_nested_out.cleanup()

    payload = {
        "generated_at": now_utc_iso(),
        "db_path": str(db_path),
        "packets_dir": str(packets_dir),
        "strict_actionable": bool(args.strict_actionable),
        "strict_packet_coverage": bool(args.strict_packet_coverage),
        "strict_raw": bool(args.strict_raw),
        "strict_prepare": bool(args.strict_prepare),
        "strict_readiness": bool(args.strict_readiness),
        "dry_run": bool(args.dry_run),
        "packet_input": packet_input_payload,
        "cycle": cycle_payload,
        "raw_cycle_stdout_excerpt": raw_cycle_stdout[:2000],
        "raw_cycle_stderr_excerpt": raw_cycle_stderr[:2000],
    }
    _write_json(args.out, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if tmp_raw_dir is not None:
        tmp_raw_dir.cleanup()
    return int(cycle_exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
