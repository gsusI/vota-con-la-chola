#!/usr/bin/env python3
"""Materialize one real Eurostat indicator family with cell-level provenance."""

from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.db import apply_schema, seed_sources  # noqa: E402
from publicdata_sqlite import open_db  # noqa: E402

SOURCE_ID = "eurostat_sdmx"
DATASET_CODE = "nama_10r_3gdp"
FREQUENCY_CODE = "A"
UNIT_CODE = "PPS_EU27_2020_HAB"
INDICATOR_CODE = "gdp_current_market_prices_per_inhabitant_pps_eu27_2020"
DOMAIN_KEY = "economia_empleo"
SNAPSHOT_DATE = "2026-08-11"
SOURCE_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "nama_10r_3gdp?lang=EN&sinceTimePeriod=2000"
)
LICENSE_URL = "https://ec.europa.eu/eurostat/about/policies/copyright/"
METHODOLOGY_URL = "https://ec.europa.eu/eurostat/cache/metadata/en/reg_eco10_esms.htm"
RAW_PATH = Path(
    "etl/data/object-origin/eurostat-indicators/85/84/"
    "8584b2c144ad608be5f28e2fc028517ba7c583a6245ca65bdc87238f1e1cf491.json"
)
RAW_BYTES = 4_763_587
RAW_SHA256 = "8584b2c144ad608be5f28e2fc028517ba7c583a6245ca65bdc87238f1e1cf491"
CORPUS_MANIFEST_PATH = Path(
    "docs/etl/sprints/SCALE-FOUNDATION-20260810/evidence/"
    "eurostat-indicator-real-s2-semantic-manifest.json"
)
CORPUS_MANIFEST_BYTES = 51_065
CORPUS_MANIFEST_SHA256 = (
    "b8d8bde43f8e788f465ad980cea2c6803822a2ea71584ff7390d7fed6078ddbc"
)
CORPUS_ROWS = 1_755_809
EXTRACTION_METHOD = "eurostat_jsonstat_coordinate_projection"
EXTRACTOR_VERSION = "eurostat_gdp_es_v1"
SCHEMA_VERSION = "indicator_public_slice_v1"
NULL = "\0"

DEFAULT_SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
DEFAULT_OUT_DB = REPO_ROOT / "etl/data/staging/indicators-eurostat-gdp-mvp.db"
DEFAULT_PUBLISHED = REPO_ROOT / "etl/data/published/indicators-eurostat-gdp-es.json"
DEFAULT_PUBLIC = (
    REPO_ROOT / "ui/gh-pages-next/public/indicators/data/eurostat-gdp-es.json"
)
DEFAULT_REPORT = (
    REPO_ROOT
    / "docs/etl/sprints/INDICATORS-20260820/evidence/"
    "eurostat-gdp-materialization.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--out-db", type=Path, default=DEFAULT_OUT_DB)
    parser.add_argument("--published-out", type=Path, default=DEFAULT_PUBLISHED)
    parser.add_argument("--public-out", type=Path, default=DEFAULT_PUBLIC)
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


def stable_id(kind: str, *parts: object) -> str:
    payload = NULL.join([kind, *(str(part if part is not None else "") for part in parts)])
    return f"vclc:{kind}:{sha256_bytes(payload.encode('utf-8'))[:24]}"


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_bytes(data)
    temporary.replace(path)


def report_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def ordered_category(dimension: dict[str, Any], dimension_id: str) -> tuple[list[str], dict[str, str]]:
    category = dimension[dimension_id]["category"]
    raw_index = category["index"]
    if isinstance(raw_index, list):
        codes = [str(item) for item in raw_index]
    else:
        ordered = sorted((int(position), str(code)) for code, position in raw_index.items())
        if [position for position, _ in ordered] != list(range(len(ordered))):
            raise RuntimeError(f"non-contiguous Eurostat dimension: {dimension_id}")
        codes = [code for _, code in ordered]
    labels = {str(key): str(value) for key, value in category.get("label", {}).items()}
    return codes, labels


def scalar_at(container: Any, index: int) -> Any:
    if isinstance(container, list):
        return container[index] if index < len(container) else None
    if isinstance(container, dict):
        return container.get(str(index))
    raise TypeError("Eurostat value/status container must be an object or array")


