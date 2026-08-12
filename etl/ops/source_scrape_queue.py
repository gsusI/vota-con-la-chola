"""Execute the public source scrape queue against a target SQLite DB."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from publicdata_ops.queue import MANUAL_STATES, REPEATABLE_NOW_STATES
from publicdata_ops.queue import normalize_command as _normalize_command
from publicdata_ops.queue import pre_commands as _pre_commands
from publicdata_ops.queue import prerequisite_source_ids as _prerequisite_source_ids
from publicdata_ops.queue import render_command as _render_command
from publicdata_ops.queue import sort_items_by_dependencies as _sort_items_by_dependencies


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute source scrape queue items reproducibly")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Target SQLite DB")
    parser.add_argument("--queue", default="", help="Existing queue JSON (optional)")
    parser.add_argument("--snapshot-date", default="", help="Optional YYYY-MM-DD override for ingest commands")
    parser.add_argument(
        "--mode",
        choices=("preferred", "network", "sample"),
        default="preferred",
        help="Which command variant to execute per item",
    )
    parser.add_argument(
        "--only-repeatable-now",
        action="store_true",
        help="Run only states that are already repeatable now",
    )
    parser.add_argument(
        "--fallback-on-failure",
        choices=("none",),
        default="none",
        help="Fail closed; synthetic or sample fallback is forbidden",
    )
    parser.add_argument("--include-logs", action="store_true", help="Include raw stdout/stderr in summary JSON")
    parser.add_argument("--command-timeout-seconds", type=int, default=90, help="Per-source subprocess timeout in seconds")
    parser.add_argument("--allow-failures", action="store_true", help="Exit 0 even if some items fail")
    parser.add_argument("--summary-out", default="", help="Optional JSON summary path")
    parser.add_argument("--dry-run", action="store_true", help="Do not execute commands")
    return parser.parse_args(argv)


def _load_queue(queue_path: str, db_path: Path, snapshot_date: str) -> dict[str, Any]:
    if str(queue_path or "").strip():
        return json.loads(Path(queue_path).read_text(encoding="utf-8"))
    from scripts import graph_ui_server as g  # noqa: WPS433

    return g.build_source_scrape_queue_payload(db_path, snapshot_date=snapshot_date)


def _latest_ingestion_run_id(db_path: Path, source_id: str) -> int:
    if not source_id or not db_path.exists():
        return 0
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT COALESCE(MAX(run_id), 0) FROM ingestion_runs WHERE source_id = ?",
            (source_id,),
        ).fetchone()
    except sqlite3.Error:
        return 0
    finally:
        conn.close()
    return int(row[0] or 0) if row else 0


def _validate_ingest_run(
    *,
    db_path: Path,
    source_id: str,
    strict_target: int,
    min_run_id_exclusive: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": True,
        "reason": "",
        "run_id": 0,
        "status": "",
        "records_loaded": 0,
    }
    if not source_id or int(strict_target or 0) <= 0:
        return result
    if not db_path.exists():
        result["ok"] = False
        result["reason"] = "db_missing"
        return result

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT run_id, status, records_loaded
            FROM ingestion_runs
            WHERE source_id = ?
              AND run_id > ?
            ORDER BY run_id DESC
            LIMIT 1
            """,
            (source_id, int(min_run_id_exclusive or 0)),
        ).fetchone()
    except sqlite3.Error as exc:
        result["ok"] = False
        result["reason"] = f"sqlite_error:{type(exc).__name__}"
        return result
    finally:
        conn.close()

    if row is None:
        result["ok"] = False
        result["reason"] = "missing_ingestion_run"
        return result

    result["run_id"] = int(row["run_id"] or 0)
    result["status"] = str(row["status"] or "")
    result["records_loaded"] = int(row["records_loaded"] or 0)
    if result["status"] != "ok":
        result["ok"] = False
        result["reason"] = "run_status_not_ok"
        return result
    if result["records_loaded"] < int(strict_target):
        result["ok"] = False
        result["reason"] = "records_loaded_below_target"
    return result


