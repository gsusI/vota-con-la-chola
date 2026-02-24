#!/usr/bin/env python3
"""Validate citizen concerns config contract (ui/citizen/concerns_v1.json)."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_REQUIRED_KEYS = ("version", "concerns", "packs")
ROOT_OPTIONAL_KEYS = ("notes", "normalization")
NORMALIZATION_REQUIRED_KEYS = ("lowercase", "strip_diacritics")
CONCERN_REQUIRED_KEYS = ("id", "label", "description", "keywords")
PACK_REQUIRED_KEYS = ("id", "label", "concern_ids", "tradeoff")
ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _add_issue(
    issues: list[dict[str, Any]],
    *,
    code: str,
    path: str,
    message: str,
    max_issues: int,
) -> None:
    if len(issues) >= int(max_issues):
        return
    issues.append(
        {
            "code": str(code),
            "path": str(path),
            "message": str(message),
        }
    )


def validate_concerns_config(path: Path, *, max_issues: int = 200) -> dict[str, Any]:
    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "path": str(path),
        "valid": False,
        "version": None,
        "concerns_total": 0,
        "packs_total": 0,
        "keywords_total": 0,
        "errors_count": 0,
        "warnings_count": 0,
        "errors": [],
        "warnings": [],
    }

    if not path.exists():
        report["errors"] = [
            {
                "code": "config_not_found",
                "path": "$",
                "message": f"Config not found: {path}",
            }
        ]
        report["errors_count"] = 1
        return report
    if path.is_dir():
        report["errors"] = [
            {
                "code": "config_is_dir",
                "path": "$",
                "message": f"Config path is a directory: {path}",
            }
        ]
        report["errors_count"] = 1
        return report

    try:
        root = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report["errors"] = [
            {
                "code": "invalid_json",
                "path": "$",
                "message": f"Invalid JSON: {exc}",
            }
        ]
        report["errors_count"] = 1
        return report

    if not isinstance(root, dict):
        report["errors"] = [
            {
                "code": "root_not_object",
                "path": "$",
                "message": "Root must be a JSON object",
            }
        ]
        report["errors_count"] = 1
        return report

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    root_keys = set(root.keys())
    missing_root = [k for k in ROOT_REQUIRED_KEYS if k not in root_keys]
    if missing_root:
        _add_issue(
            errors,
            code="missing_root_keys",
            path="$",
            message=f"Missing required root keys: {', '.join(missing_root)}",
            max_issues=max_issues,
        )

    allowed_root = set(ROOT_REQUIRED_KEYS + ROOT_OPTIONAL_KEYS)
    unknown_root = sorted(str(k) for k in root_keys if k not in allowed_root)
    if unknown_root:
        _add_issue(
            warnings,
            code="unknown_root_keys",
            path="$",
            message=f"Unknown root keys: {', '.join(unknown_root)}",
            max_issues=max_issues,
        )

    version = _norm(root.get("version"))
    report["version"] = version or None
    if not version:
        _add_issue(errors, code="missing_version", path="$.version", message="version is required", max_issues=max_issues)
    elif version != "v1":
        _add_issue(
            errors,
            code="invalid_version",
            path="$.version",
            message=f"Expected version 'v1', got {version!r}",
            max_issues=max_issues,
        )

    normalization = root.get("normalization")
    if normalization is not None:
        if not isinstance(normalization, dict):
            _add_issue(
                errors,
                code="normalization_not_object",
                path="$.normalization",
                message="normalization must be an object",
                max_issues=max_issues,
            )
        else:
            norm_keys = set(normalization.keys())
            missing_norm = [k for k in NORMALIZATION_REQUIRED_KEYS if k not in norm_keys]
            if missing_norm:
                _add_issue(
                    errors,
                    code="missing_normalization_keys",
                    path="$.normalization",
                    message=f"Missing required normalization keys: {', '.join(missing_norm)}",
                    max_issues=max_issues,
                )
            unknown_norm = sorted(str(k) for k in norm_keys if k not in set(NORMALIZATION_REQUIRED_KEYS))
            if unknown_norm:
                _add_issue(
                    warnings,
                    code="unknown_normalization_keys",
                    path="$.normalization",
                    message=f"Unknown normalization keys: {', '.join(unknown_norm)}",
                    max_issues=max_issues,
                )
            for key in NORMALIZATION_REQUIRED_KEYS:
                if key in normalization and not isinstance(normalization[key], bool):
                    _add_issue(
                        errors,
                        code="invalid_normalization_value",
                        path=f"$.normalization.{key}",
                        message=f"{key} must be boolean",
                        max_issues=max_issues,
                    )

    concern_ids_seen: set[str] = set()
    concerns = root.get("concerns")
    if not isinstance(concerns, list):
        _add_issue(
            errors,
            code="concerns_not_list",
            path="$.concerns",
            message="concerns must be a list",
            max_issues=max_issues,
        )
        concerns = []
    if not concerns:
        _add_issue(
            errors,
            code="concerns_empty",
            path="$.concerns",
            message="concerns must contain at least one item",
            max_issues=max_issues,
        )

    keywords_total = 0
    for i, item in enumerate(concerns):
        ctx = f"$.concerns[{i}]"
        if not isinstance(item, dict):
            _add_issue(
                errors,
                code="concern_not_object",
                path=ctx,
                message="concern item must be an object",
                max_issues=max_issues,
            )
            continue

        keys = set(item.keys())
        missing = [k for k in CONCERN_REQUIRED_KEYS if k not in keys]
        if missing:
            _add_issue(
                errors,
                code="missing_concern_keys",
                path=ctx,
                message=f"Missing required keys: {', '.join(missing)}",
                max_issues=max_issues,
            )
        unknown = sorted(str(k) for k in keys if k not in set(CONCERN_REQUIRED_KEYS))
        if unknown:
            _add_issue(
                warnings,
                code="unknown_concern_keys",
                path=ctx,
                message=f"Unknown concern keys: {', '.join(unknown)}",
                max_issues=max_issues,
            )

        cid = _norm(item.get("id"))
        if not cid:
            _add_issue(errors, code="missing_concern_id", path=f"{ctx}.id", message="id is required", max_issues=max_issues)
        elif not ID_PATTERN.match(cid):
            _add_issue(
                errors,
                code="invalid_concern_id",
                path=f"{ctx}.id",
                message=f"id must match {ID_PATTERN.pattern}, got {cid!r}",
                max_issues=max_issues,
            )
        elif cid in concern_ids_seen:
            _add_issue(
                errors,
                code="duplicate_concern_id",
                path=f"{ctx}.id",
                message=f"Duplicate concern id: {cid!r}",
                max_issues=max_issues,
            )
        else:
            concern_ids_seen.add(cid)

        label = _norm(item.get("label"))
        if not label:
            _add_issue(
                errors,
                code="missing_concern_label",
                path=f"{ctx}.label",
                message="label is required",
                max_issues=max_issues,
            )

        description = _norm(item.get("description"))
        if not description:
            _add_issue(
                errors,
                code="missing_concern_description",
                path=f"{ctx}.description",
                message="description is required",
                max_issues=max_issues,
            )

        keywords = item.get("keywords")
        if not isinstance(keywords, list):
            _add_issue(
                errors,
                code="keywords_not_list",
                path=f"{ctx}.keywords",
                message="keywords must be a list",
                max_issues=max_issues,
            )
            continue
        if not keywords:
            _add_issue(
                errors,
                code="keywords_empty",
                path=f"{ctx}.keywords",
                message="keywords must contain at least one item",
                max_issues=max_issues,
            )
            continue

        keywords_seen: set[str] = set()
        for j, kw in enumerate(keywords):
            kw_ctx = f"{ctx}.keywords[{j}]"
            if not isinstance(kw, str):
                _add_issue(
                    errors,
                    code="keyword_not_string",
                    path=kw_ctx,
                    message="keyword must be a string",
                    max_issues=max_issues,
                )
                continue
            token = _norm(kw)
            if not token:
                _add_issue(
                    errors,
                    code="keyword_empty",
                    path=kw_ctx,
                    message="keyword cannot be empty",
                    max_issues=max_issues,
                )
                continue
            dedupe = token.casefold()
            if dedupe in keywords_seen:
                _add_issue(
                    errors,
                    code="duplicate_keyword",
                    path=kw_ctx,
                    message=f"Duplicate keyword in concern {cid!r}: {token!r}",
                    max_issues=max_issues,
                )
                continue
            keywords_seen.add(dedupe)
            keywords_total += 1

    packs = root.get("packs")
    if not isinstance(packs, list):
        _add_issue(
            errors,
            code="packs_not_list",
            path="$.packs",
            message="packs must be a list",
            max_issues=max_issues,
        )
        packs = []
    if not packs:
        _add_issue(
            errors,
            code="packs_empty",
            path="$.packs",
            message="packs must contain at least one item",
            max_issues=max_issues,
        )

    pack_ids_seen: set[str] = set()
    concerns_used_in_packs: set[str] = set()
    for i, item in enumerate(packs):
        ctx = f"$.packs[{i}]"
        if not isinstance(item, dict):
            _add_issue(
                errors,
                code="pack_not_object",
                path=ctx,
                message="pack item must be an object",
                max_issues=max_issues,
            )
            continue

        keys = set(item.keys())
        missing = [k for k in PACK_REQUIRED_KEYS if k not in keys]
        if missing:
            _add_issue(
                errors,
                code="missing_pack_keys",
                path=ctx,
                message=f"Missing required keys: {', '.join(missing)}",
                max_issues=max_issues,
            )
        unknown = sorted(str(k) for k in keys if k not in set(PACK_REQUIRED_KEYS))
        if unknown:
            _add_issue(
                warnings,
                code="unknown_pack_keys",
                path=ctx,
                message=f"Unknown pack keys: {', '.join(unknown)}",
                max_issues=max_issues,
            )

        pack_id = _norm(item.get("id"))
        if not pack_id:
            _add_issue(errors, code="missing_pack_id", path=f"{ctx}.id", message="id is required", max_issues=max_issues)
        elif not ID_PATTERN.match(pack_id):
            _add_issue(
                errors,
                code="invalid_pack_id",
                path=f"{ctx}.id",
                message=f"id must match {ID_PATTERN.pattern}, got {pack_id!r}",
                max_issues=max_issues,
            )
        elif pack_id in pack_ids_seen:
            _add_issue(
                errors,
                code="duplicate_pack_id",
                path=f"{ctx}.id",
                message=f"Duplicate pack id: {pack_id!r}",
                max_issues=max_issues,
            )
        else:
            pack_ids_seen.add(pack_id)

        label = _norm(item.get("label"))
        if not label:
            _add_issue(errors, code="missing_pack_label", path=f"{ctx}.label", message="label is required", max_issues=max_issues)

        tradeoff = _norm(item.get("tradeoff"))
        if not tradeoff:
            _add_issue(
                errors,
                code="missing_pack_tradeoff",
                path=f"{ctx}.tradeoff",
                message="tradeoff is required",
                max_issues=max_issues,
            )

        concern_ids = item.get("concern_ids")
        if not isinstance(concern_ids, list):
            _add_issue(
                errors,
                code="pack_concern_ids_not_list",
                path=f"{ctx}.concern_ids",
                message="concern_ids must be a list",
                max_issues=max_issues,
            )
            continue
        if not concern_ids:
            _add_issue(
                errors,
                code="pack_concern_ids_empty",
                path=f"{ctx}.concern_ids",
                message="concern_ids must contain at least one concern id",
                max_issues=max_issues,
            )
            continue

        ids_seen_in_pack: set[str] = set()
        for j, raw_cid in enumerate(concern_ids):
            cid_ctx = f"{ctx}.concern_ids[{j}]"
            if not isinstance(raw_cid, str):
                _add_issue(
                    errors,
                    code="pack_concern_id_not_string",
                    path=cid_ctx,
                    message="concern id must be a string",
                    max_issues=max_issues,
                )
                continue
            cid = _norm(raw_cid)
            if not cid:
                _add_issue(
                    errors,
                    code="pack_concern_id_empty",
                    path=cid_ctx,
                    message="concern id cannot be empty",
                    max_issues=max_issues,
                )
                continue
            if cid in ids_seen_in_pack:
                _add_issue(
                    errors,
                    code="duplicate_pack_concern_id",
                    path=cid_ctx,
                    message=f"Duplicate concern id in pack {pack_id!r}: {cid!r}",
                    max_issues=max_issues,
                )
                continue
            ids_seen_in_pack.add(cid)
            concerns_used_in_packs.add(cid)
            if cid not in concern_ids_seen:
                _add_issue(
                    errors,
                    code="unknown_pack_concern_id",
                    path=cid_ctx,
                    message=f"Unknown concern id referenced by pack: {cid!r}",
                    max_issues=max_issues,
                )

    uncovered = sorted(cid for cid in concern_ids_seen if cid not in concerns_used_in_packs)
    if uncovered:
        _add_issue(
            errors,
            code="concerns_without_pack",
            path="$.packs",
            message=f"Concerns not referenced by any pack: {', '.join(uncovered)}",
            max_issues=max_issues,
        )

    report["concerns_total"] = len(concern_ids_seen)
    report["packs_total"] = len(pack_ids_seen)
    report["keywords_total"] = int(keywords_total)
    report["errors_count"] = len(errors)
    report["warnings_count"] = len(warnings)
    report["errors"] = errors
    report["warnings"] = warnings
    report["valid"] = len(errors) == 0
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate citizen concerns config contract (v1).")
    ap.add_argument("--path", required=True, help="Path to concerns_v1.json")
    ap.add_argument("--out", default="", help="Optional JSON report output path")
    ap.add_argument("--max-issues", type=int, default=200, help="Maximum issues included in errors/warnings arrays")
    args = ap.parse_args()

    report = validate_concerns_config(Path(args.path), max_issues=max(int(args.max_issues), 1))
    payload = json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True)

    out_path = str(args.out or "").strip()
    if out_path:
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload + "\n", encoding="utf-8")

    print(payload)
    return 0 if bool(report.get("valid")) else 2


if __name__ == "__main__":
    raise SystemExit(main())
