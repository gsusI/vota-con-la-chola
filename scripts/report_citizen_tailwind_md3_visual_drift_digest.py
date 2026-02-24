#!/usr/bin/env python3
"""Digest for citizen Tailwind+MD3 visual drift and source/published parity."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TAILWIND_CONTRACT_JSON = Path("docs/etl/sprints/AI-OPS-96/evidence/citizen_tailwind_md3_contract_latest.json")
DEFAULT_SOURCE_TOKENS = Path("ui/citizen/tailwind_md3.tokens.json")
DEFAULT_SOURCE_CSS = Path("ui/citizen/tailwind_md3.generated.css")
DEFAULT_SOURCE_UI_HTML = Path("ui/citizen/index.html")
DEFAULT_PUBLISHED_TOKENS = Path("docs/gh-pages/citizen/tailwind_md3.tokens.json")
DEFAULT_PUBLISHED_DATA_TOKENS = Path("docs/gh-pages/citizen/data/tailwind_md3.tokens.json")
DEFAULT_PUBLISHED_CSS = Path("docs/gh-pages/citizen/tailwind_md3.generated.css")
DEFAULT_PUBLISHED_UI_HTML = Path("docs/gh-pages/citizen/index.html")

HTML_COMPONENT_MARKERS = ("md3-card", "md3-chip", "md3-button", "md3-tab")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _to_bool(value: Any) -> bool:
    return bool(value)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return int(default)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _first_line_diff(a_text: str, b_text: str) -> tuple[int, str, str]:
    a_lines = a_text.splitlines()
    b_lines = b_text.splitlines()
    total = max(len(a_lines), len(b_lines))
    for idx in range(total):
        a_line = a_lines[idx] if idx < len(a_lines) else ""
        b_line = b_lines[idx] if idx < len(b_lines) else ""
        if a_line != b_line:
            return idx + 1, a_line, b_line
    return 0, "", ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Citizen Tailwind+MD3 visual drift digest")
    p.add_argument(
        "--tailwind-contract-json",
        default=str(DEFAULT_TAILWIND_CONTRACT_JSON),
        help=f"Tailwind contract JSON path (default: {DEFAULT_TAILWIND_CONTRACT_JSON})",
    )
    p.add_argument("--source-tokens", default=str(DEFAULT_SOURCE_TOKENS))
    p.add_argument("--source-css", default=str(DEFAULT_SOURCE_CSS))
    p.add_argument("--source-ui-html", default=str(DEFAULT_SOURCE_UI_HTML))
    p.add_argument("--published-tokens", default=str(DEFAULT_PUBLISHED_TOKENS))
    p.add_argument("--published-data-tokens", default=str(DEFAULT_PUBLISHED_DATA_TOKENS))
    p.add_argument("--published-css", default=str(DEFAULT_PUBLISHED_CSS))
    p.add_argument("--published-ui-html", default=str(DEFAULT_PUBLISHED_UI_HTML))
    p.add_argument("--strict", action="store_true", help="Exit with code 4 when strict checks fail.")
    p.add_argument("--strict-require-complete", action="store_true", help="With --strict, also fail on degraded status.")
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"expected object JSON: {path}")
    return obj


def _count_markers(text: str) -> dict[str, int]:
    return {marker: text.count(marker) for marker in HTML_COMPONENT_MARKERS}


def _compare_text_pair(source_path: Path, published_path: Path) -> dict[str, Any]:
    source_exists = source_path.exists()
    published_exists = published_path.exists()
    result: dict[str, Any] = {
        "source_path": str(source_path),
        "published_path": str(published_path),
        "source_exists": bool(source_exists),
        "published_exists": bool(published_exists),
        "source_bytes": 0,
        "published_bytes": 0,
        "source_sha256": "",
        "published_sha256": "",
        "parity_ok": False,
        "first_diff_line": 0,
        "first_diff_source_line": "",
        "first_diff_published_line": "",
    }

    if not source_exists or not published_exists:
        return result

    source_text = _read_text(source_path)
    published_text = _read_text(published_path)
    result["source_bytes"] = len(source_text.encode("utf-8"))
    result["published_bytes"] = len(published_text.encode("utf-8"))
    result["source_sha256"] = _sha256_text(source_text)
    result["published_sha256"] = _sha256_text(published_text)
    result["parity_ok"] = source_text == published_text
    if not result["parity_ok"]:
        line_no, source_line, published_line = _first_line_diff(source_text, published_text)
        result["first_diff_line"] = int(line_no)
        result["first_diff_source_line"] = source_line
        result["first_diff_published_line"] = published_line
    return result


def build_drift_digest(
    *,
    tailwind_contract_path: Path,
    source_tokens_path: Path,
    source_css_path: Path,
    source_ui_html_path: Path,
    published_tokens_path: Path,
    published_data_tokens_path: Path,
    published_css_path: Path,
    published_ui_html_path: Path,
) -> dict[str, Any]:
    contract_exists = tailwind_contract_path.exists()
    contract = _read_json(tailwind_contract_path) if contract_exists else {}
    contract_checks = _safe_obj(contract.get("checks"))
    contract_metrics = _safe_obj(contract.get("metrics"))

    contract_status = _safe_text(contract.get("status")) or "failed"
    contract_failed_reasons = list(contract.get("failure_reasons") or []) if isinstance(contract.get("failure_reasons"), list) else []
    contract_checks_all_ok = len(contract_checks) > 0 and all(_to_bool(v) for v in contract_checks.values())

    tokens_parity = _compare_text_pair(source_tokens_path, published_tokens_path)
    tokens_data_parity = _compare_text_pair(source_tokens_path, published_data_tokens_path)
    css_parity = _compare_text_pair(source_css_path, published_css_path)
    ui_parity = _compare_text_pair(source_ui_html_path, published_ui_html_path)

    source_html_text = _read_text(source_ui_html_path) if source_ui_html_path.exists() else ""
    published_html_text = _read_text(published_ui_html_path) if published_ui_html_path.exists() else ""
    source_marker_counts = _count_markers(source_html_text) if source_html_text else {m: 0 for m in HTML_COMPONENT_MARKERS}
    published_marker_counts = _count_markers(published_html_text) if published_html_text else {m: 0 for m in HTML_COMPONENT_MARKERS}

    contract_marker_counts = {
        "md3-card": _to_int(contract_metrics.get("md3_card_markers"), -1),
        "md3-chip": _to_int(contract_metrics.get("md3_chip_markers"), -1),
        "md3-button": _to_int(contract_metrics.get("md3_button_markers"), -1),
        "md3-tab": _to_int(contract_metrics.get("md3_tab_markers"), -1),
    }

    checks = {
        "tailwind_contract_exists": bool(contract_exists),
        "tailwind_contract_status_ok": contract_status == "ok",
        "tailwind_contract_checks_ok": bool(contract_checks_all_ok),
        "tokens_parity_ok": bool(tokens_parity.get("parity_ok")),
        "tokens_data_parity_ok": bool(tokens_data_parity.get("parity_ok")),
        "css_parity_ok": bool(css_parity.get("parity_ok")),
        "ui_html_parity_ok": bool(ui_parity.get("parity_ok")),
        "source_published_marker_counts_match": source_marker_counts == published_marker_counts,
        "source_markers_match_contract_snapshot": True,
        "published_markers_match_contract_snapshot": True,
    }

    for marker in HTML_COMPONENT_MARKERS:
        expected = _to_int(contract_marker_counts.get(marker), -1)
        source_val = _to_int(source_marker_counts.get(marker), 0)
        published_val = _to_int(published_marker_counts.get(marker), 0)
        if expected < 0:
            checks["source_markers_match_contract_snapshot"] = False
            checks["published_markers_match_contract_snapshot"] = False
            break
        if source_val != expected:
            checks["source_markers_match_contract_snapshot"] = False
        if published_val != expected:
            checks["published_markers_match_contract_snapshot"] = False

    strict_fail_reasons: list[str] = []
    if not checks["tailwind_contract_exists"]:
        strict_fail_reasons.append("tailwind_contract_missing")
    if not checks["tailwind_contract_status_ok"]:
        strict_fail_reasons.append("tailwind_contract_failed")
    if not checks["tailwind_contract_checks_ok"]:
        strict_fail_reasons.append("tailwind_contract_checks_failed")
    if not checks["tokens_parity_ok"]:
        strict_fail_reasons.append("tokens_parity_mismatch")
    if not checks["tokens_data_parity_ok"]:
        strict_fail_reasons.append("tokens_data_parity_mismatch")
    if not checks["css_parity_ok"]:
        strict_fail_reasons.append("css_parity_mismatch")
    if not checks["ui_html_parity_ok"]:
        strict_fail_reasons.append("ui_html_parity_mismatch")
    if not checks["source_published_marker_counts_match"]:
        strict_fail_reasons.append("source_published_marker_counts_mismatch")
    if not checks["source_markers_match_contract_snapshot"]:
        strict_fail_reasons.append("source_markers_mismatch_contract_snapshot")
    if not checks["published_markers_match_contract_snapshot"]:
        strict_fail_reasons.append("published_markers_mismatch_contract_snapshot")

    status = "ok"
    if strict_fail_reasons:
        status = "failed"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "paths": {
            "tailwind_contract_json": str(tailwind_contract_path),
            "source_tokens": str(source_tokens_path),
            "source_css": str(source_css_path),
            "source_ui_html": str(source_ui_html_path),
            "published_tokens": str(published_tokens_path),
            "published_data_tokens": str(published_data_tokens_path),
            "published_css": str(published_css_path),
            "published_ui_html": str(published_ui_html_path),
        },
        "tailwind_contract": {
            "status": contract_status,
            "failure_reasons": contract_failed_reasons,
            "checks_all_ok": bool(contract_checks_all_ok),
        },
        "parity": {
            "tokens": tokens_parity,
            "tokens_data": tokens_data_parity,
            "css": css_parity,
            "ui_html": ui_parity,
        },
        "markers": {
            "source": source_marker_counts,
            "published": published_marker_counts,
            "contract_snapshot": contract_marker_counts,
        },
        "checks": checks,
        "strict_fail_reasons": strict_fail_reasons,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    tailwind_contract_path = Path(str(args.tailwind_contract_json).strip())
    source_tokens_path = Path(str(args.source_tokens).strip())
    source_css_path = Path(str(args.source_css).strip())
    source_ui_html_path = Path(str(args.source_ui_html).strip())
    published_tokens_path = Path(str(args.published_tokens).strip())
    published_data_tokens_path = Path(str(args.published_data_tokens).strip())
    published_css_path = Path(str(args.published_css).strip())
    published_ui_html_path = Path(str(args.published_ui_html).strip())

    try:
        report = build_drift_digest(
            tailwind_contract_path=tailwind_contract_path,
            source_tokens_path=source_tokens_path,
            source_css_path=source_css_path,
            source_ui_html_path=source_ui_html_path,
            published_tokens_path=published_tokens_path,
            published_data_tokens_path=published_data_tokens_path,
            published_css_path=published_css_path,
            published_ui_html_path=published_ui_html_path,
        )
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"runtime_error:{type(exc).__name__}:{exc}"}, ensure_ascii=False))
        return 3

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out).strip()) if _safe_text(args.out) else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    strict_reasons = list(report.get("strict_fail_reasons") or [])
    if bool(args.strict) and strict_reasons:
        return 4
    if bool(args.strict) and bool(args.strict_require_complete) and str(report.get("status") or "") != "ok":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
