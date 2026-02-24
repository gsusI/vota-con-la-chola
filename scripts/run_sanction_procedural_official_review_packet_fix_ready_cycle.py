#!/usr/bin/env python3
"""Run packet-fix queue + ready-packets cycle in one command."""

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
from scripts.export_sanction_procedural_official_review_packet_fix_queue import (
    build_packet_fix_queue_report,
)
from scripts.export_sanction_procedural_official_review_raw_template import (
    DEFAULT_PERIOD_GRANULARITY,
    DEFAULT_SOURCE_ID,
)
from scripts.run_sanction_procedural_official_review_apply_cycle import (
    DEFAULT_DB,
    today_utc_date,
)
from scripts.run_sanction_procedural_official_review_raw_packets_cycle import (
    _build_skipped_cycle_payload,
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


def _write_fix_csv(path: str, rows: list[dict[str, Any]]) -> None:
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


def _run_ready_cycle(
    *,
    db_path: Path,
    packets_dir: Path,
    period_date: str,
    period_granularity: str,
    statuses: str,
    queue_limit: int,
    include_ready: bool,
    source_id: str,
    min_ready_packets: int,
    strict_actionable: bool,
    strict_min_ready: bool,
    raw_in_out: Path,
    progress_out: Path,
    nested_out: Path,
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
        "run_sanction_procedural_official_review_ready_packets_cycle.py"
    )
    repo_root = script_path.resolve().parents[1]
    cmd = [
        sys.executable,
        str(script_path),
        "--db",
        str(db_path),
        "--packets-dir",
        str(packets_dir),
        "--period-date",
        _norm(period_date),
        "--period-granularity",
        _norm(period_granularity) or DEFAULT_PERIOD_GRANULARITY,
        "--statuses",
        _norm(statuses) or DEFAULT_STATUSES,
        "--queue-limit",
        str(int(queue_limit)),
        "--source-id",
        _norm(source_id) or DEFAULT_SOURCE_ID,
        "--min-ready-packets",
        str(max(0, int(min_ready_packets))),
        "--raw-in-out",
        str(raw_in_out),
        "--progress-out",
        str(progress_out),
        "--cycle-out",
        str(nested_out),
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
    if bool(include_ready):
        cmd.append("--include-ready")
    if bool(strict_actionable):
        cmd.append("--strict-actionable")
    if bool(strict_min_ready):
        cmd.append("--strict-min-ready")
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
                "error": "ready_cycle_payload_unavailable",
            }
    return int(run.returncode), nested_payload, _norm(run.stdout), _norm(run.stderr)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Run packet-fix queue export + ready-packets cycle for official procedural-review metrics"
    )
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--packets-dir", required=True)
    ap.add_argument("--period-date", required=True)
    ap.add_argument("--period-granularity", default=DEFAULT_PERIOD_GRANULARITY)
    ap.add_argument("--statuses", default=DEFAULT_STATUSES)
    ap.add_argument("--queue-limit", type=int, default=0)
    ap.add_argument("--include-ready", action="store_true")
    ap.add_argument("--source-id", default=DEFAULT_SOURCE_ID)
    ap.add_argument("--strict-fix-empty", action="store_true")
    ap.add_argument("--strict-actionable", action="store_true")
    ap.add_argument("--strict-min-ready", action="store_true")
    ap.add_argument("--min-ready-packets", type=int, default=1)
    ap.add_argument("--fix-csv-out", required=True)
    ap.add_argument("--fix-out", default="")
    ap.add_argument("--raw-in-out", default="")
    ap.add_argument("--progress-out", default="")
    ap.add_argument("--snapshot-date", default=today_utc_date())
    ap.add_argument("--readiness-tolerance", type=float, default=0.01)
    ap.add_argument("--readiness-queue-limit", type=int, default=0)
    ap.add_argument("--status-queue-limit", type=int, default=0)
    ap.add_argument("--strict-raw", action="store_true")
    ap.add_argument("--strict-prepare", action="store_true")
    ap.add_argument("--strict-readiness", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ready-cycle-out", default="", help="Optional nested ready-cycle JSON output")
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
        fix_payload = build_packet_fix_queue_report(
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

    fix_rows = list(fix_payload.pop("queue_rows", []))
    fix_payload = {
        **fix_payload,
        "db_path": str(db_path),
        "packets_dir": str(packets_dir),
    }
    _write_fix_csv(args.fix_csv_out, fix_rows)
    _write_json(args.fix_out, fix_payload)

    cycle_exit_code = 0
    ready_cycle_payload: dict[str, Any] = {}
    ready_cycle_stdout = ""
    ready_cycle_stderr = ""

    if str(fix_payload.get("status")) == "failed":
        ready_cycle_payload = _build_skipped_cycle_payload(
            db_path=db_path,
            status_queue_limit=int(args.status_queue_limit),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
            skip_reason="fix_queue_failed",
        )
        cycle_exit_code = 1
    elif bool(args.strict_fix_empty) and int((fix_payload.get("totals") or {}).get("queue_rows_total") or 0) > 0:
        ready_cycle_payload = _build_skipped_cycle_payload(
            db_path=db_path,
            status_queue_limit=int(args.status_queue_limit),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
            skip_reason="fix_queue_not_empty",
        )
        cycle_exit_code = 4
    else:
        raw_in_path: Path
        tmp_raw_dir: TemporaryDirectory[str] | None = None
        if _norm(args.raw_in_out):
            raw_in_path = Path(_norm(args.raw_in_out))
        else:
            tmp_raw_dir = TemporaryDirectory(prefix="sanction_proc_fix_ready_raw_")
            raw_in_path = Path(tmp_raw_dir.name) / "raw_from_fix_ready_cycle.csv"

        progress_out_path: Path
        tmp_progress_dir: TemporaryDirectory[str] | None = None
        if _norm(args.progress_out):
            progress_out_path = Path(_norm(args.progress_out))
        else:
            tmp_progress_dir = TemporaryDirectory(prefix="sanction_proc_fix_ready_progress_")
            progress_out_path = Path(tmp_progress_dir.name) / "progress.json"

        ready_cycle_out_path: Path
        tmp_ready_cycle_out_dir: TemporaryDirectory[str] | None = None
        if _norm(args.ready_cycle_out):
            ready_cycle_out_path = Path(_norm(args.ready_cycle_out))
            ready_cycle_out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            tmp_ready_cycle_out_dir = TemporaryDirectory(prefix="sanction_proc_fix_ready_cycle_")
            ready_cycle_out_path = Path(tmp_ready_cycle_out_dir.name) / "ready_cycle_payload.json"

        cycle_exit_code, ready_cycle_payload, ready_cycle_stdout, ready_cycle_stderr = _run_ready_cycle(
            db_path=db_path,
            packets_dir=packets_dir,
            period_date=_norm(args.period_date),
            period_granularity=_norm(args.period_granularity) or DEFAULT_PERIOD_GRANULARITY,
            statuses=_norm(args.statuses) or DEFAULT_STATUSES,
            queue_limit=int(args.queue_limit),
            include_ready=bool(args.include_ready),
            source_id=_norm(args.source_id) or DEFAULT_SOURCE_ID,
            min_ready_packets=max(0, int(args.min_ready_packets)),
            strict_actionable=bool(args.strict_actionable),
            strict_min_ready=bool(args.strict_min_ready),
            raw_in_out=raw_in_path,
            progress_out=progress_out_path,
            nested_out=ready_cycle_out_path,
            snapshot_date=_norm(args.snapshot_date) or today_utc_date(),
            readiness_tolerance=float(args.readiness_tolerance),
            readiness_queue_limit=int(args.readiness_queue_limit),
            status_queue_limit=int(args.status_queue_limit),
            strict_raw=bool(args.strict_raw),
            strict_prepare=bool(args.strict_prepare),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
        )

        if tmp_raw_dir is not None:
            tmp_raw_dir.cleanup()
        if tmp_progress_dir is not None:
            tmp_progress_dir.cleanup()
        if tmp_ready_cycle_out_dir is not None:
            tmp_ready_cycle_out_dir.cleanup()

    payload = {
        "generated_at": now_utc_iso(),
        "db_path": str(db_path),
        "packets_dir": str(packets_dir),
        "strict_fix_empty": bool(args.strict_fix_empty),
        "strict_actionable": bool(args.strict_actionable),
        "strict_min_ready": bool(args.strict_min_ready),
        "min_ready_packets": max(0, int(args.min_ready_packets)),
        "strict_raw": bool(args.strict_raw),
        "strict_prepare": bool(args.strict_prepare),
        "strict_readiness": bool(args.strict_readiness),
        "dry_run": bool(args.dry_run),
        "fix_queue": fix_payload,
        "ready_cycle": ready_cycle_payload,
        "ready_cycle_stdout_excerpt": ready_cycle_stdout[:2000],
        "ready_cycle_stderr_excerpt": ready_cycle_stderr[:2000],
    }
    _write_json(args.out, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return int(cycle_exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
