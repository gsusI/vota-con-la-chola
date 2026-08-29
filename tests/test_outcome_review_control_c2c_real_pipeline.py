from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from publicdata_publish.outcome_pair_identity_safety import identity_companion_leases

REPO_ROOT = Path(__file__).resolve().parents[1]
MATERIALIZER = REPO_ROOT / "scripts/materialize_outcome_review_control_c2c.py"
VALIDATOR = REPO_ROOT / "scripts/validate_outcome_review_control_c2c.py"
OPERATOR = REPO_ROOT / "scripts/operate_outcome_review_control_c2c.py"
CONFIG = REPO_ROOT / "etl/data/manual/outcome_links/review_control_scope_c2c_v1.json"
SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
CANONICAL_DB = REPO_ROOT / "etl/data/staging/outcome-review-control-c2c-v1.db"
CANONICAL_REPORT = (
    REPO_ROOT / "etl/data/staging/outcome-review-control-c2c-v1-report.json"
)
CANONICAL_MANIFEST = (
    REPO_ROOT / "etl/data/staging/outcome-review-control-c2c-v1-manifest.json"
)
CANONICAL_VALIDATION = (
    REPO_ROOT
    / "docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/"
    / "outcome-review-control-c2c-v1-validation.json"
)


def run(*arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *(str(argument) for argument in arguments)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def sqlite_library_number() -> int:
    major, minor, patch = (int(part) for part in sqlite3.sqlite_version.split("."))
    return major * 1_000_000 + minor * 1_000 + patch


def sqlite_header_version(path: Path) -> int:
    with path.open("rb") as handle:
        handle.seek(96)
        return int.from_bytes(handle.read(4), "big")


def test_canonical_real_capacity_and_zero_human_state() -> None:
    assert CANONICAL_DB.exists()
    config = load(CONFIG)
    source = config["sources"]
    for key in ("discovery_pairs", "semantic_canary"):
        facts = source[key]
        for name, value in facts.items():
            if name == "path" or name.endswith("_path"):
                artifact = REPO_ROOT / str(value)
                assert artifact.exists()
    connection = sqlite3.connect(CANONICAL_DB)
    try:
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        assert list(connection.execute("PRAGMA foreign_key_check")) == []
        assert (
            connection.execute("SELECT COUNT(*) FROM outcome_review_tasks").fetchone()[
                0
            ]
            == 2_865_603
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM outcome_review_slots").fetchone()[
                0
            ]
            == 2_865_604
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM outcome_review_tasks WHERE cohort_id=?",
                ("vclc:outcome-review-cohort:c2b-l0-v1",),
            ).fetchone()[0]
            == 2_865_602
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM outcome_review_slots WHERE slot_kind='discovery_primary'"
            ).fetchone()[0]
            == 2_865_602
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM outcome_review_slots WHERE slot_kind LIKE 'semantic_%'"
            ).fetchone()[0]
            == 2
        )
        for table in (
            "outcome_review_trust_roots",
            "outcome_review_reviewer_identities",
            "outcome_review_auth_events",
            "outcome_review_conflict_events",
            "outcome_review_assignment_events",
            "outcome_review_claim_events",
            "outcome_review_decisions",
            "outcome_review_adjudications",
            "outcome_review_semantic_eligibility_events",
            "outcome_review_semantic_promotions",
            "outcome_review_release_bindings",
            "outcome_review_publication_eligibility_events",
            "outcome_review_publication_events",
            "outcome_review_operation_requests",
            "outcome_review_operational_audit_events",
        ):
            assert (
                connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] == 0
            )
        assert connection.execute(
            "SELECT artifact_scope,trust_root_contract_sha256,"
            "operational_state,control_plane_capacity_status,human_review_status,"
            "semantic_promotion_status,public_release_status,real_data_only,"
            "synthetic_or_mock_decisions FROM outcome_review_control_meta"
        ).fetchone() == (
            "capacity_only",
            "ce76316802e222eafe5a4823bb52cc17c76167f22a3ffcef240ad67c267c16c8",
            "not_materialized",
            "PASS",
            "OPEN",
            "OPEN",
            "OPEN",
            1,
            0,
        )
    finally:
        connection.close()
    operated = run(OPERATOR, "status")
    assert operated.returncode == 0, operated.stderr
    operation_status = json.loads(operated.stdout)
    assert operation_status["mutation_enabled"] is False
    assert operation_status["trust_root_present"] is False
    assert operation_status["operational_event_count"] == 0
    assert operation_status["synthetic_or_mock_events"] == 0
    assert operation_status["capabilities"]["publication"]["state"] == "unavailable"


