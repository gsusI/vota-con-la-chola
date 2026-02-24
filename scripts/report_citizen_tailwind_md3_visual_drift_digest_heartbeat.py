#!/usr/bin/env python3
"""Append-only heartbeat lane for citizen Tailwind+MD3 visual drift digest."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DIGEST_JSON = Path("docs/etl/sprints/AI-OPS-96/evidence/citizen_tailwind_md3_visual_drift_digest_latest.json")
DEFAULT_HEARTBEAT_JSONL = Path("docs/etl/runs/citizen_tailwind_md3_visual_drift_digest_heartbeat.jsonl")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        token = _safe_text(item)
        if token:
            out.append(token)
    return out


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return int(default)


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    token = _safe_text(value).lower()
    if token in {"1", "true", "yes", "y"}:
        return True
    if token in {"0", "false", "no", "n"}:
        return False
    return bool(value)


def _normalize_status(value: Any) -> str:
    token = _safe_text(value).lower()
    if token in {"ok", "degraded", "failed"}:
        return token
    return "failed"


def _dedupe_ordered(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = _safe_text(value)
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _pair_bytes(pair: dict[str, Any]) -> tuple[int, int]:
    return _to_int(pair.get("source_bytes"), 0), _to_int(pair.get("published_bytes"), 0)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append heartbeat JSONL for citizen Tailwind+MD3 visual drift digest")
    p.add_argument(
        "--digest-json",
        default=str(DEFAULT_DIGEST_JSON),
        help=f"Input drift digest JSON (default: {DEFAULT_DIGEST_JSON})",
    )
    p.add_argument(
        "--heartbeat-jsonl",
        default=str(DEFAULT_HEARTBEAT_JSONL),
        help=f"Heartbeat JSONL path (default: {DEFAULT_HEARTBEAT_JSONL})",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 4 when heartbeat is invalid or status=failed.",
    )
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def build_heartbeat(
    digest_payload: dict[str, Any],
    *,
    digest_path: str,
) -> dict[str, Any]:
    digest = _safe_obj(digest_payload)
    if "status" not in digest and isinstance(digest.get("digest"), dict):
        digest = _safe_obj(digest.get("digest"))

    run_at = _safe_text(digest.get("generated_at")) or now_utc_iso()
    status = _normalize_status(digest.get("status"))
    checks = _safe_obj(digest.get("checks"))
    contract = _safe_obj(digest.get("tailwind_contract"))
    parity = _safe_obj(digest.get("parity"))

    tokens = _safe_obj(parity.get("tokens"))
    tokens_data = _safe_obj(parity.get("tokens_data"))
    css = _safe_obj(parity.get("css"))
    ui_html = _safe_obj(parity.get("ui_html"))

    tailwind_contract_exists = _to_bool(checks.get("tailwind_contract_exists"))
    tailwind_contract_status_ok = _to_bool(checks.get("tailwind_contract_status_ok"))
    tailwind_contract_checks_ok = _to_bool(checks.get("tailwind_contract_checks_ok"))

    tokens_parity_ok = _to_bool(checks.get("tokens_parity_ok"))
    tokens_data_parity_ok = _to_bool(checks.get("tokens_data_parity_ok"))
    css_parity_ok = _to_bool(checks.get("css_parity_ok"))
    ui_html_parity_ok = _to_bool(checks.get("ui_html_parity_ok"))

    source_published_marker_counts_match = _to_bool(checks.get("source_published_marker_counts_match"))
    source_markers_match_contract_snapshot = _to_bool(checks.get("source_markers_match_contract_snapshot"))
    published_markers_match_contract_snapshot = _to_bool(checks.get("published_markers_match_contract_snapshot"))

    source_published_parity_ok = all([tokens_parity_ok, tokens_data_parity_ok, css_parity_ok, ui_html_parity_ok])
    marker_parity_ok = all(
        [
            source_published_marker_counts_match,
            source_markers_match_contract_snapshot,
            published_markers_match_contract_snapshot,
        ]
    )

    parity_fail_reasons: list[str] = []
    if not tokens_parity_ok:
        parity_fail_reasons.append("tokens_parity_mismatch")
    if not tokens_data_parity_ok:
        parity_fail_reasons.append("tokens_data_parity_mismatch")
    if not css_parity_ok:
        parity_fail_reasons.append("css_parity_mismatch")
    if not ui_html_parity_ok:
        parity_fail_reasons.append("ui_html_parity_mismatch")
    if not source_published_marker_counts_match:
        parity_fail_reasons.append("source_published_marker_counts_mismatch")
    if not source_markers_match_contract_snapshot:
        parity_fail_reasons.append("source_markers_mismatch_contract_snapshot")
    if not published_markers_match_contract_snapshot:
        parity_fail_reasons.append("published_markers_mismatch_contract_snapshot")
    parity_fail_reasons = _dedupe_ordered(parity_fail_reasons)

    digest_strict_fail_reasons = _safe_list_str(digest.get("strict_fail_reasons"))
    contract_failure_reasons = _safe_list_str(contract.get("failure_reasons"))
    strict_fail_reasons: list[str] = []
    if status == "failed":
        strict_fail_reasons.extend(digest_strict_fail_reasons)
        strict_fail_reasons.extend(parity_fail_reasons)
        if not strict_fail_reasons:
            strict_fail_reasons.append("visual_drift_failed_without_reason")
    strict_fail_reasons = _dedupe_ordered(strict_fail_reasons)

    tokens_source_bytes, tokens_published_bytes = _pair_bytes(tokens)
    tokens_data_source_bytes, tokens_data_published_bytes = _pair_bytes(tokens_data)
    css_source_bytes, css_published_bytes = _pair_bytes(css)
    ui_source_bytes, ui_published_bytes = _pair_bytes(ui_html)

    heartbeat_id = "|".join(
        [
            run_at,
            status,
            "1" if source_published_parity_ok else "0",
            "1" if marker_parity_ok else "0",
            str(len(parity_fail_reasons)),
            ",".join(parity_fail_reasons),
            ",".join(strict_fail_reasons),
        ]
    )

    return {
        "run_at": run_at,
        "heartbeat_id": heartbeat_id,
        "digest_path": _safe_text(digest_path),
        "digest_generated_at": _safe_text(digest.get("generated_at")),
        "status": status,
        "tailwind_contract_exists": tailwind_contract_exists,
        "tailwind_contract_status": _safe_text(contract.get("status")),
        "tailwind_contract_status_ok": tailwind_contract_status_ok,
        "tailwind_contract_checks_ok": tailwind_contract_checks_ok,
        "tokens_parity_ok": tokens_parity_ok,
        "tokens_data_parity_ok": tokens_data_parity_ok,
        "css_parity_ok": css_parity_ok,
        "ui_html_parity_ok": ui_html_parity_ok,
        "source_published_marker_counts_match": source_published_marker_counts_match,
        "source_markers_match_contract_snapshot": source_markers_match_contract_snapshot,
        "published_markers_match_contract_snapshot": published_markers_match_contract_snapshot,
        "source_published_parity_ok": source_published_parity_ok,
        "marker_parity_ok": marker_parity_ok,
        "tokens_source_bytes": tokens_source_bytes,
        "tokens_published_bytes": tokens_published_bytes,
        "tokens_data_source_bytes": tokens_data_source_bytes,
        "tokens_data_published_bytes": tokens_data_published_bytes,
        "css_source_bytes": css_source_bytes,
        "css_published_bytes": css_published_bytes,
        "ui_html_source_bytes": ui_source_bytes,
        "ui_html_published_bytes": ui_published_bytes,
        "parity_fail_count": len(parity_fail_reasons),
        "parity_fail_reasons": parity_fail_reasons,
        "digest_strict_fail_reasons": digest_strict_fail_reasons,
        "contract_failure_reasons": contract_failure_reasons,
        "strict_fail_count": len(strict_fail_reasons),
        "strict_fail_reasons": strict_fail_reasons,
    }


def validate_heartbeat(heartbeat: dict[str, Any]) -> list[str]:
    reasons: list[str] = []

    if not _safe_text(heartbeat.get("run_at")):
        reasons.append("missing_run_at")
    if not _safe_text(heartbeat.get("heartbeat_id")):
        reasons.append("missing_heartbeat_id")

    status = _normalize_status(heartbeat.get("status"))
    if _safe_text(heartbeat.get("status")).lower() not in {"ok", "degraded", "failed"}:
        reasons.append("invalid_status")

    bool_keys = (
        "tailwind_contract_exists",
        "tailwind_contract_status_ok",
        "tailwind_contract_checks_ok",
        "tokens_parity_ok",
        "tokens_data_parity_ok",
        "css_parity_ok",
        "ui_html_parity_ok",
        "source_published_marker_counts_match",
        "source_markers_match_contract_snapshot",
        "published_markers_match_contract_snapshot",
        "source_published_parity_ok",
        "marker_parity_ok",
    )
    for key in bool_keys:
        if not isinstance(heartbeat.get(key), bool):
            reasons.append(f"invalid_{key}")

    expected_source_published_parity_ok = all(
        [
            bool(heartbeat.get("tokens_parity_ok")),
            bool(heartbeat.get("tokens_data_parity_ok")),
            bool(heartbeat.get("css_parity_ok")),
            bool(heartbeat.get("ui_html_parity_ok")),
        ]
    )
    if isinstance(heartbeat.get("source_published_parity_ok"), bool) and bool(heartbeat.get("source_published_parity_ok")) != expected_source_published_parity_ok:
        reasons.append("source_published_parity_ok_mismatch")

    expected_marker_parity_ok = all(
        [
            bool(heartbeat.get("source_published_marker_counts_match")),
            bool(heartbeat.get("source_markers_match_contract_snapshot")),
            bool(heartbeat.get("published_markers_match_contract_snapshot")),
        ]
    )
    if isinstance(heartbeat.get("marker_parity_ok"), bool) and bool(heartbeat.get("marker_parity_ok")) != expected_marker_parity_ok:
        reasons.append("marker_parity_ok_mismatch")

    for key in (
        "tokens_source_bytes",
        "tokens_published_bytes",
        "tokens_data_source_bytes",
        "tokens_data_published_bytes",
        "css_source_bytes",
        "css_published_bytes",
        "ui_html_source_bytes",
        "ui_html_published_bytes",
    ):
        value = _to_int(heartbeat.get(key), -1)
        if value < 0:
            reasons.append(f"invalid_{key}")

    parity_fail_reasons = _safe_list_str(heartbeat.get("parity_fail_reasons"))
    parity_fail_count = _to_int(heartbeat.get("parity_fail_count"), -1)
    if parity_fail_count != len(parity_fail_reasons):
        reasons.append("parity_fail_count_mismatch")

    strict_fail_reasons = _safe_list_str(heartbeat.get("strict_fail_reasons"))
    strict_fail_count = _to_int(heartbeat.get("strict_fail_count"), -1)
    if strict_fail_count != len(strict_fail_reasons):
        reasons.append("strict_fail_count_mismatch")

    if status == "ok" and strict_fail_count != 0:
        reasons.append("strict_fail_reasons_present_for_ok_status")
    if status == "failed" and strict_fail_count == 0:
        reasons.append("missing_strict_fail_reasons_for_failed_status")

    return _dedupe_ordered(reasons)


def read_history_entries(history_path: Path) -> list[dict[str, Any]]:
    if not history_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    raw = history_path.read_text(encoding="utf-8")
    lines = [line for line in raw.splitlines() if _safe_text(line)]
    for idx, line in enumerate(lines, start=1):
        try:
            entry = json.loads(line)
            rows.append({"line_no": idx, "malformed_line": False, "entry": _safe_obj(entry)})
        except Exception:  # noqa: BLE001
            rows.append({"line_no": idx, "malformed_line": True, "entry": {}})
    return rows


def history_has_heartbeat(rows: list[dict[str, Any]], heartbeat_id: str) -> bool:
    needle = _safe_text(heartbeat_id)
    if not needle:
        return False
    for row in rows:
        if bool(row.get("malformed_line")):
            continue
        entry = _safe_obj(row.get("entry"))
        if _safe_text(entry.get("heartbeat_id")) == needle:
            return True
    return False


def append_heartbeat(history_path: Path, heartbeat: dict[str, Any]) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(heartbeat, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    digest_path = Path(str(args.digest_json))
    if not digest_path.exists():
        print(json.dumps({"error": f"digest json not found: {digest_path}"}, ensure_ascii=False))
        return 2

    try:
        digest_payload = json.loads(digest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"invalid digest json: {exc}"}, ensure_ascii=False))
        return 3
    if not isinstance(digest_payload, dict):
        print(json.dumps({"error": "invalid digest json: root must be object"}, ensure_ascii=False))
        return 3

    heartbeat_path = Path(str(args.heartbeat_jsonl))
    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "strict": bool(args.strict),
        "input_path": str(digest_path),
        "heartbeat_path": str(heartbeat_path),
        "history_size_before": 0,
        "history_size_after": 0,
        "history_malformed_lines_before": 0,
        "appended": False,
        "duplicate_detected": False,
        "validation_errors": [],
        "strict_fail_reasons": [],
        "heartbeat": {},
        "status": "failed",
    }

    try:
        heartbeat = build_heartbeat(digest_payload, digest_path=str(digest_path))
        report["heartbeat"] = heartbeat
        report["validation_errors"] = validate_heartbeat(heartbeat)

        history_before = read_history_entries(heartbeat_path)
        report["history_size_before"] = len(history_before)
        report["history_malformed_lines_before"] = sum(1 for row in history_before if bool(row.get("malformed_line")))

        if not report["validation_errors"]:
            report["duplicate_detected"] = history_has_heartbeat(history_before, _safe_text(heartbeat.get("heartbeat_id")))
            if not report["duplicate_detected"]:
                append_heartbeat(heartbeat_path, heartbeat)
                report["appended"] = True

        report["history_size_after"] = int(report["history_size_before"]) + (1 if report["appended"] else 0)
    except Exception as exc:  # noqa: BLE001
        report["status"] = "failed"
        report["strict_fail_reasons"] = [f"runtime_error:{type(exc).__name__}"]
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        print(payload)
        out_path = Path(str(args.out).strip()) if _safe_text(args.out) else None
        if out_path is not None:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(payload + "\n", encoding="utf-8")
        return 3

    strict_fail_reasons: list[str] = []
    for reason in _safe_list_str(report.get("validation_errors")):
        strict_fail_reasons.append(f"validation:{reason}")

    heartbeat_status = _normalize_status(_safe_obj(report.get("heartbeat")).get("status"))
    if heartbeat_status == "failed":
        strict_fail_reasons.append("heartbeat_status_failed")
        strict_fail_reasons.extend(_safe_list_str(_safe_obj(report.get("heartbeat")).get("strict_fail_reasons")))
    report["strict_fail_reasons"] = _dedupe_ordered(strict_fail_reasons)

    if report["validation_errors"]:
        report["status"] = "failed"
    elif heartbeat_status == "failed":
        report["status"] = "failed"
    elif heartbeat_status == "degraded":
        report["status"] = "degraded"
    else:
        report["status"] = "ok"

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out).strip()) if _safe_text(args.out) else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and len(_safe_list_str(report.get("strict_fail_reasons"))) > 0:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
