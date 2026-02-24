#!/usr/bin/env python3
"""Machine-readable mobile/performance budget contract for /citizen.

Checks:
- UI HTML size budget
- Citizen JS companion assets total size budget
- Snapshot JSON size budget
- Interaction latency markers present in UI source (debounce + coalesced compare render)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_UI_HTML = Path("ui/citizen/index.html")
DEFAULT_UI_ASSETS = [
    Path("ui/citizen/preset_codec.js"),
    Path("ui/citizen/onboarding_funnel.js"),
    Path("ui/citizen/first_answer_accelerator.js"),
    Path("ui/citizen/unknown_explainability.js"),
    Path("ui/citizen/cross_method_stability.js"),
    Path("ui/citizen/evidence_trust_panel.js"),
]
DEFAULT_SNAPSHOT = Path("docs/gh-pages/citizen/data/citizen.json")

DEFAULT_MAX_UI_HTML_BYTES = 220_000
DEFAULT_MAX_UI_ASSETS_TOTAL_BYTES = 60_000
DEFAULT_MAX_SNAPSHOT_BYTES = 5_000_000

REQUIRED_INTERACTION_MARKERS = [
    "SEARCH_INPUT_DEBOUNCE_MS",
    "RENDER_COMPARE_SCHEDULE",
    "scheduleRenderCompare",
    "MOBILE_LATENCY_OBS_VERSION",
    "markInputLatencySampleStart",
    "commitInputLatencySample",
    'addEventListener("input", onConcernSearchInputRaw)',
    'addEventListener("input", onTopicSearchInputRaw)',
]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Citizen mobile performance budget report")
    ap.add_argument("--ui-html", default=str(DEFAULT_UI_HTML))
    ap.add_argument(
        "--ui-assets",
        default=",".join(str(p) for p in DEFAULT_UI_ASSETS),
        help="Comma-separated list of UI asset paths to include in aggregate budget",
    )
    ap.add_argument("--snapshot", default=str(DEFAULT_SNAPSHOT))
    ap.add_argument("--max-ui-html-bytes", type=int, default=DEFAULT_MAX_UI_HTML_BYTES)
    ap.add_argument("--max-ui-assets-total-bytes", type=int, default=DEFAULT_MAX_UI_ASSETS_TOTAL_BYTES)
    ap.add_argument("--max-snapshot-bytes", type=int, default=DEFAULT_MAX_SNAPSHOT_BYTES)
    ap.add_argument("--strict", action="store_true", help="Fail (exit 4) when status is failed")
    ap.add_argument("--out", default="", help="Optional JSON output path")
    return ap.parse_args(argv)


def _parse_assets_csv(raw: str) -> list[Path]:
    assets: list[Path] = []
    for token in str(raw or "").split(","):
        txt = token.strip()
        if not txt:
            continue
        assets.append(Path(txt))
    return assets


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _file_size(path: Path) -> int:
    return int(path.stat().st_size)


def build_report(
    *,
    ui_html_path: Path,
    ui_assets: list[Path],
    snapshot_path: Path,
    max_ui_html_bytes: int,
    max_ui_assets_total_bytes: int,
    max_snapshot_bytes: int,
) -> dict[str, Any]:
    html_text = _read_text(ui_html_path)
    ui_html_bytes = _file_size(ui_html_path)

    ui_asset_rows: list[dict[str, Any]] = []
    ui_assets_total_bytes = 0
    for p in ui_assets:
        size = _file_size(p)
        ui_assets_total_bytes += size
        ui_asset_rows.append(
            {
                "path": str(p),
                "bytes": int(size),
            }
        )

    snapshot_bytes = _file_size(snapshot_path)

    missing_markers = [m for m in REQUIRED_INTERACTION_MARKERS if m not in html_text]

    checks = {
        "ui_html_within_budget": bool(ui_html_bytes <= int(max_ui_html_bytes)),
        "ui_assets_total_within_budget": bool(ui_assets_total_bytes <= int(max_ui_assets_total_bytes)),
        "snapshot_within_budget": bool(snapshot_bytes <= int(max_snapshot_bytes)),
        "interaction_markers_present": bool(not missing_markers),
    }

    failure_reasons: list[str] = []
    if not checks["ui_html_within_budget"]:
        failure_reasons.append("ui_html_over_budget")
    if not checks["ui_assets_total_within_budget"]:
        failure_reasons.append("ui_assets_total_over_budget")
    if not checks["snapshot_within_budget"]:
        failure_reasons.append("snapshot_over_budget")
    if not checks["interaction_markers_present"]:
        failure_reasons.append("interaction_markers_missing")

    status = "ok" if not failure_reasons else "failed"

    return {
        "generated_at": now_utc_iso(),
        "status": status,
        "paths": {
            "ui_html": str(ui_html_path),
            "ui_assets": [str(p) for p in ui_assets],
            "snapshot": str(snapshot_path),
        },
        "metrics": {
            "ui_html_bytes": int(ui_html_bytes),
            "ui_assets_total_bytes": int(ui_assets_total_bytes),
            "snapshot_bytes": int(snapshot_bytes),
            "ui_assets_count": len(ui_assets),
            "interaction_markers_missing": missing_markers,
        },
        "thresholds": {
            "max_ui_html_bytes": int(max_ui_html_bytes),
            "max_ui_assets_total_bytes": int(max_ui_assets_total_bytes),
            "max_snapshot_bytes": int(max_snapshot_bytes),
        },
        "checks": checks,
        "failure_reasons": failure_reasons,
        "ui_assets": ui_asset_rows,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    ui_html_path = Path(str(args.ui_html).strip())
    snapshot_path = Path(str(args.snapshot).strip())
    ui_assets = _parse_assets_csv(str(args.ui_assets).strip())

    if not ui_html_path.exists():
        print(json.dumps({"error": f"ui-html not found: {ui_html_path}"}, ensure_ascii=False))
        return 2
    if not snapshot_path.exists():
        print(json.dumps({"error": f"snapshot not found: {snapshot_path}"}, ensure_ascii=False))
        return 2
    if not ui_assets:
        print(json.dumps({"error": "ui-assets list is empty"}, ensure_ascii=False))
        return 2
    missing_assets = [str(p) for p in ui_assets if not p.exists()]
    if missing_assets:
        print(json.dumps({"error": "missing ui assets", "missing": missing_assets}, ensure_ascii=False))
        return 2

    try:
        report = build_report(
            ui_html_path=ui_html_path,
            ui_assets=ui_assets,
            snapshot_path=snapshot_path,
            max_ui_html_bytes=int(args.max_ui_html_bytes),
            max_ui_assets_total_bytes=int(args.max_ui_assets_total_bytes),
            max_snapshot_bytes=int(args.max_snapshot_bytes),
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 3

    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    out_raw = str(args.out).strip()
    if out_raw:
        out_path = Path(out_raw)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and str(report.get("status") or "") == "failed":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
