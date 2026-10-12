from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GRAPH_DB = REPO_ROOT / "etl/data/staging/actor-graph-v1.db"
PUBLISHED = REPO_ROOT / "etl/data/published/actor-graph-v1.json"
PUBLIC = REPO_ROOT / "ui/site/public/actor-graph/data/graph.json"
MAIN_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
EXPECTED_RELEASE_ID = "e52dd7fac6f29570d23756e927e0b9cfe73d1bf2f7c30fa01de75d4dc3a6f4a5"
EXPECTED_ARTIFACT_SHA256 = (
    "9272fb7395b1aa2392f1626d85ae1bc438ab9583a414b5ba6d4c1e37cc8b9f25"
)


def run_validator(report: Path, reference: Path | None = None) -> dict:
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts/validate_actor_graph.py"),
        "--report-out",
        str(report),
    ]
    if reference is not None:
        command.extend(("--idempotence-reference", str(reference)))
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(report.read_text(encoding="utf-8"))


def test_real_actor_graph_reconciles_every_selected_official_fact(tmp_path: Path) -> None:
    # Inputs are current full official-source databases and published artifacts.
    # No generated rows, fixtures, stubs, or replacement databases are used.
    assert MAIN_DB.stat().st_size > 1_000_000_000
    assert GRAPH_DB.stat().st_size > 100_000_000
    assert PUBLISHED.read_bytes() == PUBLIC.read_bytes()

    first_report = tmp_path / "actor-graph-validation-first.json"
    first = run_validator(first_report)
    assert first["schema_version"] == "actor_graph_validation_v1"
    assert first["status"] == "passed"
    assert first["failed_checks"] == []
    assert all(first["checks"].values())
    assert first["release_id"] == EXPECTED_RELEASE_ID
    assert first["artifact_sha256"] == EXPECTED_ARTIFACT_SHA256
    assert first["database_counts"]["actor_graph_nodes"] == 133_595
    assert first["database_counts"]["actor_graph_source_mappings"] == 55
    assert first["database_counts"]["actor_graph_relationships"] == 237_973
    assert first["database_counts"]["actor_graph_relationship_evidence"] == 237_973
    assert first["relationship_counts"] == {
        "acts_in_geopolitical_action": 11,
        "acts_in_spending_item": 40,
        "affiliated_with_party": 87_068,
        "candidate_for": 42_056,
        "effective_candidate_for": 10_820,
        "elected_in": 8_926,
        "holds_role_at": 88_031,
        "member_of_organization": 12,
        "member_of_parliamentary_group": 949,
        "participates_in_meeting": 22,
        "party_to_agreement": 37,
        "publishes_manifesto": 1,
    }
    metrics = first["metrics"]
    assert metrics["missing_public_label_pairs"] == 0
    assert metrics["unique_actor_label_pairs_retained"] == metrics[
        "unique_actor_label_pairs_expected"
    ]
    assert metrics["unsafe_identity_rows"] == 0
    assert metrics["relationship_evidence_contract_violations"] == 0
    assert metrics["evidence_source_mismatches"] == 0
    assert metrics["person_identity_validity_violations"] == 0
    assert metrics["actor_identity_validity_violations"] == 0
    assert metrics["resolution_identity_validity_violations"] == 0
    assert metrics["source_mapping_summary"] == {
        "mapping_rows": 55,
        "upstream_source_ids": 51,
        "graph_source_ids": 55,
        "conflicting_upstream_source_ids": 3,
        "namespaced_mapping_rows": 7,
        "identical_metadata_mapping_rows": 0,
        "unique_mapping_rows": 48,
    }
    assert metrics["conflicting_upstream_source_ids"] == [
        "moncloa_referencias",
        "placsp_sindicacion",
        "programas_partidos",
    ]
    assert metrics["source_mapping_semantic_sha256"] == (
        "b7d7d06f456bad77204d4b4e1a7fe9c17bd5cfc58a9a2888f2db9b26a22b40e3"
    )
    assert metrics["foreign_key_violations"] == 0
    assert metrics["integrity_check"] == "ok"

    connection = sqlite3.connect(f"file:{GRAPH_DB.resolve()}?mode=ro", uri=True)
    try:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert connection.execute(
            "SELECT COUNT(*) FROM actor_graph_nodes WHERE identity_scope <> 'source_scoped'"
        ).fetchone()[0] == 0
        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM actor_graph_nodes AS node
            JOIN actor_graph_node_versions AS version
              ON version.actor_id = node.actor_id
            WHERE node.actor_kind = 'person'
              AND (version.valid_from IS NOT NULL OR version.valid_to IS NOT NULL)
            """
        ).fetchone()[0] == 0
    finally:
        connection.close()

    # Second independent validation compares exact release, counts, and every ID
    # fingerprint. Producer rerun can use this same reference gate without test data.
    second_report = tmp_path / "actor-graph-validation-second.json"
    second = run_validator(second_report, first_report)
    assert second["status"] == "passed"
    assert second["checks"]["idempotent_rerun_reference"] is True
    assert second["deterministic_fingerprint"] == first["deterministic_fingerprint"]
    assert second["database_counts"] == first["database_counts"]
