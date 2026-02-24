#!/usr/bin/env python3
"""Validate liberty_proportionality_seed_v1 JSON contract."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_REQUIRED_KEYS = ("schema_version", "generated_at", "methodology", "reviews")
METHODOLOGY_REQUIRED_KEYS = ("method_version", "method_label", "weights")
WEIGHT_KEYS = (
    "necessity_score",
    "observed_effectiveness_score",
    "alternatives_less_restrictive_considered",
    "objective_defined",
    "indicator_defined",
    "sunset_review_present",
)
REVIEW_REQUIRED_KEYS = (
    "fragment_id",
    "objective_defined",
    "indicator_defined",
    "alternatives_less_restrictive_considered",
    "sunset_review_present",
    "observed_effectiveness_score",
    "necessity_score",
    "assessment_label",
    "source_url",
)
ALLOWED_ASSESSMENT_LABELS = {"supported", "weak", "insufficient_evidence"}
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


def _is_binary(v: Any) -> bool:
    token = _norm(v)
    return token in {"0", "1"}


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
        "reviews_total": 0,
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
    if schema_version != "liberty_proportionality_seed_v1":
        _add_error(
            errors,
            code="invalid_schema_version",
            path="$.schema_version",
            message=f"expected 'liberty_proportionality_seed_v1', got {schema_version!r}",
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

    weights = methodology.get("weights")
    if not isinstance(weights, dict):
        _add_error(errors, code="invalid_weights", path="$.methodology.weights", message="weights must be object", max_errors=max_errors)
        weights = {}
    weight_sum = 0.0
    for key in WEIGHT_KEYS:
        if key not in weights:
            _add_error(errors, code="missing_weight_key", path="$.methodology.weights", message=f"missing weight key: {key}", max_errors=max_errors)
            continue
        if not _is_number(weights.get(key)):
            _add_error(errors, code="invalid_weight", path=f"$.methodology.weights.{key}", message="weight must be numeric", max_errors=max_errors)
            continue
        val = float(weights.get(key))
        if val < 0:
            _add_error(errors, code="negative_weight", path=f"$.methodology.weights.{key}", message="weight must be >= 0", max_errors=max_errors)
        weight_sum += val
    if abs(weight_sum - 1.0) > 1e-6:
        _add_error(errors, code="invalid_weight_sum", path="$.methodology.weights", message=f"weights must sum to 1.0, got {weight_sum}", max_errors=max_errors)

    reviews = raw.get("reviews")
    if not isinstance(reviews, list) or not reviews:
        _add_error(errors, code="invalid_reviews", path="$.reviews", message="reviews must be non-empty array", max_errors=max_errors)
        reviews = []
    out["reviews_total"] = len(reviews)

    seen_fragments: set[str] = set()
    for i, row in enumerate(reviews):
        path = f"$.reviews[{i}]"
        if not isinstance(row, dict):
            _add_error(errors, code="review_not_object", path=path, message="row must be object", max_errors=max_errors)
            continue
        for key in REVIEW_REQUIRED_KEYS:
            if key not in row:
                _add_error(errors, code="missing_review_key", path=path, message=f"missing required key: {key}", max_errors=max_errors)
            elif key in {"fragment_id", "assessment_label", "source_url"} and _norm(row.get(key)) == "":
                _add_error(errors, code="missing_review_key", path=path, message=f"missing required key: {key}", max_errors=max_errors)
        fragment_id = _norm(row.get("fragment_id"))
        if fragment_id in seen_fragments:
            _add_error(errors, code="duplicate_fragment_id", path=f"{path}.fragment_id", message=f"duplicate fragment_id: {fragment_id}", max_errors=max_errors)
        seen_fragments.add(fragment_id)

        for key in ("objective_defined", "indicator_defined", "alternatives_less_restrictive_considered", "sunset_review_present"):
            if not _is_binary(row.get(key)):
                _add_error(errors, code="invalid_binary_field", path=f"{path}.{key}", message=f"{key} must be 0 or 1", max_errors=max_errors)
        for key in ("observed_effectiveness_score", "necessity_score", "confidence"):
            if _norm(row.get(key)) and not _in_01(row.get(key)):
                _add_error(errors, code="invalid_score_field", path=f"{path}.{key}", message=f"{key} must be numeric in [0,1]", max_errors=max_errors)
        label = _norm(row.get("assessment_label"))
        if label and label not in ALLOWED_ASSESSMENT_LABELS:
            _add_error(
                errors,
                code="invalid_assessment_label",
                path=f"{path}.assessment_label",
                message=f"assessment_label must be one of {sorted(ALLOWED_ASSESSMENT_LABELS)}, got {label!r}",
                max_errors=max_errors,
            )
        if _norm(row.get("source_url")) and not HTTP_RE.match(_norm(row.get("source_url"))):
            _add_error(errors, code="invalid_source_url", path=f"{path}.source_url", message=f"source_url must be http/https URL, got {_norm(row.get('source_url'))!r}", max_errors=max_errors)

    out["errors"] = errors
    out["warnings"] = warnings
    out["errors_count"] = len(errors)
    out["warnings_count"] = len(warnings)
    out["valid"] = len(errors) == 0
    return out


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate liberty_proportionality_seed_v1 JSON")
    ap.add_argument("--seed", default="etl/data/seeds/liberty_proportionality_seed_v1.json")
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