def decimal_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def raw_scalar_json(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    return canonical_json(value)


def annual_interval(period: str) -> tuple[str, str]:
    year = int(period)
    return f"{year:04d}-01-01", f"{year:04d}-12-{calendar.monthrange(year, 12)[1]:02d}"


def geography_level(code: str) -> str:
    levels = {2: "country", 3: "NUTS1", 4: "NUTS2", 5: "NUTS3"}
    level = levels.get(len(code))
    if level is None:
        raise RuntimeError(f"unsupported Spanish NUTS code length: {code}")
    return level


def verify_inputs() -> tuple[bytes, dict[str, Any], dict[str, Any]]:
    raw_path = REPO_ROOT / RAW_PATH
    manifest_path = REPO_ROOT / CORPUS_MANIFEST_PATH
    for path in (raw_path, manifest_path):
        if not path.is_file():
            raise RuntimeError(f"missing required real artifact: {report_path(path)}")
    raw_bytes = raw_path.read_bytes()
    if len(raw_bytes) != RAW_BYTES or sha256_bytes(raw_bytes) != RAW_SHA256:
        raise RuntimeError("official Eurostat capture bytes/hash mismatch")
    if (
        manifest_path.stat().st_size != CORPUS_MANIFEST_BYTES
        or sha256_file(manifest_path) != CORPUS_MANIFEST_SHA256
    ):
        raise RuntimeError("Eurostat million-row corpus manifest bytes/hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if int(manifest.get("totals", {}).get("rows") or 0) != CORPUS_ROWS:
        raise RuntimeError("Eurostat corpus row count mismatch")
    cube = json.loads(raw_bytes, parse_float=Decimal, parse_int=Decimal)
    if cube.get("class") != "dataset" or cube.get("extension", {}).get("id", "").lower() != DATASET_CODE:
        raise RuntimeError("unexpected Eurostat JSON-stat dataset")
    if cube.get("id") != ["freq", "unit", "geo", "time"]:
        raise RuntimeError("unexpected Eurostat dimension order")
    if [int(item) for item in cube.get("size", [])] != [1, 7, 1814, 25]:
        raise RuntimeError("unexpected Eurostat cube dimensions")
    return raw_bytes, cube, manifest


def prepare_database(path: Path, schema: Path) -> sqlite3.Connection:
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = open_db(path)
    apply_schema(connection, schema)
    seed_sources(connection)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def build_materialization(cube: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    dimensions = cube["dimension"]
    frequency_codes, frequency_labels = ordered_category(dimensions, "freq")
    unit_codes, unit_labels = ordered_category(dimensions, "unit")
    geography_codes, geography_labels = ordered_category(dimensions, "geo")
    time_codes, _ = ordered_category(dimensions, "time")
    frequency_index = frequency_codes.index(FREQUENCY_CODE)
    unit_index = unit_codes.index(UNIT_CODE)
    selected_geographies = [code for code in geography_codes if code.startswith("ES")]
    status_labels = {
        str(key): str(value)
        for key, value in cube.get("extension", {}).get("status", {}).get("label", {}).items()
    }
    values = cube["value"]
    statuses = cube.get("status", {})
    sizes = [int(item) for item in cube["size"]]
    source_updated_at = str(cube.get("updated") or "") or None
    methodology_version = (
        f"jsonstat={cube.get('version')};"
        f"dataset={cube.get('extension', {}).get('version')};"
        f"datastructure={cube.get('extension', {}).get('datastructure', {}).get('version')}"
    )
    indicator_id = stable_id(
        "indicator",
        SOURCE_ID,
        DATASET_CODE,
        INDICATOR_CODE,
        FREQUENCY_CODE,
        UNIT_CODE,
    )
    release_id = stable_id("indicator-release", indicator_id, RAW_SHA256)
    definition = {
        "indicator_id": indicator_id,
        "source_id": SOURCE_ID,
        "dataset_code": DATASET_CODE,
        "indicator_code": INDICATOR_CODE,
        "label": "PIB por habitante en estándar de poder adquisitivo",
        "source_label": str(cube.get("label") or DATASET_CODE),
        "definition": (
            "Producto interior bruto a precios corrientes por habitante, expresado "
            "en estándar de poder adquisitivo PPS UE-27 desde 2020."
        ),
        "domain_key": DOMAIN_KEY,
        "frequency_code": FREQUENCY_CODE,
        "frequency_label": frequency_labels[FREQUENCY_CODE],
        "unit_code": UNIT_CODE,
        "unit_label": unit_labels[UNIT_CODE],
        "methodology_version": methodology_version,
        "methodology_url": METHODOLOGY_URL,
        "revision_policy": "append_new_release_and_compare_every_observation",
        "license_url": LICENSE_URL,
        "source_url": SOURCE_URL,
    }
    series_records: list[dict[str, Any]] = []
    time_size = sizes[3]
    for geo_code in selected_geographies:
        geo_index = geography_codes.index(geo_code)
        stable_series_key = (
            f"{DATASET_CODE}|freq={FREQUENCY_CODE}|unit={UNIT_CODE}|geo={geo_code}"
        )
        series_version_id = stable_id("indicator-series-version", release_id, stable_series_key)
        observations: list[dict[str, Any]] = []
        for time_index, period in enumerate(time_codes):
            flat_index = (
                ((frequency_index * sizes[1] + unit_index) * sizes[2] + geo_index)
                * time_size
                + time_index
            )
            raw_value = scalar_at(values, flat_index)
            if raw_value is None:
                continue
            value_decimal = decimal_text(raw_value)
            value_text = None if value_decimal is not None else str(raw_value)
            status_code_raw = scalar_at(statuses, flat_index)
            status_code = str(status_code_raw) if status_code_raw is not None else None
            labels = []
            if status_code:
                labels.append(
                    {
                        "code": status_code,
                        "label": status_labels.get(status_code),
                    }
                )
            period_start, period_end = annual_interval(period)
            observation_id = stable_id(
                "indicator-observation-version",
                series_version_id,
                period,
                raw_scalar_json(raw_value),
                status_code,
            )
            evidence_id = stable_id(
                "indicator-observation-evidence",
                observation_id,
                RAW_SHA256,
                flat_index,
            )
            observations.append(
                {
                    "indicator_observation_version_id": observation_id,
                    "period_label": period,
                    "period_start": period_start,
                    "period_end": period_end,
                    "interval_kind": "calendar_year",
                    "value_decimal": value_decimal,
                    "value_text": value_text,
                    "source_status_code": status_code,
                    "source_status_labels": labels,
                    "uncertainty_state": "not_provided",
                    "revision_ordinal": 1,
                    "revision_state": "baseline",
                    "previous_observation_version_id": None,
                    "source_published_at": source_updated_at,
                    "raw_cell_index": flat_index,
                    "raw_value_json": raw_scalar_json(raw_value),
                    "evidence": {
                        "indicator_observation_evidence_id": evidence_id,
                        "source_url": SOURCE_URL,
                        "source_content_sha256": RAW_SHA256,
                        "raw_path": RAW_PATH.as_posix(),
                        "value_json_pointer": f"/value/{flat_index}",
                        "status_json_pointer": f"/status/{flat_index}" if status_code else None,
                        "extraction_method": EXTRACTION_METHOD,
                        "extractor_version": EXTRACTOR_VERSION,
                    },
                }
            )
        if observations:
            series_records.append(
                {
                    "indicator_series_version_id": series_version_id,
                    "stable_series_key": stable_series_key,
                    "geography_code": geo_code,
                    "geography_name": geography_labels.get(geo_code),
                    "geography_system": "NUTS",
                    "geography_level": geography_level(geo_code),
                    "geography_version": None,
                    "dimensions": {
                        "freq": FREQUENCY_CODE,
                        "unit": UNIT_CODE,
                        "geo": geo_code,
                    },
                    "observations": observations,
                }
            )
    if not series_records:
        raise RuntimeError("Eurostat projection produced no Spanish series")
    return {
        "definition": definition,
        "indicator_release_id": release_id,
        "source_updated_at": source_updated_at,
        "source_metadata": {
            "agency": cube.get("source"),
            "jsonstat_version": cube.get("version"),
            "dataset_version": cube.get("extension", {}).get("version"),
            "datastructure": cube.get("extension", {}).get("datastructure"),
            "cube_dimensions": cube.get("id"),
            "cube_sizes": sizes,
            "cube_observations": len(cube.get("value", {})),
            "status_labels": status_labels,
        },
    }, series_records


def insert_materialization(
    connection: sqlite3.Connection,
    release: dict[str, Any],
    series_records: list[dict[str, Any]],
) -> None:
    definition = release["definition"]
    timestamp = f"{SNAPSHOT_DATE}T00:00:00+00:00"
    connection.execute(
        """
        INSERT INTO indicator_definitions (
          indicator_id, source_id, dataset_code, indicator_code, label, definition,
          domain_key, frequency_code, frequency_label, unit_code, unit_label,
          methodology_version, methodology_url, revision_policy, license_url,
          source_url, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            definition["indicator_id"], definition["source_id"],
            definition["dataset_code"], definition["indicator_code"],
            definition["label"], definition["definition"], definition["domain_key"],
            definition["frequency_code"], definition["frequency_label"],
            definition["unit_code"], definition["unit_label"],
            definition["methodology_version"], definition["methodology_url"],
            definition["revision_policy"], definition["license_url"],
            definition["source_url"], timestamp, timestamp,
        ),
    )
    connection.execute(
        """
        INSERT INTO indicator_releases (
          indicator_release_id, indicator_id, source_snapshot_date,
          source_updated_at, source_url, source_content_sha256, source_bytes,
          raw_path, source_metadata_json, comparison_state,
          previous_indicator_release_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'baseline', NULL, ?, ?)
        """,
        (
            release["indicator_release_id"], definition["indicator_id"], SNAPSHOT_DATE,
            release["source_updated_at"], SOURCE_URL, RAW_SHA256, RAW_BYTES,
            RAW_PATH.as_posix(), canonical_json(release["source_metadata"]),
            timestamp, timestamp,
        ),
    )
    for series in series_records:
        connection.execute(
            """
            INSERT INTO indicator_series_versions (
              indicator_series_version_id, indicator_id, indicator_release_id,
              stable_series_key, geography_code, geography_name, geography_system,
              geography_level, geography_version, territory_id, dimensions_json,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                series["indicator_series_version_id"], definition["indicator_id"],
                release["indicator_release_id"], series["stable_series_key"],
                series["geography_code"], series["geography_name"],
                series["geography_system"], series["geography_level"],
                series["geography_version"], canonical_json(series["dimensions"]),
                timestamp, timestamp,
            ),
        )
        observation_rows = []
        evidence_rows = []
        for observation in series["observations"]:
            observation_rows.append(
                (
                    observation["indicator_observation_version_id"],
                    series["indicator_series_version_id"],
                    release["indicator_release_id"], observation["period_label"],
                    observation["period_start"], observation["period_end"],
                    observation["interval_kind"], observation["value_decimal"],
                    observation["value_text"], observation["source_status_code"],
                    canonical_json(observation["source_status_labels"]),
                    observation["uncertainty_state"], observation["revision_ordinal"],
                    observation["revision_state"], observation["source_published_at"],
                    observation["raw_cell_index"], observation["raw_value_json"],
                    timestamp, timestamp,
                )
            )
            evidence = observation["evidence"]
            evidence_rows.append(
                (
                    evidence["indicator_observation_evidence_id"],
                    observation["indicator_observation_version_id"],
                    evidence["source_url"], evidence["source_content_sha256"],
                    evidence["raw_path"], evidence["value_json_pointer"],
                    evidence["status_json_pointer"], evidence["extraction_method"],
                    evidence["extractor_version"], timestamp,
                )
            )
        connection.executemany(
            """
            INSERT INTO indicator_observation_versions (
              indicator_observation_version_id, indicator_series_version_id,
              indicator_release_id, period_label, period_start, period_end,
              interval_kind, value_decimal, value_text, source_status_code,
              source_status_labels_json, uncertainty_lower_decimal,
              uncertainty_upper_decimal, uncertainty_state, revision_ordinal,
              revision_state, previous_observation_version_id, source_published_at,
              raw_cell_index, raw_value_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, NULL,
                      ?, ?, ?, ?, ?)
            """,
            observation_rows,
        )
        connection.executemany(
            """
            INSERT INTO indicator_observation_evidence (
              indicator_observation_evidence_id, indicator_observation_version_id,
              source_url, source_content_sha256, raw_path, value_json_pointer,
              status_json_pointer, extraction_method, extractor_version, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            evidence_rows,
        )
    connection.commit()


def main() -> int:
    args = parse_args()
    raw_bytes, cube, manifest = verify_inputs()
    release, series_records = build_materialization(cube)
    connection = prepare_database(args.out_db, args.schema)
    try:
        insert_materialization(connection, release, series_records)
        foreign_keys = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        counts = {
            "indicator_definitions": int(connection.execute("SELECT COUNT(*) FROM indicator_definitions").fetchone()[0]),
            "indicator_releases": int(connection.execute("SELECT COUNT(*) FROM indicator_releases").fetchone()[0]),
            "indicator_series_versions": int(connection.execute("SELECT COUNT(*) FROM indicator_series_versions").fetchone()[0]),
            "indicator_observation_versions": int(connection.execute("SELECT COUNT(*) FROM indicator_observation_versions").fetchone()[0]),
            "indicator_observation_evidence": int(connection.execute("SELECT COUNT(*) FROM indicator_observation_evidence").fetchone()[0]),
        }
        if foreign_keys or integrity != "ok":
            raise RuntimeError(
                f"database validation failed: fk={len(foreign_keys)} integrity={integrity}"
            )
    finally:
        connection.close()

    observations = [observation for series in series_records for observation in series["observations"]]
    status_counts: dict[str, int] = {}
    level_counts: dict[str, int] = {}
    for observation in observations:
        key = observation["source_status_code"] or "none"
        status_counts[key] = status_counts.get(key, 0) + 1
    for series in series_records:
        key = series["geography_level"]
        level_counts[key] = level_counts.get(key, 0) + 1

    public_series = []
    for series in series_records:
        public_series.append(
            {
                **{key: value for key, value in series.items() if key != "observations"},
                "observation_count": len(series["observations"]),
                "observations": series["observations"],
            }
        )
    core = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": f"{SNAPSHOT_DATE}T00:00:00+00:00",
        "policy": {
            "real_data_only": True,
            "synthetic_or_mock": False,
            "official_public_domain_information_retained": True,
            "revision_mode": "append_only_baseline",
            "causal_claim": "none",
            "political_merit_or_blame": "not_assessed",
        },
        "source": {
            "source_id": SOURCE_ID,
            "source_name": "Eurostat",
            "source_url": SOURCE_URL,
            "snapshot_date": SNAPSHOT_DATE,
            "source_updated_at": release["source_updated_at"],
            "raw_path": RAW_PATH.as_posix(),
            "raw_bytes": len(raw_bytes),
            "raw_content_sha256": RAW_SHA256,
            "methodology_url": METHODOLOGY_URL,
            "license_url": LICENSE_URL,
            "extractor_method": EXTRACTION_METHOD,
            "extractor_version": EXTRACTOR_VERSION,
        },
        "full_corpus": {
            "manifest_path": CORPUS_MANIFEST_PATH.as_posix(),
            "manifest_bytes": CORPUS_MANIFEST_BYTES,
            "manifest_sha256": CORPUS_MANIFEST_SHA256,
            "observations": int(manifest["totals"]["rows"]),
            "series": int(manifest["totals"]["series_table_rows"]),
            "parquet_files": int(manifest["totals"]["files"]),
            "parquet_bytes": int(manifest["totals"]["parquet_bytes"]),
            "representative_scope": False,
        },
        "indicator": release["definition"],
        "indicator_release": {
            "indicator_release_id": release["indicator_release_id"],
            "comparison_state": "baseline",
            "previous_indicator_release_id": None,
            "source_metadata": release["source_metadata"],
        },
        "coverage": {
            **counts,
            "series": len(series_records),
            "observations": len(observations),
            "period_min": min(item["period_label"] for item in observations),
            "period_max": max(item["period_label"] for item in observations),
            "geography_levels": dict(sorted(level_counts.items())),
            "source_status_codes": dict(sorted(status_counts.items())),
            "uncertainty_not_provided": sum(
                item["uncertainty_state"] == "not_provided" for item in observations
            ),
            "revision_baseline": sum(item["revision_state"] == "baseline" for item in observations),
        },
        "limitations": [
            "GDP per inhabitant in PPS is economic context, not a complete measure of welfare, distribution, service quality, integrity, or democratic accountability.",
            "This is one real Eurostat family selected by an explicit Spain/unit rule; the four acquired datasets are not a representative outcome codebook.",
            "Only one verified source release is available here, so every observation is baseline; no real revision, deletion, or correction is claimed yet.",
            "Eurostat status codes are retained exactly. Breaks, provisional values, estimates, confidentiality, changing NUTS boundaries, and methodology must be considered before comparison.",
            "No political action is credited or blamed and no causal effect is inferred.",
        ],
        "series": public_series,
    }
    release_id = sha256_bytes(canonical_json(core).encode("utf-8"))
    artifact = {"release_id": release_id, **core}
    artifact_bytes = (canonical_json(artifact) + "\n").encode("utf-8")
    artifact_sha256 = sha256_bytes(artifact_bytes)
    atomic_write(args.published_out, artifact_bytes)
    atomic_write(args.public_out, artifact_bytes)

    report = {
        "schema_version": "eurostat_gdp_materialization_v1",
        "status": "passed",
        "release_id": release_id,
        "artifact_sha256": artifact_sha256,
        "artifact_bytes": len(artifact_bytes),
        "source": artifact["source"],
        "full_corpus": artifact["full_corpus"],
        "coverage": artifact["coverage"],
        "database": {
            "path": args.out_db.name,
            "foreign_key_violations": 0,
            "integrity_check": "ok",
        },
        "outputs": {
            "published": report_path(args.published_out),
            "public": report_path(args.public_out),
            "report": report_path(args.report_out),
        },
    }
    atomic_write(args.report_out, (canonical_json(report) + "\n").encode("utf-8"))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
