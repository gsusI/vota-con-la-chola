from __future__ import annotations

import ast
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLANNER = REPO_ROOT / "scripts/plan_outcome_context_pairs_c2b.py"
VALIDATOR = REPO_ROOT / "scripts/validate_outcome_context_pair_plan_c2b.py"
CONFIG = REPO_ROOT / "etl/data/manual/outcome_links/planner_scope_c2b_v1.json"
SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
ACTIONS_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
INDICATORS_DB = REPO_ROOT / "etl/data/staging/eurostat-indicators-real-s2-20260811.db"
PLAN_DB = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1.db"
MATERIALIZATION = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1-report.json"
INTERRUPTION_REPORT = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1-interruption-report.json"
MANIFEST = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1-manifest.json"
VALIDATION = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1-validation.json"

PIPELINE_KEY = "vclc:outcome-pair-plan-c2b-pipeline:294c93befa7e73b46c84355d"
SEMANTIC_ROOT = "e9fecdb89e518c7d8f6ecc947c6930c84afa96dad031c4bbc332842cc685d7ae"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_canonical_real_c2b_artifact_contract() -> None:
    materialization = json.loads(MATERIALIZATION.read_text(encoding="utf-8"))
    interruption = json.loads(INTERRUPTION_REPORT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    assert materialization["status"] == "passed"
    assert materialization["execution"] in {"fresh", "resumed", "replayed_noop"}
    assert materialization["pipeline_key"] == PIPELINE_KEY
    assert interruption["status"] == "interrupted"
    assert interruption["execution"] == "fresh"
    assert interruption["plan_counts"]["pairs"] == 25000
    interrupted_checkpoints = {
        row["stage"]: row for row in interruption["checkpoints"]
    }
    assert interrupted_checkpoints["pairs"]["last_key"] == [4, 5800]
    assert interrupted_checkpoints["pairs"]["rows_written"] == 25000
    assert interrupted_checkpoints["pairs"]["batches_committed"] == 1
    assert not interrupted_checkpoints["pairs"]["completed"]
    assert interruption["artifacts"]["manifest"] is None
    assert materialization["roots"]["semantic_root_sha256"] == SEMANTIC_ROOT
    assert materialization["plan_counts"] == {
        "actions": 458,
        "base_partitions": 1205,
        "bucket_partitions": 197196,
        "global_unfiltered_product": 71189230,
        "max_bucket_partition_rows": 114,
        "pairs": 2865602,
        "selected_product": 2931200,
        "series": 6400,
    }
    assert materialization["source_counts"] == {
        "actions": 458,
        "all_indicator_series": 155435,
        "datasets": 4,
        "distinct_official_names": 490,
        "geographies": 89,
        "members": 119116,
        "points": 79722,
        "series": 6400,
    }
    assert materialization["base_partition_distribution"] == {
        "partition_count": 1205,
        "row_count": 2865602,
        "minimum_rows": 27,
        "maximum_rows": 18348,
        "distribution_root_sha256": "5f99039a47a875db7fda653df297fe9749eb66184fcb2553688b4362235b9ec1",
    }
    assert materialization["bucket_partition_distribution"] == {
        "partition_count": 197196,
        "row_count": 2865602,
        "minimum_rows": 1,
        "maximum_rows": 114,
        "distribution_root_sha256": "c9a31ef95bc7af66bc32670d9107e5778d90ab722d0109c83ae3ab6e9534c037",
    }
    checkpoints = {row["stage"]: row for row in materialization["checkpoints"]}
    assert checkpoints["actions"]["batches_committed"] == 1
    assert checkpoints["series"]["batches_committed"] == 1
    assert checkpoints["pairs"]["batches_committed"] == 118
    assert checkpoints["pairs"]["last_key"] == [458, 6400]
    assert checkpoints["pairs"]["rows_written"] == 2865602
    assert all(row["completed"] for row in checkpoints.values())

    shard = manifest["shards"]
    assert len(shard) == 1
    assert shard[0]["shard_id"] == "sqlite-00000"
    assert shard[0]["bytes"] == PLAN_DB.stat().st_size
    assert shard[0]["sha256"] == sha256_file(PLAN_DB)
    assert shard[0]["pair_rows"] == 2865602
    assert manifest["roots"]["semantic_root_sha256"] == SEMANTIC_ROOT

    assert validation["status"] == "passed"
    assert validation["failed_checks"] == []
    assert validation["counts"]["pairs"] == 2865602
    assert validation["counts"]["geographies"] == 89
    assert validation["roots"]["semantic_root_sha256"] == SEMANTIC_ROOT
    assert validation["performance"]["max_rss_bytes"] < 512 * 1024 * 1024

    connection = sqlite3.connect(
        f"file:{PLAN_DB.resolve().as_posix()}?mode=ro&immutable=1", uri=True
    )
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM outcome_pair_plan_pairs"
        ).fetchone()[0] == 2865602
        assert connection.execute(
            "SELECT COUNT(DISTINCT s.geography_code) "
            "FROM outcome_pair_plan_series s"
        ).fetchone()[0] == 89
        assert connection.execute(
            """
            SELECT COUNT(*) FROM outcome_pair_plan_pairs
            WHERE base_partition_key NOT LIKE '%/country=ES/geography=ES%'
               OR partition_key<>base_partition_key || '/bucket=' || pair_bucket
               OR pair_bucket<>substr(pair_plan_id,24,2)
            """
        ).fetchone()[0] == 0
        assert connection.execute(
            """
            SELECT COUNT(*) FROM outcome_pair_plan_pairs
            WHERE evidence_level<>'L0'
               OR association_assessment<>'not_assessed'
               OR causal_assessment<>'not_assessed'
               OR effect_estimate_state<>'not_computed'
               OR corruption_assessment<>'not_assessed'
               OR ranking_eligible<>0 OR publication_eligible<>0
            """
        ).fetchone()[0] == 0
        assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
    finally:
        connection.close()


