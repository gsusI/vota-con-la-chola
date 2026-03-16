#!/usr/bin/env python3
"""Run Senado manual-capture gate and conditional doc-retry backfill in one cycle."""

from __future__ import annotations

import argparse
import glob
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts import report_senado_manual_capture_target_progress as target_progress
except ModuleNotFoundError:  # pragma: no cover - runtime fallback for direct script execution
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    from scripts import report_senado_manual_capture_target_progress as target_progress


STRICT_FAIL_EXIT = 4
DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_TARGETS_CSV = Path("docs/etl/sprints/AI-OPS-299/exports/senado_manual_capture_targets_latest.csv")
DEFAULT_OUT = Path("docs/etl/sprints/AI-OPS-301/evidence/senado_manual_capture_retry_cycle_latest.json")
DEFAULT_PROGRESS_OUT = Path(
    "docs/etl/sprints/AI-OPS-301/evidence/senado_manual_capture_target_progress_latest.json"
)
DEFAULT_PROGRESS_CSV_OUT = Path(
    "docs/etl/sprints/AI-OPS-301/exports/senado_manual_capture_target_progress_latest.csv"
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


def _resolve_path(token: str) -> Path:
    raw = Path(str(token))
    if raw.is_absolute():
        return raw
    return (Path.cwd() / raw).resolve()


def _display_any_path(token: str) -> str:
    if not _norm(token):
        return ""
    return _display(_resolve_path(token))


def _derive_cookie_path(meta_path_abs: Path, cookie_file_hint: str) -> Path:
    hinted = _norm(cookie_file_hint)
    if hinted:
        hint_path = _resolve_path(hinted)
        if hint_path.exists():
            return hint_path
    base_name = meta_path_abs.name
    if base_name.endswith(".meta.json"):
        prefix = base_name[: -len(".meta.json")]
    else:
        prefix = meta_path_abs.stem
    return meta_path_abs.with_name(f"{prefix}.cookies.json")


def _load_capture_rows(
    *,
    captures_glob: str,
    cookie_domain_contains: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in sorted(glob.glob(captures_glob)):
        meta_path = Path(raw)
        if not meta_path.is_file() or not meta_path.name.endswith(".meta.json"):
            continue
        try:
            parsed = target_progress._capture_row(  # noqa: SLF001
                meta_path, cookie_domain_contains=cookie_domain_contains
            )
        except Exception as exc:  # noqa: BLE001
            out.append(
                {
                    "meta_path_abs": str(meta_path.resolve()),
                    "meta_file": _display(meta_path.resolve()),
                    "cookie_file": "",
                    "cookie_file_exists": False,
                    "usable_capture": False,
                    "ended_at_epoch": 0.0,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        meta_abs = meta_path.resolve()
        cookie_abs = _derive_cookie_path(meta_abs, _norm(parsed.get("cookie_file")))
        row = {
            "meta_path_abs": str(meta_abs),
            "meta_file": _display(meta_abs),
            "cookie_file": _display(cookie_abs),
            "cookie_file_exists": bool(cookie_abs.exists()),
            "usable_capture": bool(parsed.get("usable_capture")),
            "ended_at": _norm(parsed.get("ended_at")),
            "ended_at_epoch": float(parsed.get("ended_at_epoch") or 0.0),
            "final_url": _norm(parsed.get("final_url")),
            "access_denied_detected": bool(parsed.get("access_denied_detected")),
            "cookies_domain_total": int(parsed.get("cookies_domain_total") or 0),
            "error": _norm(parsed.get("error")),
        }
        out.append(row)

    out.sort(
        key=lambda r: (
            float(r.get("ended_at_epoch") or 0.0),
            _norm(r.get("meta_file")),
        ),
        reverse=True,
    )
    return out


def _pick_latest_usable_capture(captures: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in captures:
        if bool(row.get("usable_capture")) and bool(row.get("cookie_file_exists")):
            return row
    return None


def _build_backfill_command(
    *,
    python_bin: str,
    ingestar_script: str,
    db: str,
    initiative_source_ids: str,
    cookie_file: str,
    timeout: int,
    limit_initiatives: int,
    max_docs_per_initiative: int,
    snapshot_date: str,
) -> list[str]:
    cmd = [
        _norm(python_bin) or sys.executable,
        _norm(ingestar_script) or "scripts/ingestar_parlamentario_es.py",
        "backfill-initiative-documents",
        "--db",
        _norm(db),
        "--initiative-source-ids",
        _norm(initiative_source_ids) or "senado_iniciativas",
        "--skip-link-backfill",
        "--retry-forbidden",
        "--cookie-file",
        _norm(cookie_file),
        "--timeout",
        str(max(1, int(timeout))),
        "--limit-initiatives",
        str(max(1, int(limit_initiatives))),
        "--max-docs-per-initiative",
        str(max(1, int(max_docs_per_initiative))),
    ]
    snapshot = _norm(snapshot_date)
    if snapshot:
        cmd.extend(["--snapshot-date", snapshot])
    return cmd


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _command_display(cmd: list[str]) -> str:
    return " ".join(shlex.quote(_norm(part)) for part in cmd if _norm(part))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--targets-csv", default=str(DEFAULT_TARGETS_CSV))
    p.add_argument(
        "--captures-glob",
        default="etl/data/raw/manual/senado*_cookie_refresh_*.meta.json",
        help="Glob pattern for manual capture meta files.",
    )
    p.add_argument("--cookie-domain-contains", default="senado.es")
    p.add_argument("--strict-min-covered-targets", type=int, default=1)
    p.add_argument("--strict-min-usable-targets", type=int, default=1)
    p.add_argument("--initiative-source-ids", default="senado_iniciativas")
    p.add_argument("--limit-initiatives", type=int, default=25)
    p.add_argument("--max-docs-per-initiative", type=int, default=1)
    p.add_argument("--timeout", type=int, default=15)
    p.add_argument("--snapshot-date", default="")
    p.add_argument("--python-bin", default=sys.executable)
    p.add_argument("--ingestar-script", default="scripts/ingestar_parlamentario_es.py")
    p.add_argument("--dry-run-backfill", action="store_true")
    p.add_argument("--strict-ready", action="store_true")
    p.add_argument("--strict-backfill", action="store_true")
    p.add_argument("--progress-out", default=str(DEFAULT_PROGRESS_OUT))
    p.add_argument("--progress-csv-out", default=str(DEFAULT_PROGRESS_CSV_OUT))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(str(args.db))
    if not db_path.exists():
        payload = {
            "generated_at": _now_iso(),
            "status": "failed",
            "error": "db_not_found",
            "db_path": _display(db_path if db_path.is_absolute() else _resolve_path(str(db_path))),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    progress_report, progress_rows = target_progress.build_report(
        targets_csv=Path(str(args.targets_csv)),
        captures_glob=str(args.captures_glob),
        cookie_domain_contains=str(args.cookie_domain_contains),
        strict_min_covered_targets=max(0, int(args.strict_min_covered_targets or 0)),
        strict_min_usable_targets=max(0, int(args.strict_min_usable_targets or 0)),
    )
    progress_status = _norm(progress_report.get("status"))
    progress_checks = progress_report.get("checks") if isinstance(progress_report, dict) else {}
    progress_checks = progress_checks if isinstance(progress_checks, dict) else {}

    progress_out_token = _norm(args.progress_out)
    progress_csv_out_token = _norm(args.progress_csv_out)
    if progress_out_token:
        _write_json(Path(progress_out_token), progress_report)
    if progress_csv_out_token:
        target_progress._write_csv(Path(progress_csv_out_token), progress_rows)  # noqa: SLF001

    captures = _load_capture_rows(
        captures_glob=str(args.captures_glob),
        cookie_domain_contains=str(args.cookie_domain_contains),
    )
    selected_capture = _pick_latest_usable_capture(captures)

    ready_checks = {
        "progress_report_ok": progress_status == "ok",
        "has_targets": bool(progress_checks.get("has_targets")),
        "covered_targets_min_met": bool(progress_checks.get("covered_targets_min_met")),
        "usable_targets_min_met": bool(progress_checks.get("usable_targets_min_met")),
        "selected_usable_capture_with_cookie": selected_capture is not None,
    }
    ready_to_retry = (
        ready_checks["has_targets"]
        and ready_checks["covered_targets_min_met"]
        and ready_checks["usable_targets_min_met"]
        and ready_checks["selected_usable_capture_with_cookie"]
    )

    strict_fail_reasons: list[str] = []
    if not ready_checks["has_targets"]:
        strict_fail_reasons.append("no_targets")
    if not ready_checks["covered_targets_min_met"]:
        strict_fail_reasons.append("covered_targets_below_min")
    if not ready_checks["usable_targets_min_met"]:
        strict_fail_reasons.append("usable_targets_below_min")
    if not ready_checks["selected_usable_capture_with_cookie"]:
        strict_fail_reasons.append("no_usable_capture_cookie_file")

    if progress_status == "failed":
        strict_fail_reasons.append("progress_report_failed")
        raw_progress_error = _norm(progress_report.get("error"))
    else:
        raw_progress_error = ""

    if not ready_to_retry:
        strict_fail_reasons.append("capture_gate_not_ready")

    strict_fail_reasons = list(dict.fromkeys([_norm(r) for r in strict_fail_reasons if _norm(r)]))

    backfill_command: list[str] = []
    backfill_attempted = False
    backfill_exit_code: int | None = None
    backfill_status = "skipped"
    backfill_skip_reason = "capture_gate_not_ready"

    if ready_to_retry and selected_capture is not None:
        backfill_command = _build_backfill_command(
            python_bin=str(args.python_bin),
            ingestar_script=str(args.ingestar_script),
            db=str(args.db),
            initiative_source_ids=str(args.initiative_source_ids),
            cookie_file=_norm(selected_capture.get("cookie_file")),
            timeout=int(args.timeout),
            limit_initiatives=int(args.limit_initiatives),
            max_docs_per_initiative=int(args.max_docs_per_initiative),
            snapshot_date=str(args.snapshot_date),
        )

        if bool(args.dry_run_backfill):
            backfill_status = "dry_run"
            backfill_skip_reason = "dry_run_backfill"
        else:
            run = subprocess.run(
                backfill_command,
                capture_output=True,
                text=True,
                check=False,
                cwd=str(Path.cwd()),
            )
            backfill_attempted = True
            backfill_exit_code = int(run.returncode)
            backfill_skip_reason = ""
            backfill_status = "ok" if run.returncode == 0 else "failed"
            if run.returncode != 0:
                strict_fail_reasons.append("backfill_failed")

    if progress_status == "failed":
        status = "failed"
    elif ready_to_retry and (backfill_status in {"ok", "dry_run"}):
        status = "ok"
    elif ready_to_retry and backfill_status == "failed":
        status = "failed"
    else:
        status = "degraded"

    report = {
        "generated_at": _now_iso(),
        "status": status,
        "db_path": _display_any_path(str(args.db)),
        "targets_csv": _display_any_path(str(args.targets_csv)),
        "captures_glob": str(args.captures_glob),
        "cookie_domain_contains": str(args.cookie_domain_contains),
        "strict_thresholds": {
            "min_covered_targets": max(0, int(args.strict_min_covered_targets or 0)),
            "min_usable_targets": max(0, int(args.strict_min_usable_targets or 0)),
        },
        "progress_report_status": progress_status,
        "progress_report_error": raw_progress_error,
        "progress_report_path": _display_any_path(progress_out_token),
        "progress_csv_path": _display_any_path(progress_csv_out_token),
        "ready_checks": ready_checks,
        "ready_to_retry": ready_to_retry,
        "capture_inventory": {
            "capture_files_total": len(captures),
            "usable_capture_files_total": sum(1 for row in captures if bool(row.get("usable_capture"))),
            "usable_with_cookie_files_total": sum(
                1
                for row in captures
                if bool(row.get("usable_capture")) and bool(row.get("cookie_file_exists"))
            ),
            "usable_missing_cookie_files_total": sum(
                1
                for row in captures
                if bool(row.get("usable_capture")) and not bool(row.get("cookie_file_exists"))
            ),
        },
        "selected_capture": (
            {
                "meta_file": _norm(selected_capture.get("meta_file")),
                "cookie_file": _norm(selected_capture.get("cookie_file")),
                "ended_at": _norm(selected_capture.get("ended_at")),
                "final_url": _norm(selected_capture.get("final_url")),
                "cookies_domain_total": int(selected_capture.get("cookies_domain_total") or 0),
                "access_denied_detected": bool(selected_capture.get("access_denied_detected")),
            }
            if selected_capture is not None
            else {}
        ),
        "backfill": {
            "attempted": backfill_attempted,
            "dry_run": bool(args.dry_run_backfill),
            "status": backfill_status,
            "skip_reason": backfill_skip_reason,
            "exit_code": backfill_exit_code,
            "command_display": _command_display(backfill_command),
            "initiative_source_ids": str(args.initiative_source_ids),
            "limit_initiatives": max(1, int(args.limit_initiatives)),
            "max_docs_per_initiative": max(1, int(args.max_docs_per_initiative)),
            "timeout": max(1, int(args.timeout)),
            "snapshot_date": _norm(args.snapshot_date),
        },
        "strict_fail_reasons": strict_fail_reasons,
    }

    out_path = Path(str(args.out))
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if bool(args.strict_ready) and not ready_to_retry:
        return STRICT_FAIL_EXIT
    if bool(args.strict_backfill):
        if not backfill_attempted:
            return STRICT_FAIL_EXIT
        if backfill_exit_code is None or backfill_exit_code != 0:
            return STRICT_FAIL_EXIT
    if status == "failed":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
