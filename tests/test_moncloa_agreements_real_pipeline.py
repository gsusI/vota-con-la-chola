from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DB = REPO_ROOT / "etl/data/staging/moncloa-aiops04-matrix-20260216.db"
SOURCE_CAPTURE = (
    REPO_ROOT
    / "etl/data/raw/moncloa_referencias/2026/02/16/"
    "moncloa_referencias_20260216T141256Z.json"
)
EXPECTED_CAPTURE_SHA256 = (
    "ab08b7dc09a46c890f055e95fdeac5e7d716a5023f8792f19ce440a239271ddf"
)
EXPECTED_RELEASE = "6f75ec32a5c085fbf71109919de785e48a5d7b2dcdf8ea13b2aaddfcffdf3753"
EXPECTED_ARTIFACT_SHA256 = (
    "8d8ce21967ac1c63a869dd2b5661877e789bb32fcc7e36f9626f9c2678fea678"
)


def run_materializer(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    db = tmp_path / "agreements.db"
    published = tmp_path / "published.json"
    public = tmp_path / "public.json"
    report = tmp_path / "materialization.json"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/materialize_moncloa_agreements_sample.py"),
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


def test_real_moncloa_agreements_are_exact_idempotent_and_non_inferential(
    tmp_path: Path,
) -> None:
    assert SOURCE_DB.is_file(), f"missing real Moncloa database: {SOURCE_DB}"
    assert SOURCE_CAPTURE.is_file(), f"missing official capture: {SOURCE_CAPTURE}"
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
    assert payload["real_data_only"] is True
    assert payload["synthetic_or_mock"] is False
    assert payload["public_domain_information_policy"] == "retained_exactly"
    assert payload["source"]["corpus_counts"] == {
        "source_records_total": 28,
        "moncloa_referencias_records": 20,
        "explicit_agreement_records": 11,
    }
    assert payload["counts"]["meetings"] == 11
    assert payload["counts"]["agreements"] == 11
    assert payload["counts"]["meeting_participants"] == 22
    assert payload["counts"]["agreement_parties"] == 37
    assert payload["counts"]["agreement_topics"] == 20
    assert payload["counts"]["attendance_claims"] == 0
    assert payload["counts"]["influence_assertions"] == 0
    assert payload["influence_assertions"] == []
    assert len(payload["records"]) == 11

    for record in payload["records"]:
        meeting = record["meeting"]
        agreement = record["agreement"]
        assert meeting["scheduled_state"] == "occurred"
        assert meeting["attendance_disclosure_state"] == "not_disclosed"
        assert all(
            participant["attendance_claim_state"] == "not_claimed"
            for participant in meeting["participants"]
        )
        assert agreement["agreement_kind"] == "executive_decision"
        assert agreement["agreement_status"] == "adopted"
        assert agreement["influence_state"] == "not_asserted"
        assert "acuerdo" in agreement["summary"].casefold()
        assert agreement["meeting_id"] == meeting["meeting_id"]
        assert agreement["evidence"][0]["exact_quote"] == agreement["summary"]
        assert all(
            topic["assignment_kind"] == "derived_rule"
            and topic["review_status"] == "unreviewed"
            for topic in agreement["topics"]
        )

    conn = sqlite3.connect(db)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        counts = {
            table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in (
                "accountability_meetings",
                "meeting_participants",
                "meeting_agenda_items",
                "meeting_evidence",
                "agreements",
                "agreement_parties",
                "agreement_evidence",
                "agreement_topics",
                "influence_assertions",
            )
        }
    finally:
        conn.close()
    assert counts == {
        "accountability_meetings": 11,
        "meeting_participants": 22,
        "meeting_agenda_items": 11,
        "meeting_evidence": 11,
        "agreements": 11,
        "agreement_parties": 37,
        "agreement_evidence": 11,
        "agreement_topics": 20,
        "influence_assertions": 0,
    }

    validation = tmp_path / "validation.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/validate_moncloa_agreements_sample.py"),
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
    assert validation_payload["metrics"]["records"] == 11
    assert validation_payload["metrics"]["attendance_claims"] == 0
    assert validation_payload["metrics"]["influence_assertions"] == 0
