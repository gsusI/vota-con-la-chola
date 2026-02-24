#!/usr/bin/env python3
"""Machine-readable contract for citizen Tailwind+MD3 build slice."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TOKENS = Path("ui/citizen/tailwind_md3.tokens.json")
DEFAULT_GENERATED_CSS = Path("ui/citizen/tailwind_md3.generated.css")
DEFAULT_UI_HTML = Path("ui/citizen/index.html")
DEFAULT_MAX_GENERATED_CSS_BYTES = 40_000

REQUIRED_TOKEN_SECTIONS = ("schema_version", "colors", "radii", "shadows", "spacing", "typography")
REQUIRED_CSS_MARKERS = (
    "generated_by=build_citizen_tailwind_md3_css.py",
    "--md3-color-primary:",
    ".md3-card",
    ".md3-chip",
    ".md3-button",
    ".md3-tab",
    ".tw-bg-surface",
)
REQUIRED_HTML_MARKERS = (
    "./tailwind_md3.generated.css",
    "md3-card",
    "md3-chip",
    "md3-button",
    "md3-tab",
)
DEFAULT_MIN_MD3_CARD_MARKERS = 1
DEFAULT_MIN_MD3_CHIP_MARKERS = 1
DEFAULT_MIN_MD3_BUTTON_MARKERS = 1
DEFAULT_MIN_MD3_TAB_MARKERS = 1


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Citizen Tailwind+MD3 contract report")
    ap.add_argument("--tokens", default=str(DEFAULT_TOKENS))
    ap.add_argument("--generated-css", default=str(DEFAULT_GENERATED_CSS))
    ap.add_argument("--ui-html", default=str(DEFAULT_UI_HTML))
    ap.add_argument("--max-generated-css-bytes", type=int, default=DEFAULT_MAX_GENERATED_CSS_BYTES)
    ap.add_argument("--min-md3-card-markers", type=int, default=DEFAULT_MIN_MD3_CARD_MARKERS)
    ap.add_argument("--min-md3-chip-markers", type=int, default=DEFAULT_MIN_MD3_CHIP_MARKERS)
    ap.add_argument("--min-md3-button-markers", type=int, default=DEFAULT_MIN_MD3_BUTTON_MARKERS)
    ap.add_argument("--min-md3-tab-markers", type=int, default=DEFAULT_MIN_MD3_TAB_MARKERS)
    ap.add_argument("--strict", action="store_true", help="Fail (exit 4) when status is failed")
    ap.add_argument("--out", default="", help="Optional JSON output path")
    return ap.parse_args(argv)


def _read_json(path: Path) -> dict[str, Any]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("expected JSON object")
    return obj


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _file_size(path: Path) -> int:
    return int(path.stat().st_size)


def _count_marker(text: str, marker: str) -> int:
    return int(str(text).count(str(marker)))


def build_report(
    *,
    tokens_path: Path,
    generated_css_path: Path,
    ui_html_path: Path,
    max_generated_css_bytes: int,
    min_md3_card_markers: int,
    min_md3_chip_markers: int,
    min_md3_button_markers: int,
    min_md3_tab_markers: int,
) -> dict[str, Any]:
    tokens = _read_json(tokens_path)
    css_text = _read_text(generated_css_path)
    html_text = _read_text(ui_html_path)

    token_missing_sections = [k for k in REQUIRED_TOKEN_SECTIONS if k not in tokens]
    token_schema_ok = str(tokens.get("schema_version") or "") == "md3-tailwind-v1"
    css_missing_markers = [m for m in REQUIRED_CSS_MARKERS if m not in css_text]
    html_missing_markers = [m for m in REQUIRED_HTML_MARKERS if m not in html_text]
    generated_css_bytes = _file_size(generated_css_path)
    md3_card_markers = _count_marker(html_text, "md3-card")
    md3_chip_markers = _count_marker(html_text, "md3-chip")
    md3_button_markers = _count_marker(html_text, "md3-button")
    md3_tab_markers = _count_marker(html_text, "md3-tab")

    checks = {
        "token_sections_present": bool(not token_missing_sections),
        "token_schema_version_valid": bool(token_schema_ok),
        "generated_css_within_budget": bool(generated_css_bytes <= int(max_generated_css_bytes)),
        "generated_css_markers_present": bool(not css_missing_markers),
        "ui_html_markers_present": bool(not html_missing_markers),
        "md3_card_markers_meet_minimum": bool(md3_card_markers >= int(min_md3_card_markers)),
        "md3_chip_markers_meet_minimum": bool(md3_chip_markers >= int(min_md3_chip_markers)),
        "md3_button_markers_meet_minimum": bool(md3_button_markers >= int(min_md3_button_markers)),
        "md3_tab_markers_meet_minimum": bool(md3_tab_markers >= int(min_md3_tab_markers)),
    }

    failure_reasons: list[str] = []
    if not checks["token_sections_present"]:
        failure_reasons.append("token_sections_missing")
    if not checks["token_schema_version_valid"]:
        failure_reasons.append("token_schema_invalid")
    if not checks["generated_css_within_budget"]:
        failure_reasons.append("generated_css_over_budget")
    if not checks["generated_css_markers_present"]:
        failure_reasons.append("generated_css_markers_missing")
    if not checks["ui_html_markers_present"]:
        failure_reasons.append("ui_html_markers_missing")
    if not checks["md3_card_markers_meet_minimum"]:
        failure_reasons.append("md3_card_markers_below_minimum")
    if not checks["md3_chip_markers_meet_minimum"]:
        failure_reasons.append("md3_chip_markers_below_minimum")
    if not checks["md3_button_markers_meet_minimum"]:
        failure_reasons.append("md3_button_markers_below_minimum")
    if not checks["md3_tab_markers_meet_minimum"]:
        failure_reasons.append("md3_tab_markers_below_minimum")

    status = "ok" if not failure_reasons else "failed"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "paths": {
            "tokens": str(tokens_path),
            "generated_css": str(generated_css_path),
            "ui_html": str(ui_html_path),
        },
        "metrics": {
            "generated_css_bytes": generated_css_bytes,
            "token_colors_count": len(tokens.get("colors") or {}) if isinstance(tokens.get("colors"), dict) else 0,
            "token_spacing_count": len(tokens.get("spacing") or {}) if isinstance(tokens.get("spacing"), dict) else 0,
            "token_missing_sections": token_missing_sections,
            "generated_css_missing_markers": css_missing_markers,
            "ui_html_missing_markers": html_missing_markers,
            "md3_card_markers": md3_card_markers,
            "md3_chip_markers": md3_chip_markers,
            "md3_button_markers": md3_button_markers,
            "md3_tab_markers": md3_tab_markers,
        },
        "thresholds": {
            "max_generated_css_bytes": int(max_generated_css_bytes),
            "min_md3_card_markers": int(min_md3_card_markers),
            "min_md3_chip_markers": int(min_md3_chip_markers),
            "min_md3_button_markers": int(min_md3_button_markers),
            "min_md3_tab_markers": int(min_md3_tab_markers),
        },
        "checks": checks,
        "failure_reasons": failure_reasons,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    tokens_path = Path(str(args.tokens).strip())
    generated_css_path = Path(str(args.generated_css).strip())
    ui_html_path = Path(str(args.ui_html).strip())

    if not tokens_path.exists():
        print(json.dumps({"error": f"tokens not found: {tokens_path}"}, ensure_ascii=False))
        return 2
    if not generated_css_path.exists():
        print(json.dumps({"error": f"generated-css not found: {generated_css_path}"}, ensure_ascii=False))
        return 2
    if not ui_html_path.exists():
        print(json.dumps({"error": f"ui-html not found: {ui_html_path}"}, ensure_ascii=False))
        return 2

    try:
        report = build_report(
            tokens_path=tokens_path,
            generated_css_path=generated_css_path,
            ui_html_path=ui_html_path,
            max_generated_css_bytes=int(args.max_generated_css_bytes),
            min_md3_card_markers=int(args.min_md3_card_markers),
            min_md3_chip_markers=int(args.min_md3_chip_markers),
            min_md3_button_markers=int(args.min_md3_button_markers),
            min_md3_tab_markers=int(args.min_md3_tab_markers),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 3

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out).strip()) if str(args.out).strip() else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and str(report.get("status") or "") == "failed":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
