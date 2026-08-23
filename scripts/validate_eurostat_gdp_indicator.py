#!/usr/bin/env python3
"""Independently validate the real Eurostat GDP indicator release."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = REPO_ROOT / (
    "etl/data/object-origin/eurostat-indicators/85/84/"
    "8584b2c144ad608be5f28e2fc028517ba7c583a6245ca65bdc87238f1e1cf491.json"
)
RAW_BYTES = 4_763_587
RAW_SHA256 = "8584b2c144ad608be5f28e2fc028517ba7c583a6245ca65bdc87238f1e1cf491"
MANIFEST_PATH = REPO_ROOT / (
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "eurostat-indicator-real-s2-semantic-manifest.json"
)
MANIFEST_SHA256 = "b8d8bde43f8e788f465ad980cea2c6803822a2ea71584ff7390d7fed6078ddbc"
DEFAULT_DB = REPO_ROOT / "etl/data/staging/indicators-eurostat-gdp-mvp.db"
DEFAULT_PUBLISHED = REPO_ROOT / "etl/data/published/indicators-eurostat-gdp-es.json"
DEFAULT_PUBLIC = REPO_ROOT / "ui/gh-pages-next/public/indicators/data/eurostat-gdp-es.json"
DEFAULT_REPORT = REPO_ROOT / (
    "docs/etl/sprints/INDICATORS-20260820/evidence/"
    "eurostat-gdp-validation.json"
)
EXPECTED_SCHEMA = "indicator_public_slice_v1"
EXPECTED_DATASET = "nama_10r_3gdp"
EXPECTED_UNIT = "PPS_EU27_2020_HAB"
EXPECTED_RELEASE_ID = "a5d2782888c550487087244b679cd0c5c89f95392a9de3d6a8384c734d757a69"
EXPECTED_ARTIFACT_SHA256 = "8a878b41108d2eb58989af825aa1a9309aca389c4da041b09a915230172ab8d7"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--published", type=Path, default=DEFAULT_PUBLISHED)
    parser.add_argument("--public", type=Path, default=DEFAULT_PUBLIC)
    parser.add_argument("--report-out", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_bytes(data)
    temporary.replace(path)


def scalar_at(container: Any, index: int) -> Any:
    if isinstance(container, list):
        return container[index] if index < len(container) else None
    return container.get(str(index)) if isinstance(container, dict) else None


def ordered_codes(cube: dict[str, Any], dimension_id: str) -> list[str]:
    raw = cube["dimension"][dimension_id]["category"]["index"]
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return [code for _, code in sorted((int(position), str(code)) for code, position in raw.items())]


def raw_scalar(value: Any) -> str:
    return str(value) if isinstance(value, Decimal) else canonical_json(value)


def build_expected_cells(cube: dict[str, Any]) -> dict[int, dict[str, Any]]:
    freq = ordered_codes(cube, "freq")
    units = ordered_codes(cube, "unit")
    geographies = ordered_codes(cube, "geo")
    periods = ordered_codes(cube, "time")
    sizes = [int(item) for item in cube["size"]]
    freq_index = freq.index("A")
    unit_index = units.index(EXPECTED_UNIT)
    expected: dict[int, dict[str, Any]] = {}
    for geo_index, geography in enumerate(geographies):
        if not geography.startswith("ES"):
            continue
        for time_index, period in enumerate(periods):
            flat_index = (
                ((freq_index * sizes[1] + unit_index) * sizes[2] + geo_index)
                * sizes[3]
                + time_index
            )
            value = scalar_at(cube["value"], flat_index)
            if value is None:
                continue
            status = scalar_at(cube.get("status", {}), flat_index)
            expected[flat_index] = {
                "geography_code": geography,
                "period": period,
                "raw_value_json": raw_scalar(value),
                "source_status_code": None if status is None else str(status),
            }
    return expected


def main() -> int:
    args = parse_args()
    checks: dict[str, bool] = {}
    raw_bytes = RAW_PATH.read_bytes()
    checks["raw_bytes"] = len(raw_bytes) == RAW_BYTES
    checks["raw_sha256"] = sha256_bytes(raw_bytes) == RAW_SHA256
    checks["corpus_manifest_sha256"] = sha256_file(MANIFEST_PATH) == MANIFEST_SHA256
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    checks["million_row_corpus"] = int(manifest["totals"]["rows"]) == 1_755_809
    checks["million_row_corpus_validated"] = bool(manifest.get("analytical_partition_gate_passed"))

    published_bytes = args.published.read_bytes()
    public_bytes = args.public.read_bytes()
    checks["published_public_byte_parity"] = published_bytes == public_bytes
    artifact_sha256 = sha256_bytes(published_bytes)
    checks["artifact_sha256"] = artifact_sha256 == EXPECTED_ARTIFACT_SHA256
    artifact = json.loads(published_bytes)
    checks["schema_version"] = artifact.get("schema_version") == EXPECTED_SCHEMA
    release_id = str(artifact.get("release_id") or "")
    unsigned = dict(artifact)
    unsigned.pop("release_id", None)
    checks["release_hash"] = release_id == sha256_bytes(canonical_json(unsigned).encode("utf-8"))
    checks["pinned_release_id"] = release_id == EXPECTED_RELEASE_ID
    checks["real_only_policy"] = artifact.get("policy", {}).get("real_data_only") is True
    checks["no_mock_policy"] = artifact.get("policy", {}).get("synthetic_or_mock") is False
    checks["no_causal_claim"] = artifact.get("policy", {}).get("causal_claim") == "none"
    checks["baseline_only"] = artifact.get("indicator_release", {}).get("comparison_state") == "baseline"
    checks["dataset"] = artifact.get("indicator", {}).get("dataset_code") == EXPECTED_DATASET
    checks["unit"] = artifact.get("indicator", {}).get("unit_code") == EXPECTED_UNIT

    cube = json.loads(raw_bytes, parse_float=Decimal, parse_int=Decimal)
    expected_cells = build_expected_cells(cube)
    actual_cells: dict[int, dict[str, Any]] = {}
    evidence_ids: set[str] = set()
    observation_ids: set[str] = set()
    series_ids: set[str] = set()
    all_public_urls = True
    all_paths_relative = True
    all_baseline = True
    all_uncertainty_explicit = True
    all_geo_es = True
    for series in artifact.get("series", []):
        series_ids.add(str(series["indicator_series_version_id"]))
        geography = str(series["geography_code"])
        all_geo_es = all_geo_es and geography.startswith("ES")
        all_paths_relative = all_paths_relative and series.get("geography_version") is None
        for observation in series.get("observations", []):
            cell_index = int(observation["raw_cell_index"])
            evidence = observation["evidence"]
            actual_cells[cell_index] = {
                "geography_code": geography,
                "period": str(observation["period_label"]),
                "raw_value_json": str(observation["raw_value_json"]),
                "source_status_code": observation.get("source_status_code"),
            }
            observation_ids.add(str(observation["indicator_observation_version_id"]))
            evidence_ids.add(str(evidence["indicator_observation_evidence_id"]))
            parsed_url = urlsplit(str(evidence["source_url"]))
            all_public_urls = all_public_urls and parsed_url.scheme == "https" and parsed_url.netloc == "ec.europa.eu"
            raw_path = str(evidence["raw_path"])
            all_paths_relative = all_paths_relative and not raw_path.startswith(("/", "file:")) and "/Users/" not in raw_path
            all_baseline = all_baseline and observation["revision_state"] == "baseline" and int(observation["revision_ordinal"]) == 1 and observation.get("previous_observation_version_id") is None
            all_uncertainty_explicit = all_uncertainty_explicit and observation["uncertainty_state"] == "not_provided"
            if evidence["value_json_pointer"] != f"/value/{cell_index}":
                checks["value_pointers"] = False
            expected_status_pointer = f"/status/{cell_index}" if observation.get("source_status_code") else None
            if evidence.get("status_json_pointer") != expected_status_pointer:
                checks["status_pointers"] = False
    checks.setdefault("value_pointers", True)
    checks.setdefault("status_pointers", True)
    checks["all_selected_cells_exact"] = actual_cells == expected_cells
    checks["series_count"] = len(series_ids) == 86 == int(artifact["coverage"]["series"])
    checks["observation_count"] = len(observation_ids) == 2_091 == int(artifact["coverage"]["observations"])
    checks["evidence_count"] = len(evidence_ids) == 2_091
    checks["identities_unique"] = len(observation_ids) == len(actual_cells) == len(evidence_ids)
    checks["official_https_urls"] = all_public_urls
    checks["repo_relative_public_paths"] = all_paths_relative
    checks["spanish_geographies_only"] = all_geo_es
    checks["revision_state_explicit"] = all_baseline
    checks["uncertainty_state_explicit"] = all_uncertainty_explicit
    checks["provisional_count"] = sum(cell["source_status_code"] == "p" for cell in actual_cells.values()) == 113

    connection = sqlite3.connect(f"file:{args.db.resolve()}?mode=ro", uri=True)
    try:
        db_counts = {
            table: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in (
                "indicator_definitions",
                "indicator_releases",
                "indicator_series_versions",
                "indicator_observation_versions",
                "indicator_observation_evidence",
            )
        }
        foreign_keys = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        db_cells = {
            int(row[0]): {
                "geography_code": str(row[1]),
                "period": str(row[2]),
                "raw_value_json": str(row[3]),
                "source_status_code": row[4],
            }
            for row in connection.execute(
                """
                SELECT o.raw_cell_index, s.geography_code, o.period_label,
                       o.raw_value_json, o.source_status_code
                FROM indicator_observation_versions AS o
                JOIN indicator_series_versions AS s
                  ON s.indicator_series_version_id = o.indicator_series_version_id
                """
            )
        }
    finally:
        connection.close()
    checks["database_counts"] = db_counts == {
        "indicator_definitions": 1,
        "indicator_releases": 1,
        "indicator_series_versions": 86,
        "indicator_observation_versions": 2_091,
        "indicator_observation_evidence": 2_091,
    }
    checks["database_cell_parity"] = db_cells == expected_cells
    checks["foreign_keys"] = not foreign_keys
    checks["integrity_check"] = integrity == "ok"

    serialized = published_bytes.decode("utf-8", errors="replace").lower()
    checks["no_synthetic_markers"] = not any(
        marker in serialized
        for marker in ("example.test", "mock data", "synthetic data", "fixture data")
    )
    checks["no_private_paths"] = all(
        marker not in serialized for marker in ("/users/", "file:///", "/home/")
    )

    failed = sorted(key for key, passed in checks.items() if not passed)
    report = {
        "schema_version": "eurostat_gdp_validation_v1",
        "status": "passed" if not failed else "failed",
        "release_id": release_id,
        "artifact_sha256": artifact_sha256,
        "checks": checks,
        "failed_checks": failed,
        "coverage": artifact.get("coverage"),
        "database_counts": db_counts,
        "raw_cells_compared": len(expected_cells),
    }
    atomic_write(args.report_out, (canonical_json(report) + "\n").encode("utf-8"))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
