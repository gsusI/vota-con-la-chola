#!/usr/bin/env python3
"""Run raw->prepare->apply cycle using only packet files that are ready."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from etl.parlamentario_es.db import open_db
from scripts.export_sanction_procedural_official_review_raw_template import (
    DEFAULT_PERIOD_GRANULARITY,
    DEFAULT_SOURCE_ID,
    RAW_FIELDNAMES,
)
from scripts.report_sanction_procedural_official_review_raw_packets_progress import (
    build_raw_packets_progress_report,
)
from scripts.run_sanction_procedural_official_review_apply_cycle import (
    DEFAULT_DB,
    today_utc_date,
)
from scripts.run_sanction_procedural_official_review_raw_packets_cycle import (
    _build_skipped_cycle_payload,
    _run_raw_cycle,
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


def _select_ready_rows(progress_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = list(progress_payload.get("packets_rows") or [])
    selected: list[dict[str, Any]] = []
    selected_meta: list[dict[str, Any]] = []
    for row in rows:
        if not bool(row.get("ready_for_transform")):
            continue
        packet_path = Path(_norm(row.get("packet_path")))
        if not packet_path.exists():
            continue
        _, packet_rows = _read_csv(packet_path)
        if len(packet_rows) <= 0:
            continue
        selected.append({key: _norm(packet_rows[0].get(key)) for key in RAW_FIELDNAMES})
        selected_meta.append(
            {
                "sanction_source_id": _norm(row.get("sanction_source_id")),
                "packet_filename": _norm(row.get("packet_filename")),
                "packet_path": str(packet_path),
            }
        )
    return selected, selected_meta


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Run official procedural-review raw cycle using only ready packet files"
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
    ap.add_argument("--strict-min-ready", action="store_true")
    ap.add_argument("--min-ready-packets", type=int, default=1)
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
    ap.add_argument("--cycle-out", default="")
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
        progress_payload = build_raw_packets_progress_report(
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

    progress_rows = list(progress_payload.pop("packets_rows", []))
    progress_payload = {
        **progress_payload,
        "db_path": str(db_path),
        "packets_dir": str(packets_dir),
    }
    _write_json(args.progress_out, progress_payload)

    progress_for_selection = {**progress_payload, "packets_rows": progress_rows}
    raw_rows, selected_packets = _select_ready_rows(progress_for_selection)

    raw_in_path: Path
    tmp_raw_dir: TemporaryDirectory[str] | None = None
    if _norm(args.raw_in_out):
        raw_in_path = Path(_norm(args.raw_in_out))
    else:
        tmp_raw_dir = TemporaryDirectory(prefix="sanction_proc_ready_packets_")
        raw_in_path = Path(tmp_raw_dir.name) / "raw_from_ready_packets.csv"
    _write_csv(raw_in_path, raw_rows)

    expected_total = int((progress_payload.get("totals") or {}).get("packets_expected_total") or 0)
    ready_total = int((progress_payload.get("totals") or {}).get("packets_ready_total") or 0)
    min_ready = max(0, int(args.min_ready_packets))

    cycle_exit_code = 0
    cycle_payload: dict[str, Any] = {}
    raw_cycle_stdout = ""
    raw_cycle_stderr = ""
    skip_reason = ""
    if expected_total <= 0:
        skip_reason = "no_actionable_packets"
        cycle_exit_code = 4 if bool(args.strict_actionable) else 0
    elif ready_total <= 0:
        skip_reason = "no_ready_packets"
        cycle_exit_code = 4 if bool(args.strict_min_ready) else 0
    elif ready_total < min_ready:
        skip_reason = "ready_packets_below_minimum"
        cycle_exit_code = 4 if bool(args.strict_min_ready) else 0

    if skip_reason:
        cycle_payload = _build_skipped_cycle_payload(
            db_path=db_path,
            status_queue_limit=int(args.status_queue_limit),
            strict_readiness=bool(args.strict_readiness),
            dry_run=bool(args.dry_run),
            skip_reason=skip_reason,
        )
    else:
        nested_out_path: Path
        tmp_nested_out: TemporaryDirectory[str] | None = None
        if _norm(args.cycle_out):
            nested_out_path = Path(_norm(args.cycle_out))
            nested_out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            tmp_nested_out = TemporaryDirectory(prefix="sanction_proc_ready_packets_cycle_")
            nested_out_path = Path(tmp_nested_out.name) / "ready_raw_cycle_payload.json"

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
        "raw_input_csv": str(raw_in_path),
        "strict_actionable": bool(args.strict_actionable),
        "strict_min_ready": bool(args.strict_min_ready),
        "min_ready_packets": min_ready,
        "strict_raw": bool(args.strict_raw),
        "strict_prepare": bool(args.strict_prepare),
        "strict_readiness": bool(args.strict_readiness),
        "dry_run": bool(args.dry_run),
        "progress": progress_payload,
        "ready_packets_selected_total": len(selected_packets),
        "ready_packets_selected_preview": selected_packets[:20],
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
