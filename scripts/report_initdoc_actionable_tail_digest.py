#!/usr/bin/env python3
"""Compact digest for initiative-doc actionable-tail contract."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Initiative-doc actionable-tail digest report")
    p.add_argument(
        "--contract-json",
        required=True,
        help="Path to JSON emitted by scripts/report_initdoc_actionable_tail_contract.py",
    )
    p.add_argument(
        "--max-actionable-missing",
        type=int,
        default=0,
        help="Threshold for actionable_missing (default: 0)",
    )
    p.add_argument(
        "--max-actionable-missing-pct",
        type=float,
        default=0.0,
        help="Threshold for actionable_missing_pct (default: 0)",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 4 when digest status is failed.",
    )
    p.add_argument("--out", default="", help="Optional JSON output path")
    return p.parse_args(argv)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:  # noqa: BLE001
        return int(default)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:  # noqa: BLE001
        return float(default)


def build_digest(
    contract: dict[str, Any],
    *,
    max_actionable_missing: int,
    max_actionable_missing_pct: float,
) -> dict[str, Any]:
    total_missing = _to_int(contract.get("total_missing"), 0)
    redundant_missing = _to_int(contract.get("redundant_missing"), 0)
    actionable_missing = _to_int(contract.get("actionable_missing"), 0)
    fallback_pct = (float(actionable_missing) / float(total_missing)) if total_missing > 0 else 0.0
    actionable_missing_pct = _to_float(contract.get("actionable_missing_pct"), fallback_pct)

    checks = {
        "actionable_queue_empty": actionable_missing == 0,
        "actionable_missing_within_threshold": actionable_missing <= int(max_actionable_missing),
        "actionable_missing_pct_within_threshold": actionable_missing_pct <= float(max_actionable_missing_pct),
    }

    strict_fail_reasons: list[str] = []
    if not checks["actionable_missing_within_threshold"]:
        strict_fail_reasons.append(
            f"actionable_missing_exceeds_threshold:{actionable_missing}>{int(max_actionable_missing)}",
        )
    if not checks["actionable_missing_pct_within_threshold"]:
        strict_fail_reasons.append(
            f"actionable_missing_pct_exceeds_threshold:{actionable_missing_pct:.6f}>{float(max_actionable_missing_pct):.6f}",
        )

    if strict_fail_reasons:
        status = "failed"
    elif not checks["actionable_queue_empty"]:
        status = "degraded"
    else:
        status = "ok"

    return {
        "generated_at": now_utc_iso(),
        "contract_generated_at": str(contract.get("generated_at") or ""),
        "initiative_source_ids": list(contract.get("initiative_source_ids") or []),
        "status": status,
        "totals": {
            "total_missing": int(total_missing),
            "redundant_missing": int(redundant_missing),
            "actionable_missing": int(actionable_missing),
            "actionable_missing_pct": round(float(actionable_missing_pct), 6),
        },
        "thresholds": {
            "max_actionable_missing": int(max_actionable_missing),
            "max_actionable_missing_pct": float(max_actionable_missing_pct),
        },
        "checks": checks,
        "strict_fail_reasons": strict_fail_reasons,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    contract_path = Path(str(args.contract_json))
    if not contract_path.exists():
        print(json.dumps({"error": f"contract json not found: {contract_path}"}, ensure_ascii=False))
        return 2

    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": f"invalid contract json: {exc}"}, ensure_ascii=False))
        return 3

    if not isinstance(contract, dict):
        print(json.dumps({"error": "invalid contract json: root must be object"}, ensure_ascii=False))
        return 3

    digest = build_digest(
        contract,
        max_actionable_missing=int(args.max_actionable_missing or 0),
        max_actionable_missing_pct=float(args.max_actionable_missing_pct or 0.0),
    )

    payload = json.dumps(digest, ensure_ascii=False, indent=2)
    print(payload)

    out_path = Path(str(args.out or "").strip()) if str(args.out or "").strip() else None
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")

    if bool(args.strict) and str(digest.get("status") or "") == "failed":
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
