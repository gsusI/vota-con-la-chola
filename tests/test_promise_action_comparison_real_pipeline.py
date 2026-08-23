from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.materialize_promise_action_comparisons import (
    comparison_release_id,
    require_strictly_later_action,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PROMISES_DB = REPO_ROOT / "etl/data/staging/promises-bng-2023.db"
ACTIONS_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
ACTOR_GRAPH_DB = REPO_ROOT / "etl/data/staging/actor-graph-v1.db"
REVIEWED_MAPPINGS = (
    REPO_ROOT
    / "etl/data/manual/promise_action_comparisons/reviewed_mappings_v1.json"
)


def run_materializer(
    root: Path, *, promises_db: Path = PROMISES_DB
) -> tuple[Path, Path, Path, dict]:
    root.mkdir(parents=True, exist_ok=True)
    out_db = root / "comparisons.db"
    out_json = root / "published.json"
    public_out = root / "public.json"
    report_out = root / "materialization.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/materialize_promise_action_comparisons.py"),
            "--promises-db",
            str(promises_db),
            "--actions-db",
            str(ACTIONS_DB),
            "--actor-graph-db",
            str(ACTOR_GRAPH_DB),
            "--reviewed-mappings",
            str(REVIEWED_MAPPINGS),
            "--out-db",
            str(out_db),
            "--out-json",
            str(out_json),
            "--public-out",
            str(public_out),
            "--report-out",
            str(report_out),
            "--snapshot-date",
            "2026-08-20",
            "--batch-size",
            "2",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return out_db, out_json, public_out, json.loads(completed.stdout)


def run_validator(
    root: Path,
    comparison_db: Path,
    published: Path,
    public_copy: Path,
    *,
    promises_db: Path = PROMISES_DB,
) -> dict:
    report_out = root / "validation.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/validate_promise_action_comparisons.py"),
            "--promises-db",
            str(promises_db),
            "--actions-db",
            str(ACTIONS_DB),
            "--actor-graph-db",
            str(ACTOR_GRAPH_DB),
            "--comparison-db",
            str(comparison_db),
            "--reviewed-mappings",
            str(REVIEWED_MAPPINGS),
            "--published",
            str(published),
            "--public",
            str(public_copy),
            "--report-out",
            str(report_out),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert report_out.is_file()
    return json.loads(completed.stdout)


