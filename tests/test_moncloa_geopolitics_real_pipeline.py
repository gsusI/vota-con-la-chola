from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DB = REPO_ROOT / "etl/data/staging/agreements-moncloa-mvp.db"
SOURCE_CAPTURE = (
    REPO_ROOT
    / "etl/data/raw/moncloa_referencias/2026/02/16/"
    "moncloa_referencias_20260216T141256Z.json"
)
EXPECTED_CAPTURE_SHA256 = (
    "ab08b7dc09a46c890f055e95fdeac5e7d716a5023f8792f19ce440a239271ddf"
)
EXPECTED_RELEASE = "6683fd44eece98198ab3040e264c584b878cb33aa43be719ae19b99f58246204"
EXPECTED_ARTIFACT_SHA256 = (
    "ea8c3eb11ff2e31e0a6585ee3f965b7d6dd5d662b2953952f4eb440a988c880e"
)


def run_materializer(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    db = tmp_path / "geopolitics.db"
    published = tmp_path / "published.json"
    public = tmp_path / "public.json"
    report = tmp_path / "materialization.json"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/materialize_moncloa_geopolitics_sample.py"),
            "--source-db",
            str(SOURCE_DB),
            "--schema",
            str(REPO_ROOT / "etl/load/sqlite_schema.sql"),
            "--out-db",
            str(db),
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
    return db, published, public, report


def test_real_moncloa_geopolitics_is_exact_idempotent_and_fact_only(
    tmp_path: Path,
) -> None:
    assert SOURCE_DB.is_file(), f"missing real agreements database: {SOURCE_DB}"
    assert SOURCE_CAPTURE.stat().st_size == 21_234
    assert hashlib.sha256(SOURCE_CAPTURE.read_bytes()).hexdigest() == (
        EXPECTED_CAPTURE_SHA256
    )

    db, published, public, report = run_materializer(tmp_path)
    first_artifact = published.read_bytes()
    first_report = report.read_bytes()
    assert hashlib.sha256(first_artifact).hexdigest() == EXPECTED_ARTIFACT_SHA256

    run_materializer(tmp_path)
    assert published.read_bytes() == first_artifact
    assert public.read_bytes() == first_artifact
    assert report.read_bytes() == first_report

    payload = json.loads(first_artifact)
    assert payload["release_id"] == EXPECTED_RELEASE
    assert payload["policy"] == {
        "real_data_only": True,
        "synthetic_or_mock": False,
        "official_public_domain_information_retained": True,
        "inference_level": "fact_only",
        "treaty_entry_into_force_inferred": False,
        "implementation_inferred": False,
        "alignment_inferred": False,
        "influence_inferred": False,
        "causal_outcome_inferred": False,
    }
    assert payload["coverage"]["source_records"] == 20
    assert payload["coverage"]["qualifying_foreign_policy_records"] == 2
    assert payload["coverage"]["actions"] == 2
    assert payload["coverage"]["actors"] == 11
    assert payload["coverage"]["evidence"] == 2
    assert payload["coverage"]["topics"] == 4
    assert payload["coverage"]["positions"] == 0
    assert payload["coverage"]["later_observations"] == 0
    assert len(payload["records"]) == 2

    actor_labels: set[str] = set()
    for record in payload["records"]:
        assert record["action_kind"] == "treaty_process"
        assert record["action_status"] == "authorized"
        assert record["procedure_stage"] == (
            "domestic_referral_and_authorization_to_consent"
        )
        assert record["binding_state"] == "not_assessed"
        assert record["entry_into_force_state"] == "not_assessed"
        assert record["implementation_state"] == "not_assessed"
        assert record["outcome_state"] == "not_assessed"
        assert record["position_state"] == "not_assessed"
        assert record["instrument_name"] in record["summary"]
        assert record["evidence"][0]["exact_quote"] == record["summary"]
        assert record["evidence"][0]["capture_sha256"] == EXPECTED_CAPTURE_SHA256
        assert len(record["topics"]) == 2
        assert all(
            topic["assignment_kind"] == "derived_rule"
            and topic["review_status"] == "unreviewed"
            and topic["match_text"] in record["summary"]
            for topic in record["topics"]
        )
        assert len(record["links"]) == 1
        actor_labels.update(actor["source_label"] for actor in record["actors"])

    assert actor_labels == {
        "Consejo de Ministros",
        "Gobierno de España / La Moncloa",
        "Cortes Generales",
        "Reino de España",
        "Unión Europea",
        "Comunidad Europea de la Energía Atómica",
        "Sultanato de Omán",
    }

    connection = sqlite3.connect(db)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        counts = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in (
                "geopolitical_actions",
                "geopolitical_action_actors",
                "geopolitical_action_evidence",
                "geopolitical_action_topics",
                "geopolitical_positions",
                "geopolitical_position_evidence",
                "geopolitical_action_links",
                "geopolitical_observations",
            )
        }
    finally:
        connection.close()
    assert counts == {
        "geopolitical_actions": 2,
        "geopolitical_action_actors": 11,
        "geopolitical_action_evidence": 2,
        "geopolitical_action_topics": 4,
        "geopolitical_positions": 0,
        "geopolitical_position_evidence": 0,
        "geopolitical_action_links": 2,
        "geopolitical_observations": 0,
    }

    validation = tmp_path / "validation.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/validate_moncloa_geopolitics_sample.py"),
            "--source-db",
            str(SOURCE_DB),
            "--db",
            str(db),
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
    assert validation_payload["status"] == "ok"
    assert validation_payload["metrics"]["records"] == 2
    assert validation_payload["metrics"]["explicit_positions"] == 0
    assert validation_payload["metrics"]["geopolitical_inferences"] == 0