def _run_command(tokens: list[str], *, include_logs: bool, command_timeout_seconds: int) -> dict[str, Any]:
    result: dict[str, Any] = {}
    try:
        proc = subprocess.run(
            tokens,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=max(1, int(command_timeout_seconds or 0)),
        )
        result["exit_code"] = int(proc.returncode)
        if include_logs:
            result["stdout"] = proc.stdout
            result["stderr"] = proc.stderr
    except subprocess.TimeoutExpired as exc:
        result["exit_code"] = 124
        result["timed_out"] = True
        if include_logs:
            result["stdout"] = exc.stdout or ""
            result["stderr"] = exc.stderr or ""
    return result


def select_command(item: dict[str, Any], *, mode: str) -> tuple[str, str]:
    execution = item.get("execution") if isinstance(item.get("execution"), dict) else {}
    preferred_mode = str(execution.get("preferred_mode") or "").strip()
    network_command = str(execution.get("network_command") or "").strip()
    sample_command = str(execution.get("sample_command") or "").strip()

    if mode == "network":
        return network_command, "network"
    if mode == "sample":
        return sample_command, "sample"
    if preferred_mode == "from-file" and sample_command:
        return sample_command, "sample"
    if network_command:
        return network_command, "network"
    return sample_command, "sample"


def should_run_item(item: dict[str, Any], *, only_repeatable_now: bool) -> bool:
    if not only_repeatable_now:
        return True
    execution = item.get("execution") if isinstance(item.get("execution"), dict) else {}
    state = str(execution.get("repeatability_state") or "").strip()
    return state in REPEATABLE_NOW_STATES


