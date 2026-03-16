#!/usr/bin/env python3
"""Export pending manual-capture targets from Senado target-progress artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STRICT_FAIL_EXIT = 4
DEFAULT_PROGRESS_JSON = Path("docs/etl/sprints/AI-OPS-301/evidence/senado_manual_capture_target_progress_latest.json")
DEFAULT_PROGRESS_CSV = Path("docs/etl/sprints/AI-OPS-301/exports/senado_manual_capture_target_progress_latest.csv")
DEFAULT_OUT = Path("docs/etl/sprints/AI-OPS-302/evidence/senado_manual_capture_pending_targets_latest.json")
DEFAULT_CSV_OUT = Path("docs/etl/sprints/AI-OPS-302/exports/senado_manual_capture_pending_targets_latest.csv")
DEFAULT_COMMANDS_OUT = Path(
    "docs/etl/sprints/AI-OPS-302/exports/senado_manual_capture_pending_targets_commands_latest.sh"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    token = str(value or "").strip().lower()
    if token in {"1", "true", "yes", "y"}:
        return True
    if token in {"0", "false", "no", "n", ""}:
        return False
    return _to_int(value, 0) > 0


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data
    return {}


def _load_progress_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not isinstance(row, dict):
                continue
            capture_url = str(row.get("capture_url") or "").strip()
            if not capture_url:
                continue
            rows.append(
                {
                    "target_rank": _to_int(row.get("target_rank"), 0),
                    "target_id": str(row.get("target_id") or ""),
                    "target_kind": str(row.get("target_kind") or ""),
                    "cohort": str(row.get("cohort") or ""),
                    "initiative_id": str(row.get("initiative_id") or ""),
                    "capture_url": capture_url,
                    "reason": str(row.get("reason") or ""),
                    "suggested_label": str(row.get("suggested_label") or ""),
                    "suggested_command": str(row.get("suggested_command") or ""),
                    "matched": _to_bool(row.get("matched")),
                    "match_strategy": str(row.get("match_strategy") or ""),
                    "matched_meta_file": str(row.get("matched_meta_file") or ""),
                    "matched_final_url": str(row.get("matched_final_url") or ""),
                    "matched_ended_at": str(row.get("matched_ended_at") or ""),
                    "matched_access_denied": _to_int(row.get("matched_access_denied"), 0),
                    "matched_cookies_domain_total": _to_int(row.get("matched_cookies_domain_total"), 0),
                    "matched_usable_capture": _to_int(row.get("matched_usable_capture"), 0),
                }
            )
    rows.sort(key=lambda r: (int(r.get("target_rank") or 0), str(r.get("target_id") or "")))
    return rows


def _pending_reason(row: dict[str, Any]) -> str:
    matched = bool(row.get("matched"))
    if not matched:
        return "unmatched_target"
    if _to_int(row.get("matched_usable_capture"), 0) > 0:
        return ""
    if _to_int(row.get("matched_access_denied"), 0) > 0:
        return "matched_access_denied"
    if _to_int(row.get("matched_cookies_domain_total"), 0) <= 0:
        return "matched_without_domain_cookie"
    return "matched_not_usable"


def _pending_priority(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    reason = str(row.get("pending_reason") or "")
    reason_rank = {
        "unmatched_target": 0,
        "matched_access_denied": 1,
        "matched_without_domain_cookie": 2,
        "matched_not_usable": 3,
    }.get(reason, 9)
    is_zero_doc = 1 if "zero_doc" in str(row.get("reason") or "").lower() else 0
    return (
        reason_rank,
        -is_zero_doc,
        _to_int(row.get("target_rank"), 0),
        -_to_int(row.get("matched_access_denied"), 0),
        str(row.get("target_id") or ""),
    )


def _build_suggested_command(capture_url: str, label: str, wait_seconds: int) -> str:
    q_url = shlex.quote(str(capture_url or "").strip())
    q_label = shlex.quote(str(label or "").strip())
    return (
        "python3 scripts/manual_capture_playwright.py "
        f"--url {q_url} --label {q_label} "
        "--out-dir etl/data/raw/manual "
        f"--wait-seconds {max(1, int(wait_seconds))} --channel \"\""
    )


def _filter_pending_rows(
    *,
    rows: list[dict[str, Any]],
    include_unmatched: bool,
    include_matched_not_usable: bool,
    max_targets: int,
) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    for row in rows:
        reason = _pending_reason(row)
        if not reason:
            continue
        matched = bool(row.get("matched"))
        if (not matched) and (not include_unmatched):
            continue
        if matched and (not include_matched_not_usable):
            continue
        out = dict(row)
        out["pending_reason"] = reason
        pending.append(out)
    pending.sort(key=_pending_priority)
    cap = int(max_targets or 0)
    if cap > 0:
        return pending[:cap]
    return pending


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "pending_rank",
        "pending_reason",
        "target_rank",
        "target_id",
        "target_kind",
        "cohort",
        "initiative_id",
        "capture_url",
        "reason",
        "suggested_label",
        "suggested_command",
        "matched",
        "match_strategy",
        "matched_meta_file",
        "matched_final_url",
        "matched_ended_at",
        "matched_access_denied",
        "matched_cookies_domain_total",
        "matched_usable_capture",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for idx, row in enumerate(rows, start=1):
            out = dict(row)
            out["pending_rank"] = idx
            writer.writerow({k: out.get(k, "") for k in fieldnames})


def _write_commands(path: Path, rows: list[dict[str, Any]], *, wait_seconds: int) -> tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    commands: list[str] = []
    seen: set[str] = set()
    fallback_total = 0
    for row in rows:
        cmd = str(row.get("suggested_command") or "").strip()
        if not cmd:
            capture_url = str(row.get("capture_url") or "").strip()
            if not capture_url:
                continue
            label = str(row.get("suggested_label") or "").strip() or str(row.get("target_id") or "senado_pending")
            cmd = _build_suggested_command(capture_url, label, wait_seconds)
            fallback_total += 1
        if not cmd or cmd in seen:
            continue
        seen.add(cmd)
        commands.append(cmd)
    payload = "#!/usr/bin/env bash\nset -euo pipefail\n\n" + "\n".join(commands) + ("\n" if commands else "")
    path.write_text(payload, encoding="utf-8")
    path.chmod(0o755)
    return len(commands), fallback_total


def build_report(
    *,
    progress_json_path: Path,
    progress_csv_path: Path,
    include_unmatched: bool,
    include_matched_not_usable: bool,
    max_targets: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not progress_json_path.exists():
        return (
            {
                "generated_at": _now_iso(),
                "status": "failed",
                "error": "progress_json_not_found",
                "progress_json": _display(progress_json_path),
            },
            [],
        )
    if not progress_csv_path.exists():
        return (
            {
                "generated_at": _now_iso(),
                "status": "failed",
                "error": "progress_csv_not_found",
                "progress_csv": _display(progress_csv_path),
            },
            [],
        )

    progress = _load_json(progress_json_path)
    rows = _load_progress_rows(progress_csv_path)
    pending = _filter_pending_rows(
        rows=rows,
        include_unmatched=bool(include_unmatched),
        include_matched_not_usable=bool(include_matched_not_usable),
        max_targets=max(0, int(max_targets or 0)),
    )

    pending_reasons: dict[str, int] = {}
    for row in pending:
        reason = str(row.get("pending_reason") or "")
        if not reason:
            continue
        pending_reasons[reason] = pending_reasons.get(reason, 0) + 1

    checks = {
        "has_targets": len(rows) > 0,
        "pending_queue_empty": len(pending) == 0,
    }
    strict_fail_reasons: list[str] = []
    if not checks["has_targets"]:
        strict_fail_reasons.append("no_targets")
    if not checks["pending_queue_empty"]:
        strict_fail_reasons.append("pending_targets_remaining")

    status = "ok" if all(checks.values()) else "degraded"
    report = {
        "generated_at": _now_iso(),
        "status": status,
        "progress_json": _display(progress_json_path),
        "progress_csv": _display(progress_csv_path),
        "progress_status": str(progress.get("status") or ""),
        "inputs": {
            "include_unmatched": bool(include_unmatched),
            "include_matched_not_usable": bool(include_matched_not_usable),
            "max_targets": max(0, int(max_targets or 0)),
        },
        "totals": {
            "targets_total": len(rows),
            "pending_targets_total": len(pending),
            "pending_unmatched_total": sum(1 for r in pending if str(r.get("pending_reason")) == "unmatched_target"),
            "pending_matched_not_usable_total": sum(
                1 for r in pending if str(r.get("pending_reason")) != "unmatched_target"
            ),
            "pending_access_denied_total": sum(
                1 for r in pending if str(r.get("pending_reason")) == "matched_access_denied"
            ),
            "pending_missing_domain_cookie_total": sum(
                1 for r in pending if str(r.get("pending_reason")) == "matched_without_domain_cookie"
            ),
            "pending_cohorts_total": len({str(r.get("cohort") or "") for r in pending if str(r.get("cohort") or "")}),
        },
        "pending_reasons": pending_reasons,
        "checks": checks,
        "strict_fail_reasons": strict_fail_reasons,
        "sample_pending_targets": [
            {
                "target_rank": r.get("target_rank"),
                "target_id": r.get("target_id"),
                "cohort": r.get("cohort"),
                "capture_url": r.get("capture_url"),
                "pending_reason": r.get("pending_reason"),
            }
            for r in pending[:20]
        ],
    }
    return report, pending


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--progress-json", default=str(DEFAULT_PROGRESS_JSON))
    p.add_argument("--progress-csv", default=str(DEFAULT_PROGRESS_CSV))
    p.add_argument(
        "--include-unmatched",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keep unmatched targets in pending queue (default true).",
    )
    p.add_argument(
        "--include-matched-not-usable",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Keep matched but non-usable targets in pending queue (default true).",
    )
    p.add_argument(
        "--max-targets",
        type=int,
        default=0,
        help="Maximum pending targets to emit (0 = all).",
    )
    p.add_argument("--wait-seconds", type=int, default=120)
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--csv-out", default=str(DEFAULT_CSV_OUT))
    p.add_argument("--commands-out", default=str(DEFAULT_COMMANDS_OUT))
    p.add_argument("--strict", action="store_true", help="Exit 4 unless status=ok.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    progress_json_path = Path(str(args.progress_json))
    progress_csv_path = Path(str(args.progress_csv))
    out_path = Path(str(args.out))
    csv_out_path = Path(str(args.csv_out))
    commands_out_path = Path(str(args.commands_out))

    report, pending_rows = build_report(
        progress_json_path=progress_json_path,
        progress_csv_path=progress_csv_path,
        include_unmatched=bool(args.include_unmatched),
        include_matched_not_usable=bool(args.include_matched_not_usable),
        max_targets=max(0, int(args.max_targets or 0)),
    )
    commands_total, fallback_commands_total = _write_commands(
        commands_out_path, pending_rows, wait_seconds=max(1, int(args.wait_seconds or 120))
    )
    report["commands_out"] = _display(commands_out_path)
    totals = report.get("totals")
    if isinstance(totals, dict):
        totals["pending_commands_total"] = int(commands_total)
        totals["pending_commands_fallback_total"] = int(fallback_commands_total)
    else:
        report["pending_commands_total"] = int(commands_total)
        report["pending_commands_fallback_total"] = int(fallback_commands_total)

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")
    _write_csv(csv_out_path, pending_rows)

    if bool(args.strict) and str(report.get("status") or "") != "ok":
        return STRICT_FAIL_EXIT
    if str(report.get("status") or "") == "failed":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