def test_schema_and_programs_enforce_bounded_append_only_control() -> None:
    schema_text = SCHEMA.read_text(encoding="utf-8")
    begin = "-- BEGIN OUTCOME REVIEW CONTROL C2C SCHEMA"
    end = "-- END OUTCOME REVIEW CONTROL C2C SCHEMA"
    block = schema_text[schema_text.index(begin) : schema_text.index(end) + len(end)]
    expected_guards = (
        "trg_outcome_review_assignment_guard",
        "trg_outcome_review_claim_guard",
        "trg_outcome_review_decision_guard",
        "trg_outcome_review_adjudication_guard",
        "trg_outcome_review_semantic_eligibility_guard",
        "trg_outcome_review_semantic_promotion_guard",
        "trg_outcome_review_release_binding_guard",
        "trg_outcome_review_publication_eligibility_guard",
        "trg_outcome_review_publication_guard",
        "trg_outcome_review_operation_request_target_guard",
        "trg_outcome_review_operational_audit_chain_guard",
        "dual semantic review requires distinct humans",
        "review assignment conflicts with declared interest",
        "claim reclaim lacks active coordinator authorization",
    )
    for guard in expected_guards:
        assert guard in block
    for table in (
        "outcome_review_tasks",
        "outcome_review_slots",
        "outcome_review_trust_roots",
        "outcome_review_reviewer_identities",
        "outcome_review_auth_events",
        "outcome_review_conflict_events",
        "outcome_review_assignment_events",
        "outcome_review_claim_events",
        "outcome_review_decisions",
        "outcome_review_adjudications",
        "outcome_review_semantic_eligibility_events",
        "outcome_review_semantic_promotions",
        "outcome_review_release_bindings",
        "outcome_review_publication_eligibility_events",
        "outcome_review_publication_events",
        "outcome_review_operation_requests",
        "outcome_review_operational_audit_events",
        "outcome_review_audit_events",
    ):
        assert f"trg_{table}_no_update" in block
        assert f"trg_{table}_no_delete" in block
    connection = sqlite3.connect(
        f"file:{CANONICAL_DB.resolve().as_posix()}?mode=ro&immutable=1", uri=True
    )
    try:
        actual_trigger_sql = {
            row[0]: row[1]
            for row in connection.execute(
                "SELECT name,sql FROM sqlite_master WHERE type='trigger' "
                "AND tbl_name LIKE 'outcome_review_%'"
            )
        }
        for guard in expected_guards[:11]:
            assert guard in actual_trigger_sql
            assert actual_trigger_sql[guard].startswith(f"CREATE TRIGGER {guard}")
        canary_version_id = str(
            load(CONFIG)["sources"]["semantic_canary"]["candidate_version_id"]
        )
        query_plans = {
            "claim_current": connection.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM outcome_review_claim_events "
                "WHERE slot_pk=? ORDER BY claim_event_pk DESC LIMIT 1",
                (1,),
            ).fetchall(),
            "claim_supersession": connection.execute(
                "EXPLAIN QUERY PLAN SELECT 1 FROM outcome_review_claim_events "
                "WHERE supersedes_claim_event_id=? AND claim_state=? "
                "AND recorded_at<=? LIMIT 1",
                (canary_version_id, "released", "2026-08-24T00:00:00Z"),
            ).fetchall(),
            "auth_supersession": connection.execute(
                "EXPLAIN QUERY PLAN SELECT 1 FROM outcome_review_auth_events "
                "WHERE supersedes_auth_event_id=? AND auth_state=? "
                "AND effective_at<=? LIMIT 1",
                (canary_version_id, "revoked", "2026-08-24T00:00:00Z"),
            ).fetchall(),
        }
        for name, plan in query_plans.items():
            details = " ".join(str(row[3]) for row in plan)
            assert "USING" in details, (name, details)
            assert "SCAN outcome_review_" not in details, (name, details)
    finally:
        connection.close()
    pair_checkpoint_sql = schema_text[
        schema_text.index(
            "CREATE TABLE IF NOT EXISTS pipeline_keyset_checkpoints"
        ) : schema_text.index("CREATE TABLE IF NOT EXISTS outcome_pair_plan_actions")
    ]
    assert "artifact_scope" not in pair_checkpoint_sql
    assert "trust_root_contract_sha256" not in pair_checkpoint_sql
    for program in (MATERIALIZER, VALIDATOR):
        text = program.read_text(encoding="utf-8")
        assert ".fetchall(" not in text
        assert " OFFSET " not in text.upper()
        assert "ORDER BY action_plan_pk,series_plan_pk LIMIT ?" in text


