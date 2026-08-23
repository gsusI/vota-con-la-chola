from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DB = REPO_ROOT / "etl/data/staging/placsp-contracts-real-s1-20260811.db"
SOURCE_ARCHIVE = (
    REPO_ROOT / "etl/data/object-origin/placsp-contracts/bd/a7/"
    "bda70aa0a7437d031e5d3f6114e5a637920ea1a460e1aba67d200209ae5eab7f.zip"
)
EXPECTED_RELEASE = "7abe9ac62d4af254aa41a2ffb2a7b4b9cf3e1ae607c6082329da17330a86a7a6"
EXPECTED_ARTIFACT_SHA256 = (
    "b09990e1c05be599d728156f1e98030a8d1f5eb08ea90139467fd471cc40df34"
)


def run_materializer(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    db = tmp_path / "spending.db"
    published = tmp_path / "published.json"
    public = tmp_path / "public.json"
    report = tmp_path / "materialization.json"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/materialize_placsp_spending_sample.py"),
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


def test_real_placsp_spending_pipeline_is_exact_idempotent_and_traceable(
    tmp_path: Path,
) -> None:
    assert SOURCE_DB.is_file(), f"missing real PLACSP database: {SOURCE_DB}"
    assert SOURCE_ARCHIVE.is_file(), (
        f"missing official PLACSP archive: {SOURCE_ARCHIVE}"
    )
    assert SOURCE_ARCHIVE.stat().st_size == 146_382_691

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
    assert payload["methodology"]["award_is_payment"] is False
    assert payload["methodology"]["representative_sample"] is False
    assert payload["source"]["corpus_counts"] == {
        "money_contract_records": 330_577,
        "money_contract_award_results": 262_558,
        "money_contract_documents": 3_190_620,
        "source_records": 330_597,
        "placsp_bulk_archives": 6,
        "placsp_bulk_members": 667,
        "placsp_bulk_record_sightings": 330_688,
    }
    assert payload["counts"]["published_items"] == 20
    assert payload["counts"]["published_actors"] == 40
    assert payload["counts"]["published_evidence"] == 38
    assert payload["counts"]["counterparty_legal_entity"] == 10
    assert payload["counts"]["counterparty_potential_natural_person"] == 5
    assert payload["counts"]["counterparty_unclassified"] == 5
    assert payload["amounts"]["award_amount_total_decimal"] == "4835494.71"
    assert payload["amounts"]["payable_amount_total_decimal"] == "5845384.70"
    assert len(payload["items"]) == 20
    assert len({item["spending_item_id"] for item in payload["items"]}) == 20
    for item in payload["items"]:
        assert item["spending_kind"] == "procurement_award"
        assert item["phase_caveat"] == (
            "adjudicacion_publicada_no_prueba_contrato_pago_ni_entrega"
        )
        assert item["dates"]["paid_on"] is None
        assert item["dates"]["delivered_on"] is None
        assert [actor["actor_role"] for actor in item["actors"]] == [
            "contracting_authority",
            "supplier",
        ]
        assert item["evidence"][0]["evidence_state"] == "captured_bytes"
        assert len(item["provenance"]["source_record_sha256"]) == 64

    conn = sqlite3.connect(db)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        counts = {
            table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in (
                "spending_items",
                "spending_item_actors",
                "spending_item_evidence",
                "spending_item_links",
            )
        }
    finally:
        conn.close()
    assert counts == {
        "spending_items": 20,
        "spending_item_actors": 40,
        "spending_item_evidence": 38,
        "spending_item_links": 0,
    }

    validation = tmp_path / "validation.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/validate_placsp_spending_sample.py"),
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
    assert validation_payload["validated_items"] == 20
    assert validation_payload["validated_actor_rows"] == 40
    assert validation_payload["validated_evidence_rows"] == 38
    assert validation_payload["checks"]["public_identity_retained_exactly"] is True
    assert validation_payload["official_archives_verified"][0]["sha256"] == (
        "bda70aa0a7437d031e5d3f6114e5a637920ea1a460e1aba67d200209ae5eab7f"
    )
