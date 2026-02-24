#!/usr/bin/env python3
"""Validate sanction norms seed contract (v1)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_REQUIRED_KEYS = ("schema_version", "generated_at", "norms")
NORM_REQUIRED_KEYS = (
    "norm_id",
    "boe_id",
    "title",
    "scope",
    "organismo_competente",
    "incidence_hypothesis",
    "source_url",
    "evidence_required",
    "key_fragments",
)
FRAGMENT_REQUIRED_KEYS = (
    "fragment_type",
    "fragment_label",
    "conducta_sancionada",
    "organo_competente",
    "via_recurso",
)
ALLOWED_FRAGMENT_TYPES = {"articulo", "disposicion", "anexo"}
ALLOWED_RESP_ROLES = {"propose", "approve", "delegate", "enforce", "audit"}
ALLOWED_RESP_EVIDENCE_TYPES = {
    "boe_publicacion",
    "congreso_diario",
    "senado_diario",
    "congreso_vote",
    "senado_vote",
    "other",
}
ALLOWED_LINEAGE_RELATION_TYPES = {"deroga", "modifica", "desarrolla"}
ALLOWED_LINEAGE_RELATION_SCOPES = {"total", "parcial"}
BOE_ID_RE = re.compile(r"^BOE-A-\d{4}-\d+$")
HTTP_RE = re.compile(r"^https?://")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _add_error(errors: list[dict[str, Any]], *, code: str, path: str, message: str, max_errors: int) -> None:
    if len(errors) >= int(max_errors):
        return
    errors.append({"code": str(code), "path": str(path), "message": str(message)})


def _is_number(v: Any) -> bool:
    try:
        float(v)
        return True
    except Exception:
        return False


def validate_seed(seed_path: Path, *, max_errors: int = 200) -> dict[str, Any]:
    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "seed_path": str(seed_path),
        "valid": False,
        "errors_count": 0,
        "warnings_count": 0,
        "norms_total": 0,
        "norms_valid": 0,
        "fragments_total": 0,
        "responsibility_hints_total": 0,
        "responsibility_evidence_items_total": 0,
        "lineage_hints_total": 0,
        "duplicate_norm_id_count": 0,
        "duplicate_boe_id_count": 0,
        "schema_version": "",
        "errors": [],
        "warnings": [],
    }

    if not seed_path.exists():
        report["errors"] = [{"code": "seed_not_found", "path": "$", "message": f"Seed not found: {seed_path}"}]
        report["errors_count"] = 1
        return report
    if seed_path.is_dir():
        report["errors"] = [{"code": "seed_is_dir", "path": "$", "message": f"Seed is a directory: {seed_path}"}]
        report["errors_count"] = 1
        return report

    try:
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
    except Exception as exc:
        report["errors"] = [{"code": "invalid_json", "path": "$", "message": str(exc)}]
        report["errors_count"] = 1
        return report

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if not isinstance(raw, dict):
        _add_error(errors, code="root_not_object", path="$", message="root must be object", max_errors=max_errors)
        report["errors"] = errors
        report["errors_count"] = len(errors)
        return report

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
    report["schema_version"] = schema_version
    if schema_version != "sanction_norms_seed_v1":
        _add_error(
            errors,
            code="invalid_schema_version",
            path="$.schema_version",
            message=f"expected 'sanction_norms_seed_v1', got {schema_version!r}",
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

    norms = raw.get("norms")
    if not isinstance(norms, list) or not norms:
        _add_error(
            errors,
            code="invalid_norms_list",
            path="$.norms",
            message="norms must be a non-empty array",
            max_errors=max_errors,
        )
        norms = []

    seen_norm_ids: dict[str, int] = {}
    seen_boe_ids: dict[str, int] = {}

    norms_valid = 0
    fragments_total = 0
    responsibilities_total = 0
    responsibility_evidence_total = 0
    lineage_total = 0

    for idx, norm in enumerate(norms, start=1):
        path = f"$.norms[{idx - 1}]"
        if not isinstance(norm, dict):
            _add_error(errors, code="norm_not_object", path=path, message="norm must be an object", max_errors=max_errors)
            continue

        row_ok = True
        for key in NORM_REQUIRED_KEYS:
            if key not in norm:
                row_ok = False
                _add_error(
                    errors,
                    code="missing_norm_key",
                    path=path,
                    message=f"missing required norm key: {key}",
                    max_errors=max_errors,
                )

        norm_id = _norm(norm.get("norm_id"))
        boe_id = _norm(norm.get("boe_id"))
        source_url = _norm(norm.get("source_url"))

        if not norm_id:
            row_ok = False
            _add_error(errors, code="empty_norm_id", path=f"{path}.norm_id", message="norm_id is required", max_errors=max_errors)
        if not boe_id:
            row_ok = False
            _add_error(errors, code="empty_boe_id", path=f"{path}.boe_id", message="boe_id is required", max_errors=max_errors)
        elif not BOE_ID_RE.match(boe_id):
            row_ok = False
            _add_error(
                errors,
                code="invalid_boe_id",
                path=f"{path}.boe_id",
                message=f"boe_id must match BOE-A-YYYY-NNN, got {boe_id!r}",
                max_errors=max_errors,
            )

        if source_url and not HTTP_RE.match(source_url):
            row_ok = False
            _add_error(
                errors,
                code="invalid_source_url",
                path=f"{path}.source_url",
                message=f"source_url must be http/https URL, got {source_url!r}",
                max_errors=max_errors,
            )

        if norm_id:
            seen_norm_ids[norm_id] = seen_norm_ids.get(norm_id, 0) + 1
            if seen_norm_ids[norm_id] > 1:
                row_ok = False
                _add_error(
                    errors,
                    code="duplicate_norm_id",
                    path=f"{path}.norm_id",
                    message=f"duplicate norm_id: {norm_id}",
                    max_errors=max_errors,
                )

        if boe_id:
            seen_boe_ids[boe_id] = seen_boe_ids.get(boe_id, 0) + 1
            if seen_boe_ids[boe_id] > 1:
                row_ok = False
                _add_error(
                    errors,
                    code="duplicate_boe_id",
                    path=f"{path}.boe_id",
                    message=f"duplicate boe_id: {boe_id}",
                    max_errors=max_errors,
                )

        evidence_required = norm.get("evidence_required")
        if not isinstance(evidence_required, list) or not evidence_required:
            row_ok = False
            _add_error(
                errors,
                code="invalid_evidence_required",
                path=f"{path}.evidence_required",
                message="evidence_required must be non-empty array",
                max_errors=max_errors,
            )
        elif any(not _norm(x) for x in evidence_required):
            row_ok = False
            _add_error(
                errors,
                code="empty_evidence_required_item",
                path=f"{path}.evidence_required",
                message="evidence_required items must be non-empty strings",
                max_errors=max_errors,
            )

        key_fragments = norm.get("key_fragments")
        if not isinstance(key_fragments, list) or not key_fragments:
            row_ok = False
            _add_error(
                errors,
                code="invalid_key_fragments",
                path=f"{path}.key_fragments",
                message="key_fragments must be non-empty array",
                max_errors=max_errors,
            )
            key_fragments = []

        frag_labels_seen: dict[str, int] = {}
        for f_idx, frag in enumerate(key_fragments, start=1):
            f_path = f"{path}.key_fragments[{f_idx - 1}]"
            if not isinstance(frag, dict):
                row_ok = False
                _add_error(errors, code="fragment_not_object", path=f_path, message="fragment must be object", max_errors=max_errors)
                continue
            fragments_total += 1

            for key in FRAGMENT_REQUIRED_KEYS:
                if key not in frag:
                    row_ok = False
                    _add_error(
                        errors,
                        code="missing_fragment_key",
                        path=f_path,
                        message=f"missing required fragment key: {key}",
                        max_errors=max_errors,
                    )

            f_type = _norm(frag.get("fragment_type")).lower()
            f_label = _norm(frag.get("fragment_label"))
            if f_type not in ALLOWED_FRAGMENT_TYPES:
                row_ok = False
                _add_error(
                    errors,
                    code="invalid_fragment_type",
                    path=f"{f_path}.fragment_type",
                    message=f"fragment_type must be one of {sorted(ALLOWED_FRAGMENT_TYPES)}, got {f_type!r}",
                    max_errors=max_errors,
                )
            if not f_label:
                row_ok = False
                _add_error(
                    errors,
                    code="empty_fragment_label",
                    path=f"{f_path}.fragment_label",
                    message="fragment_label is required",
                    max_errors=max_errors,
                )
            if f_label:
                frag_labels_seen[f_label] = frag_labels_seen.get(f_label, 0) + 1
                if frag_labels_seen[f_label] > 1:
                    row_ok = False
                    _add_error(
                        errors,
                        code="duplicate_fragment_label",
                        path=f"{f_path}.fragment_label",
                        message=f"duplicate fragment_label within norm: {f_label}",
                        max_errors=max_errors,
                    )

            min_raw = frag.get("importe_min_eur")
            max_raw = frag.get("importe_max_eur")
            if min_raw is not None and min_raw != "" and not _is_number(min_raw):
                row_ok = False
                _add_error(
                    errors,
                    code="invalid_importe_min_eur",
                    path=f"{f_path}.importe_min_eur",
                    message=f"importe_min_eur must be numeric, got {min_raw!r}",
                    max_errors=max_errors,
                )
            if max_raw is not None and max_raw != "" and not _is_number(max_raw):
                row_ok = False
                _add_error(
                    errors,
                    code="invalid_importe_max_eur",
                    path=f"{f_path}.importe_max_eur",
                    message=f"importe_max_eur must be numeric, got {max_raw!r}",
                    max_errors=max_errors,
                )
            if _is_number(min_raw) and _is_number(max_raw):
                if float(max_raw) < float(min_raw):
                    row_ok = False
                    _add_error(
                        errors,
                        code="invalid_importe_range",
                        path=f_path,
                        message="importe_max_eur must be >= importe_min_eur",
                        max_errors=max_errors,
                    )

        resp_hints = norm.get("responsibility_hints")
        if resp_hints is not None:
            if not isinstance(resp_hints, list):
                row_ok = False
                _add_error(
                    errors,
                    code="invalid_responsibility_hints",
                    path=f"{path}.responsibility_hints",
                    message="responsibility_hints must be array",
                    max_errors=max_errors,
                )
            else:
                for r_idx, hint in enumerate(resp_hints, start=1):
                    r_path = f"{path}.responsibility_hints[{r_idx - 1}]"
                    if not isinstance(hint, dict):
                        row_ok = False
                        _add_error(errors, code="responsibility_hint_not_object", path=r_path, message="hint must be object", max_errors=max_errors)
                        continue
                    responsibilities_total += 1
                    role = _norm(hint.get("role")).lower()
                    actor_label = _norm(hint.get("actor_label"))
                    resp_source_url = _norm(hint.get("source_url"))
                    evidence_date = _norm(hint.get("evidence_date"))
                    evidence_quote = _norm(hint.get("evidence_quote"))
                    if role not in ALLOWED_RESP_ROLES:
                        row_ok = False
                        _add_error(
                            errors,
                            code="invalid_responsibility_role",
                            path=f"{r_path}.role",
                            message=f"role must be one of {sorted(ALLOWED_RESP_ROLES)}, got {role!r}",
                            max_errors=max_errors,
                        )
                    if not actor_label:
                        row_ok = False
                        _add_error(
                            errors,
                            code="missing_responsibility_actor_label",
                            path=f"{r_path}.actor_label",
                            message="actor_label is required",
                            max_errors=max_errors,
                        )
                    if not resp_source_url:
                        row_ok = False
                        _add_error(
                            errors,
                            code="missing_responsibility_source_url",
                            path=f"{r_path}.source_url",
                            message="source_url is required for responsibility hints",
                            max_errors=max_errors,
                        )
                    elif not HTTP_RE.match(resp_source_url):
                        row_ok = False
                        _add_error(
                            errors,
                            code="invalid_responsibility_source_url",
                            path=f"{r_path}.source_url",
                            message=f"source_url must be http/https URL, got {resp_source_url!r}",
                            max_errors=max_errors,
                        )
                    if not evidence_date:
                        row_ok = False
                        _add_error(
                            errors,
                            code="missing_responsibility_evidence_date",
                            path=f"{r_path}.evidence_date",
                            message="evidence_date is required for responsibility hints",
                            max_errors=max_errors,
                        )
                    elif not DATE_RE.match(evidence_date):
                        row_ok = False
                        _add_error(
                            errors,
                            code="invalid_responsibility_evidence_date",
                            path=f"{r_path}.evidence_date",
                            message=f"evidence_date must be YYYY-MM-DD, got {evidence_date!r}",
                            max_errors=max_errors,
                        )
                    if not evidence_quote:
                        row_ok = False
                        _add_error(
                            errors,
                            code="missing_responsibility_evidence_quote",
                            path=f"{r_path}.evidence_quote",
                            message="evidence_quote is required for responsibility hints",
                            max_errors=max_errors,
                        )

                    evidence_items = hint.get("evidence_items")
                    if evidence_items is not None:
                        if not isinstance(evidence_items, list) or not evidence_items:
                            row_ok = False
                            _add_error(
                                errors,
                                code="invalid_responsibility_evidence_items",
                                path=f"{r_path}.evidence_items",
                                message="evidence_items must be a non-empty array when present",
                                max_errors=max_errors,
                            )
                        else:
                            for e_idx, evidence_item in enumerate(evidence_items, start=1):
                                e_path = f"{r_path}.evidence_items[{e_idx - 1}]"
                                if not isinstance(evidence_item, dict):
                                    row_ok = False
                                    _add_error(
                                        errors,
                                        code="responsibility_evidence_item_not_object",
                                        path=e_path,
                                        message="evidence item must be object",
                                        max_errors=max_errors,
                                    )
                                    continue
                                responsibility_evidence_total += 1
                                ev_type = _norm(evidence_item.get("evidence_type")).lower()
                                ev_source_id = _norm(evidence_item.get("source_id"))
                                ev_url = _norm(evidence_item.get("source_url"))
                                ev_date = _norm(evidence_item.get("evidence_date"))
                                ev_quote = _norm(evidence_item.get("evidence_quote"))
                                ev_source_record_id = _norm(evidence_item.get("source_record_id"))
                                if ev_type not in ALLOWED_RESP_EVIDENCE_TYPES:
                                    row_ok = False
                                    _add_error(
                                        errors,
                                        code="invalid_responsibility_evidence_type",
                                        path=f"{e_path}.evidence_type",
                                        message=(
                                            "evidence_type must be one of "
                                            f"{sorted(ALLOWED_RESP_EVIDENCE_TYPES)}, got {ev_type!r}"
                                        ),
                                        max_errors=max_errors,
                                    )
                                if not ev_url:
                                    row_ok = False
                                    _add_error(
                                        errors,
                                        code="missing_responsibility_evidence_source_url",
                                        path=f"{e_path}.source_url",
                                        message="source_url is required for responsibility evidence items",
                                        max_errors=max_errors,
                                    )
                                elif not HTTP_RE.match(ev_url):
                                    row_ok = False
                                    _add_error(
                                        errors,
                                        code="invalid_responsibility_evidence_source_url",
                                        path=f"{e_path}.source_url",
                                        message=f"source_url must be http/https URL, got {ev_url!r}",
                                        max_errors=max_errors,
                                    )
                                if not ev_date:
                                    row_ok = False
                                    _add_error(
                                        errors,
                                        code="missing_responsibility_evidence_date",
                                        path=f"{e_path}.evidence_date",
                                        message="evidence_date is required for responsibility evidence items",
                                        max_errors=max_errors,
                                    )
                                elif not DATE_RE.match(ev_date):
                                    row_ok = False
                                    _add_error(
                                        errors,
                                        code="invalid_responsibility_evidence_date",
                                        path=f"{e_path}.evidence_date",
                                        message=f"evidence_date must be YYYY-MM-DD, got {ev_date!r}",
                                        max_errors=max_errors,
                                    )
                                if not ev_quote:
                                    row_ok = False
                                    _add_error(
                                        errors,
                                        code="missing_responsibility_evidence_quote",
                                        path=f"{e_path}.evidence_quote",
                                        message="evidence_quote is required for responsibility evidence items",
                                        max_errors=max_errors,
                                    )
                                if "source_record_id" in evidence_item:
                                    if not ev_source_record_id:
                                        row_ok = False
                                        _add_error(
                                            errors,
                                            code="invalid_responsibility_evidence_source_record_id",
                                            path=f"{e_path}.source_record_id",
                                            message="source_record_id must be non-empty when present",
                                            max_errors=max_errors,
                                        )
                                    if not ev_source_id:
                                        row_ok = False
                                        _add_error(
                                            errors,
                                            code="missing_responsibility_evidence_source_id_for_source_record_id",
                                            path=f"{e_path}.source_id",
                                            message="source_id is required when source_record_id is present",
                                            max_errors=max_errors,
                                        )
                                if "source_record_pk" in evidence_item:
                                    source_record_pk_raw = evidence_item.get("source_record_pk")
                                    source_record_pk_token = _norm(source_record_pk_raw)
                                    if not source_record_pk_token:
                                        row_ok = False
                                        _add_error(
                                            errors,
                                            code="invalid_responsibility_evidence_source_record_pk",
                                            path=f"{e_path}.source_record_pk",
                                            message="source_record_pk must be a positive integer when present",
                                            max_errors=max_errors,
                                        )
                                    else:
                                        try:
                                            source_record_pk = int(source_record_pk_token)
                                        except Exception:
                                            source_record_pk = 0
                                        if source_record_pk <= 0:
                                            row_ok = False
                                            _add_error(
                                                errors,
                                                code="invalid_responsibility_evidence_source_record_pk",
                                                path=f"{e_path}.source_record_pk",
                                                message="source_record_pk must be a positive integer when present",
                                                max_errors=max_errors,
                                            )

        lineage_hints = norm.get("lineage_hints")
        if lineage_hints is not None:
            if not isinstance(lineage_hints, list):
                row_ok = False
                _add_error(
                    errors,
                    code="invalid_lineage_hints",
                    path=f"{path}.lineage_hints",
                    message="lineage_hints must be array",
                    max_errors=max_errors,
                )
            else:
                for l_idx, hint in enumerate(lineage_hints, start=1):
                    l_path = f"{path}.lineage_hints[{l_idx - 1}]"
                    if not isinstance(hint, dict):
                        row_ok = False
                        _add_error(
                            errors,
                            code="lineage_hint_not_object",
                            path=l_path,
                            message="lineage hint must be object",
                            max_errors=max_errors,
                        )
                        continue
                    lineage_total += 1

                    relation_type = _norm(hint.get("relation_type")).lower()
                    relation_scope = _norm(hint.get("relation_scope")).lower()
                    target_boe_id = _norm(hint.get("target_boe_id"))
                    target_norm_id = _norm(hint.get("target_norm_id"))
                    source_url = _norm(hint.get("source_url"))
                    evidence_date = _norm(hint.get("evidence_date"))
                    evidence_quote = _norm(hint.get("evidence_quote"))

                    if relation_type not in ALLOWED_LINEAGE_RELATION_TYPES:
                        row_ok = False
                        _add_error(
                            errors,
                            code="invalid_lineage_relation_type",
                            path=f"{l_path}.relation_type",
                            message=(
                                "relation_type must be one of "
                                f"{sorted(ALLOWED_LINEAGE_RELATION_TYPES)}, got {relation_type!r}"
                            ),
                            max_errors=max_errors,
                        )
                    if relation_scope and relation_scope not in ALLOWED_LINEAGE_RELATION_SCOPES:
                        row_ok = False
                        _add_error(
                            errors,
                            code="invalid_lineage_relation_scope",
                            path=f"{l_path}.relation_scope",
                            message=(
                                "relation_scope must be one of "
                                f"{sorted(ALLOWED_LINEAGE_RELATION_SCOPES)}, got {relation_scope!r}"
                            ),
                            max_errors=max_errors,
                        )
                    if not target_boe_id and not target_norm_id:
                        row_ok = False
                        _add_error(
                            errors,
                            code="missing_lineage_target",
                            path=l_path,
                            message="lineage hint requires target_boe_id or target_norm_id",
                            max_errors=max_errors,
                        )
                    if target_boe_id and not BOE_ID_RE.match(target_boe_id):
                        row_ok = False
                        _add_error(
                            errors,
                            code="invalid_lineage_target_boe_id",
                            path=f"{l_path}.target_boe_id",
                            message=f"target_boe_id must match BOE-A-YYYY-NNN, got {target_boe_id!r}",
                            max_errors=max_errors,
                        )
                    if not source_url:
                        row_ok = False
                        _add_error(
                            errors,
                            code="missing_lineage_source_url",
                            path=f"{l_path}.source_url",
                            message="source_url is required for lineage hints",
                            max_errors=max_errors,
                        )
                    elif not HTTP_RE.match(source_url):
                        row_ok = False
                        _add_error(
                            errors,
                            code="invalid_lineage_source_url",
                            path=f"{l_path}.source_url",
                            message=f"source_url must be http/https URL, got {source_url!r}",
                            max_errors=max_errors,
                        )
                    if not evidence_date:
                        row_ok = False
                        _add_error(
                            errors,
                            code="missing_lineage_evidence_date",
                            path=f"{l_path}.evidence_date",
                            message="evidence_date is required for lineage hints",
                            max_errors=max_errors,
                        )
                    elif not DATE_RE.match(evidence_date):
                        row_ok = False
                        _add_error(
                            errors,
                            code="invalid_lineage_evidence_date",
                            path=f"{l_path}.evidence_date",
                            message=f"evidence_date must be YYYY-MM-DD, got {evidence_date!r}",
                            max_errors=max_errors,
                        )
                    if not evidence_quote:
                        row_ok = False
                        _add_error(
                            errors,
                            code="missing_lineage_evidence_quote",
                            path=f"{l_path}.evidence_quote",
                            message="evidence_quote is required for lineage hints",
                            max_errors=max_errors,
                        )

        if row_ok:
            norms_valid += 1

    report["valid"] = len(errors) == 0
    report["errors"] = errors
    report["warnings"] = warnings
    report["errors_count"] = len(errors)
    report["warnings_count"] = len(warnings)
    report["norms_total"] = len(norms)
    report["norms_valid"] = norms_valid
    report["fragments_total"] = fragments_total
    report["responsibility_hints_total"] = responsibilities_total
    report["responsibility_evidence_items_total"] = responsibility_evidence_total
    report["lineage_hints_total"] = lineage_total
    report["duplicate_norm_id_count"] = sum(1 for _, c in seen_norm_ids.items() if c > 1)
    report["duplicate_boe_id_count"] = sum(1 for _, c in seen_boe_ids.items() if c > 1)
    return report


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate sanction_norms_seed_v1 JSON")
    ap.add_argument("--seed", default="etl/data/seeds/sanction_norms_seed_v1.json")
    ap.add_argument("--out", default="", help="optional output JSON path")
    ap.add_argument("--max-errors", type=int, default=200)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    report = validate_seed(Path(args.seed), max_errors=int(args.max_errors))
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if bool(report.get("valid")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
