#!/usr/bin/env python3
"""Validate sanction volume pilot seed contract (v1)."""

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
    "volume_observations",
    "procedural_metrics",
    "municipal_ordinances",
    "municipal_fragments",
)
OBS_REQUIRED_KEYS = (
    "sanction_source_id",
    "period_date",
    "period_granularity",
    "infraction_type_id",
    "expediente_count",
    "importe_total_eur",
    "source_url",
)
METRIC_REQUIRED_KEYS = (
    "kpi_id",
    "sanction_source_id",
    "period_date",
    "period_granularity",
    "value",
    "source_url",
)
ORD_REQUIRED_KEYS = (
    "ordinance_id",
    "city_name",
    "ordinance_label",
    "ordinance_status",
    "source_url",
)
FRAG_REQUIRED_KEYS = (
    "ordinance_fragment_id",
    "ordinance_id",
    "fragment_label",
)

ALLOWED_PERIOD_GRANULARITY = {"day", "month", "quarter", "year"}
ALLOWED_ORD_STATUS = {"identified", "normalized", "blocked"}
HTTP_RE = re.compile(r"^https?://")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _is_number(v: Any) -> bool:
    try:
        float(v)
        return True
    except Exception:
        return False


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
        "errors_count": 0,
        "warnings_count": 0,
        "volume_observations_total": 0,
        "procedural_metrics_total": 0,
        "municipal_ordinances_total": 0,
        "municipal_fragments_total": 0,
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
    if schema_version != "sanction_volume_pilot_seed_v1":
        _add_error(
            errors,
            code="invalid_schema_version",
            path="$.schema_version",
            message=f"expected 'sanction_volume_pilot_seed_v1', got {schema_version!r}",
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

    obs = raw.get("volume_observations")
    if not isinstance(obs, list) or not obs:
        _add_error(
            errors,
            code="invalid_volume_observations",
            path="$.volume_observations",
            message="volume_observations must be non-empty array",
            max_errors=max_errors,
        )
        obs = []
    out["volume_observations_total"] = len(obs)

    metrics = raw.get("procedural_metrics")
    if not isinstance(metrics, list) or not metrics:
        _add_error(
            errors,
            code="invalid_procedural_metrics",
            path="$.procedural_metrics",
            message="procedural_metrics must be non-empty array",
            max_errors=max_errors,
        )
        metrics = []
    out["procedural_metrics_total"] = len(metrics)

    ordinances = raw.get("municipal_ordinances")
    if not isinstance(ordinances, list) or not ordinances:
        _add_error(
            errors,
            code="invalid_municipal_ordinances",
            path="$.municipal_ordinances",
            message="municipal_ordinances must be non-empty array",
            max_errors=max_errors,
        )
        ordinances = []
    out["municipal_ordinances_total"] = len(ordinances)

    fragments = raw.get("municipal_fragments")
    if not isinstance(fragments, list):
        _add_error(
            errors,
            code="invalid_municipal_fragments",
            path="$.municipal_fragments",
            message="municipal_fragments must be array",
            max_errors=max_errors,
        )
        fragments = []
    out["municipal_fragments_total"] = len(fragments)

    for idx, row in enumerate(obs):
        path = f"$.volume_observations[{idx}]"
        if not isinstance(row, dict):
            _add_error(errors, code="observation_not_object", path=path, message="row must be object", max_errors=max_errors)
            continue
        for key in OBS_REQUIRED_KEYS:
            if _norm(row.get(key)) == "":
                _add_error(
                    errors,
                    code="missing_observation_key",
                    path=path,
                    message=f"missing required key: {key}",
                    max_errors=max_errors,
                )
        granularity = _norm(row.get("period_granularity"))
        if granularity and granularity not in ALLOWED_PERIOD_GRANULARITY:
            _add_error(
                errors,
                code="invalid_period_granularity",
                path=f"{path}.period_granularity",
                message=f"period_granularity must be one of {sorted(ALLOWED_PERIOD_GRANULARITY)}, got {granularity!r}",
                max_errors=max_errors,
            )
        if _norm(row.get("source_url")) and not HTTP_RE.match(_norm(row.get("source_url"))):
            _add_error(
                errors,
                code="invalid_source_url",
                path=f"{path}.source_url",
                message=f"source_url must be http/https URL, got {_norm(row.get('source_url'))!r}",
                max_errors=max_errors,
            )
        if not _is_number(row.get("expediente_count")):
            _add_error(
                errors,
                code="invalid_expediente_count",
                path=f"{path}.expediente_count",
                message="expediente_count must be numeric",
                max_errors=max_errors,
            )
        if not _is_number(row.get("importe_total_eur")):
            _add_error(
                errors,
                code="invalid_importe_total_eur",
                path=f"{path}.importe_total_eur",
                message="importe_total_eur must be numeric",
                max_errors=max_errors,
            )

    for idx, row in enumerate(metrics):
        path = f"$.procedural_metrics[{idx}]"
        if not isinstance(row, dict):
            _add_error(errors, code="metric_not_object", path=path, message="row must be object", max_errors=max_errors)
            continue
        for key in METRIC_REQUIRED_KEYS:
            if _norm(row.get(key)) == "":
                _add_error(
                    errors,
                    code="missing_metric_key",
                    path=path,
                    message=f"missing required key: {key}",
                    max_errors=max_errors,
                )
        if not _is_number(row.get("value")):
            _add_error(
                errors,
                code="invalid_metric_value",
                path=f"{path}.value",
                message="value must be numeric",
                max_errors=max_errors,
            )
        if _norm(row.get("source_url")) and not HTTP_RE.match(_norm(row.get("source_url"))):
            _add_error(
                errors,
                code="invalid_metric_source_url",
                path=f"{path}.source_url",
                message=f"source_url must be http/https URL, got {_norm(row.get('source_url'))!r}",
                max_errors=max_errors,
            )

    ordinance_ids: set[str] = set()
    for idx, row in enumerate(ordinances):
        path = f"$.municipal_ordinances[{idx}]"
        if not isinstance(row, dict):
            _add_error(errors, code="ordinance_not_object", path=path, message="row must be object", max_errors=max_errors)
            continue
        for key in ORD_REQUIRED_KEYS:
            if _norm(row.get(key)) == "":
                _add_error(
                    errors,
                    code="missing_ordinance_key",
                    path=path,
                    message=f"missing required key: {key}",
                    max_errors=max_errors,
                )
        oid = _norm(row.get("ordinance_id"))
        if oid in ordinance_ids:
            _add_error(
                errors,
                code="duplicate_ordinance_id",
                path=f"{path}.ordinance_id",
                message=f"duplicate ordinance_id: {oid}",
                max_errors=max_errors,
            )
        ordinance_ids.add(oid)

        status = _norm(row.get("ordinance_status"))
        if status and status not in ALLOWED_ORD_STATUS:
            _add_error(
                errors,
                code="invalid_ordinance_status",
                path=f"{path}.ordinance_status",
                message=f"ordinance_status must be one of {sorted(ALLOWED_ORD_STATUS)}, got {status!r}",
                max_errors=max_errors,
            )
        if _norm(row.get("source_url")) and not HTTP_RE.match(_norm(row.get("source_url"))):
            _add_error(
                errors,
                code="invalid_ordinance_source_url",
                path=f"{path}.source_url",
                message=f"source_url must be http/https URL, got {_norm(row.get('source_url'))!r}",
                max_errors=max_errors,
            )

    fragment_ids: set[str] = set()
    for idx, row in enumerate(fragments):
        path = f"$.municipal_fragments[{idx}]"
        if not isinstance(row, dict):
            _add_error(errors, code="fragment_not_object", path=path, message="row must be object", max_errors=max_errors)
            continue
        for key in FRAG_REQUIRED_KEYS:
            if _norm(row.get(key)) == "":
                _add_error(
                    errors,
                    code="missing_fragment_key",
                    path=path,
                    message=f"missing required key: {key}",
                    max_errors=max_errors,
                )
        fid = _norm(row.get("ordinance_fragment_id"))
        if fid in fragment_ids:
            _add_error(
                errors,
                code="duplicate_ordinance_fragment_id",
                path=f"{path}.ordinance_fragment_id",
                message=f"duplicate ordinance_fragment_id: {fid}",
                max_errors=max_errors,
            )
        fragment_ids.add(fid)
        oid = _norm(row.get("ordinance_id"))
        if oid and oid not in ordinance_ids:
            _add_error(
                errors,
                code="unknown_fragment_ordinance_id",
                path=f"{path}.ordinance_id",
                message=f"unknown ordinance_id for fragment: {oid}",
                max_errors=max_errors,
            )
        if _norm(row.get("source_url")) and not HTTP_RE.match(_norm(row.get("source_url"))):
            _add_error(
                errors,
                code="invalid_fragment_source_url",
                path=f"{path}.source_url",
                message=f"source_url must be http/https URL, got {_norm(row.get('source_url'))!r}",
                max_errors=max_errors,
            )

    out["errors"] = errors
    out["warnings"] = warnings
    out["errors_count"] = len(errors)
    out["warnings_count"] = len(warnings)
    out["valid"] = len(errors) == 0
    return out


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate sanction_volume_pilot_seed_v1 JSON")
    ap.add_argument("--seed", default="etl/data/seeds/sanction_volume_pilot_seed_v1.json")
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
