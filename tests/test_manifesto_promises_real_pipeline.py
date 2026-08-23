from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "b8994deec0bbc45cdcbef5d7c5395cabf30b0509706303c3d8e76058c48eebfd"
SOURCE_PDF = (
    REPO_ROOT
    / "etl/data/raw/text_documents/programas_partidos"
    / f"{SOURCE_SHA256}.pdf"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_pipeline(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    db = tmp_path / "promises.db"
    published = tmp_path / "published.json"
    public = tmp_path / "public.json"
    report = tmp_path / "ingest-report.json"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/ingest_manifesto_promises.py"),
            "--pdf",
            str(SOURCE_PDF),
            "--db",
            str(db),
            "--schema",
            str(REPO_ROOT / "etl/load/sqlite_schema.sql"),
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


def test_official_bng_source_is_the_exact_real_pdf() -> None:
    data = SOURCE_PDF.read_bytes()
    assert data.startswith(b"%PDF-")
    assert len(data) == 396_842
    assert hashlib.sha256(data).hexdigest() == SOURCE_SHA256


def test_real_manifesto_pipeline_is_idempotent_and_page_traceable(
    tmp_path: Path,
) -> None:
    db, published, public, report = run_pipeline(tmp_path)
    first_artifact = published.read_bytes()
    first_report = report.read_bytes()

    run_pipeline(tmp_path)
    assert published.read_bytes() == first_artifact
    assert public.read_bytes() == first_artifact
    assert report.read_bytes() == first_report

    payload = json.loads(first_artifact)
    assert payload["real_data_only"] is True
    assert payload["synthetic_or_mock"] is False
    assert payload["public_domain_information_policy"] == "retained_exactly"
    assert payload["source"]["content_sha256"] == SOURCE_SHA256
    assert payload["counts"] == {
        "segments_seen": 266,
        "claims_loaded": 266,
        "explicit_promises": 97,
        "promises_loaded": 91,
        "soft_commitments": 26,
        "pending_claims": 169,
        "needs_context_claims": 6,
        "topic_links": 323,
        "published_promises": 20,
    }
    assert len(payload["items"]) == 20
    assert len({row["claim_id"] for row in payload["items"]}) == 20
    assert len({row["promise_id"] for row in payload["items"]}) == 20
    for row in payload["items"]:
        assert row["actor"] == {
            "actor_kind": "party",
            "acronym": "BNG",
            "name": "Bloque Nacionalista Galego",
            "source_label": "BNG",
        }
        assert row["claim_kind"] == "explicit_promise"
        assert row["review"]["status"] == "rule_confirmed"
        assert row["observation_status"] == "not_assessed"
        assert row["topics"]
        quote = row["evidence"]["exact_quote"]
        assert quote.startswith("•")
        assert (
            row["evidence"]["quote_sha256"]
            == hashlib.sha256(quote.encode("utf-8")).hexdigest()
        )

    conn = sqlite3.connect(db)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "manifesto_documents",
                "claim_extraction_runs",
                "claims",
                "claim_evidence",
                "promises",
                "claim_topics",
            )
        }
    finally:
        conn.close()
    assert counts == {
        "manifesto_documents": 1,
        "claim_extraction_runs": 1,
        "claims": 266,
        "claim_evidence": 266,
        "promises": 91,
        "claim_topics": 323,
    }


def test_real_manifesto_public_validator_accepts_exact_artifact(tmp_path: Path) -> None:
    db, published, public, _report = run_pipeline(tmp_path)
    validation_report = tmp_path / "validation.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/validate_manifesto_promises.py"),
            "--db",
            str(db),
            "--pdf",
            str(SOURCE_PDF),
            "--published",
            str(published),
            "--public",
            str(public),
            "--report-out",
            str(validation_report),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(validation_report.read_text(encoding="utf-8"))
    assert report["status"] == "ok"
    assert report["public_claims_validated"] == 20
    assert report["quote_page_offset_matches"] == 20
    assert report["official_pdf"]["content_sha256"] == SOURCE_SHA256
    assert report["artifact_sha256"] == sha256(published)
