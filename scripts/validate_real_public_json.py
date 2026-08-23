#!/usr/bin/env python3
"""Fail closed unless public JSON inputs are real, present, and parseable."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


FORBIDDEN_TEXT_MARKERS = (
    "dev-local-stub",
    "example.invalid",
    "example.test",
    "fixture data",
    "generated person",
    "mock data",
    "mock person",
    "placeholder data",
    "placeholder person",
    "synthetic data",
    "synthetic sample",
)
NON_REAL_FLAG_KEYS = {
    "is_mock",
    "is_placeholder",
    "is_synthetic",
    "mock",
    "placeholder",
    "synthetic",
    "synthetic_or_mock",
}
NON_REAL_PROVENANCE_KEYS = {
    "data_origin",
    "generated_at",
    "generated_by",
    "origin_kind",
    "snapshot_db",
}
NON_REAL_PROVENANCE_VALUE = re.compile(
    r"(?:^|[^a-z])(?:mock|placeholder|stub|synthetic)(?:$|[^a-z])",
    re.IGNORECASE,
)


def _json_files(path: Path) -> tuple[list[Path], list[str]]:
    if not path.exists():
        return [], [f"required artifact missing: {path}"]
    if path.is_file():
        return [path], []
    if not path.is_dir():
        return [], [f"required artifact is not a file or directory: {path}"]
    files = sorted(
        candidate for candidate in path.rglob("*.json") if candidate.is_file()
    )
    if not files:
        return [], [f"required artifact directory has no JSON files: {path}"]
    return files, []


def _non_real_findings(value: Any, location: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            key_folded = key_text.casefold()
            child_location = f"{location}.{key_text}"
            if key_folded in NON_REAL_FLAG_KEYS and child is True:
                findings.append(f"{child_location} marks non-real data")
            if key_folded == "real_data_only" and child is not True:
                findings.append(f"{child_location} does not enforce real-only data")
            if (
                key_folded in NON_REAL_PROVENANCE_KEYS
                and isinstance(child, str)
                and NON_REAL_PROVENANCE_VALUE.search(child)
            ):
                findings.append(f"{child_location} contains non-real provenance marker")
            findings.extend(_non_real_findings(child, child_location))
        return findings
    if isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_non_real_findings(child, f"{location}[{index}]"))
        return findings
    if isinstance(value, str):
        folded = value.casefold()
        for marker in FORBIDDEN_TEXT_MARKERS:
            if marker in folded:
                findings.append(f"{location} contains forbidden marker {marker}")
    return findings


def validate_paths(paths: list[Path]) -> dict[str, Any]:
    artifact_paths: list[Path] = []
    errors: list[str] = []
    seen: set[Path] = set()
    for path in paths:
        files, path_errors = _json_files(path)
        errors.extend(path_errors)
        for candidate in files:
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                artifact_paths.append(candidate)

    artifacts: list[dict[str, Any]] = []
    for path in artifact_paths:
        artifact_errors: list[str] = []
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raw = b""
            artifact_errors.append(f"cannot read {path}: {exc}")
        if not raw.strip():
            artifact_errors.append(f"required artifact is empty: {path}")
            payload: Any = None
        else:
            try:
                payload = json.loads(raw)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                payload = None
                artifact_errors.append(f"invalid JSON in {path}: {exc}")
        if payload is not None:
            if not isinstance(payload, (dict, list)):
                artifact_errors.append(f"JSON root must be object or array: {path}")
            elif not payload:
                artifact_errors.append(f"JSON root must not be empty: {path}")
            artifact_errors.extend(
                f"{path}: {finding}" for finding in _non_real_findings(payload)
            )
        errors.extend(artifact_errors)
        artifacts.append(
            {
                "path": str(path),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest() if raw else "",
                "errors": artifact_errors,
            }
        )

    return {
        "schema_version": "real_public_json_validation_v1",
        "passed": not errors,
        "artifacts_total": len(artifacts),
        "artifacts": artifacts,
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path",
        action="append",
        required=True,
        help="Required JSON file or directory; repeat for multiple inputs",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = validate_paths([Path(raw) for raw in args.path])
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    if not report["passed"]:
        for error in report["errors"]:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
