#!/usr/bin/env python3
"""Validate liberty_enforcement_seed_v1 JSON contract."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_REQUIRED_KEYS = ("schema_version", "generated_at", "methodology", "observations")
METHODOLOGY_REQUIRED_KEYS = ("method_version", "method_label", "thresholds")
THRESHOLD_KEYS = (
    "sanction_rate_spread_pct",
    "annulment_rate_spread_pp",
    "resolution_delay_spread_days",
)
OBS_REQUIRED_KEYS = (
    "fragment_id",
    "territory_key",
    "period_date",
    "sanction_rate_per_1000",
    "annulment_rate",
    "resolution_delay_p90_days",
    "source_url",
)
HTTP_RE = re.compile(r"^https?://")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _is_number(v: Any) -> bool:
    try:
        float(v)
        return True
    except Exception:
        return False


def _in_01(v: Any) -> bool:
    if not _is_number(v):
        return False
    token = float(v)
    return 0.0 <= token <= 1.0


def _add_error(errors: list[dict[str, str]], *, code: str, path: str, message: str, max_errors: int) -> None:
    if len(errors) >= int(max_errors):
        return
    errors.append({"code": code, "path": path, "message": message})


def validate_seed(seed_path: Path, *, max_errors: int = 200) -> dict[str, Any]:
    out: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "seed_path": str(seed_path),
        "valid": False,
        "schema_version": "",
        "method_version": "",
        "observations_total": 0,
        "errors_count": 0,
        "warnings_count": 0,
        "errors": [],
        "warnings": [],
    }
    if not seed_path.exists():
        out["errors"] = [{"code": "seed_not_found", "path": "$", "message": f"Seed not found: {seed_path}"}]
        out["errors_count"] = 1
        return out

    try:
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
    except Exception as exc:
        out["errors"] = [{"code": "invalid_json", "path": "$", "message": str(exc)}]
        out["errors_count"] = 1
        return out

    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    if not isinstance(raw, dict):
        _add_error(errors, code="root_not_object", path="$", message="root must be object", max_errors=max_errors)
        out["errors"] = errors
        out["errors_count"] = len(errors)
        return out

    for key in ROOT_REQUIRED_KEYS:
        if key not in raw:
            _add_error(errors, code="missing_root_key", path="$", message=f"missing required root key: {key}", max_errors=max_errors)

    schema_version = _norm(raw.get("schema_version"))
    out["schema_version"] = schema_version
    if schema_version != "liberty_enforcement_seed_v1":
        _add_error(
            errors,
            code="invalid_schema_version",
            path="$.schema_version",
            message=f"expected 'liberty_enforcement_seed_v1', got {schema_version!r}",
            max_errors=max_errors,
        )

    generated_at = _norm(raw.get("generated_at"))
    if generated_at:
        try:
            datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError:
            _add_error(errors, code="invalid_generated_at", path="$.generated_at", message=f"invalid ISO datetime: {generated_at!r}", max_errors=max_errors)

    methodology = raw.get("methodology")
    if not isinstance(methodology, dict):
        _add_error(errors, code="invalid_methodology", path="$.methodology", message="methodology must be object", max_errors=max_errors)
        methodology = {}
    for key in METHODOLOGY_REQUIRED_KEYS:
        if _norm(methodology.get(key)) == "":
            _add_error(errors, code="missing_methodology_key", path="$.methodology", message=f"missing required key: {key}", max_errors=max_errors)
    out["method_version"] = _norm(methodology.get("method_version"))

    thresholds = methodology.get("thresholds")
    if not isinstance(thresholds, dict):
        _add_error(errors, code="invalid_thresholds", path="$.methodology.thresholds", message="thresholds must be object", max_errors=max_errors)
        thresholds = {}
    for key in THRESHOLD_KEYS:
        if key not in thresholds:
            _add_error(errors, code="missing_threshold_key", path="$.methodology.thresholds", message=f"missing threshold key: {key}", max_errors=max_errors)
            continue
        if not _is_number(thresholds.get(key)):
            _add_error(errors, code="invalid_threshold", path=f"$.methodology.thresholds.{key}", message="threshold must be numeric", max_errors=max_errors)
            continue
        if float(thresholds.get(key)) < 0.0:
            _add_error(errors, code="negative_threshold", path=f"$.methodology.thresholds.{key}", message="threshold must be >= 0", max_errors=max_errors)

    observations = raw.get("observations")
    if not isinstance(observations, list) or not observations:
        _add_error(errors, code="invalid_observations", path="$.observations", message="observations must be non-empty array", max_errors=max_errors)
        observations = []
    out["observations_total"] = len(observations)

    seen_keys: set[str] = set()
    for i, row in enumerate(observations):
        path = f"$.observations[{i}]"
        if not isinstance(row, dict):
            _add_error(errors, code="observation_not_object", path=path, message="row must be object", max_errors=max_errors)
            continue
        for key in OBS_REQUIRED_KEYS:
            if key not in row or _norm(row.get(key)) == "":
                _add_error(errors, code="missing_observation_key", path=path, message=f"missing required key: {key}", max_errors=max_errors)

        dedupe_key = "|".join(
            [
                _norm(row.get("fragment_id")),
                _norm(row.get("territory_key")),
                _norm(row.get("period_date")),
            ]
        )
        if dedupe_key in seen_keys:
            _add_error(errors, code="duplicate_observation_key", path=path, message=f"duplicate observation key tuple: {dedupe_key}", max_errors=max_errors)
        seen_keys.add(dedupe_key)

        for key in ("sanction_rate_per_1000", "resolution_delay_p90_days"):
            if _norm(row.get(key)) and (not _is_number(row.get(key)) or float(row.get(key)) < 0.0):
                _add_error(errors, code="invalid_nonnegative_metric", path=f"{path}.{key}", message=f"{key} must be numeric >= 0", max_errors=max_errors)
        if _norm(row.get("annulment_rate")) and not _in_01(row.get("annulment_rate")):
            _add_error(errors, code="invalid_annulment_rate", path=f"{path}.annulment_rate", message="annulment_rate must be numeric in [0,1]", max_errors=max_errors)
        if _norm(row.get("sample_size")):
            if not _is_number(row.get("sample_size")) or int(float(row.get("sample_size"))) < 0:
                _add_error(errors, code="invalid_sample_size", path=f"{path}.sample_size", message="sample_size must be integer >= 0", max_errors=max_errors)
        if _norm(row.get("source_url")) and not HTTP_RE.match(_norm(row.get("source_url"))):
            _add_error(errors, code="invalid_source_url", path=f"{path}.source_url", message=f"source_url must be http/https URL, got {_norm(row.get('source_url'))!r}", max_errors=max_errors)

    out["errors"] = errors
    out["warnings"] = warnings
    out["errors_count"] = len(errors)
    out["warnings_count"] = len(warnings)
    out["valid"] = len(errors) == 0
    return out


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate liberty_enforcement_seed_v1 JSON")
    ap.add_argument("--seed", default="etl/data/seeds/liberty_enforcement_seed_v1.json")
    ap.add_argument("--out", default="")
    ap.add_argument("--max-errors", type=int, default=200)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    report = validate_seed(Path(args.seed), max_errors=int(args.max_errors))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if bool(report.get("valid")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
