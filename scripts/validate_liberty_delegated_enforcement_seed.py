#!/usr/bin/env python3
"""Validate liberty_delegated_enforcement_seed_v1 JSON contract."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_REQUIRED_KEYS = ("schema_version", "generated_at", "methodology", "links")
METHODOLOGY_REQUIRED_KEYS = ("method_version", "method_label", "rules")
RULE_KEYS = (
    "target_fragment_coverage_min",
    "designated_actor_coverage_min",
    "enforcement_evidence_coverage_min",
)
LINK_REQUIRED_KEYS = (
    "fragment_id",
    "delegating_actor_label",
    "delegated_institution_label",
    "enforcement_action_label",
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
        "links_total": 0,
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
    if schema_version != "liberty_delegated_enforcement_seed_v1":
        _add_error(
            errors,
            code="invalid_schema_version",
            path="$.schema_version",
            message=f"expected 'liberty_delegated_enforcement_seed_v1', got {schema_version!r}",
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

    rules = methodology.get("rules")
    if not isinstance(rules, dict):
        _add_error(errors, code="invalid_rules", path="$.methodology.rules", message="rules must be object", max_errors=max_errors)
        rules = {}
    for key in RULE_KEYS:
        if key not in rules:
            _add_error(errors, code="missing_rule_key", path="$.methodology.rules", message=f"missing rule key: {key}", max_errors=max_errors)
            continue
        if not _in_01(rules.get(key)):
            _add_error(errors, code="invalid_rule", path=f"$.methodology.rules.{key}", message=f"{key} must be numeric in [0,1]", max_errors=max_errors)

    links = raw.get("links")
    if not isinstance(links, list) or not links:
        _add_error(errors, code="invalid_links", path="$.links", message="links must be non-empty array", max_errors=max_errors)
        links = []
    out["links_total"] = len(links)

    seen_keys: set[str] = set()
    for i, row in enumerate(links):
        path = f"$.links[{i}]"
        if not isinstance(row, dict):
            _add_error(errors, code="link_not_object", path=path, message="row must be object", max_errors=max_errors)
            continue
        for key in LINK_REQUIRED_KEYS:
            if key not in row or _norm(row.get(key)) == "":
                _add_error(errors, code="missing_link_key", path=path, message=f"missing required key: {key}", max_errors=max_errors)

        dedupe_key = "|".join(
            [
                _norm(row.get("fragment_id")),
                _norm(row.get("delegating_actor_label")),
                _norm(row.get("delegated_institution_label")),
                _norm(row.get("designated_actor_label")),
                _norm(row.get("source_url")),
            ]
        )
        if dedupe_key in seen_keys:
            _add_error(errors, code="duplicate_link", path=path, message=f"duplicate link tuple: {dedupe_key}", max_errors=max_errors)
        seen_keys.add(dedupe_key)

        if _norm(row.get("chain_confidence")) and not _in_01(row.get("chain_confidence")):
            _add_error(errors, code="invalid_chain_confidence", path=f"{path}.chain_confidence", message="chain_confidence must be numeric in [0,1]", max_errors=max_errors)
        if _norm(row.get("source_url")) and not HTTP_RE.match(_norm(row.get("source_url"))):
            _add_error(errors, code="invalid_source_url", path=f"{path}.source_url", message=f"source_url must be http/https URL, got {_norm(row.get('source_url'))!r}", max_errors=max_errors)

    out["errors"] = errors
    out["warnings"] = warnings
    out["errors_count"] = len(errors)
    out["warnings_count"] = len(warnings)
    out["valid"] = len(errors) == 0
    return out


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate liberty_delegated_enforcement_seed_v1 JSON")
    ap.add_argument("--seed", default="etl/data/seeds/liberty_delegated_enforcement_seed_v1.json")
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
