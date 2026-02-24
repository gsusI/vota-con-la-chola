#!/usr/bin/env python3
"""Validate liberty_indirect_accountability_seed_v1 JSON contract."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT_REQUIRED_KEYS = ("schema_version", "generated_at", "methodology", "edges")
METHODOLOGY_REQUIRED_KEYS = ("method_version", "method_label", "confidence_rules")
CONFIDENCE_RULE_KEYS = (
    "attributable_confidence_min",
    "attributable_max_causal_distance",
)
EDGE_REQUIRED_KEYS = (
    "fragment_id",
    "actor_label",
    "role",
    "causal_distance",
    "edge_confidence",
    "source_url",
)
ALLOWED_ROLES = {"delegate", "appoint", "instruct", "design"}
HTTP_RE = re.compile(r"^https?://")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


def _is_int(v: Any) -> bool:
    try:
        int(float(v))
        return True
    except Exception:
        return False


def _in_01(v: Any) -> bool:
    if not _is_number(v):
        return False
    token = float(v)
    return 0.0 <= token <= 1.0


def _parse_iso_date(v: Any) -> date | None:
    token = _norm(v)
    if not token or not DATE_RE.match(token):
        return None
    try:
        return datetime.strptime(token, "%Y-%m-%d").date()
    except ValueError:
        return None


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
        "edges_total": 0,
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
    if schema_version != "liberty_indirect_accountability_seed_v1":
        _add_error(
            errors,
            code="invalid_schema_version",
            path="$.schema_version",
            message=f"expected 'liberty_indirect_accountability_seed_v1', got {schema_version!r}",
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

    confidence_rules = methodology.get("confidence_rules")
    if not isinstance(confidence_rules, dict):
        _add_error(errors, code="invalid_confidence_rules", path="$.methodology.confidence_rules", message="confidence_rules must be object", max_errors=max_errors)
        confidence_rules = {}
    for key in CONFIDENCE_RULE_KEYS:
        if key not in confidence_rules:
            _add_error(errors, code="missing_confidence_rule", path="$.methodology.confidence_rules", message=f"missing rule key: {key}", max_errors=max_errors)
            continue
        if key == "attributable_confidence_min" and not _in_01(confidence_rules.get(key)):
            _add_error(errors, code="invalid_confidence_rule", path=f"$.methodology.confidence_rules.{key}", message=f"{key} must be numeric in [0,1]", max_errors=max_errors)
        if key == "attributable_max_causal_distance" and (not _is_int(confidence_rules.get(key)) or int(float(confidence_rules.get(key))) < 1):
            _add_error(errors, code="invalid_confidence_rule", path=f"$.methodology.confidence_rules.{key}", message=f"{key} must be integer >= 1", max_errors=max_errors)

    edges = raw.get("edges")
    if not isinstance(edges, list) or not edges:
        _add_error(errors, code="invalid_edges", path="$.edges", message="edges must be non-empty array", max_errors=max_errors)
        edges = []
    out["edges_total"] = len(edges)

    seen_keys: set[str] = set()
    for i, row in enumerate(edges):
        path = f"$.edges[{i}]"
        if not isinstance(row, dict):
            _add_error(errors, code="edge_not_object", path=path, message="row must be object", max_errors=max_errors)
            continue
        for key in EDGE_REQUIRED_KEYS:
            if key not in row or _norm(row.get(key)) == "":
                _add_error(errors, code="missing_edge_key", path=path, message=f"missing required key: {key}", max_errors=max_errors)

        dedupe_key = "|".join(
            [
                _norm(row.get("fragment_id")),
                _norm(row.get("actor_label")),
                _norm(row.get("role")),
                _norm(row.get("direct_actor_label")),
                _norm(row.get("source_url")),
            ]
        )
        if dedupe_key in seen_keys:
            _add_error(errors, code="duplicate_edge", path=path, message=f"duplicate edge tuple: {dedupe_key}", max_errors=max_errors)
        seen_keys.add(dedupe_key)

        role = _norm(row.get("role"))
        if role and role not in ALLOWED_ROLES:
            _add_error(
                errors,
                code="invalid_role",
                path=f"{path}.role",
                message=f"role must be one of {sorted(ALLOWED_ROLES)}, got {role!r}",
                max_errors=max_errors,
            )
        if _norm(row.get("causal_distance")):
            if not _is_int(row.get("causal_distance")):
                _add_error(errors, code="invalid_causal_distance", path=f"{path}.causal_distance", message="causal_distance must be integer", max_errors=max_errors)
            else:
                cd = int(float(row.get("causal_distance")))
                if cd < 1 or cd > 5:
                    _add_error(errors, code="invalid_causal_distance", path=f"{path}.causal_distance", message="causal_distance must be in [1,5]", max_errors=max_errors)
        if _norm(row.get("edge_confidence")) and not _in_01(row.get("edge_confidence")):
            _add_error(errors, code="invalid_edge_confidence", path=f"{path}.edge_confidence", message="edge_confidence must be numeric in [0,1]", max_errors=max_errors)
        if _norm(row.get("source_url")) and not HTTP_RE.match(_norm(row.get("source_url"))):
            _add_error(errors, code="invalid_source_url", path=f"{path}.source_url", message=f"source_url must be http/https URL, got {_norm(row.get('source_url'))!r}", max_errors=max_errors)

        evidence_date = _parse_iso_date(row.get("evidence_date"))
        if _norm(row.get("evidence_date")) and evidence_date is None:
            _add_error(
                errors,
                code="invalid_evidence_date",
                path=f"{path}.evidence_date",
                message=f"evidence_date must be YYYY-MM-DD, got {_norm(row.get('evidence_date'))!r}",
                max_errors=max_errors,
            )

        appointment_start_token = _norm(row.get("appointment_start_date"))
        appointment_end_token = _norm(row.get("appointment_end_date"))
        appointment_start = _parse_iso_date(appointment_start_token)
        appointment_end = _parse_iso_date(appointment_end_token)
        if appointment_start_token and appointment_start is None:
            _add_error(
                errors,
                code="invalid_appointment_start_date",
                path=f"{path}.appointment_start_date",
                message=f"appointment_start_date must be YYYY-MM-DD, got {appointment_start_token!r}",
                max_errors=max_errors,
            )
        if appointment_end_token and appointment_end is None:
            _add_error(
                errors,
                code="invalid_appointment_end_date",
                path=f"{path}.appointment_end_date",
                message=f"appointment_end_date must be YYYY-MM-DD, got {appointment_end_token!r}",
                max_errors=max_errors,
            )
        if appointment_end_token and not appointment_start_token:
            _add_error(
                errors,
                code="missing_appointment_start_date",
                path=f"{path}.appointment_start_date",
                message="appointment_start_date is required when appointment_end_date is set",
                max_errors=max_errors,
            )
        if appointment_start is not None and appointment_end is not None and appointment_end < appointment_start:
            _add_error(
                errors,
                code="invalid_appointment_window",
                path=path,
                message="appointment_end_date must be >= appointment_start_date",
                max_errors=max_errors,
            )

        actor_person_name = _norm(row.get("actor_person_name"))
        actor_role_title = _norm(row.get("actor_role_title"))
        has_person_window_context = bool(actor_person_name or actor_role_title or appointment_start_token or appointment_end_token)
        if has_person_window_context:
            if not actor_person_name:
                _add_error(
                    errors,
                    code="missing_actor_person_name",
                    path=f"{path}.actor_person_name",
                    message="actor_person_name is required when using person-window context",
                    max_errors=max_errors,
                )
            if not actor_role_title:
                _add_error(
                    errors,
                    code="missing_actor_role_title",
                    path=f"{path}.actor_role_title",
                    message="actor_role_title is required when using person-window context",
                    max_errors=max_errors,
                )
            if not appointment_start_token:
                _add_error(
                    errors,
                    code="missing_appointment_start_date",
                    path=f"{path}.appointment_start_date",
                    message="appointment_start_date is required when using person-window context",
                    max_errors=max_errors,
                )

        if evidence_date is not None and appointment_start is not None:
            if evidence_date < appointment_start:
                _add_error(
                    errors,
                    code="evidence_outside_appointment_window",
                    path=path,
                    message="evidence_date must be >= appointment_start_date when window is provided",
                    max_errors=max_errors,
                )
            if appointment_end is not None and evidence_date > appointment_end:
                _add_error(
                    errors,
                    code="evidence_outside_appointment_window",
                    path=path,
                    message="evidence_date must be <= appointment_end_date when appointment_end_date is provided",
                    max_errors=max_errors,
                )

    out["errors"] = errors
    out["warnings"] = warnings
    out["errors_count"] = len(errors)
    out["warnings_count"] = len(warnings)
    out["valid"] = len(errors) == 0
    return out


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate liberty_indirect_accountability_seed_v1 JSON")
    ap.add_argument("--seed", default="etl/data/seeds/liberty_indirect_accountability_seed_v1.json")
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