def execute_item(
    *,
    item: dict[str, Any],
    db_path: Path,
    snapshot_date: str = "",
    mode: str = "preferred",
    only_repeatable_now: bool = False,
    fallback_on_failure: str = "none",
    include_logs: bool = False,
    command_timeout_seconds: int = 90,
    dry_run: bool = False,
) -> dict[str, Any]:
    source_id = str(item.get("source_id") or "").strip()
    execution = item.get("execution") if isinstance(item.get("execution"), dict) else {}
    state = str(execution.get("repeatability_state") or "").strip()
    if not should_run_item(item, only_repeatable_now=only_repeatable_now):
        return {
            "source_id": source_id,
            "status": "skipped",
            "reason": "not_repeatable_now" if state in MANUAL_STATES else "filtered_out",
            "repeatability_state": state,
        }

    command, chosen_mode = select_command(item, mode=mode)
    if not command:
        return {
            "source_id": source_id,
            "status": "skipped",
            "reason": "no_command_available",
            "repeatability_state": state,
        }

    tokens = _normalize_command(command, db_path=db_path, snapshot_date=snapshot_date)
    result_row: dict[str, Any] = {
        "source_id": source_id,
        "rank": int(item.get("rank") or 0),
        "repeatability_state": state,
        "chosen_mode": chosen_mode,
        "command": tokens,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    pre_commands = _pre_commands(item)
    if pre_commands:
        result_row["pre_commands"] = [
            _normalize_command(command, db_path=db_path, snapshot_date=snapshot_date) for command in pre_commands
        ]

    if dry_run:
        result_row["status"] = "dry_run"
        return result_row

    if pre_commands:
        pre_results: list[dict[str, Any]] = []
        pre_failed = False
        for command in pre_commands:
            pre_tokens = _normalize_command(command, db_path=db_path, snapshot_date=snapshot_date)
            pre_row = {"command": pre_tokens}
            pre_row.update(
                _run_command(
                    pre_tokens,
                    include_logs=include_logs,
                    command_timeout_seconds=command_timeout_seconds,
                )
            )
            pre_results.append(pre_row)
            if int(pre_row.get("exit_code") or 0) != 0:
                pre_failed = True
                break
        result_row["pre_command_results"] = pre_results
        if pre_failed:
            result_row["status"] = "failed"
            result_row["failure_reason"] = "pre_command_failed"
            result_row["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            return result_row

    before_run_id = _latest_ingestion_run_id(db_path, source_id)
    result_row.update(
        _run_command(
            tokens,
            include_logs=include_logs,
            command_timeout_seconds=command_timeout_seconds,
        )
    )
    strict_target = int(execution.get("strict_target") or 0)
    validation = _validate_ingest_run(
        db_path=db_path,
        source_id=source_id,
        strict_target=strict_target,
        min_run_id_exclusive=before_run_id,
    )
    result_row["validation"] = validation
    result_row["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if result_row["exit_code"] == 0 and bool(validation.get("ok")):
        result_row["status"] = "ok"
        return result_row

    if fallback_on_failure != "none":
        raise ValueError("real-data-only policy requires fallback_on_failure='none'")

    result_row["status"] = "failed"
    if not bool(validation.get("ok")) and not str(result_row.get("failure_reason") or "").strip():
        result_row["failure_reason"] = str(validation.get("reason") or "validation_failed")
    return result_row


def _totals_from_results(results: list[dict[str, Any]]) -> dict[str, int]:
    totals = {"selected_total": 0, "ok_total": 0, "failed_total": 0, "skipped_total": 0, "fallback_total": 0}
    for row in results:
        status = str(row.get("status") or "")
        if status == "skipped":
            totals["skipped_total"] += 1
            continue
        totals["selected_total"] += 1
        if status in {"ok", "ok_with_fallback", "dry_run"}:
            totals["ok_total"] += 1
        elif status == "failed":
            totals["failed_total"] += 1
        if status == "ok_with_fallback":
            totals["fallback_total"] += 1
    return totals


def execute_queue(
    *,
    db_path: Path,
    queue_payload: dict[str, Any],
    snapshot_date: str = "",
    mode: str = "preferred",
    only_repeatable_now: bool = False,
    fallback_on_failure: str = "none",
    include_logs: bool = False,
    command_timeout_seconds: int = 90,
    dry_run: bool = False,
) -> dict[str, Any]:
    items = queue_payload.get("items") if isinstance(queue_payload.get("items"), list) else []
    ordered_items = _sort_items_by_dependencies([item for item in items if isinstance(item, dict)])
    results = [
        execute_item(
            item=item,
            db_path=db_path,
            snapshot_date=snapshot_date,
            mode=mode,
            only_repeatable_now=only_repeatable_now,
            fallback_on_failure=fallback_on_failure,
            include_logs=include_logs,
            command_timeout_seconds=command_timeout_seconds,
            dry_run=dry_run,
        )
        for item in ordered_items
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "snapshot_date": snapshot_date,
        "mode": mode,
        "only_repeatable_now": only_repeatable_now,
        "fallback_on_failure": fallback_on_failure,
        "queue_summary": dict(queue_payload.get("summary") or {}),
        "totals": _totals_from_results(results),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    queue_payload = _load_queue(str(args.queue or "").strip(), db_path, str(args.snapshot_date or "").strip())
    summary = execute_queue(
        db_path=db_path,
        queue_payload=queue_payload,
        snapshot_date=str(args.snapshot_date or "").strip(),
        mode=str(args.mode or "preferred"),
        only_repeatable_now=bool(args.only_repeatable_now),
        fallback_on_failure=str(args.fallback_on_failure or "none"),
        include_logs=bool(args.include_logs),
        command_timeout_seconds=int(args.command_timeout_seconds or 90),
        dry_run=bool(args.dry_run),
    )
    if str(args.summary_out or "").strip():
        out_path = Path(args.summary_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "db_path": summary.get("db_path"),
                "totals": summary.get("totals"),
            },
            ensure_ascii=True,
        )
    )
    failed_total = int(((summary.get("totals") or {}).get("failed_total")) or 0)
    if failed_total and not args.allow_failures:
        return 1
    return 0
