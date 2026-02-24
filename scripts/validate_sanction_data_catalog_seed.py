#!/usr/bin/env python3
"""Validate sanction data catalog seed contract (v1)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_REQUIRED_KEYS = (
    "schema_version",
    "generated_at",
    "volume_sources",
    "infraction_types",
    "infraction_mappings",
    "procedural_kpis",
)
SOURCE_REQUIRED_KEYS = (
    "sanction_source_id",
    "label",
    "organismo",
    "admin_scope",
    "territory_scope",
    "source_url",
    "expected_metrics",
)
INFRACTION_TYPE_REQUIRED_KEYS = (
    "infraction_type_id",
    "label",
    "domain",
    "description",
)
MAPPING_REQUIRED_KEYS = (
    "mapping_scope",
    "infraction_type_id",
    "source_system",
    "source_code",
    "source_label",
)
KPI_REQUIRED_KEYS = (
    "kpi_id",
    "label",
    "metric_formula",
    "target_direction",
    "source_requirements",
)

ALLOWED_ADMIN_SCOPE = {"estado", "autonomico", "municipal", "mixto"}
ALLOWED_MAPPING_SCOPE = {"norm_fragment", "source_only"}
ALLOWED_TARGET_DIRECTION = {"higher_is_better", "lower_is_better", "range"}
ALLOWED_METRICS = {
    "expediente_count",
    "importe_total_eur",
    "importe_medio_eur",
    "infraction_type_id",
    "norm_fragment_id",
    "recurso_presentado_count",
    "recurso_estimado_count",
    "recurso_desestimado_count",
    "anulaciones_formales_count",
    "resolution_days",
}
HTTP_RE = re.compile(r"^https?://")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _add_error(errors: list[dict[str, str]], *, code: str, path: str, message: str, max_errors: int) -> None:
    if len(errors) >= int(max_errors):
        return
    errors.append({"code": code, "path": path, "message": message})


def _add_warning(warnings: list[dict[str, str]], *, code: str, path: str, message: str) -> None:
    warnings.append({"code": code, "path": path, "message": message})


def validate_seed(seed_path: Path, *, max_errors: int = 200) -> dict[str, Any]:
    out: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "seed_path": str(seed_path),
        "valid": False,
        "schema_version": "",
        "errors_count": 0,
        "warnings_count": 0,
        "volume_sources_total": 0,
        "infraction_types_total": 0,
        "infraction_mappings_total": 0,
        "procedural_kpis_total": 0,
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
            _add_error(
                errors,
                code="missing_root_key",
                path="$",
                message=f"missing required root key: {key}",
                max_errors=max_errors,
            )

    schema_version = _norm(raw.get("schema_version"))
    out["schema_version"] = schema_version
    if schema_version != "sanction_data_catalog_seed_v1":
        _add_error(
            errors,
            code="invalid_schema_version",
            path="$.schema_version",
            message=f"expected 'sanction_data_catalog_seed_v1', got {schema_version!r}",
            max_errors=max_errors,
        )

    generated_at = _norm(raw.get("generated_at"))
    if generated_at:
        try:
            datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError:
            _add_error(
                errors,
                code="invalid_generated_at",
                path="$.generated_at",
                message=f"generated_at must be ISO datetime, got {generated_at!r}",
                max_errors=max_errors,
            )

    volume_sources = raw.get("volume_sources")
    if not isinstance(volume_sources, list) or not volume_sources:
        _add_error(
            errors,
            code="invalid_volume_sources",
            path="$.volume_sources",
            message="volume_sources must be non-empty array",
            max_errors=max_errors,
        )
        volume_sources = []
    out["volume_sources_total"] = len(volume_sources)

    infraction_types = raw.get("infraction_types")
    if not isinstance(infraction_types, list) or not infraction_types:
        _add_error(
            errors,
            code="invalid_infraction_types",
            path="$.infraction_types",
            message="infraction_types must be non-empty array",
            max_errors=max_errors,
        )
        infraction_types = []
    out["infraction_types_total"] = len(infraction_types)

    infraction_mappings = raw.get("infraction_mappings")
    if not isinstance(infraction_mappings, list) or not infraction_mappings:
        _add_error(
            errors,
            code="invalid_infraction_mappings",
            path="$.infraction_mappings",
            message="infraction_mappings must be non-empty array",
            max_errors=max_errors,
        )
        infraction_mappings = []
    out["infraction_mappings_total"] = len(infraction_mappings)

    procedural_kpis = raw.get("procedural_kpis")
    if not isinstance(procedural_kpis, list) or not procedural_kpis:
        _add_error(
            errors,
            code="invalid_procedural_kpis",
            path="$.procedural_kpis",
            message="procedural_kpis must be non-empty array",
            max_errors=max_errors,
        )
        procedural_kpis = []
    out["procedural_kpis_total"] = len(procedural_kpis)

    source_ids: set[str] = set()
    for idx, row in enumerate(volume_sources):
        path = f"$.volume_sources[{idx}]"
        if not isinstance(row, dict):
            _add_error(errors, code="volume_source_not_object", path=path, message="row must be object", max_errors=max_errors)
            continue
        for key in SOURCE_REQUIRED_KEYS:
            if _norm(row.get(key)) == "":
                _add_error(
                    errors,
                    code="missing_volume_source_key",
                    path=path,
                    message=f"missing required key: {key}",
                    max_errors=max_errors,
                )
        source_id = _norm(row.get("sanction_source_id"))
        if source_id in source_ids:
            _add_error(
                errors,
                code="duplicate_sanction_source_id",
                path=f"{path}.sanction_source_id",
                message=f"duplicate sanction_source_id: {source_id}",
                max_errors=max_errors,
            )
        source_ids.add(source_id)

        admin_scope = _norm(row.get("admin_scope"))
        if admin_scope and admin_scope not in ALLOWED_ADMIN_SCOPE:
            _add_error(
                errors,
                code="invalid_admin_scope",
                path=f"{path}.admin_scope",
                message=f"admin_scope must be one of {sorted(ALLOWED_ADMIN_SCOPE)}, got {admin_scope!r}",
                max_errors=max_errors,
            )
        source_url = _norm(row.get("source_url"))
        if source_url and not HTTP_RE.match(source_url):
            _add_error(
                errors,
                code="invalid_source_url",
                path=f"{path}.source_url",
                message=f"source_url must be http/https URL, got {source_url!r}",
                max_errors=max_errors,
            )
        expected_metrics = row.get("expected_metrics")
        if not isinstance(expected_metrics, list) or not expected_metrics:
            _add_error(
                errors,
                code="invalid_expected_metrics",
                path=f"{path}.expected_metrics",
                message="expected_metrics must be non-empty array",
                max_errors=max_errors,
            )
        else:
            for midx, metric in enumerate(expected_metrics):
                mt = _norm(metric)
                if mt not in ALLOWED_METRICS:
                    _add_warning(
                        warnings,
                        code="unknown_expected_metric",
                        path=f"{path}.expected_metrics[{midx}]",
                        message=f"metric not in known set: {mt!r}",
                    )

    infraction_type_ids: set[str] = set()
    for idx, row in enumerate(infraction_types):
        path = f"$.infraction_types[{idx}]"
        if not isinstance(row, dict):
            _add_error(errors, code="infraction_type_not_object", path=path, message="row must be object", max_errors=max_errors)
            continue
        for key in INFRACTION_TYPE_REQUIRED_KEYS:
            if _norm(row.get(key)) == "":
                _add_error(
                    errors,
                    code="missing_infraction_type_key",
                    path=path,
                    message=f"missing required key: {key}",
                    max_errors=max_errors,
                )
        infraction_type_id = _norm(row.get("infraction_type_id"))
        if infraction_type_id in infraction_type_ids:
            _add_error(
                errors,
                code="duplicate_infraction_type_id",
                path=f"{path}.infraction_type_id",
                message=f"duplicate infraction_type_id: {infraction_type_id}",
                max_errors=max_errors,
            )
        infraction_type_ids.add(infraction_type_id)

    mapping_keys: set[str] = set()
    for idx, row in enumerate(infraction_mappings):
        path = f"$.infraction_mappings[{idx}]"
        if not isinstance(row, dict):
            _add_error(errors, code="mapping_not_object", path=path, message="row must be object", max_errors=max_errors)
            continue
        for key in MAPPING_REQUIRED_KEYS:
            if _norm(row.get(key)) == "":
                _add_error(
                    errors,
                    code="missing_mapping_key",
                    path=path,
                    message=f"missing required key: {key}",
                    max_errors=max_errors,
                )
        mapping_scope = _norm(row.get("mapping_scope"))
        if mapping_scope not in ALLOWED_MAPPING_SCOPE:
            _add_error(
                errors,
                code="invalid_mapping_scope",
                path=f"{path}.mapping_scope",
                message=f"mapping_scope must be one of {sorted(ALLOWED_MAPPING_SCOPE)}, got {mapping_scope!r}",
                max_errors=max_errors,
            )

        infraction_type_id = _norm(row.get("infraction_type_id"))
        if infraction_type_id and infraction_type_id not in infraction_type_ids:
            _add_error(
                errors,
                code="unknown_infraction_type_id",
                path=f"{path}.infraction_type_id",
                message=f"unknown infraction_type_id: {infraction_type_id}",
                max_errors=max_errors,
            )

        norm_id = _norm(row.get("norm_id"))
        fragment_id = _norm(row.get("fragment_id"))
        if mapping_scope == "norm_fragment":
            if not norm_id:
                _add_error(
                    errors,
                    code="missing_mapping_norm_id",
                    path=f"{path}.norm_id",
                    message="norm_id required for mapping_scope=norm_fragment",
                    max_errors=max_errors,
                )
            if not fragment_id:
                _add_error(
                    errors,
                    code="missing_mapping_fragment_id",
                    path=f"{path}.fragment_id",
                    message="fragment_id required for mapping_scope=norm_fragment",
                    max_errors=max_errors,
                )

        source_url = _norm(row.get("source_url"))
        if source_url and not HTTP_RE.match(source_url):
            _add_error(
                errors,
                code="invalid_mapping_source_url",
                path=f"{path}.source_url",
                message=f"source_url must be http/https URL, got {source_url!r}",
                max_errors=max_errors,
            )

        dedupe_key = "|".join(
            [
                infraction_type_id,
                _norm(row.get("source_system")),
                _norm(row.get("source_code")),
                norm_id,
                fragment_id,
            ]
        )
        if dedupe_key in mapping_keys:
            _add_error(
                errors,
                code="duplicate_mapping",
                path=path,
                message=f"duplicate mapping tuple: {dedupe_key}",
                max_errors=max_errors,
            )
        mapping_keys.add(dedupe_key)

    kpi_ids: set[str] = set()
    for idx, row in enumerate(procedural_kpis):
        path = f"$.procedural_kpis[{idx}]"
        if not isinstance(row, dict):
            _add_error(errors, code="kpi_not_object", path=path, message="row must be object", max_errors=max_errors)
            continue
        for key in KPI_REQUIRED_KEYS:
            if _norm(row.get(key)) == "":
                _add_error(
                    errors,
                    code="missing_kpi_key",
                    path=path,
                    message=f"missing required key: {key}",
                    max_errors=max_errors,
                )
        kpi_id = _norm(row.get("kpi_id"))
        if kpi_id in kpi_ids:
            _add_error(
                errors,
                code="duplicate_kpi_id",
                path=f"{path}.kpi_id",
                message=f"duplicate kpi_id: {kpi_id}",
                max_errors=max_errors,
            )
        kpi_ids.add(kpi_id)

        direction = _norm(row.get("target_direction"))
        if direction and direction not in ALLOWED_TARGET_DIRECTION:
            _add_error(
                errors,
                code="invalid_target_direction",
                path=f"{path}.target_direction",
                message=f"target_direction must be one of {sorted(ALLOWED_TARGET_DIRECTION)}, got {direction!r}",
                max_errors=max_errors,
            )

        req = row.get("source_requirements")
        if not isinstance(req, list) or not req:
            _add_error(
                errors,
                code="invalid_source_requirements",
                path=f"{path}.source_requirements",
                message="source_requirements must be non-empty array",
                max_errors=max_errors,
            )

    out["errors"] = errors
    out["warnings"] = warnings
    out["errors_count"] = len(errors)
    out["warnings_count"] = len(warnings)
    out["valid"] = len(errors) == 0
    return out


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate sanction_data_catalog_seed_v1 JSON")
    ap.add_argument("--seed", default="etl/data/seeds/sanction_data_catalog_seed_v1.json")
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