def test_crash_atomicity_and_committed_resume(tmp_path: Path) -> None:
    database = tmp_path / "outcome-review-control-c2c-v1.db"
    report = tmp_path / "materialization.json"
    manifest = tmp_path / "manifest.json"
    crashed = run(
        MATERIALIZER,
        "--out-db",
        database,
        "--report-out",
        report,
        "--manifest-out",
        manifest,
        "--fault-before-checkpoint-batch",
        1,
    )
    assert crashed.returncode == 1
    connection = sqlite3.connect(database)
    try:
        checkpoint = connection.execute(
            "SELECT tasks_written,slots_written,batches_committed,completed "
            "FROM outcome_review_control_checkpoints"
        ).fetchone()
        assert checkpoint == (0, 0, 0, 0)
        assert (
            connection.execute("SELECT COUNT(*) FROM outcome_review_tasks").fetchone()[
                0
            ]
            == 1
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM outcome_review_slots").fetchone()[
                0
            ]
            == 2
        )
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM outcome_review_audit_events"
            ).fetchone()[0]
            == 1
        )
    finally:
        connection.close()

    first = run(
        MATERIALIZER,
        "--out-db",
        database,
        "--report-out",
        report,
        "--manifest-out",
        manifest,
        "--stop-after-batches",
        1,
    )
    assert first.returncode == 3
    second = run(
        MATERIALIZER,
        "--out-db",
        database,
        "--report-out",
        report,
        "--manifest-out",
        manifest,
        "--stop-after-batches",
        1,
    )
    assert second.returncode == 3
    interrupted = load(report)
    assert interrupted["status"] == "interrupted"
    assert interrupted["execution"] == "resumed"
    assert interrupted["checkpoint"] == {
        "tasks_written": 50_000,
        "slots_written": 50_000,
        "batches_committed": 2,
        "completed": 0,
        "last_action_plan_pk": 8,
        "last_series_plan_pk": 5200,
    }
    completed = run(
        MATERIALIZER,
        "--out-db",
        database,
        "--report-out",
        report,
        "--manifest-out",
        manifest,
    )
    assert completed.returncode == 0, completed.stderr
    completed_report = load(report)
    assert completed_report["status"] == "passed"
    assert completed_report["execution"] == "resumed"
    assert completed_report["checkpoint"]["completed"] == 1
    if sqlite_library_number() == sqlite_header_version(CANONICAL_DB):
        assert digest(database) == digest(CANONICAL_DB)
        assert digest(manifest) == digest(CANONICAL_MANIFEST)
    else:
        canonical_report = load(CANONICAL_REPORT)
        assert (
            completed_report["semantic_root_sha256"]
            == canonical_report["semantic_root_sha256"]
        )
        assert completed_report["counts"] == canonical_report["counts"]
        rebuilt_manifest = load(manifest)
        canonical_manifest = load(CANONICAL_MANIFEST)
        for key in (
            "config_sha256",
            "source_root_sha256",
            "schema_root_sha256",
            "pipeline_key",
            "semantic_root_sha256",
            "counts",
            "statuses",
            "root_scope",
            "trust_root_contract",
            "operational_lifecycle",
            "publication_state",
            "real_data_only",
            "synthetic_or_mock_decisions",
        ):
            assert rebuilt_manifest[key] == canonical_manifest[key]
        connection = sqlite3.connect(database)
        try:
            assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            assert list(connection.execute("PRAGMA foreign_key_check")) == []
        finally:
            connection.close()


