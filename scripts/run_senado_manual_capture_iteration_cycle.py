#!/usr/bin/env python3
"""Run one Senado manual-capture iteration: retry-cycle + pending-queue + delta."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts import export_senado_manual_capture_pending_targets as pending_targets
    from scripts import run_senado_manual_capture_retry_cycle as retry_cycle
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for direct script execution
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    from scripts import export_senado_manual_capture_pending_targets as pending_targets
    from scripts import run_senado_manual_capture_retry_cycle as retry_cycle


STRICT_FAIL_EXIT = 4
DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_OUT = Path("docs/etl/sprints/AI-OPS-303/evidence/senado_manual_capture_iteration_cycle_latest.json")
DEFAULT_RETRY_OUT = Path("docs/etl/sprints/AI-OPS-303/evidence/senado_manual_capture_retry_cycle_latest.json")
DEFAULT_PROGRESS_OUT = Path(
    "docs/etl/sprints/AI-OPS-303/evidence/senado_manual_capture_target_progress_latest.json"
)
DEFAULT_PROGRESS_CSV_OUT = Path(
    "docs/etl/sprints/AI-OPS-303/exports/senado_manual_capture_target_progress_latest.csv"
)
DEFAULT_PENDING_OUT = Path("docs/etl/sprints/AI-OPS-303/evidence/senado_manual_capture_pending_targets_latest.json")
DEFAULT_PENDING_CSV_OUT = Path("docs/etl/sprints/AI-OPS-303/exports/senado_manual_capture_pending_targets_latest.csv")
DEFAULT_PENDING_COMMANDS_OUT = Path(
    "docs/etl/sprints/AI-OPS-303/exports/senado_manual_capture_pending_targets_commands_latest.sh"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _display(path: Path) -> str:
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.name


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return int(default)
        if isinstance(value, bool):
            return int(value)
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data
    return {}


def _safe_report(path: Path, fallback_error: str) -> dict[str, Any]:
    if path.exists():
        try:
            payload = _load_json(path)
            if isinstance(payload, dict) and payload:
                return payload
        except Exception:  # noqa: BLE001
            pass
    return {
        "generated_at": _now_iso(),
        "status": "failed",
        "error": fallback_error,
    }


def _pending_total(report: dict[str, Any]) -> int:
    totals = report.get("totals")
    if not isinstance(totals, dict):
        return 0
    return _to_int(totals.get("pending_targets_total"), 0)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument(
        "--targets-csv",
        default="docs/etl/sprints/AI-OPS-299/exports/senado_manual_capture_targets_latest.csv",
    )
    p.add_argument("--captures-glob", default="etl/data/raw/manual/senado*_cookie_refresh_*.meta.json")
    p.add_argument("--cookie-domain-contains", default="senado.es")
    p.add_argument("--strict-min-covered-targets", type=int, default=1)
    p.add_argument("--strict-min-usable-targets", type=int, default=1)
    p.add_argument("--initiative-source-ids", default="senado_iniciativas")
    p.add_argument("--limit-initiatives", type=int, default=25)
    p.add_argument("--max-docs-per-initiative", type=int, default=1)
    p.add_argument("--timeout", type=int, default=15)
    p.add_argument("--snapshot-date", default="")
    p.add_argument("--python-bin", default="")
    p.add_argument("--ingestar-script", default="scripts/ingestar_parlamentario_es.py")
    p.add_argument("--retry-dry-run-backfill", action="store_true")

    p.add_argument("--pending-include-unmatched", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument(
        "--pending-include-matched-not-usable", action=argparse.BooleanOptionalAction, default=True
    )
    p.add_argument("--pending-max-targets", type=int, default=0)
    p.add_argument("--pending-wait-seconds", type=int, default=120)

    p.add_argument("--retry-out", default=str(DEFAULT_RETRY_OUT))
    p.add_argument("--progress-out", default=str(DEFAULT_PROGRESS_OUT))
    p.add_argument("--progress-csv-out", default=str(DEFAULT_PROGRESS_CSV_OUT))
    p.add_argument("--pending-out", default=str(DEFAULT_PENDING_OUT))
    p.add_argument("--pending-csv-out", default=str(DEFAULT_PENDING_CSV_OUT))
    p.add_argument("--pending-commands-out", default=str(DEFAULT_PENDING_COMMANDS_OUT))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--strict", action="store_true")
    p.add_argument("--strict-min-pending-reduction", type=int, default=0)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(str(args.db))
    if not db_path.exists():
        payload = {
            "generated_at": _now_iso(),
            "status": "failed",
            "error": "db_not_found",
            "db_path": _display(db_path),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    retry_out_path = Path(str(args.retry_out))
    progress_out_path = Path(str(args.progress_out))
    progress_csv_out_path = Path(str(args.progress_csv_out))
    pending_out_path = Path(str(args.pending_out))
    pending_csv_out_path = Path(str(args.pending_csv_out))
    pending_commands_out_path = Path(str(args.pending_commands_out))

    previous_pending_report = _safe_report(pending_out_path, "previous_pending_report_unavailable")
    previous_pending_total = _pending_total(previous_pending_report)
    has_previous_pending = pending_out_path.exists()

    retry_argv = [
        "--db",
        str(args.db),
        "--targets-csv",
        str(args.targets_csv),
        "--captures-glob",
        str(args.captures_glob),
        "--cookie-domain-contains",
        str(args.cookie_domain_contains),
        "--strict-min-covered-targets",
        str(max(0, int(args.strict_min_covered_targets or 0))),
        "--strict-min-usable-targets",
        str(max(0, int(args.strict_min_usable_targets or 0))),
        "--initiative-source-ids",
        str(args.initiative_source_ids),
        "--limit-initiatives",
        str(max(1, int(args.limit_initiatives or 1))),
        "--max-docs-per-initiative",
        str(max(1, int(args.max_docs_per_initiative or 1))),
        "--timeout",
        str(max(1, int(args.timeout or 1))),
        "--ingestar-script",
        str(args.ingestar_script),
        "--out",
        str(retry_out_path),
        "--progress-out",
        str(progress_out_path),
        "--progress-csv-out",
        str(progress_csv_out_path),
    ]
    if _norm(args.snapshot_date):
        retry_argv.extend(["--snapshot-date", str(args.snapshot_date)])
    if _norm(args.python_bin):
        retry_argv.extend(["--python-bin", str(args.python_bin)])
    if bool(args.retry_dry_run_backfill):
        retry_argv.append("--dry-run-backfill")
    retry_rc = retry_cycle.main(retry_argv)
    retry_report = _safe_report(retry_out_path, "retry_report_unavailable")

    pending_argv = [
        "--progress-json",
        str(progress_out_path),
        "--progress-csv",
        str(progress_csv_out_path),
        "--max-targets",
        str(max(0, int(args.pending_max_targets or 0))),
        "--wait-seconds",
        str(max(1, int(args.pending_wait_seconds or 120))),
        "--out",
        str(pending_out_path),
        "--csv-out",
        str(pending_csv_out_path),
        "--commands-out",
        str(pending_commands_out_path),
    ]
    if not bool(args.pending_include_unmatched):
        pending_argv.append("--no-include-unmatched")
    if not bool(args.pending_include_matched_not_usable):
        pending_argv.append("--no-include-matched-not-usable")
    pending_rc = pending_targets.main(pending_argv)
    pending_report = _safe_report(pending_out_path, "pending_report_unavailable")

    current_pending_total = _pending_total(pending_report)
    pending_reduction_total = (
        int(previous_pending_total - current_pending_total) if has_previous_pending else None
    )

    retry_status = _norm(retry_report.get("status"))
    pending_status = _norm(pending_report.get("status"))
    retry_backfill = retry_report.get("backfill") if isinstance(retry_report, dict) else {}
    retry_backfill = retry_backfill if isinstance(retry_backfill, dict) else {}
    backfill_status = _norm(retry_backfill.get("status"))
    backfill_attempted = bool(retry_backfill.get("attempted"))

    checks = {
        "retry_report_ok": retry_status == "ok",
        "pending_report_ok": pending_status in {"ok", "degraded"},
        "pending_queue_empty": current_pending_total == 0,
        "has_previous_pending_snapshot": bool(has_previous_pending),
        "backfill_attempted": bool(backfill_attempted),
        "backfill_ok": backfill_status in {"ok", "dry_run"},
    }

    strict_fail_reasons: list[str] = []
    if retry_status == "failed":
        strict_fail_reasons.append("retry_report_failed")
    if pending_status == "failed":
        strict_fail_reasons.append("pending_report_failed")
    if current_pending_total > 0:
        strict_fail_reasons.append("pending_targets_remaining")
    if not checks["backfill_ok"]:
        strict_fail_reasons.append("backfill_not_ok")

    min_reduction = max(0, int(args.strict_min_pending_reduction or 0))
    if min_reduction > 0:
        if pending_reduction_total is None:
            strict_fail_reasons.append("no_previous_pending_snapshot")
        elif int(pending_reduction_total) < min_reduction:
            strict_fail_reasons.append("pending_reduction_below_min")

    strict_fail_reasons = list(dict.fromkeys([r for r in strict_fail_reasons if r]))

    if retry_status == "failed" or pending_status == "failed":
        status = "failed"
    elif current_pending_total <= 0 and checks["backfill_ok"]:
        status = "ok"
    else:
        status = "degraded"

    combined = {
        "generated_at": _now_iso(),
        "status": status,
        "db_path": _display(db_path),
        "inputs": {
            "targets_csv": _norm(args.targets_csv),
            "captures_glob": _norm(args.captures_glob),
            "pending_max_targets": max(0, int(args.pending_max_targets or 0)),
            "pending_wait_seconds": max(1, int(args.pending_wait_seconds or 120)),
            "strict_min_pending_reduction": min_reduction,
        },
        "totals": {
            "previous_pending_total": previous_pending_total if has_previous_pending else None,
            "current_pending_total": int(current_pending_total),
            "pending_reduction_total": pending_reduction_total,
            "retry_rc": int(retry_rc),
            "pending_rc": int(pending_rc),
        },
        "checks": checks,
        "strict_fail_reasons": strict_fail_reasons,
        "artifacts": {
            "retry_out": _display(retry_out_path),
            "progress_out": _display(progress_out_path),
            "progress_csv_out": _display(progress_csv_out_path),
            "pending_out": _display(pending_out_path),
            "pending_csv_out": _display(pending_csv_out_path),
            "pending_commands_out": _display(pending_commands_out_path),
        },
        "retry_report": retry_report,
        "pending_report": pending_report,
    }

    out_path = Path(str(args.out))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(combined, ensure_ascii=False, indent=2))

    if bool(args.strict) and status != "ok":
        return STRICT_FAIL_EXIT
    if status == "failed":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