def test_real_reviewed_comparison_slice_is_idempotent_and_fail_closed(
    tmp_path: Path,
) -> None:
    # These are current official-source databases, not replacement inputs.
    assert PROMISES_DB.stat().st_size > 1_000_000
    assert ACTIONS_DB.stat().st_size > 1_000_000_000
    assert ACTOR_GRAPH_DB.stat().st_size > 1_000_000_000

    promises_connection = sqlite3.connect(PROMISES_DB)
    try:
        real_claim_date = promises_connection.execute(
            """
            SELECT md.published_date
            FROM claims AS c
            JOIN manifesto_documents AS md
              ON md.manifesto_document_id = c.manifesto_document_id
            WHERE c.claim_id = ?
            """,
            (
                "claim_67146dd9977d23b456c0a65f9d0b396baa01a4a177f179e1ac379b2567137cdf",
            ),
        ).fetchone()[0]
    finally:
        promises_connection.close()

    prior_action_id = (
        "url:https://www.senado.es/legis14/votaciones/ses_70_4415.xml"
    )
    actions_connection = sqlite3.connect(ACTIONS_DB)
    try:
        prior_action = actions_connection.execute(
            """
            SELECT e.vote_date, v.member_name, v.vote_choice
            FROM parl_vote_events AS e
            JOIN parl_vote_member_votes AS v
              ON v.vote_event_id = e.vote_event_id
            WHERE e.vote_event_id = ?
              AND v.member_name = ?
            """,
            (prior_action_id, "ABELARDO VICO RUIZ"),
        ).fetchone()
    finally:
        actions_connection.close()
    assert prior_action == ("2023-05-10", "ABELARDO VICO RUIZ", "SÍ")
    with pytest.raises(RuntimeError, match="must be strictly later"):
        require_strictly_later_action(
            claim_published_date=real_claim_date,
            action_date=prior_action[0],
            action_id=prior_action_id,
        )

    first_db, first_json, first_public, first_report = run_materializer(
        tmp_path / "first"
    )
    second_db, second_json, second_public, second_report = run_materializer(
        tmp_path / "second"
    )

    assert first_json.read_bytes() == first_public.read_bytes()
    assert second_json.read_bytes() == second_public.read_bytes()
    assert first_json.read_bytes() == second_json.read_bytes()
    assert first_db.read_bytes() == second_db.read_bytes()
    assert first_report["comparison_release_id"] == second_report[
        "comparison_release_id"
    ]
    assert first_report["semantic_sha256"] == second_report["semantic_sha256"]
    assert first_report["comparison_count"] == 5
    assert first_report["evidence_count"] == 18
    assert first_report["status_counts"] == {
        "ambiguous_mapping": 3,
        "insufficient_evidence": 1,
        "not_comparable": 1,
    }
    assert first_report["million_row_physical_run_proven"] is False

    expected_input_release_keys = {
        "actions",
        "actor_graph",
        "promises",
        "reviewed_mappings",
    }
    assert set(first_report["input_scope_sha256"]) == expected_input_release_keys
    assert "input_file_facts" in first_report
    real_review_input = json.loads(REVIEWED_MAPPINGS.read_text(encoding="utf-8"))
    real_input_releases = first_report["input_scope_sha256"]
    assert comparison_release_id(
        review_version=real_review_input["review_version"],
        snapshot_date="2026-08-20",
        promises_digest=real_input_releases["promises"]["selected_scope_sha256"],
        actions_digest=real_input_releases["actions"]["selected_scope_sha256"],
        action_coverage_cutoff=real_input_releases["actions"]["coverage_cutoff"],
        actors_digest=real_input_releases["actor_graph"]["selected_scope_sha256"],
        actor_graph_release_id=real_input_releases["actor_graph"]["release_id"],
        mappings_sha256=real_input_releases["reviewed_mappings"][
            "canonical_sha256"
        ],
    ) == "vclc:comparison-release:ea65f3b8104dd678cb7ebce724b78f86"
    assert (
        real_input_releases["actions"]["selected_scope_sha256"]
        == "e7535d6a4c186c79ff8ba7b56cbe96c886aa2c49ebe5adef4d83d2bd6db933e1"
    )

    payload = json.loads(first_json.read_text(encoding="utf-8"))
    assert payload["real_data_only"] is True
    assert payload["synthetic_or_mock"] is False
    assert payload["counts"] == {
        "action_pairs_total": 4,
        "bounded_action_search_assessments_total": 1,
        "comparisons_total": 5,
        "evidence_total": 18,
        "strong_pairs_total": 0,
        "unique_claims_total": 4,
    }
    assert payload["coverage"]["ranking_state"] == "hidden"
    assert payload["freshness"]["tier"] == "stale"
    assert set(payload["input_releases"]) == expected_input_release_keys
    assert payload["input_releases"] == first_report["input_scope_sha256"]
    assert "path" not in json.dumps(payload["input_releases"], sort_keys=True)
    assert payload["scale_contract"] == {
        "artifact_set_atomic": False,
        "million_row_physical_run_proven": False,
        "per_file_atomic_replacement": True,
        "source_lookup": "bulk indexed selection via json_each sets",
        "write_mode": "bounded executemany batches",
    }

    bounded = [row for row in payload["items"] if row["action"] is None]
    assert len(bounded) == 1
    assert bounded[0]["comparison_status"] == "insufficient_evidence"
    assert bounded[0]["action_search"]["state"] == "no_reviewed_action_found"
    assert bounded[0]["action_search"]["scope"]["candidate_events_scanned"] == 97
    assert bounded[0]["action_search"]["scope"]["candidate_rows_sha256"] == (
        "1b8e4e8e982edf2985a5e184395331d3271ae7a0d055eb9d6a9f3d509dbadb0a"
    )
    assert bounded[0]["action_search"]["scope"]["matching_event_ids"] == []

    assert {row["claim"]["actor_label"] for row in payload["items"]} == {"BNG"}
    assert {
        row["action"]["member_name"]
        for row in payload["items"]
        if row["action"] is not None
    } == {"MARÍA CARMEN DA SILVA MÉNDEZ", "Néstor Rego Candamil"}
    for row in payload["items"]:
        assert row["directional_countable"] is False
        assert row["comparison_status"] not in {"aligned", "conflicted"}
        assert row["frame"]["same_exact_frame_confirmed"] is False
        assert row["frame"]["material_differences"]
        assert row["reason_codes"]
        assert row["confidence"]["aggregate_value"] == 0.0
        assert row["counterevidence"]["exhaustive"] is False
        assert row["evidence_links"]
        claim_evidence = [
            edge
            for edge in row["evidence"]
            if edge["evidence_side"] == "claim"
            and edge["evidence_role"] == "primary"
        ]
        assert len(claim_evidence) == 1
        assert claim_evidence[0]["source_url"].startswith("https://")
        assert len(claim_evidence[0]["content_sha256"]) == 64

    connection = sqlite3.connect(first_db)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT COUNT(*) FROM promise_action_comparisons"
        ).fetchone()[0] == 5
        assert connection.execute(
            "SELECT COUNT(*) FROM comparison_evidence"
        ).fetchone()[0] == 18
        assert connection.execute(
            """
            SELECT COUNT(*) FROM promise_action_comparisons
            WHERE directional_countable <> 0
               OR comparison_status IN ('aligned', 'conflicted')
            """
        ).fetchone()[0] == 0
        assert connection.execute(
            """
            SELECT COUNT(*) FROM promise_action_comparisons
            WHERE action_kind = 'bounded_action_search'
              AND action_id IS NULL
              AND action_search_state = 'no_reviewed_action_found'
            """
        ).fetchone()[0] == 1
    finally:
        connection.close()

    # Replaying with the same real inputs preserves every public byte and ID.
    second_connection = sqlite3.connect(second_db)
    try:
        second_ids = second_connection.execute(
            "SELECT comparison_id FROM promise_action_comparisons ORDER BY comparison_id"
        ).fetchall()
    finally:
        second_connection.close()
    first_connection = sqlite3.connect(first_db)
    try:
        first_ids = first_connection.execute(
            "SELECT comparison_id FROM promise_action_comparisons ORDER BY comparison_id"
        ).fetchall()
    finally:
        first_connection.close()
    assert first_ids == second_ids

    # Keep every official row intact. Change only SQLite's physical header
    # user_version field, then prove semantic lineage ignores that file-only drift.
    drift_promises_db = tmp_path / "real-promises-user-version-drift.db"
    shutil.copy2(PROMISES_DB, drift_promises_db)
    drift_connection = sqlite3.connect(drift_promises_db)
    try:
        original_user_version = drift_connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]
        drift_user_version = 1 if original_user_version != 1 else 2
        drift_connection.execute(f"PRAGMA user_version = {drift_user_version}")
        assert drift_connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        drift_connection.close()

    drift_db, drift_json, drift_public, drift_report = run_materializer(
        tmp_path / "physical-drift",
        promises_db=drift_promises_db,
    )
    assert drift_report["comparison_release_id"] == first_report[
        "comparison_release_id"
    ]
    assert drift_report["semantic_sha256"] == first_report["semantic_sha256"]
    assert drift_report["input_scope_sha256"] == first_report["input_scope_sha256"]
    assert drift_json.read_bytes() == first_json.read_bytes()
    assert drift_public.read_bytes() == first_public.read_bytes()
    assert drift_db.read_bytes() == first_db.read_bytes()
    assert drift_report["input_file_facts"]["promises_db"]["bytes"] == first_report[
        "input_file_facts"
    ]["promises_db"]["bytes"]
    assert drift_report["input_file_facts"]["promises_db"]["sha256"] != first_report[
        "input_file_facts"
    ]["promises_db"]["sha256"]

    validation = run_validator(
        tmp_path,
        first_db,
        first_json,
        first_public,
    )
    assert validation["status"] == "passed"
    assert validation["failed_checks"] == []
    assert validation["errors"] == []
    assert validation["counts"]["comparisons"] == 5
    assert validation["counts"]["evidence"] == 18
    assert validation["strong_comparisons"] == 0
    assert validation["checks"]["source_rows_reconstructed"] is True
    assert validation["checks"]["semantic_hash_reconstructed"] is True
    assert validation["checks"]["v1_changed_framing_disabled"] is True
    assert validation["checks"]["source_manifest_semantic_lineage_exact"] is True
    assert validation["checks"]["public_input_releases_semantic_lineage_exact"] is True
    assert validation["checks"]["actions_scope_hash_includes_real_bounded_searches"] is True
    assert validation["checks"]["bounded_search_candidate_rows_hashed"] is True
    assert validation["bounded_action_searches"] == [
        {
            "claim_id": "claim_8c34c8252fed8dd130a66dac7ef9233394d4d33ef607a9b5542a1ca2f72d09a5",
            "candidate_vote_rows_scanned": 97,
            "candidate_events_scanned": 97,
            "candidate_rows_sha256": (
                "1b8e4e8e982edf2985a5e184395331d3271ae7a0d055eb9d6a9f3d509dbadb0a"
            ),
            "matching_events": 0,
        }
    ]
    assert validation["checks"]["temporal_order_valid"] is True

    drift_validation = run_validator(
        tmp_path / "physical-drift",
        drift_db,
        drift_json,
        drift_public,
        promises_db=drift_promises_db,
    )
    assert drift_validation["status"] == "passed"
    assert drift_validation["failed_checks"] == []
    assert drift_validation["input_file_facts"]["promises_db"]["sha256"] == (
        drift_report["input_file_facts"]["promises_db"]["sha256"]
    )
    assert drift_validation["source_scope_sha256"] == validation[
        "source_scope_sha256"
    ]
    assert validation["checks"]["official_public_identity_retained"] is True
    assert validation["checks"]["published_public_byte_parity"] is True