def test_canonical_validator_and_noop_replay(tmp_path: Path) -> None:
    validation = tmp_path / "validation.json"
    checked = run(
        VALIDATOR,
        "--plan-db",
        CANONICAL_DB,
        "--materialization-report",
        CANONICAL_REPORT,
        "--manifest",
        CANONICAL_MANIFEST,
        "--report-out",
        validation,
    )
    assert checked.returncode == 0, checked.stderr
    validation_value = load(validation)
    assert validation_value["status"] == "passed"
    assert validation_value["counts"]["tasks"] == 2_865_603
    assert validation_value["counts"]["decisions"] == 0

    before = CANONICAL_DB.stat()
    before_sha = digest(CANONICAL_DB)
    replay_report = tmp_path / "replay-report.json"
    replay_manifest = tmp_path / CANONICAL_MANIFEST.name
    replay = run(
        MATERIALIZER,
        "--out-db",
        CANONICAL_DB,
        "--report-out",
        replay_report,
        "--manifest-out",
        replay_manifest,
    )
    assert replay.returncode == 0, replay.stderr
    assert load(replay_report)["execution"] == "replayed_noop"
    after = CANONICAL_DB.stat()
    assert (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) == (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    assert digest(CANONICAL_DB) == before_sha


def test_failure_reports_atomically_invalidate_stale_success(tmp_path: Path) -> None:
    producer_report = tmp_path / "producer.json"
    shutil.copyfile(CANONICAL_REPORT, producer_report)
    producer_original = producer_report.read_bytes()
    with producer_report.open("rb") as stale_producer:
        failed_producer = run(
            MATERIALIZER,
            "--out-db",
            tmp_path / "unused.db",
            "--report-out",
            producer_report,
            "--manifest-out",
            tmp_path / "unused-manifest.json",
            "--batch-size",
            1,
        )
        assert stale_producer.read() == producer_original
    assert failed_producer.returncode == 1
    producer_failure = load(producer_report)
    assert producer_failure == {
        "format_version": "outcome_review_control_c2c_materialization_report_v1",
        "status": "failed",
        "error_type": "RuntimeError",
        "success_report_invalidated": True,
        "success_manifest_invalidated": True,
    }

    validator_report = tmp_path / "validator.json"
    shutil.copyfile(CANONICAL_VALIDATION, validator_report)
    validator_original = validator_report.read_bytes()
    with validator_report.open("rb") as stale_validator:
        failed_validator = run(
            VALIDATOR,
            "--plan-db",
            CANONICAL_DB,
            "--materialization-report",
            CANONICAL_REPORT,
            "--manifest",
            CANONICAL_REPORT,
            "--report-out",
            validator_report,
        )
        assert stale_validator.read() == validator_original
    assert failed_validator.returncode == 1
    validator_failure = load(validator_report)
    assert validator_failure == {
        "format_version": "outcome_review_control_c2c_validation_report_v1",
        "status": "failed",
        "error_type": "RuntimeError",
        "success_report_invalidated": True,
        "publication_gate_passed": False,
        "semantic_promotion_gate_passed": False,
    }
    serialized = json.dumps(
        {"producer": producer_failure, "validator": validator_failure}
    )
    assert "/Users/" not in serialized
    assert "/home/" not in serialized
    assert "file://" not in serialized


def test_duplicate_manifest_json_fails_closed(tmp_path: Path) -> None:
    duplicate_manifest = tmp_path / "manifest.json"
    canonical_manifest = CANONICAL_MANIFEST.read_text(encoding="utf-8")
    assert canonical_manifest.startswith("{")
    duplicate_manifest.write_text(
        '{"format_version":"outcome_review_control_c2c_manifest_v1",'
        + canonical_manifest[1:],
        encoding="utf-8",
    )
    validation = tmp_path / "validation.json"
    result = run(
        VALIDATOR,
        "--plan-db",
        CANONICAL_DB,
        "--materialization-report",
        CANONICAL_REPORT,
        "--manifest",
        duplicate_manifest,
        "--report-out",
        validation,
    )
    assert result.returncode == 1
    assert load(validation)["status"] == "failed"


def test_duplicate_materialization_report_json_fails_closed(tmp_path: Path) -> None:
    duplicate_report = tmp_path / "materialization.json"
    canonical_report = CANONICAL_REPORT.read_text(encoding="utf-8")
    assert canonical_report.startswith("{")
    duplicate_report.write_text(
        '{"status":"passed",' + canonical_report[1:], encoding="utf-8"
    )
    validation = tmp_path / "validation.json"
    result = run(
        VALIDATOR,
        "--plan-db",
        CANONICAL_DB,
        "--materialization-report",
        duplicate_report,
        "--manifest",
        CANONICAL_MANIFEST,
        "--report-out",
        validation,
    )
    assert result.returncode == 1
    failure = load(validation)
    assert failure["status"] == "failed"
    assert failure["error_type"] == "ValueError"


def test_operator_capacity_root_fails_closed_before_event_parsing() -> None:
    before = CANONICAL_DB.stat()
    before_sha = digest(CANONICAL_DB)
    config = load(CONFIG)
    actor_public_id = str(config["sources"]["semantic_canary"]["candidate_version_id"])
    idempotency_key = str(load(CANONICAL_MANIFEST)["manifest_root_sha256"])
    result = run(
        OPERATOR,
        "--db",
        CANONICAL_DB,
        "claim",
        "--event-json",
        CONFIG,
        "--idempotency-key",
        idempotency_key,
        "--actor-public-id",
        actor_public_id,
    )
    assert result.returncode == 1
    failure = json.loads(result.stderr)
    assert failure == {
        "error_type": "OperationError",
        "format_version": "outcome_review_control_c2c_operation_result_v1",
        "mutation_committed": False,
        "status": "failed",
    }
    after = CANONICAL_DB.stat()
    assert (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) == (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    assert digest(CANONICAL_DB) == before_sha


def test_operator_rejects_linked_and_special_database_paths(tmp_path: Path) -> None:
    symlink = tmp_path / "review-control-symlink.db"
    symlink.symlink_to(CANONICAL_DB)
    linked = run(OPERATOR, "--db", symlink, "status")
    assert linked.returncode == 1

    hardlink_source = tmp_path / "review-control-hardlink-source.db"
    shutil.copyfile(CANONICAL_MANIFEST, hardlink_source)
    hardlink = tmp_path / "review-control-hardlink.db"
    os.link(hardlink_source, hardlink)
    try:
        aliased = run(OPERATOR, "--db", hardlink, "status")
        assert aliased.returncode == 1
    finally:
        hardlink.unlink()
    assert hardlink_source.stat().st_nlink == 1

    fifo = tmp_path / "review-control.fifo"
    os.mkfifo(fifo)
    special = run(OPERATOR, "--db", fifo, "status")
    assert special.returncode == 1


def test_operator_kernel_lease_rejects_concurrent_status() -> None:
    with identity_companion_leases([CANONICAL_DB], namespace="command"):
        collision = run(OPERATOR, "--db", CANONICAL_DB, "status")
    assert collision.returncode == 1
    failure = json.loads(collision.stderr)
    assert failure["status"] == "failed"
    assert failure["mutation_committed"] is False


def test_ancestor_overlap_invalidates_real_stale_success(tmp_path: Path) -> None:
    report_directory = tmp_path / "control"
    output_directory = tmp_path / "output"
    report_directory.mkdir()
    output_directory.mkdir()
    report = report_directory / "materialization.json"
    shutil.copyfile(CANONICAL_REPORT, report)
    original = report.read_bytes()
    with report.open("rb") as stale_report:
        failed = run(
            MATERIALIZER,
            "--out-db",
            output_directory / "review-control.db",
            "--report-out",
            report,
            "--manifest-out",
            output_directory,
        )
        assert stale_report.read() == original
    assert failed.returncode == 1
    invalidated = load(report)
    assert invalidated["status"] == "failed"
    assert invalidated["success_report_invalidated"] is True
    assert invalidated["success_manifest_invalidated"] is True


def test_validator_rejects_linked_real_manifest_and_invalidates_report(
    tmp_path: Path,
) -> None:
    linked_manifest = tmp_path / "manifest-link.json"
    linked_manifest.symlink_to(CANONICAL_MANIFEST)
    validation = tmp_path / "validation.json"
    shutil.copyfile(CANONICAL_VALIDATION, validation)
    original = validation.read_bytes()
    with validation.open("rb") as stale_validation:
        result = run(
            VALIDATOR,
            "--plan-db",
            CANONICAL_DB,
            "--materialization-report",
            CANONICAL_REPORT,
            "--manifest",
            linked_manifest,
            "--report-out",
            validation,
        )
        assert stale_validation.read() == original
    assert result.returncode == 1
    invalidated = load(validation)
    assert invalidated["status"] == "failed"
    assert invalidated["publication_gate_passed"] is False
    assert invalidated["semantic_promotion_gate_passed"] is False
