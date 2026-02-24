#!/usr/bin/env python3
"""Compaction reporter for citizen mobile observability heartbeat JSONL."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/citizen_mobile_observability_heartbeat.jsonl")
DEFAULT_COMPACTED_JSONL = Path("docs/etl/runs/citizen_mobile_observability_heartbeat.compacted.jsonl")
DEFAULT_KEEP_RECENT = 20
DEFAULT_KEEP_MID_SPAN = 100
DEFAULT_KEEP_MID_EVERY = 5
DEFAULT_KEEP_OLD_EVERY = 20
DEFAULT_MIN_RAW_FOR_DROPPED_CHECK = 25


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return int(default)


def _to_bool(value: Any) -> bool:
    return bool(value)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:  # noqa: BLE001
        return None


def _safe_obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_text(v) for v in value if _safe_text(v)]


def _normalize_status(value: Any) -> str:
    token = _safe_text(value).lower()
    if token in {"ok", "degraded", "failed"}:
        return token
    return "failed"


def _round4(value: float) -> float:
    return round(float(value), 4)


def _parse_positive_int(raw: Any, *, arg_name: str) -> int:
    value = _to_int(raw, -1)
    if value < 1:
        raise ValueError(f"{arg_name} must be >= 1")
    return value


def _parse_non_negative_int(raw: Any, *, arg_name: str) -> int:
    value = _to_int(raw, -1)
    if value < 0:
        raise ValueError(f"{arg_name} must be >= 0")
    return value


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Citizen mobile observability heartbeat compaction report")
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Raw heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument(
        "--compacted-jsonl",
        default=str(DEFAULT_COMPACTED_JSONL),
        help=f"Compacted heartbeat JSONL path (default: {DEFAULT_COMPACTED_JSONL})",
    )
    p.add_argument(
        "--keep-recent",
        type=int,
        default=DEFAULT_KEEP_RECENT,
        help=f"Keep every row for recent window (default: {DEFAULT_KEEP_RECENT})",
    )
    p.add_argument(
        "--keep-mid-span",
        type=int,
        default=DEFAULT_KEEP_MID_SPAN,
        help=f"Mid window size after recent window (default: {DEFAULT_KEEP_MID_SPAN})",
    )
    p.add_argument(
        "--keep-mid-every",
        type=int,
        default=DEFAULT_KEEP_MID_EVERY,
        help=f"Cadence in mid window (default: {DEFAULT_KEEP_MID_EVERY})",
    )
    p.add_argument(
        "--keep-old-every",
        type=int,
        default=DEFAULT_KEEP_OLD_EVERY,
        help=f"Cadence in old window (default: {DEFAULT_KEEP_OLD_EVERY})",
    )
    p.add_argument(
        "--min-raw-for-dropped-check",
        type=int,
        default=DEFAULT_MIN_RAW_FOR_DROPPED_CHECK,
        help=f"Require at least one dropped row when raw >= N (default: {DEFAULT_MIN_RAW_FOR_DROPPED_CHECK})",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 4 when strict checks fail.",
    )
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def read_heartbeat_rows(heartbeat_path: Path) -> list[dict[str, Any]]:
    if not heartbeat_path.exists():
        return []
    raw = heartbeat_path.read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    lines = [line for line in raw.splitlines() if _safe_text(line)]
    for idx, line in enumerate(lines, start=1):
        try:
            entry = json.loads(line)
            rows.append(
                {
                    "line_no": idx,
                    "raw_line": line,
                    "malformed_line": False,
                    "entry": _safe_obj(entry),
                }
            )
        except Exception:  # noqa: BLE001
            rows.append(
                {
                    "line_no": idx,
                    "raw_line": line,
                    "malformed_line": True,
                    "entry": {},
                }
            )
    return rows


def _tier_for_age(age: int, *, keep_recent: int, keep_mid_span: int) -> str:
    if age < keep_recent:
        return "recent"
    if age < keep_recent + keep_mid_span:
        return "mid"
    return "old"


def _cadence_matches(
    age: int,
    *,
    keep_recent: int,
    keep_mid_span: int,
    keep_mid_every: int,
    keep_old_every: int,
) -> bool:
    tier = _tier_for_age(age, keep_recent=keep_recent, keep_mid_span=keep_mid_span)
    if tier == "recent":
        return True
    if tier == "mid":
        return age % keep_mid_every == 0
    return age % keep_old_every == 0


def _p90_within_threshold(entry: dict[str, Any]) -> bool | None:
    raw = entry.get("input_to_render_p90_within_threshold")
    if isinstance(raw, bool):
        return raw
    p90 = _safe_float(entry.get("input_to_render_p90_ms"))
    max_p90 = _safe_float(entry.get("max_input_to_render_p90_ms"))
    if p90 is None or max_p90 is None:
        return None
    return bool(p90 <= max_p90)


def _has_incident(row: dict[str, Any]) -> bool:
    if _to_bool(row.get("malformed_line")):
        return True
    entry = _safe_obj(row.get("entry"))
    status = _normalize_status(entry.get("status"))
    if status in {"failed", "degraded"}:
        return True
    if _to_int(entry.get("strict_fail_count"), 0) > 0:
        return True
    if len(_safe_list_str(entry.get("strict_fail_reasons"))) > 0:
        return True
    if _p90_within_threshold(entry) is False:
        return True
    return False


def _build_selection(
    rows: list[dict[str, Any]],
    *,
    keep_recent: int,
    keep_mid_span: int,
    keep_mid_every: int,
    keep_old_every: int,
) -> tuple[set[int], dict[int, list[str]]]:
    n = len(rows)
    selected: set[int] = set()
    reasons_by_index: dict[int, list[str]] = {}

    for i, row in enumerate(rows):
        age = n - 1 - i
        reasons: list[str] = []

        if i == 0:
            reasons.append("anchor_oldest")
        if i == n - 1:
            reasons.append("anchor_latest")
        if _to_bool(row.get("malformed_line")):
            reasons.append("malformed_line")
        if _has_incident(row):
            reasons.append("incident_entry")

        if _cadence_matches(
            age,
            keep_recent=keep_recent,
            keep_mid_span=keep_mid_span,
            keep_mid_every=keep_mid_every,
            keep_old_every=keep_old_every,
        ):
            reasons.append(f"cadence_{_tier_for_age(age, keep_recent=keep_recent, keep_mid_span=keep_mid_span)}")

        if reasons:
            selected.add(i)
            reasons_by_index[i] = reasons

    return selected, reasons_by_index


def build_compaction_report(
    rows: list[dict[str, Any]],
    *,
    heartbeat_path: str = "",
    compacted_path: str = "",
    keep_recent: int = DEFAULT_KEEP_RECENT,
    keep_mid_span: int = DEFAULT_KEEP_MID_SPAN,
    keep_mid_every: int = DEFAULT_KEEP_MID_EVERY,
    keep_old_every: int = DEFAULT_KEEP_OLD_EVERY,
    min_raw_for_dropped_check: int = DEFAULT_MIN_RAW_FOR_DROPPED_CHECK,
    strict: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    keep_recent_n = _parse_positive_int(keep_recent, arg_name="keep_recent")
    keep_mid_span_n = _parse_non_negative_int(keep_mid_span, arg_name="keep_mid_span")
    keep_mid_every_n = _parse_positive_int(keep_mid_every, arg_name="keep_mid_every")
    keep_old_every_n = _parse_positive_int(keep_old_every, arg_name="keep_old_every")
    min_raw_n = _parse_non_negative_int(min_raw_for_dropped_check, arg_name="min_raw_for_dropped_check")

    selected_idx, reasons_by_index = _build_selection(
        rows,
        keep_recent=keep_recent_n,
        keep_mid_span=keep_mid_span_n,
        keep_mid_every=keep_mid_every_n,
        keep_old_every=keep_old_every_n,
    )

    n = len(rows)
    selected_rows = [rows[i] for i in range(n) if i in selected_idx]
    dropped_rows = [rows[i] for i in range(n) if i not in selected_idx]

    tiers: dict[str, dict[str, int]] = {
        "recent": {"raw_entries": 0, "selected_entries": 0, "cadence_every": 1},
        "mid": {"raw_entries": 0, "selected_entries": 0, "cadence_every": keep_mid_every_n},
        "old": {"raw_entries": 0, "selected_entries": 0, "cadence_every": keep_old_every_n},
    }

    malformed_total = 0
    malformed_selected = 0
    incidents_total = 0
    incidents_selected = 0
    failed_total = 0
    failed_selected = 0
    degraded_total = 0
    degraded_selected = 0
    strict_rows_total = 0
    strict_rows_selected = 0
    p90_violations_total = 0
    p90_violations_selected = 0

    for i, row in enumerate(rows):
        age = n - 1 - i
        tier = _tier_for_age(age, keep_recent=keep_recent_n, keep_mid_span=keep_mid_span_n)
        tiers[tier]["raw_entries"] += 1
        if i in selected_idx:
            tiers[tier]["selected_entries"] += 1

        entry = _safe_obj(row.get("entry"))
        status = _normalize_status(entry.get("status"))
        strict_fail_count = _to_int(entry.get("strict_fail_count"), 0)
        strict_fail_reasons = _safe_list_str(entry.get("strict_fail_reasons"))
        is_malformed = _to_bool(row.get("malformed_line"))
        is_incident = _has_incident(row)
        has_p90_violation = _p90_within_threshold(entry) is False

        if is_malformed:
            malformed_total += 1
            if i in selected_idx:
                malformed_selected += 1

        if is_incident:
            incidents_total += 1
            if i in selected_idx:
                incidents_selected += 1

        if status == "failed":
            failed_total += 1
            if i in selected_idx:
                failed_selected += 1

        if status == "degraded":
            degraded_total += 1
            if i in selected_idx:
                degraded_selected += 1

        if strict_fail_count > 0 or strict_fail_reasons:
            strict_rows_total += 1
            if i in selected_idx:
                strict_rows_selected += 1

        if has_p90_violation:
            p90_violations_total += 1
            if i in selected_idx:
                p90_violations_selected += 1

    entries_total = n
    selected_entries = len(selected_rows)
    dropped_entries = len(dropped_rows)
    dropped_rate_pct = _round4((float(dropped_entries) / float(entries_total) * 100.0) if entries_total > 0 else 0.0)

    selected_reasons_sample: list[dict[str, Any]] = []
    for i in sorted(selected_idx)[:20]:
        row = rows[i]
        entry = _safe_obj(row.get("entry"))
        selected_reasons_sample.append(
            {
                "index": i,
                "line_no": _to_int(row.get("line_no"), 0),
                "run_at": _safe_text(entry.get("run_at")),
                "status": _normalize_status(entry.get("status")),
                "reasons": list(reasons_by_index.get(i, [])),
            }
        )

    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(strict),
        "heartbeat_path": heartbeat_path,
        "compacted_path": compacted_path,
        "strategy": {
            "keep_recent": keep_recent_n,
            "keep_mid_span": keep_mid_span_n,
            "keep_mid_every": keep_mid_every_n,
            "keep_old_every": keep_old_every_n,
        },
        "min_raw_for_dropped_check": min_raw_n,
        "entries_total": entries_total,
        "selected_entries": selected_entries,
        "dropped_entries": dropped_entries,
        "dropped_rate_pct": dropped_rate_pct,
        "tiers": tiers,
        "malformed_total": malformed_total,
        "malformed_selected": malformed_selected,
        "malformed_dropped": malformed_total - malformed_selected,
        "incidents_total": incidents_total,
        "incidents_selected": incidents_selected,
        "incidents_dropped": incidents_total - incidents_selected,
        "failed_total": failed_total,
        "failed_selected": failed_selected,
        "failed_dropped": failed_total - failed_selected,
        "degraded_total": degraded_total,
        "degraded_selected": degraded_selected,
        "degraded_dropped": degraded_total - degraded_selected,
        "strict_rows_total": strict_rows_total,
        "strict_rows_selected": strict_rows_selected,
        "strict_rows_dropped": strict_rows_total - strict_rows_selected,
        "p90_threshold_violations_total": p90_violations_total,
        "p90_threshold_violations_selected": p90_violations_selected,
        "p90_threshold_violations_dropped": p90_violations_total - p90_violations_selected,
        "anchors": {
            "oldest_selected": entries_total > 0 and 0 in selected_idx,
            "latest_selected": entries_total > 0 and (entries_total - 1) in selected_idx,
        },
        "raw_first_run_at": _safe_text(_safe_obj(rows[0].get("entry")).get("run_at")) if rows else "",
        "raw_last_run_at": _safe_text(_safe_obj(rows[-1].get("entry")).get("run_at")) if rows else "",
        "selected_first_run_at": _safe_text(_safe_obj(selected_rows[0].get("entry")).get("run_at")) if selected_rows else "",
        "selected_last_run_at": _safe_text(_safe_obj(selected_rows[-1].get("entry")).get("run_at")) if selected_rows else "",
        "selected_indices_sample": sorted(selected_idx)[:20],
        "selected_reasons_sample": selected_reasons_sample,
        "checks": {
            "latest_selected_ok": entries_total == 0 or (entries_total - 1) in selected_idx,
            "incidents_preserved_ok": incidents_total == incidents_selected,
            "failed_preserved_ok": failed_total == failed_selected,
            "degraded_preserved_ok": degraded_total == degraded_selected,
            "malformed_preserved_ok": malformed_total == malformed_selected,
            "strict_rows_preserved_ok": strict_rows_total == strict_rows_selected,
            "p90_violations_preserved_ok": p90_violations_total == p90_violations_selected,
            "dropped_when_above_threshold_ok": True,
        },
        "strict_fail_reasons": [],
        "status": "ok",
    }

    if entries_total >= min_raw_n:
        report["checks"]["dropped_when_above_threshold_ok"] = dropped_entries > 0

    reasons: list[str] = []
    if not report["checks"]["latest_selected_ok"]:
        reasons.append("latest_not_selected")
    if not report["checks"]["incidents_preserved_ok"]:
        reasons.append("incident_entries_dropped")
    if not report["checks"]["failed_preserved_ok"]:
        reasons.append("failed_entries_dropped")
    if not report["checks"]["degraded_preserved_ok"]:
        reasons.append("degraded_entries_dropped")
    if not report["checks"]["malformed_preserved_ok"]:
        reasons.append("malformed_entries_dropped")
    if not report["checks"]["strict_rows_preserved_ok"]:
        reasons.append("strict_rows_dropped")
    if not report["checks"]["p90_violations_preserved_ok"]:
        reasons.append("p90_threshold_violation_entries_dropped")
    if not report["checks"]["dropped_when_above_threshold_ok"]:
        reasons.append("no_entries_dropped_above_threshold")
    report["strict_fail_reasons"] = reasons

    if entries_total == 0:
        report["status"] = "degraded"
    elif reasons:
        report["status"] = "failed"
    elif dropped_entries == 0:
        report["status"] = "degraded"
    else:
        report["status"] = "ok"

    return report, selected_rows


def write_compacted_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for row in rows:
        raw_line = _safe_text(row.get("raw_line"))
        if raw_line:
            lines.append(raw_line)
        else:
            lines.append(json.dumps(_safe_obj(row.get("entry")), ensure_ascii=False))
    payload = "\n".join(lines)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        rows = read_heartbeat_rows(Path(str(args.heartbeat_jsonl)))
        report, selected_rows = build_compaction_report(
            rows,
            heartbeat_path=str(args.heartbeat_jsonl),
            compacted_path=str(args.compacted_jsonl),
            keep_recent=int(args.keep_recent),
            keep_mid_span=int(args.keep_mid_span),
            keep_mid_every=int(args.keep_mid_every),
            keep_old_every=int(args.keep_old_every),
            min_raw_for_dropped_check=int(args.min_raw_for_dropped_check),
            strict=bool(args.strict),
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"runtime_error:{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 3

    compacted_path = Path(str(args.compacted_jsonl))
    write_compacted_jsonl(compacted_path, selected_rows)

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out).strip()) if str(args.out).strip() else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and len(list(report.get("strict_fail_reasons") or [])) > 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
