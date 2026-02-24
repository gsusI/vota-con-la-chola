#!/usr/bin/env python3
"""Validate programas_partidos manifest CSV with deterministic checks."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REQUIRED_COLUMNS = (
    "party_id",
    "party_name",
    "election_cycle",
    "kind",
)
OPTIONAL_COLUMNS = (
    "source_url",
    "format_hint",
    "language",
    "scope",
    "snapshot_date",
    "local_path",
    "notes",
)
ALLOWED_FORMAT_HINTS = {"", "html", "pdf", "xml", "txt", "md"}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _norm(v: Any) -> str:
    return str(v or "").strip()


def _add_error(errors: list[dict[str, Any]], *, code: str, row_number: int, message: str, max_errors: int) -> None:
    if len(errors) >= int(max_errors):
        return
    errors.append(
        {
            "code": str(code),
            "row_number": int(row_number),
            "message": str(message),
        }
    )


def _is_valid_url(url: str) -> bool:
    p = urlparse(url)
    if p.scheme not in ("http", "https"):
        return False
    return bool(p.netloc)


def validate_manifest(
    manifest_path: Path,
    *,
    require_local_path: bool = False,
    max_errors: int = 200,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "generated_at": now_utc_iso(),
        "manifest_path": str(manifest_path),
        "valid": False,
        "rows_total": 0,
        "rows_valid": 0,
        "errors_count": 0,
        "warnings_count": 0,
        "duplicate_key_count": 0,
        "party_ids_distinct": 0,
        "election_cycles": [],
        "errors": [],
        "warnings": [],
    }

    if not manifest_path.exists():
        report["errors"] = [{"code": "manifest_not_found", "row_number": 0, "message": f"Manifest not found: {manifest_path}"}]
        report["errors_count"] = 1
        return report
    if manifest_path.is_dir():
        report["errors"] = [{"code": "manifest_is_dir", "row_number": 0, "message": f"Manifest is a directory: {manifest_path}"}]
        report["errors_count"] = 1
        return report

    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    keys_seen: dict[tuple[str, str, str], int] = {}
    party_ids: set[int] = set()
    election_cycles: set[str] = set()

    try:
        with manifest_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = [str(x or "").strip() for x in (reader.fieldnames or [])]
            fieldname_set = set(fieldnames)

            missing_cols = [c for c in REQUIRED_COLUMNS if c not in fieldname_set]
            if missing_cols:
                report["errors"] = [
                    {
                        "code": "missing_required_columns",
                        "row_number": 0,
                        "message": f"Missing required columns: {', '.join(missing_cols)}",
                    }
                ]
                report["errors_count"] = 1
                return report

            unknown_cols = sorted(c for c in fieldname_set if c and c not in set(REQUIRED_COLUMNS + OPTIONAL_COLUMNS))
            if unknown_cols:
                warnings.append(
                    {
                        "code": "unknown_columns",
                        "row_number": 0,
                        "message": f"Unknown columns present: {', '.join(unknown_cols)}",
                    }
                )

            row_number = 1
            rows_total = 0
            rows_valid = 0
            for row in reader:
                row_number += 1
                if not isinstance(row, dict):
                    _add_error(
                        errors,
                        code="bad_row",
                        row_number=row_number,
                        message="Row is not a mapping",
                        max_errors=max_errors,
                    )
                    continue

                rows_total += 1
                party_id_raw = _norm(row.get("party_id"))
                party_name = _norm(row.get("party_name"))
                election_cycle = _norm(row.get("election_cycle"))
                kind = _norm(row.get("kind"))
                source_url = _norm(row.get("source_url"))
                local_path_raw = _norm(row.get("local_path"))
                snapshot_date = _norm(row.get("snapshot_date"))
                format_hint = _norm(row.get("format_hint")).lower()

                row_ok = True

                if not party_id_raw:
                    row_ok = False
                    _add_error(
                        errors,
                        code="missing_party_id",
                        row_number=row_number,
                        message="party_id is required",
                        max_errors=max_errors,
                    )
                    party_id_int = None
                else:
                    try:
                        party_id_int = int(party_id_raw)
                        if party_id_int <= 0:
                            raise ValueError("party_id must be > 0")
                    except Exception:
                        row_ok = False
                        party_id_int = None
                        _add_error(
                            errors,
                            code="invalid_party_id",
                            row_number=row_number,
                            message=f"party_id must be positive integer, got {party_id_raw!r}",
                            max_errors=max_errors,
                        )

                if not party_name:
                    row_ok = False
                    _add_error(
                        errors,
                        code="missing_party_name",
                        row_number=row_number,
                        message="party_name is required",
                        max_errors=max_errors,
                    )

                if not election_cycle:
                    row_ok = False
                    _add_error(
                        errors,
                        code="missing_election_cycle",
                        row_number=row_number,
                        message="election_cycle is required",
                        max_errors=max_errors,
                    )

                if not kind:
                    row_ok = False
                    _add_error(
                        errors,
                        code="missing_kind",
                        row_number=row_number,
                        message="kind is required",
                        max_errors=max_errors,
                    )

                if require_local_path and not local_path_raw:
                    row_ok = False
                    _add_error(
                        errors,
                        code="missing_local_path_required",
                        row_number=row_number,
                        message="local_path is required by --require-local-path",
                        max_errors=max_errors,
                    )

                if not source_url and not local_path_raw:
                    row_ok = False
                    _add_error(
                        errors,
                        code="missing_source_and_local_path",
                        row_number=row_number,
                        message="at least one of source_url/local_path is required",
                        max_errors=max_errors,
                    )

                if source_url and not _is_valid_url(source_url):
                    row_ok = False
                    _add_error(
                        errors,
                        code="invalid_source_url",
                        row_number=row_number,
                        message=f"source_url must be absolute http/https URL, got {source_url!r}",
                        max_errors=max_errors,
                    )

                if local_path_raw:
                    p = Path(local_path_raw)
                    if not p.exists():
                        row_ok = False
                        _add_error(
                            errors,
                            code="local_path_not_found",
                            row_number=row_number,
                            message=f"local_path does not exist: {local_path_raw}",
                            max_errors=max_errors,
                        )
                    elif p.is_dir():
                        row_ok = False
                        _add_error(
                            errors,
                            code="local_path_is_dir",
                            row_number=row_number,
                            message=f"local_path is a directory: {local_path_raw}",
                            max_errors=max_errors,
                        )

                if snapshot_date:
                    try:
                        datetime.strptime(snapshot_date, "%Y-%m-%d")
                    except ValueError:
                        row_ok = False
                        _add_error(
                            errors,
                            code="invalid_snapshot_date",
                            row_number=row_number,
                            message=f"snapshot_date must be YYYY-MM-DD, got {snapshot_date!r}",
                            max_errors=max_errors,
                        )

                if format_hint not in ALLOWED_FORMAT_HINTS:
                    row_ok = False
                    _add_error(
                        errors,
                        code="invalid_format_hint",
                        row_number=row_number,
                        message=(
                            "format_hint must be one of "
                            + ", ".join(sorted(x or "<empty>" for x in ALLOWED_FORMAT_HINTS))
                            + f"; got {format_hint!r}"
                        ),
                        max_errors=max_errors,
                    )

                if election_cycle and kind and party_id_raw:
                    key = (election_cycle, party_id_raw, kind)
                    if key in keys_seen:
                        row_ok = False
                        _add_error(
                            errors,
                            code="duplicate_key",
                            row_number=row_number,
                            message=(
                                "duplicate key (election_cycle, party_id, kind): "
                                f"{key} first seen at row {keys_seen[key]}"
                            ),
                            max_errors=max_errors,
                        )
                    else:
                        keys_seen[key] = row_number

                if row_ok:
                    rows_valid += 1
                    if party_id_int is not None:
                        party_ids.add(int(party_id_int))
                    if election_cycle:
                        election_cycles.add(election_cycle)

            report["rows_total"] = int(rows_total)
            report["rows_valid"] = int(rows_valid)
    except Exception as exc:  # noqa: BLE001
        report["errors"] = [
            {
                "code": "manifest_read_error",
                "row_number": 0,
                "message": f"{type(exc).__name__}: {exc}",
            }
        ]
        report["errors_count"] = 1
        return report

    duplicate_key_count = sum(1 for e in errors if str(e.get("code")) == "duplicate_key")
    report["errors"] = errors
    report["warnings"] = warnings
    report["errors_count"] = int(len(errors))
    report["warnings_count"] = int(len(warnings))
    report["duplicate_key_count"] = int(duplicate_key_count)
    report["party_ids_distinct"] = int(len(party_ids))
    report["election_cycles"] = sorted(election_cycles)
    report["valid"] = bool(report["errors_count"] == 0)
    return report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate programas_partidos manifest CSV")
    p.add_argument("--manifest", required=True, help="Path to manifest CSV")
    p.add_argument(
        "--require-local-path",
        action="store_true",
        help="Require local_path for every row",
    )
    p.add_argument(
        "--max-errors",
        type=int,
        default=200,
        help="Maximum number of detailed row errors to retain",
    )
    p.add_argument("--out", default="", help="Optional output JSON path")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    report = validate_manifest(
        Path(str(args.manifest)),
        require_local_path=bool(args.require_local_path),
        max_errors=max(1, int(args.max_errors)),
    )
    payload = json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if args.out:
        out_path = Path(str(args.out))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(f"OK wrote: {out_path}")
    print(payload, end="")
    return 0 if bool(report.get("valid")) else 1


if __name__ == "__main__":
    raise SystemExit(main())

