#!/usr/bin/env python3
"""Fail closed when configured ETL fallback payloads lack real official provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.config import SOURCE_CONFIG  # noqa: E402


DEFAULT_REGISTRY = Path("etl/data/raw/samples/official-sample-origin-registry.json")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_PAYLOAD_MARKERS = (
    b"sample record",
    b"example.invalid",
    b"example.test",
    b'"cd-0001"',
    b"se-0001;",
    b"mu-28001-0001;",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _repo_path(raw: str, *, field: str) -> Path:
    value = str(raw or "").strip()
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field} must be a non-empty repo-relative path")
    return REPO_ROOT / path


def _official_https_url(raw: str, *, field: str) -> str:
    value = str(raw or "").strip()
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        raise ValueError(f"{field} must be an official public HTTPS URL")
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith((".test", ".invalid", ".example")):
        raise ValueError(f"{field} cannot use a test or loopback origin")
    return value


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing {label}: {path.relative_to(REPO_ROOT)}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label}: {path.relative_to(REPO_ROOT)}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object")
    return data


def _validate_sidecar(path: Path, *, sample_data: bytes) -> dict[str, Any]:
    data = _load_json(path, label="sample provenance sidecar")
    if data.get("synthetic_or_mock") is not False:
        raise ValueError(f"sidecar must declare synthetic_or_mock=false: {path.relative_to(REPO_ROOT)}")
    if (
        data.get("public_domain_personal_information_retained") is not True
        and data.get("official_public_domain_personal_information_retained") is not True
    ):
        raise ValueError(
            "sidecar must retain public-domain personal information: "
            f"{path.relative_to(REPO_ROOT)}"
        )
    _official_https_url(
        str(data.get("official_url") or data.get("source_url") or ""),
        field="sidecar official URL",
    )
    if not str(data.get("rights_basis") or "").strip():
        raise ValueError(f"sidecar rights_basis is required: {path.relative_to(REPO_ROOT)}")

    declared_sample_sha = str(data.get("sample_sha256") or "").lower()
    if declared_sample_sha and declared_sample_sha != _sha256(sample_data):
        raise ValueError(f"sidecar sample SHA-256 mismatch: {path.relative_to(REPO_ROOT)}")
    declared_sample_bytes = data.get("sample_bytes")
    if declared_sample_bytes is not None and int(declared_sample_bytes) != len(sample_data):
        raise ValueError(f"sidecar sample byte-count mismatch: {path.relative_to(REPO_ROOT)}")

    capture_path_raw = str(data.get("official_capture_path") or "").strip()
    if capture_path_raw:
        capture_path = _repo_path(capture_path_raw, field="official_capture_path")
        if not capture_path.is_file():
            raise ValueError(f"missing official capture: {capture_path_raw}")
        capture_data = capture_path.read_bytes()
        capture_sha = str(data.get("official_capture_sha256") or "").lower()
        if not SHA256_RE.fullmatch(capture_sha) or _sha256(capture_data) != capture_sha:
            raise ValueError(f"official capture SHA-256 mismatch: {capture_path_raw}")
        if int(data.get("official_capture_bytes", -1)) != len(capture_data):
            raise ValueError(f"official capture byte-count mismatch: {capture_path_raw}")
    return data


def audit_official_samples(
    *,
    source_config: dict[str, dict[str, Any]],
    registry_path: Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    registry_abs = registry_path if registry_path.is_absolute() else REPO_ROOT / registry_path
    registry = _load_json(registry_abs, label="official sample origin registry")
    if registry.get("schema_version") != "official_sample_origin_registry_v1":
        raise ValueError("unsupported official sample origin registry schema")
    policy = registry.get("policy") or {}
    required_policy = {
        "configured_fallbacks_must_be_real_official_public_data": True,
        "synthetic_or_mock_forbidden": True,
        "public_domain_personal_information_retained": True,
    }
    if any(policy.get(key) is not value for key, value in required_policy.items()):
        raise ValueError("official sample registry policy is not fail-closed")

    registry_rows = registry.get("sources")
    if not isinstance(registry_rows, list):
        raise ValueError("official sample registry sources must be a list")
    by_source: dict[str, dict[str, Any]] = {}
    for row in registry_rows:
        if not isinstance(row, dict):
            raise ValueError("official sample registry row must be an object")
        source_id = str(row.get("source_id") or "").strip()
        if not source_id or source_id in by_source:
            raise ValueError(f"missing or duplicate registry source_id: {source_id!r}")
        by_source[source_id] = row

    configured = {
        source_id: cfg
        for source_id, cfg in source_config.items()
        if str(cfg.get("fallback_file") or "").strip()
    }
    if set(by_source) != set(configured):
        missing = sorted(set(configured) - set(by_source))
        extra = sorted(set(by_source) - set(configured))
        raise ValueError(f"registry/config source mismatch: missing={missing} extra={extra}")

    sidecars_validated = 0
    total_bytes = 0
    for source_id, cfg in sorted(configured.items()):
        row = by_source[source_id]
        sample_rel = str(cfg["fallback_file"])
        if row.get("sample_path") != sample_rel:
            raise ValueError(f"sample path drift for {source_id}")
        if row.get("origin_class") != "official_public_capture_or_exact_derived_subset":
            raise ValueError(f"non-official origin class for {source_id}")
        if row.get("synthetic_or_mock") is not False:
            raise ValueError(f"synthetic/mock sample forbidden for {source_id}")
        if row.get("public_domain_personal_information_retained") is not True:
            raise ValueError(f"public identity retention must be explicit for {source_id}")

        official_url = _official_https_url(str(row.get("official_url") or ""), field="official_url")
        configured_url = _official_https_url(str(cfg.get("default_url") or ""), field="configured URL")
        if official_url != configured_url:
            raise ValueError(f"official URL drift for {source_id}")

        sample_path = _repo_path(sample_rel, field="sample_path")
        if not sample_path.is_file():
            raise ValueError(f"missing official sample for {source_id}: {sample_rel}")
        sample_data = sample_path.read_bytes()
        if not sample_data:
            raise ValueError(f"empty official sample for {source_id}")
        total_bytes += len(sample_data)
        expected_sha = str(row.get("sample_sha256") or "").lower()
        if not SHA256_RE.fullmatch(expected_sha) or _sha256(sample_data) != expected_sha:
            raise ValueError(f"sample SHA-256 mismatch for {source_id}")
        if int(row.get("sample_bytes", -1)) != len(sample_data):
            raise ValueError(f"sample byte-count mismatch for {source_id}")

        lowered = sample_data.lower()
        marker = next((item.decode("ascii") for item in FORBIDDEN_PAYLOAD_MARKERS if item in lowered), None)
        if marker:
            raise ValueError(f"forbidden invented/test marker in {source_id}: {marker}")

        sidecar_raw = str(row.get("detailed_provenance_sidecar") or "").strip()
        if sidecar_raw:
            _validate_sidecar(_repo_path(sidecar_raw, field="detailed_provenance_sidecar"), sample_data=sample_data)
            sidecars_validated += 1

    return {
        "schema_version": "official_sample_corpus_audit_v1",
        "status": "pass",
        "configured_sources": len(configured),
        "sample_bytes": total_bytes,
        "detailed_sidecars_validated": sidecars_validated,
        "synthetic_or_mock_records": 0,
        "public_domain_personal_information_retained": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--report-out", type=Path)
    return parser.parse_args()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    target = path if path.is_absolute() else REPO_ROOT / path
    try:
        target.resolve().relative_to(REPO_ROOT)
    except ValueError as exc:
        raise ValueError("report-out must remain inside the repository") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    args = parse_args()
    report = audit_official_samples(source_config=SOURCE_CONFIG, registry_path=args.registry)
    if args.report_out:
        _write_json_atomic(args.report_out, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
