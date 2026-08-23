from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_CAPTURE = REPO_ROOT / (
    "etl/data/object-origin/eurostat-indicators/85/84/"
    "8584b2c144ad608be5f28e2fc028517ba7c583a6245ca65bdc87238f1e1cf491.json"
)
EXPECTED_RAW_SHA256 = "8584b2c144ad608be5f28e2fc028517ba7c583a6245ca65bdc87238f1e1cf491"
EXPECTED_RELEASE_ID = "a5d2782888c550487087244b679cd0c5c89f95392a9de3d6a8384c734d757a69"
EXPECTED_ARTIFACT_SHA256 = "8a878b41108d2eb58989af825aa1a9309aca389c4da041b09a915230172ab8d7"


def run_materializer(output_root: Path) -> tuple[Path, Path, Path, Path]:
    database = output_root / "indicators.db"
    published = output_root / "published.json"
    public = output_root / "public.json"
    report = output_root / "materialization.json"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/materialize_eurostat_gdp_indicator.py"),
            "--schema",
            str(REPO_ROOT / "etl/load/sqlite_schema.sql"),
            "--out-db",
            str(database),
            "--published-out",
            str(published),
            "--public-out",
            str(public),
            "--report-out",
            str(report),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return database, published, public, report


def test_real_eurostat_gdp_pipeline_is_exact_and_deterministic(tmp_path: Path) -> None:
    assert RAW_CAPTURE.stat().st_size == 4_763_587
    assert hashlib.sha256(RAW_CAPTURE.read_bytes()).hexdigest() == EXPECTED_RAW_SHA256

    database, published, public, report = run_materializer(tmp_path)
    first_artifact = published.read_bytes()
    first_report = report.read_bytes()
    assert hashlib.sha256(first_artifact).hexdigest() == EXPECTED_ARTIFACT_SHA256

    run_materializer(tmp_path)
    assert published.read_bytes() == first_artifact
    assert public.read_bytes() == first_artifact
    assert report.read_bytes() == first_report

    payload = json.loads(first_artifact)
    assert payload["release_id"] == EXPECTED_RELEASE_ID
    assert payload["policy"] == {
        "real_data_only": True,
        "synthetic_or_mock": False,
        "official_public_domain_information_retained": True,
        "revision_mode": "append_only_baseline",
        "causal_claim": "none",
        "political_merit_or_blame": "not_assessed",
    }
    assert payload["full_corpus"]["observations"] == 1_755_809
    assert payload["full_corpus"]["parquet_files"] == 37
    assert payload["full_corpus"]["representative_scope"] is False
    assert payload["coverage"]["series"] == 86
    assert payload["coverage"]["observations"] == 2_091
    assert payload["coverage"]["period_min"] == "2000"
    assert payload["coverage"]["period_max"] == "2024"
    assert payload["coverage"]["source_status_codes"] == {"none": 1_978, "p": 113}
    assert payload["coverage"]["revision_baseline"] == 2_091
    assert payload["coverage"]["uncertainty_not_provided"] == 2_091

    series = payload["series"]
    assert len(series) == 86
    assert {row["geography_level"] for row in series} == {
        "country",
        "NUTS1",
        "NUTS2",
        "NUTS3",
    }
    observations = [item for row in series for item in row["observations"]]
    assert len(observations) == 2_091
    assert len({item["indicator_observation_version_id"] for item in observations}) == 2_091
    assert len({item["evidence"]["indicator_observation_evidence_id"] for item in observations}) == 2_091
    assert all(item["revision_state"] == "baseline" for item in observations)
    assert all(item["revision_ordinal"] == 1 for item in observations)
    assert all(item["uncertainty_state"] == "not_provided" for item in observations)
    assert all(item["evidence"]["source_content_sha256"] == EXPECTED_RAW_SHA256 for item in observations)
    assert all(item["evidence"]["value_json_pointer"] == f"/value/{item['raw_cell_index']}" for item in observations)

    national = next(row for row in series if row["geography_code"] == "ES")
    assert len(national["observations"]) == 25
    latest = national["observations"][-1]
    assert latest["period_label"] == "2024"
    assert latest["value_decimal"] == "36400"
    assert latest["source_status_code"] == "p"

    connection = sqlite3.connect(database)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in (
                "indicator_definitions",
                "indicator_releases",
                "indicator_series_versions",
                "indicator_observation_versions",
                "indicator_observation_evidence",
            )
        }
    finally:
        connection.close()
    assert counts == {
        "indicator_definitions": 1,
        "indicator_releases": 1,
        "indicator_series_versions": 86,
        "indicator_observation_versions": 2_091,
        "indicator_observation_evidence": 2_091,
    }

    validation = tmp_path / "validation.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/validate_eurostat_gdp_indicator.py"),
            "--db",
            str(database),
            "--published",
            str(published),
            "--public",
            str(public),
            "--report-out",
            str(validation),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    validation_payload = json.loads(validation.read_text(encoding="utf-8"))
    assert validation_payload["status"] == "passed"
    assert validation_payload["failed_checks"] == []
    assert validation_payload["raw_cells_compared"] == 2_091
