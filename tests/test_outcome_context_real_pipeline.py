from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIONS_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
INDICATORS_DB = REPO_ROOT / "etl/data/staging/indicators-eurostat-gdp-mvp.db"
ACTOR_GRAPH_DB = REPO_ROOT / "etl/data/staging/actor-graph-v1.db"
MANUAL = REPO_ROOT / "etl/data/manual/outcome_links/reviewed_links_v1.json"
CANONICAL_BUNDLE_ROOT = (
    REPO_ROOT / "etl/data/staging/outcome-context-candidates-v1"
)
MATERIALIZER = REPO_ROOT / "scripts/materialize_outcome_context.py"
VALIDATOR = REPO_ROOT / "scripts/validate_outcome_context.py"

VERSION_IDENTITY_SHA256 = (
    "193c3c8b7e5f442d0373408a28acde31972e19807f21c31c59955e3d770d1abc"
)
BUNDLE_SEMANTIC_SHA256 = (
    "2e04efb803623a5d96b6a2e7f6eb2464679e5014b02003cc1df175c16afcf16a"
)
ARTIFACT_SET_SHA256 = (
    "22f43918a8a6e54a3a8549f2f809abfcf98c3d04ef82dc37f634cd0fd71a980a"
)
EXPECTED_OUTPUT_SHA256 = {
    "outcome-context-candidates-v1.db": (
        "225c91d8ee53872f6ba98788363442021725aa5de95fbb6352e758721dff45c2"
    ),
    "outcome-context-candidates-v1.json": (
        "585986f5c2c977cc370e8efa33bb7ae88e81f78d599b9359ec17544d73a35731"
    ),
    "manifest.json": (
        "94382395eeb34ce63a74eac49ae08acf23e4bd8fe5b944778356e8bde7064bd1"
    ),
    "latest.json": (
        "50594a1032c03bfdd6b1ca6592929bce461247fbb3ef078ab9320c7ef2cfbdca"
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_validator(
    *,
    bundle_root: Path,
    report_out: Path,
    indicators_db: Path = INDICATORS_DB,
    materialization_report: Path | None = None,
) -> dict:
    command = [
        sys.executable,
        str(VALIDATOR),
        "--actions-db",
        str(ACTIONS_DB),
        "--indicators-db",
        str(indicators_db),
        "--actor-graph-db",
        str(ACTOR_GRAPH_DB),
        "--manual",
        str(MANUAL),
        "--bundle-root",
        str(bundle_root),
        "--report-out",
        str(report_out),
    ]
    if materialization_report is not None:
        command.extend(("--materialization-report", str(materialization_report)))
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert report_out.is_file()
    report = json.loads(report_out.read_text(encoding="utf-8"))
    assert report == json.loads(completed.stdout)
    return report


def run_materializer(
    *,
    out_root: Path,
    report_out: Path,
    indicators_db: Path = INDICATORS_DB,
) -> dict:
    completed = subprocess.run(
        [
            sys.executable,
            str(MATERIALIZER),
            "--actions-db",
            str(ACTIONS_DB),
            "--indicator-db",
            str(indicators_db),
            "--actor-db",
            str(ACTOR_GRAPH_DB),
            "--manual-input",
            str(MANUAL),
            "--out-root",
            str(out_root),
            "--report-out",
            str(report_out),
            "--batch-size",
            "128",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def resolved_artifacts(bundle_root: Path) -> dict[str, Path]:
    latest = json.loads((bundle_root / "latest.json").read_text(encoding="utf-8"))
    immutable = bundle_root / latest["immutable_bundle_path"]
    return {
        "latest.json": bundle_root / "latest.json",
        "manifest.json": immutable / "manifest.json",
        "outcome-context-candidates-v1.db": immutable
        / "outcome-context-candidates-v1.db",
        "outcome-context-candidates-v1.json": immutable
        / "outcome-context-candidates-v1.json",
    }


def assert_real_c0_report(
    report: dict, *, expected_artifact_set_sha256: str | None = None
) -> None:
    assert report["status"] == "passed"
    assert report["failed_checks"] == []
    assert all(report["checks"].values())
    assert report["truth"] == {
        "candidate_status": "pending_human_review",
        "evidence_level": "L1",
        "human_reviews": 0,
        "official_public_names_retained": 264,
        "publications": 0,
        "release_memberships": 0,
        "releases": 0,
        "scale_stage": "C0",
        "synthetic_or_mock_rows": 0,
    }
    assert report["counts"] == {
        "bounded_candidate_pairs": 20,
        "evidence": 7,
        "human_reviewed_pairs": 0,
        "link_versions": 1,
        "links": 1,
        "machine_audited_preproduction_candidates": 1,
        "memberships": 0,
        "observation_refs": 3,
        "observations": 3,
        "participant_refs": 264,
        "participants": 264,
        "publications": 0,
        "published_links": 0,
        "release_memberships": 0,
        "releases": 0,
        "reviews": 0,
        "scope_closures": 4,
        "synthetic_or_mock_rows": 0,
        "versions": 1,
    }
    assert report["semantic"]["outcome_link_version_identity_sha256"] == (
        VERSION_IDENTITY_SHA256
    )
    assert report["semantic"]["bundle_semantic_sha256"] == BUNDLE_SEMANTIC_SHA256
    assert report["semantic"]["bundle_semantic_identity_contract_version"] == (
        "outcome_context_bundle_semantic_identity_v1"
    )
    assert report["semantic"][
        "bundle_semantic_projection_excludes_generated_at"
    ] is True
    if expected_artifact_set_sha256 is not None:
        assert (
            report["semantic"]["artifact_set_sha256"]
            == expected_artifact_set_sha256
        )
    assert report["semantic"][
        "physical_database_hashes_are_semantic_identity_inputs"
    ] is False
    assert report["source_reconstruction"]["action_candidate_rows"] == 20
    assert report["source_reconstruction"]["indicator_series"] == 86
    assert report["source_reconstruction"]["indicator_observations"] == 25
    assert report["source_reconstruction"]["participant_source_rows"] == 264
    assert report["source_reconstruction"]["actor_reference_rows"] == 264
    assert report["source_reconstruction"]["participant_export_rows"] == 264
    assert report["source_reconstruction"]["official_public_names_retained"] == 264
    assert report["source_reconstruction"]["participant_raw_locator_indices_covered"] == 264
    assert report["source_reconstruction"]["actor_label_mismatches_preserved"] == 2
    assert report["source_reconstruction"]["original_vote_xml_capture_state"] == (
        "absent_from_current_snapshot"
    )
    assert report["scale_evidence"] == {
        "actor_release_source_lookup_scale_gate": True,
        "bounded_candidate_pairs_physically_processed": 20,
        "clean_restore_proven": False,
        "current_scale_stage": "C0",
        "durable_public_origin_proven": False,
        "fault_injection_resume_proven": False,
        "latest_pointer_is_final_materialization_operation": True,
        "materialization_report_independently_validated": True,
        "million_candidate_physical_run_proven": False,
        "million_participant_reference_run_proven": False,
        "partitioned_artifact_set_proven": False,
        "report_fsynced_before_latest_pointer": True,
        "semantic_json_layout": "monolithic",
        "single_candidate_materialization": True,
        "source_pre_post_physical_facts_match": True,
        "source_queries_materialized_with_fetchall_or_in_memory_lists": True,
    }
    assert report["artifacts"]["materialization_report"] == {
        "path": report["artifacts"]["materialization_report"]["path"],
        "schema_version": "outcome_context_materialization_report_v1",
        "status": "passed",
        "whole_report_hash_is_authoritative": False,
    }


def test_current_real_c0_bundle_is_independently_closed(tmp_path: Path) -> None:
    # These are the current official-source artifacts. No fixture or replacement
    # rows participate in this validation.
    assert ACTIONS_DB.stat().st_size > 1_000_000_000
    assert ACTOR_GRAPH_DB.stat().st_size > 1_000_000_000
    assert INDICATORS_DB.stat().st_size > 1_000_000
    assert MANUAL.stat().st_size == 463_383
    assert "materialize_outcome_context" not in VALIDATOR.read_text(encoding="utf-8")

    report = run_validator(
        bundle_root=CANONICAL_BUNDLE_ROOT,
        report_out=tmp_path / "validation.json",
    )
    assert_real_c0_report(
        report, expected_artifact_set_sha256=ARTIFACT_SET_SHA256
    )
    artifacts = resolved_artifacts(CANONICAL_BUNDLE_ROOT)
    for name, expected_sha in EXPECTED_OUTPUT_SHA256.items():
        assert sha256_file(artifacts[name]) == expected_sha


def test_real_replay_is_byte_deterministic_and_ignores_pragma_only_physical_drift(
    tmp_path: Path,
) -> None:
    # A copy of the real indicator database is changed only in SQLite's
    # application-owned user_version header. All source rows remain untouched.
    drifted_indicator = tmp_path / "real-indicator-pragma-drift.db"
    shutil.copyfile(INDICATORS_DB, drifted_indicator)
    before_physical_sha = sha256_file(drifted_indicator)
    connection = sqlite3.connect(drifted_indicator)
    try:
        previous_user_version = connection.execute("PRAGMA user_version").fetchone()[0]
        connection.execute(f"PRAGMA user_version = {previous_user_version + 1}")
        connection.commit()
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()
    after_physical_sha = sha256_file(drifted_indicator)
    assert after_physical_sha != before_physical_sha
    assert drifted_indicator.stat().st_size == INDICATORS_DB.stat().st_size

    original_root = tmp_path / "original-real-run"
    drifted_root = tmp_path / "pragma-drift-real-run"
    original_materialization_report = tmp_path / "original-materialization.json"
    drifted_materialization_report = tmp_path / "drifted-materialization.json"
    first_materialization = run_materializer(
        out_root=original_root,
        report_out=original_materialization_report,
    )
    second_materialization = run_materializer(
        out_root=drifted_root,
        report_out=drifted_materialization_report,
        indicators_db=drifted_indicator,
    )
    assert first_materialization["semantic"] == second_materialization["semantic"]

    original_artifacts = resolved_artifacts(original_root)
    drifted_artifacts = resolved_artifacts(drifted_root)
    for name in EXPECTED_OUTPUT_SHA256:
        assert original_artifacts[name].read_bytes() == drifted_artifacts[name].read_bytes()

    original_report = run_validator(
        bundle_root=original_root,
        report_out=tmp_path / "original-validation.json",
        materialization_report=original_materialization_report,
    )
    drifted_report = run_validator(
        bundle_root=drifted_root,
        report_out=tmp_path / "drifted-validation.json",
        indicators_db=drifted_indicator,
        materialization_report=drifted_materialization_report,
    )
    assert_real_c0_report(original_report)
    assert_real_c0_report(drifted_report)
    assert (
        original_report["semantic"]["artifact_set_sha256"]
        == drifted_report["semantic"]["artifact_set_sha256"]
    )
    assert (
        original_report["source_reconstruction"]
        == drifted_report["source_reconstruction"]
    )
    assert (
        original_report["deterministic_fingerprint"]
        == drifted_report["deterministic_fingerprint"]
    )
    assert (
        original_report["inputs"]["physical_database_facts_report_only"][
            "indicators"
        ]["sha256"]
        != drifted_report["inputs"]["physical_database_facts_report_only"][
            "indicators"
        ]["sha256"]
    )
    assert original_report["semantic"] == drifted_report["semantic"]
