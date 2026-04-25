#!/usr/bin/env python3
"""Export reproducible manual-capture targets from Senado WAF cohort packets.

This script converts packetized missing-doc cohorts into a bounded queue of
interactive browser-capture targets (URL + suggested command), so operators can
refresh session/cookies with deterministic priority.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PACKET_JSON = Path("docs/etl/sprints/AI-OPS-298/evidence/senado_waf_cohort_packets_latest.json")
DEFAULT_PACKET_CSV = Path("docs/etl/sprints/AI-OPS-298/exports/senado_waf_cohort_packets_latest.csv")
DEFAULT_OUT = Path("docs/etl/sprints/AI-OPS-299/evidence/senado_manual_capture_targets_latest.json")
DEFAULT_CSV_OUT = Path("docs/etl/sprints/AI-OPS-299/exports/senado_manual_capture_targets_latest.csv")
STRICT_FAIL_EXIT = 4


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _display_path(path: Path) -> str:
    if not path.is_absolute():
        return str(path)
    return f"<abs>/{path.name or 'artifact.json'}"


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
    if not isinstance(data, dict):
        return {}
    return data


def _load_packet_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not isinstance(row, dict):
                continue
            doc_url = str(row.get("doc_url") or "").strip()
            if not doc_url:
                continue
            rows.append(
                {
                    "packet_kind": str(row.get("packet_kind") or ""),
                    "packet_rank": _to_int(row.get("packet_rank"), 0),
                    "packet_id": str(row.get("packet_id") or ""),
                    "cohort": str(row.get("cohort") or "unknown"),
                    "legislature": str(row.get("legislature") or "unknown"),
                    "tipo_expediente": str(row.get("tipo_expediente") or "unknown"),
                    "initiative_id": str(row.get("initiative_id") or ""),
                    "doc_kind": str(row.get("doc_kind") or ""),
                    "doc_url": doc_url,
                    "last_http_status": _to_int(row.get("last_http_status"), 0),
                    "attempts": _to_int(row.get("attempts"), 0),
                    "last_attempt_at": str(row.get("last_attempt_at") or ""),
                    "method_hint": str(row.get("method_hint") or "unknown"),
                    "is_zero_doc_initiative": _to_int(row.get("is_zero_doc_initiative"), 0),
                    "cohort_missing_urls": _to_int(row.get("cohort_missing_urls"), 0),
                }
            )
    return rows


def _row_score(row: dict[str, Any]) -> tuple[int, int, int, int, str, str, str]:
    status = _to_int(row.get("last_http_status"), 0)
    is_zero = 1 if _to_int(row.get("is_zero_doc_initiative"), 0) > 0 else 0
    is_403 = 1 if status == 403 else 0
    is_500 = 1 if status == 500 else 0
    attempts = _to_int(row.get("attempts"), 0)
    return (
        -is_zero,
        -is_403,
        -is_500,
        -attempts,
        str(row.get("cohort") or ""),
        str(row.get("initiative_id") or ""),
        str(row.get("doc_url") or ""),
    )


def _build_suggested_command(capture_url: str, label: str, wait_seconds: int) -> str:
    return (
        "python3 scripts/manual_capture_playwright.py "
        f"--url {json.dumps(capture_url, ensure_ascii=True)} "
        f"--label {json.dumps(label, ensure_ascii=True)} "
        "--out-dir etl/data/raw/manual "
        f"--wait-seconds {int(wait_seconds)} --channel \"\""
    )


def _select_targets(
    rows: list[dict[str, Any]],
    *,
    packet_json: dict[str, Any],
    include_seed_url: bool,
    seed_url: str,
    max_targets: int,
    wait_seconds: int,
    label_prefix: str,
) -> list[dict[str, Any]]:
    if max_targets <= 0:
        return []

    selected: list[dict[str, Any]] = []
    used_urls: set[str] = set()

    def append_target(target: dict[str, Any]) -> None:
        selected.append(target)

    next_rank = 1
    if include_seed_url and seed_url.strip():
        label = f"{label_prefix}_{next_rank:02d}_seed"
        append_target(
            {
                "target_rank": next_rank,
                "target_id": f"target_{next_rank:02d}",
                "target_kind": "seed",
                "cohort": "seed",
                "initiative_id": "",
                "packet_kind": "seed",
                "capture_url": seed_url.strip(),
                "source_doc_url": "",
                "last_http_status": 0,
                "attempts": 0,
                "is_zero_doc_initiative": 0,
                "reason": "seed_homepage_for_cookie_refresh",
                "suggested_label": label,
                "suggested_command": _build_suggested_command(seed_url.strip(), label, wait_seconds),
            }
        )
        used_urls.add(seed_url.strip())
        next_rank += 1

    cohort_priority: dict[str, int] = {}
    selected_cohorts = packet_json.get("selected_cohorts") if isinstance(packet_json, dict) else []
    if isinstance(selected_cohorts, list):
        for idx, item in enumerate(selected_cohorts, start=1):
            if not isinstance(item, dict):
                continue
            cohort = str(item.get("cohort") or "").strip()
            if cohort and cohort not in cohort_priority:
                cohort_priority[cohort] = idx

    by_cohort: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        cohort = str(row.get("cohort") or "unknown")
        by_cohort.setdefault(cohort, []).append(row)

    for cohort_rows in by_cohort.values():
        cohort_rows.sort(key=_row_score)

    ordered_cohorts = sorted(
        by_cohort.keys(),
        key=lambda c: (cohort_priority.get(c, 1_000_000), c),
    )

    # Pass 1: at least one target per cohort (priority order).
    for cohort in ordered_cohorts:
        if len(selected) >= max_targets:
            break
        cohort_rows = by_cohort.get(cohort, [])
        chosen: dict[str, Any] | None = None
        for row in cohort_rows:
            url = str(row.get("doc_url") or "")
            if not url or url in used_urls:
                continue
            chosen = row
            break
        if chosen is None:
            continue
        url = str(chosen.get("doc_url") or "")
        label = f"{label_prefix}_{next_rank:02d}_{cohort.replace(':', '_')}"
        append_target(
            {
                "target_rank": next_rank,
                "target_id": f"target_{next_rank:02d}",
                "target_kind": "cohort_primary",
                "cohort": cohort,
                "initiative_id": str(chosen.get("initiative_id") or ""),
                "packet_kind": str(chosen.get("packet_kind") or "cohort"),
                "capture_url": url,
                "source_doc_url": url,
                "last_http_status": _to_int(chosen.get("last_http_status"), 0),
                "attempts": _to_int(chosen.get("attempts"), 0),
                "is_zero_doc_initiative": _to_int(chosen.get("is_zero_doc_initiative"), 0),
                "reason": "top_row_in_cohort",
                "suggested_label": label,
                "suggested_command": _build_suggested_command(url, label, wait_seconds),
            }
        )
        used_urls.add(url)
        next_rank += 1

    # Pass 2: fill remaining cap with best leftovers globally.
    if len(selected) < max_targets:
        leftovers = sorted(rows, key=_row_score)
        for row in leftovers:
            if len(selected) >= max_targets:
                break
            url = str(row.get("doc_url") or "")
            if not url or url in used_urls:
                continue
            cohort = str(row.get("cohort") or "unknown")
            label = f"{label_prefix}_{next_rank:02d}_{cohort.replace(':', '_')}"
            append_target(
                {
                    "target_rank": next_rank,
                    "target_id": f"target_{next_rank:02d}",
                    "target_kind": "cohort_secondary",
                    "cohort": cohort,
                    "initiative_id": str(row.get("initiative_id") or ""),
                    "packet_kind": str(row.get("packet_kind") or "cohort"),
                    "capture_url": url,
                    "source_doc_url": url,
                    "last_http_status": _to_int(row.get("last_http_status"), 0),
                    "attempts": _to_int(row.get("attempts"), 0),
                    "is_zero_doc_initiative": _to_int(row.get("is_zero_doc_initiative"), 0),
                    "reason": "best_remaining_row",
                    "suggested_label": label,
                    "suggested_command": _build_suggested_command(url, label, wait_seconds),
                }
            )
            used_urls.add(url)
            next_rank += 1

    return selected


def build_report(
    *,
    packet_json_path: Path,
    packet_csv_path: Path,
    include_seed_url: bool,
    seed_url: str,
    max_targets: int,
    wait_seconds: int,
    label_prefix: str,
    strict_min_targets: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not packet_json_path.exists():
        return (
            {
                "generated_at": now_utc_iso(),
                "status": "failed",
                "error": "packet_json_not_found",
                "packet_json": _display_path(packet_json_path),
            },
            [],
        )
    if not packet_csv_path.exists():
        return (
            {
                "generated_at": now_utc_iso(),
                "status": "failed",
                "error": "packet_csv_not_found",
                "packet_csv": _display_path(packet_csv_path),
            },
            [],
        )

    packet_json = _load_json(packet_json_path)
    packet_rows = _load_packet_rows(packet_csv_path)
    targets = _select_targets(
        packet_rows,
        packet_json=packet_json,
        include_seed_url=bool(include_seed_url),
        seed_url=str(seed_url or "").strip(),
        max_targets=max(0, int(max_targets)),
        wait_seconds=max(1, int(wait_seconds)),
        label_prefix=str(label_prefix or "senado_cookie_refresh").strip() or "senado_cookie_refresh",
    )

    selected_cohorts = {
        str(t.get("cohort") or "")
        for t in targets
        if str(t.get("target_kind") or "") != "seed" and str(t.get("cohort") or "")
    }
    checks = {
        "has_packet_rows": len(packet_rows) > 0,
        "targets_min_met": len(targets) >= max(0, int(strict_min_targets)),
        "has_non_seed_target": any(str(t.get("target_kind") or "") != "seed" for t in targets),
    }
    reasons: list[str] = []
    if not checks["has_packet_rows"]:
        reasons.append("no_packet_rows")
    if not checks["targets_min_met"]:
        reasons.append("targets_below_min")
    if not checks["has_non_seed_target"]:
        reasons.append("no_non_seed_target")

    status = "ok" if all(checks.values()) else "degraded"
    report = {
        "generated_at": now_utc_iso(),
        "status": status,
        "packet_json": _display_path(packet_json_path),
        "packet_csv": _display_path(packet_csv_path),
        "inputs": {
            "include_seed_url": bool(include_seed_url),
            "seed_url": str(seed_url or "").strip(),
            "max_targets": max(0, int(max_targets)),
            "wait_seconds": max(1, int(wait_seconds)),
            "label_prefix": str(label_prefix or "").strip(),
            "strict_min_targets": max(0, int(strict_min_targets)),
        },
        "totals": {
            "packet_rows_total": len(packet_rows),
            "selected_targets_total": len(targets),
            "selected_cohorts_total": len(selected_cohorts),
            "seed_targets_total": sum(
                1 for t in targets if str(t.get("target_kind") or "") == "seed"
            ),
            "targets_from_zero_doc_total": sum(
                1 for t in targets if _to_int(t.get("is_zero_doc_initiative"), 0) > 0
            ),
            "targets_with_403_total": sum(
                1 for t in targets if _to_int(t.get("last_http_status"), 0) == 403
            ),
            "targets_with_500_total": sum(
                1 for t in targets if _to_int(t.get("last_http_status"), 0) == 500
            ),
        },
        "checks": checks,
        "strict_fail_reasons": reasons,
        "targets": targets,
    }
    return report, targets


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "target_rank",
        "target_id",
        "target_kind",
        "cohort",
        "initiative_id",
        "packet_kind",
        "capture_url",
        "source_doc_url",
        "last_http_status",
        "attempts",
        "is_zero_doc_initiative",
        "reason",
        "suggested_label",
        "suggested_command",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export manual-capture targets from Senado packet queue")
    p.add_argument("--packet-json", default=str(DEFAULT_PACKET_JSON), help="Input packet summary JSON")
    p.add_argument("--packet-csv", default=str(DEFAULT_PACKET_CSV), help="Input packet rows CSV")
    p.add_argument(
        "--include-seed-url",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include a seed homepage target first (default true)",
    )
    p.add_argument("--seed-url", default="https://www.senado.es/")
    p.add_argument("--max-targets", type=int, default=8)
    p.add_argument("--wait-seconds", type=int, default=120)
    p.add_argument("--label-prefix", default="senado_cookie_refresh_ai_ops_299")
    p.add_argument("--strict-min-targets", type=int, default=1)
    p.add_argument("--out", default=str(DEFAULT_OUT), help="Output JSON path")
    p.add_argument("--csv-out", default=str(DEFAULT_CSV_OUT), help="Output CSV path")
    p.add_argument("--strict", action="store_true", help="Exit 4 unless status=ok")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    packet_json_path = Path(str(args.packet_json))
    packet_csv_path = Path(str(args.packet_csv))
    out_path = Path(str(args.out))
    csv_out_path = Path(str(args.csv_out))

    report, rows = build_report(
        packet_json_path=packet_json_path,
        packet_csv_path=packet_csv_path,
        include_seed_url=bool(args.include_seed_url),
        seed_url=str(args.seed_url or "").strip(),
        max_targets=max(0, int(args.max_targets or 0)),
        wait_seconds=max(1, int(args.wait_seconds or 120)),
        label_prefix=str(args.label_prefix or "").strip(),
        strict_min_targets=max(0, int(args.strict_min_targets or 0)),
    )

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")
    _write_csv(csv_out_path, rows)

    if bool(args.strict) and str(report.get("status") or "") != "ok":
        return STRICT_FAIL_EXIT
    if str(report.get("status") or "") == "failed":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