def test_completed_replay_is_database_noop(tmp_path: Path) -> None:
    before = sha256_file(PLAN_DB)
    replay_report = tmp_path / "replay-report.json"
    replay_manifest = tmp_path / "replay-manifest.json"
    completed = subprocess.run(
        [
            sys.executable, str(PLANNER),
            "--config", str(CONFIG), "--schema", str(SCHEMA),
            "--actions-db", str(ACTIONS_DB), "--indicators-db", str(INDICATORS_DB),
            "--out-db", str(PLAN_DB), "--report-out", str(replay_report),
            "--manifest-out", str(replay_manifest),
            "--batch-size", "25000", "--source-batch-size", "25000",
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    replay = json.loads(completed.stdout)
    assert replay["execution"] == "replayed_noop"
    assert replay["performance"]["eligible_pairs_processed_this_run"] == 0
    assert replay["performance"]["scanned_pairs_processed_this_run"] == 0
    assert replay["performance"]["eligible_pairs_per_second"] is None
    assert replay["performance"]["scanned_pairs_per_second"] is None
    assert replay["performance"]["compute_cost_proxy_seconds_per_1000_eligible_pairs"] is None
    assert before == sha256_file(PLAN_DB)
    replay_validation_out = tmp_path / "replay-validation.json"
    validated = subprocess.run(
        [
            sys.executable, str(VALIDATOR),
            "--config", str(CONFIG), "--schema", str(SCHEMA),
            "--actions-db", str(ACTIONS_DB), "--indicators-db", str(INDICATORS_DB),
            "--plan-db", str(PLAN_DB),
            "--materialization-report", str(replay_report),
            "--manifest", str(replay_manifest),
            "--report-out", str(replay_validation_out),
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert validated.returncode == 0, validated.stdout + validated.stderr
    replay_validation = json.loads(replay_validation_out.read_text(encoding="utf-8"))
    assert replay_validation["status"] == "passed"
    assert replay_validation["counts"]["pairs"] == 2865602
    assert replay_validation["roots"]["semantic_root_sha256"] == SEMANTIC_ROOT


def test_fault_rolls_back_pair_batch_and_checkpoint(tmp_path: Path) -> None:
    plan_db = tmp_path / "fault.db"
    report = tmp_path / "fault-report.json"
    manifest = tmp_path / "fault-manifest.json"
    completed = subprocess.run(
        [
            sys.executable, str(PLANNER),
            "--config", str(CONFIG), "--schema", str(SCHEMA),
            "--actions-db", str(ACTIONS_DB), "--indicators-db", str(INDICATORS_DB),
            "--out-db", str(plan_db), "--report-out", str(report),
            "--manifest-out", str(manifest),
            "--batch-size", "25000", "--source-batch-size", "25000",
            "--fault-before-checkpoint-batch", "3",
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert completed.returncode != 0
    assert "injected fault before atomic checkpoint commit" in completed.stderr
    failure_report = json.loads(report.read_text(encoding="utf-8"))
    assert failure_report["status"] == "failed"
    assert failure_report["error_code"] == "c2b_pair_plan_failed_fail_closed"
    assert not manifest.exists()
    connection = sqlite3.connect(plan_db)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM outcome_pair_plan_pairs"
        ).fetchone()[0] == 0
        checkpoint = connection.execute(
            "SELECT rows_written,batches_committed,last_key_json,completed "
            "FROM pipeline_keyset_checkpoints WHERE stage='pairs'"
        ).fetchone()
        assert checkpoint == (0, 0, "[]", 0)
    finally:
        connection.close()


def test_missing_and_corrupt_single_shard_fail_before_source_reconstruction(
    tmp_path: Path,
) -> None:
    missing_report = tmp_path / "missing.json"
    missing_report.write_text('{"status":"passed"}\n', encoding="utf-8")
    missing = subprocess.run(
        [
            sys.executable, str(VALIDATOR),
            "--config", str(CONFIG), "--schema", str(SCHEMA),
            "--actions-db", str(ACTIONS_DB), "--indicators-db", str(INDICATORS_DB),
            "--plan-db", str(tmp_path / "missing.db"),
            "--materialization-report", str(MATERIALIZATION),
            "--manifest", str(MANIFEST), "--report-out", str(missing_report),
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert missing.returncode != 0
    missing_failure = json.loads(missing_report.read_text(encoding="utf-8"))
    assert missing_failure["status"] == "failed"
    assert missing_failure["error_code"] == "c2b_pair_plan_validation_failed_fail_closed"

    corrupt = tmp_path / "corrupt.db"
    with PLAN_DB.open("rb") as source, corrupt.open("wb") as target:
        target.write(source.read(4096))
    failed = subprocess.run(
        [
            sys.executable, str(VALIDATOR),
            "--config", str(CONFIG), "--schema", str(SCHEMA),
            "--actions-db", str(ACTIONS_DB), "--indicators-db", str(INDICATORS_DB),
            "--plan-db", str(corrupt),
            "--materialization-report", str(MATERIALIZATION),
            "--manifest", str(MANIFEST), "--report-out", str(tmp_path / "corrupt.json"),
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert failed.returncode != 0
    assert "plan_database_bytes" in failed.stderr
    corrupt_failure = json.loads((tmp_path / "corrupt.json").read_text(encoding="utf-8"))
    assert corrupt_failure["status"] == "failed"


def test_failure_atomically_replaces_stale_success_report(tmp_path: Path) -> None:
    report = tmp_path / "stale-success.json"
    report.write_text('{"status":"passed"}\n', encoding="utf-8")
    stale_inode = report.stat().st_ino
    completed = subprocess.run(
        [
            sys.executable, str(PLANNER),
            "--config", str(CONFIG), "--schema", str(SCHEMA),
            "--actions-db", str(ACTIONS_DB), "--indicators-db", str(INDICATORS_DB),
            "--out-db", str(tmp_path / "not-created.db"),
            "--report-out", str(report), "--manifest-out", str(tmp_path / "manifest.json"),
            "--batch-size", "1", "--source-batch-size", "25000",
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert completed.returncode != 0
    failure_text = report.read_text(encoding="utf-8")
    failure = json.loads(failure_text)
    assert failure["status"] == "failed"
    assert failure["error_code"] == "c2b_pair_plan_failed_fail_closed"
    assert failure["success_report_invalidated"] is True
    assert report.stat().st_ino != stale_inode
    assert "/Users/" not in failure_text
    assert "/home/" not in failure_text
    assert "official_action_url" not in failure_text
    assert "member_name" not in failure_text
    assert "source_record" not in failure_text

    validation_report = tmp_path / "stale-validation-success.json"
    validation_report.write_text('{"status":"passed"}\n', encoding="utf-8")
    validation_stale_inode = validation_report.stat().st_ino
    validation = subprocess.run(
        [
            sys.executable, str(VALIDATOR),
            "--config", str(CONFIG), "--schema", str(SCHEMA),
            "--actions-db", str(ACTIONS_DB), "--indicators-db", str(INDICATORS_DB),
            "--plan-db", str(tmp_path / "missing-plan.db"),
            "--materialization-report", str(MATERIALIZATION),
            "--manifest", str(MANIFEST),
            "--report-out", str(validation_report),
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert validation.returncode != 0
    validation_failure_text = validation_report.read_text(encoding="utf-8")
    validation_failure = json.loads(validation_failure_text)
    assert validation_failure["status"] == "failed"
    assert validation_failure["error_code"] == (
        "c2b_pair_plan_validation_failed_fail_closed"
    )
    assert validation_failure["success_report_invalidated"] is True
    assert validation_report.stat().st_ino != validation_stale_inode
    assert "/Users/" not in validation_failure_text
    assert "/home/" not in validation_failure_text
    assert "official_action_url" not in validation_failure_text
    assert "member_name" not in validation_failure_text
    assert "source_record" not in validation_failure_text


def test_validator_rejects_coordinated_report_and_manifest_metadata_tamper(
    tmp_path: Path,
) -> None:
    tampered_report = json.loads(MATERIALIZATION.read_text(encoding="utf-8"))
    tampered_report["execution"] = "adversarial_execution"
    tampered_report_path = tmp_path / "tampered-materialization.json"
    tampered_report_path.write_text(
        json.dumps(tampered_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    tampered_manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tampered_manifest["counts"]["official_names"] = 999999
    tampered_manifest["local_origin_state"] = "durable_public_origin_proven"
    manifest_payload = {
        key: value
        for key, value in tampered_manifest.items()
        if key != "manifest_root_sha256"
    }
    tampered_manifest["manifest_root_sha256"] = hashlib.sha256(
        json.dumps(
            manifest_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    tampered_manifest_path = tmp_path / "tampered-manifest.json"
    tampered_manifest_path.write_text(
        json.dumps(tampered_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    coordinated_failure_out = tmp_path / "coordinated-failure.json"
    coordinated_failure_out.write_text('{"status":"passed"}\n', encoding="utf-8")
    coordinated = subprocess.run(
        [
            sys.executable, str(VALIDATOR),
            "--config", str(CONFIG), "--schema", str(SCHEMA),
            "--actions-db", str(ACTIONS_DB), "--indicators-db", str(INDICATORS_DB),
            "--plan-db", str(PLAN_DB),
            "--materialization-report", str(tampered_report_path),
            "--manifest", str(tampered_manifest_path),
            "--report-out", str(coordinated_failure_out),
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert coordinated.returncode != 0
    assert "materialization_execution_allowed" in coordinated.stderr
    coordinated_failure = json.loads(
        coordinated_failure_out.read_text(encoding="utf-8")
    )
    assert coordinated_failure["status"] == "failed"
    assert coordinated_failure["error_code"] == (
        "c2b_pair_plan_validation_failed_fail_closed"
    )

    manifest_failure_out = tmp_path / "manifest-failure.json"
    manifest_only = subprocess.run(
        [
            sys.executable, str(VALIDATOR),
            "--config", str(CONFIG), "--schema", str(SCHEMA),
            "--actions-db", str(ACTIONS_DB), "--indicators-db", str(INDICATORS_DB),
            "--plan-db", str(PLAN_DB),
            "--materialization-report", str(MATERIALIZATION),
            "--manifest", str(tampered_manifest_path),
            "--report-out", str(manifest_failure_out),
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    assert manifest_only.returncode != 0
    assert "manifest_file_sha256" in manifest_only.stderr
    manifest_failure = json.loads(manifest_failure_out.read_text(encoding="utf-8"))
    assert manifest_failure["status"] == "failed"
    assert manifest_failure["error_code"] == (
        "c2b_pair_plan_validation_failed_fail_closed"
    )


def test_c2b_implementation_is_streaming_and_validator_is_independent() -> None:
    planner_source = PLANNER.read_text(encoding="utf-8")
    validator_source = VALIDATOR.read_text(encoding="utf-8")
    for source in (planner_source, validator_source):
        assert ".fetchall(" not in source
        tree = ast.parse(source)
        sql_literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "SELECT " in node.value.upper()
        ]
        assert all(" OFFSET " not in f" {sql.upper()} " for sql in sql_literals)
    assert "import plan_outcome_context_pairs_c2b" not in validator_source
    assert "from plan_outcome_context_pairs_c2b" not in validator_source
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert config["expected"]["materialization_batch_size"] == 25000
    assert config["expected"]["eligible_pairs"] == 2865602
