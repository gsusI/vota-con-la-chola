#!/usr/bin/env python3
"""Validate liberty_person_identity_resolution_seed_v1 JSON contract."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.politicos_es.util import normalize_ws

ROOT_REQUIRED_KEYS = ("schema_version", "generated_at", "methodology", "mappings")
METHODOLOGY_REQUIRED_KEYS = ("method_version", "method_label")
MAPPING_REQUIRED_KEYS = ("actor_person_name", "person_full_name", "source_kind")
SOURCE_KIND_MANUAL = "manual_seed"
ALLOWED_SOURCE_KINDS = {
    SOURCE_KIND_MANUAL,
    "official_nombramiento",
    "official_boletin",
    "official_expediente",
    "official_resolucion",
    "official_registry",
}
HTTP_RE = re.compile(r"^https?://")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    if v is None:
        return ""
    return normalize_ws(str(v))


def _is_int(v: Any) -> bool:
    try:
        return int(float(v)) >= 1
    except Exception:
        return False


def _in_01(v: Any) -> bool:
    try:
        token = float(v)
    except Exception:
        return False
    return 0.0 <= token <= 1.0


def _canonical_alias(actor_person_name: Any) -> str:
    return _norm(actor_person_name).lower()


def _is_iso_date(v: Any) -> bool:
    token = _norm(v)
    if not token:
        return False
    try:
        datetime.strptime(token, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _add_error(errors: list[dict[str, str]], *, code: str, path: str, message: str, max_errors: int) -> None:
    if len(errors) >= int(max_errors):
        return
    errors.append({"code": code, "path": path, "message": message})


def _add_warning(warnings: list[dict[str, str]], *, code: str, path: str, message: str, max_warnings: int) -> None:
    if len(warnings) >= int(max_warnings):
        return
    warnings.append({"code": code, "path": path, "message": message})


def validate_seed(seed_path: Path, *, max_errors: int = 200) -> dict[str, Any]:
    out: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "seed_path": str(seed_path),
        "valid": False,
        "schema_version": "",
        "method_version": "",
        "mappings_total": 0,
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
    if schema_version != "liberty_person_identity_resolution_seed_v1":
        _add_error(
            errors,
            code="invalid_schema_version",
            path="$.schema_version",
            message=f"expected 'liberty_person_identity_resolution_seed_v1', got {schema_version!r}",
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

    mappings = raw.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        _add_error(errors, code="invalid_mappings", path="$.mappings", message="mappings must be non-empty array", max_errors=max_errors)
        mappings = []
    out["mappings_total"] = len(mappings)

    seen_aliases: set[str] = set()
    for i, row in enumerate(mappings):
        path = f"$.mappings[{i}]"
        if not isinstance(row, dict):
            _add_error(errors, code="mapping_not_object", path=path, message="row must be object", max_errors=max_errors)
            continue
        for key in MAPPING_REQUIRED_KEYS:
            if _norm(row.get(key)) == "":
                _add_error(errors, code="missing_mapping_key", path=path, message=f"missing required key: {key}", max_errors=max_errors)

        canonical_alias = _canonical_alias(row.get("actor_person_name"))
        if canonical_alias:
            if canonical_alias in seen_aliases:
                _add_error(errors, code="duplicate_actor_person_name", path=f"{path}.actor_person_name", message=f"duplicate alias: {canonical_alias!r}", max_errors=max_errors)
            seen_aliases.add(canonical_alias)

        person_id = _norm(row.get("person_id"))
        if person_id and not _is_int(person_id):
            _add_error(errors, code="invalid_person_id", path=f"{path}.person_id", message="person_id must be integer >= 1 when provided", max_errors=max_errors)

        confidence = _norm(row.get("confidence"))
        if confidence and not _in_01(confidence):
            _add_error(errors, code="invalid_confidence", path=f"{path}.confidence", message="confidence must be numeric in [0,1] when provided", max_errors=max_errors)

        source_kind = _norm(row.get("source_kind"))
        if source_kind and source_kind not in ALLOWED_SOURCE_KINDS:
            _add_error(
                errors,
                code="invalid_source_kind",
                path=f"{path}.source_kind",
                message=f"source_kind must be one of {sorted(ALLOWED_SOURCE_KINDS)!r}",
                max_errors=max_errors,
            )

        source_url = _norm(row.get("source_url"))
        if source_url and not HTTP_RE.match(source_url):
            _add_error(errors, code="invalid_source_url", path=f"{path}.source_url", message=f"source_url must be http/https URL, got {source_url!r}", max_errors=max_errors)

        evidence_date = _norm(row.get("evidence_date"))
        if evidence_date and not _is_iso_date(evidence_date):
            _add_error(
                errors,
                code="invalid_evidence_date",
                path=f"{path}.evidence_date",
                message="evidence_date must be YYYY-MM-DD when provided",
                max_errors=max_errors,
            )

        source_record_pk = _norm(row.get("source_record_pk"))
        if source_record_pk and not _is_int(source_record_pk):
            _add_error(
                errors,
                code="invalid_source_record_pk",
                path=f"{path}.source_record_pk",
                message="source_record_pk must be integer >= 1 when provided",
                max_errors=max_errors,
            )
        source_record_id = _norm(row.get("source_record_id"))
        source_id = _norm(row.get("source_id"))
        if source_record_id and not source_id:
            _add_error(
                errors,
                code="missing_source_id_for_source_record_id",
                path=f"{path}.source_id",
                message="source_id is required when source_record_id is provided",
                max_errors=max_errors,
            )

        evidence_quote = _norm(row.get("evidence_quote"))
        if source_kind and source_kind != SOURCE_KIND_MANUAL:
            if not source_url:
                _add_error(
                    errors,
                    code="missing_source_url_for_official_mapping",
                    path=f"{path}.source_url",
                    message="source_url is required when source_kind is official",
                    max_errors=max_errors,
                )
            if not evidence_date:
                _add_error(
                    errors,
                    code="missing_evidence_date_for_official_mapping",
                    path=f"{path}.evidence_date",
                    message="evidence_date is required when source_kind is official",
                    max_errors=max_errors,
                )
            if not evidence_quote:
                _add_error(
                    errors,
                    code="missing_evidence_quote_for_official_mapping",
                    path=f"{path}.evidence_quote",
                    message="evidence_quote is required when source_kind is official",
                    max_errors=max_errors,
                )
            if not source_record_pk and not source_record_id:
                _add_warning(
                    warnings,
                    code="official_mapping_without_source_record_reference",
                    path=path,
                    message="official mapping should include source_record_id or source_record_pk for source-record traceability",
                    max_warnings=max_errors,
                )

    out["errors"] = errors
    out["warnings"] = warnings
    out["errors_count"] = len(errors)
    out["warnings_count"] = len(warnings)
    out["valid"] = len(errors) == 0
    return out


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate liberty_person_identity_resolution_seed_v1 JSON")
    ap.add_argument("--seed", default="etl/data/seeds/liberty_person_identity_resolution_seed_v1.json")
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
