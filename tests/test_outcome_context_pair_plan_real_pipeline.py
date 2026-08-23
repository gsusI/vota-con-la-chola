from __future__ import annotations

import ast
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
PLANNER = REPO_ROOT / "scripts/plan_outcome_context_pairs.py"
VALIDATOR = REPO_ROOT / "scripts/validate_outcome_context_pair_plan.py"
CONFIG = REPO_ROOT / "etl/data/manual/outcome_links/planner_scope_v1.json"
SCHEMA = REPO_ROOT / "etl/load/sqlite_schema.sql"
ACTIONS_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
INDICATORS_DB = REPO_ROOT / "etl/data/staging/eurostat-indicators-real-s2-20260811.db"

PIPELINE_KEY = "vclc:outcome-pair-plan-pipeline:fa09600aaac1cd953030a959"
SEMANTIC_ROOT = "0fc7c257f891108dbeca034d8337bd0d342e019dfd2b0b5d6d09f76f74de54de"
BUCKET_DISTRIBUTION_ROOT = "533aa57febdf3a7406a44c535fd7ab9e890392f543d17fcc69743523d3d9b70c"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_planner(
    *,
    plan_db: Path,
    report: Path,
    batch_size: int = 1_000,
    config: Path = CONFIG,
    extra: tuple[str, ...] = (),
    expect_success: bool = True,
) -> tuple[subprocess.CompletedProcess[str], dict | None]:
    command = [
        sys.executable,
        str(PLANNER),
        "--config",
        str(config),
        "--schema",
        str(SCHEMA),
        "--actions-db",
        str(ACTIONS_DB),
        "--indicators-db",
        str(INDICATORS_DB),
        "--out-db",
        str(plan_db),
        "--report-out",
        str(report),
        "--batch-size",
        str(batch_size),
        "--source-batch-size",
        "10000",
        *extra,
    ]
    completed = subprocess.run(
        command, cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    if expect_success:
        assert completed.returncode == 0, completed.stdout + completed.stderr
        payload = json.loads(completed.stdout)
        assert payload == json.loads(report.read_text(encoding="utf-8"))
        return completed, payload
    assert completed.returncode != 0
    return completed, None


def run_validator(
    *,
    plan_db: Path,
    materialization_report: Path,
    report_out: Path,
    expect_success: bool = True,
) -> tuple[subprocess.CompletedProcess[str], dict | None]:
    completed = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--config",
            str(CONFIG),
            "--schema",
            str(SCHEMA),
            "--actions-db",
            str(ACTIONS_DB),
            "--indicators-db",
            str(INDICATORS_DB),
            "--plan-db",
            str(plan_db),
            "--materialization-report",
            str(materialization_report),
            "--report-out",
            str(report_out),
            "--page-size",
            "10000",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if expect_success:
        assert completed.returncode == 0, completed.stdout + completed.stderr
        payload = json.loads(completed.stdout)
        assert payload == json.loads(report_out.read_text(encoding="utf-8"))
        return completed, payload
    assert completed.returncode != 0
    return completed, None


@pytest.fixture(scope="module")
def canonical_plan(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path | dict]:
    root = tmp_path_factory.mktemp("real-c2a-pair-plan")
    plan_db = root / "plan.db"
    report_path = root / "materialization.json"
    _, materialization = run_planner(plan_db=plan_db, report=report_path)
    validation_path = root / "validation.json"
    _, validation = run_validator(
        plan_db=plan_db,
        materialization_report=report_path,
        report_out=validation_path,
    )
    return {
        "root": root,
        "db": plan_db,
        "materialization_path": report_path,
        "materialization": materialization,
        "validation": validation,
    }


def test_canonical_real_sparse_pair_plan(canonical_plan: dict[str, Path | dict]) -> None:
    materialization = canonical_plan["materialization"]
    validation = canonical_plan["validation"]
    assert isinstance(materialization, dict)
    assert isinstance(validation, dict)
    assert materialization["status"] == "passed"
    assert materialization["execution"] == "fresh"
    assert materialization["pipeline_key"] == PIPELINE_KEY
    assert materialization["roots"]["semantic_root_sha256"] == SEMANTIC_ROOT
    assert materialization["plan_counts"] == {
        "actions": 458,
        "base_partitions": 18,
        "bucket_partitions": 2598,
        "global_unfiltered_product": 71189230,
        "max_bucket_partition_rows": 93,
        "pairs": 33726,
        "selected_product": 34350,
        "series": 75,
    }
    assert materialization["source_counts"] == {
        "actions": 458,
        "all_indicator_series": 155435,
        "distinct_official_names": 490,
        "members": 119116,
        "points": 937,
        "series": 75,
    }
    assert materialization["bucket_partition_distribution"] == {
        "distribution_sha256": BUCKET_DISTRIBUTION_ROOT,
        "maximum_rows": 93,
        "minimum_rows": 1,
        "partition_count": 2598,
        "row_count": 33726,
    }
    performance = materialization["performance"]
    assert performance["eligible_pairs_processed_this_run"] == 33726
    assert performance["scanned_pairs_processed_this_run"] == 34350
    assert performance["eligible_pairs_per_second"] > 0
    assert performance["scanned_pairs_per_second"] > 0
    assert performance["compute_cost_proxy_seconds_per_1000_eligible_pairs"] > 0
    assert performance["max_rss_bytes"] < 256 * 1024 * 1024
    assert performance["output_database_bytes"] == Path(canonical_plan["db"]).stat().st_size
    assert performance["retries"] == performance["dead_letters"] == 0

    assert validation["status"] == "passed"
    assert validation["failed_checks"] == []
    assert validation["passed_checks"] < 200
    assert validation["counts"]["pairs"] == 33726
    assert validation["counts"]["member_votes_source_resolved"] == 119116
    assert validation["counts"]["official_names_source_resolved"] == 490
    assert validation["roots"]["semantic_root_sha256"] == SEMANTIC_ROOT
    assert validation["performance"]["max_rss_bytes"] < 256 * 1024 * 1024

    connection = sqlite3.connect(Path(canonical_plan["db"]))
    try:
        assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert tables == {
            "pipeline_keyset_checkpoints",
            "outcome_pair_plan_actions",
            "outcome_pair_plan_series",
            "outcome_pair_plan_pairs",
        }
        assert connection.execute(
            "SELECT COUNT(DISTINCT pair_bucket) FROM outcome_pair_plan_pairs"
        ).fetchone()[0] == 256
        assert connection.execute(
            """
            SELECT COUNT(*) FROM outcome_pair_plan_pairs
            WHERE length(pair_bucket)<>2
               OR pair_bucket GLOB '*[^0-9a-f]*'
               OR partition_key<>base_partition_key || '/bucket=' || pair_bucket
            """
        ).fetchone()[0] == 0
        assert connection.execute(
            """
            SELECT COUNT(*) FROM outcome_pair_plan_pairs
            WHERE association_assessment<>'not_assessed'
               OR causal_assessment<>'not_assessed'
               OR effect_estimate_state<>'not_computed'
               OR ranking_eligible<>0 OR publication_eligible<>0
            """
        ).fetchone()[0] == 0
    finally:
        connection.close()


def test_interruption_resume_replay_and_batch_invariant(
    tmp_path: Path, canonical_plan: dict[str, Path | dict]
) -> None:
    interrupted_db = tmp_path / "interrupted.db"
    interrupted_report = tmp_path / "interrupted.json"
    _, partial = run_planner(
        plan_db=interrupted_db,
        report=interrupted_report,
        batch_size=1_000,
        extra=("--max-batches", "3"),
    )
    assert partial["status"] == "interrupted"
    assert partial["performance"]["scanned_pairs_processed_this_run"] == 1000
    _, resumed = run_planner(
        plan_db=interrupted_db,
        report=interrupted_report,
        batch_size=1_000,
    )
    assert resumed["status"] == "passed"
    assert resumed["execution"] == "resumed"
    assert resumed["roots"]["semantic_root_sha256"] == SEMANTIC_ROOT

    before = sha256_file(interrupted_db)
    _, replay = run_planner(
        plan_db=interrupted_db,
        report=interrupted_report,
        batch_size=1_000,
    )
    after = sha256_file(interrupted_db)
    assert replay["execution"] == "replayed_noop"
    assert replay["performance"]["eligible_pairs_processed_this_run"] == 0
    assert replay["performance"]["scanned_pairs_processed_this_run"] == 0
    assert replay["performance"]["eligible_pairs_per_second"] is None
    assert replay["performance"]["scanned_pairs_per_second"] is None
    assert replay["performance"]["compute_cost_proxy_seconds_per_1000_eligible_pairs"] is None
    assert before == after

    rejected, _ = run_planner(
        plan_db=tmp_path / "alternate-batch.db",
        report=tmp_path / "alternate-batch.json",
        batch_size=4_096,
        expect_success=False,
    )
    assert "checkpoint_batch_size" in rejected.stderr


def test_fault_rollback_and_config_drift_are_fail_closed(tmp_path: Path) -> None:
    fault_db = tmp_path / "fault.db"
    fault_report = tmp_path / "fault.json"
    failed, _ = run_planner(
        plan_db=fault_db,
        report=fault_report,
        batch_size=1_000,
        extra=("--fault-before-checkpoint-batch", "3"),
        expect_success=False,
    )
    assert "injected fault before atomic checkpoint commit" in failed.stderr
    connection = sqlite3.connect(fault_db)
    try:
        pair_count = connection.execute(
            "SELECT COUNT(*) FROM outcome_pair_plan_pairs"
        ).fetchone()[0]
        checkpoint = connection.execute(
            "SELECT rows_written,last_key_json,batches_committed FROM pipeline_keyset_checkpoints WHERE stage='pairs'"
        ).fetchone()
        assert pair_count == 0
        assert checkpoint == (0, "[]", 0)
    finally:
        connection.close()

    _, recovered = run_planner(
        plan_db=fault_db,
        report=fault_report,
        batch_size=1_000,
    )
    assert recovered["status"] == "passed"
    assert recovered["roots"]["semantic_root_sha256"] == SEMANTIC_ROOT

    drift_config = tmp_path / "planner-scope-drift.json"
    changed = json.loads(CONFIG.read_text(encoding="utf-8"))
    changed["scope_revision"] = 2
    drift_config.write_text(
        json.dumps(changed, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    drifted, _ = run_planner(
        plan_db=fault_db,
        report=tmp_path / "drift.json",
        batch_size=1_000,
        config=drift_config,
        expect_success=False,
    )
    assert "resume drift" in drifted.stderr


def test_failed_planner_invalidates_stale_success_report(tmp_path: Path) -> None:
    report = tmp_path / "stale-success.json"
    report.write_text('{"status":"passed"}\n', encoding="utf-8")
    failed, _ = run_planner(
        plan_db=tmp_path / "rejected-batch.db",
        report=report,
        batch_size=4_096,
        expect_success=False,
    )
    assert "checkpoint_batch_size" in failed.stderr
    invalidation = json.loads(report.read_text(encoding="utf-8"))
    assert invalidation == {
        "error_type": "RuntimeError",
        "schema_version": "outcome_context_pair_plan_report_v1",
        "status": "failed",
        "success_report_invalidated": True,
    }


def test_failed_validator_invalidates_stale_success_report(
    tmp_path: Path, canonical_plan: dict[str, Path | dict]
) -> None:
    report = tmp_path / "stale-validation-success.json"
    report.write_text('{"status":"passed"}\n', encoding="utf-8")
    failed, _ = run_validator(
        plan_db=tmp_path / "missing-plan.db",
        materialization_report=Path(canonical_plan["materialization_path"]),
        report_out=report,
        expect_success=False,
    )
    assert failed.returncode == 1
    invalidation = json.loads(report.read_text(encoding="utf-8"))
    assert invalidation == {
        "error_type": "OperationalError",
        "schema_version": "outcome_context_pair_plan_validation_v1",
        "status": "failed",
        "success_report_invalidated": True,
    }


def test_scale_forward_schema_accepts_real_spain_subnational_cohort() -> None:
    schema_text = SCHEMA.read_text(encoding="utf-8")
    assert "geography_code GLOB 'ES*'" in schema_text
    assert "country_code TEXT NOT NULL CHECK (country_code = 'ES')" in schema_text

    indicators = sqlite3.connect(
        f"file:{INDICATORS_DB.resolve().as_posix()}?mode=ro&immutable=1", uri=True
    )
    try:
        series = indicators.execute(
            """
            SELECT COUNT(*)
            FROM indicator_series s JOIN source_records sr USING(source_record_pk)
            WHERE s.source_id='eurostat_sdmx'
              AND sr.source_snapshot_date='2026-08-11'
              AND s.frequency='A'
              AND json_extract(s.dimensions_json,'$.series_dimensions.geo') GLOB 'ES*'
            """
        ).fetchone()[0]
        strict_pairs = indicators.execute(
            """
            WITH eligible AS (
              SELECT s.indicator_series_id,
                     CAST(substr(MIN(p.date),1,4) AS INTEGER) AS min_year,
                     CAST(substr(MAX(p.date),1,4) AS INTEGER) AS max_year
              FROM indicator_series s
              JOIN source_records sr USING(source_record_pk)
              JOIN indicator_points p USING(indicator_series_id)
              WHERE s.source_id='eurostat_sdmx'
                AND sr.source_snapshot_date='2026-08-11'
                AND s.frequency='A'
                AND json_extract(s.dimensions_json,'$.series_dimensions.geo') GLOB 'ES*'
              GROUP BY s.indicator_series_id
            ), action_years(year,row_count) AS (
              VALUES (2020,278),(2021,41),(2022,34),(2023,27),(2024,78)
            )
            SELECT SUM(a.row_count)
            FROM eligible e CROSS JOIN action_years a
            WHERE e.min_year<a.year AND e.max_year>a.year
            """
        ).fetchone()[0]
    finally:
        indicators.close()
    assert series == 6400
    assert strict_pairs == 2865602


def test_implementation_has_no_offset_fetchall_or_producer_import() -> None:
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
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    for name in ("actions", "members", "series", "points"):
        sql = config["query_contract"][f"{name}_keyset_sql_utf8"]
        assert " OFFSET " not in f" {sql.upper()} "
    assert "import plan_outcome_context_pairs" not in validator_source
    assert "from plan_outcome_context_pairs" not in validator_source


@pytest.mark.parametrize(
    ("column", "tampered_value"),
    (("action_year", 2099), ("dataset_code", "tampered_dataset")),
)
def test_validator_rejects_pair_duplicate_field_tamper(
    tmp_path: Path,
    canonical_plan: dict[str, Path | dict],
    column: str,
    tampered_value: object,
) -> None:
    tampered_db = tmp_path / f"tampered-{column}.db"
    shutil.copy2(Path(canonical_plan["db"]), tampered_db)
    connection = sqlite3.connect(tampered_db)
    try:
        trigger_name = "trg_outcome_pair_plan_pairs_no_update"
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",
            (trigger_name,),
        ).fetchone()[0]
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("PRAGMA ignore_check_constraints=ON")
        connection.execute(f"DROP TRIGGER {trigger_name}")
        connection.execute(
            f"UPDATE outcome_pair_plan_pairs SET {column}=? "
            "WHERE pair_plan_id=(SELECT pair_plan_id FROM outcome_pair_plan_pairs "
            "ORDER BY action_plan_pk,series_plan_pk LIMIT 1)",
            (tampered_value,),
        )
        connection.execute(trigger_sql)
        connection.commit()
    finally:
        connection.close()

    failed, _ = run_validator(
        plan_db=tampered_db,
        materialization_report=Path(canonical_plan["materialization_path"]),
        report_out=tmp_path / f"tampered-{column}-validation.json",
        expect_success=False,
    )
    assert "pair row 1" in failed.stderr
    assert column in failed.stderr


def test_validator_rejects_completed_checkpoint_progress_tamper(
    tmp_path: Path, canonical_plan: dict[str, Path | dict]
) -> None:
    tampered_db = tmp_path / "tampered-checkpoint.db"
    shutil.copy2(Path(canonical_plan["db"]), tampered_db)
    connection = sqlite3.connect(tampered_db)
    try:
        trigger_name = "trg_pipeline_keyset_checkpoints_completed_immutable"
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",
            (trigger_name,),
        ).fetchone()[0]
        connection.execute(f"DROP TRIGGER {trigger_name}")
        connection.execute(
            "UPDATE pipeline_keyset_checkpoints SET last_key_json='[\"tampered\"]' "
            "WHERE stage='actions'"
        )
        connection.execute(trigger_sql)
        connection.commit()
    finally:
        connection.close()

    failed, _ = run_validator(
        plan_db=tampered_db,
        materialization_report=Path(canonical_plan["materialization_path"]),
        report_out=tmp_path / "tampered-checkpoint-validation.json",
        expect_success=False,
    )
    assert "actions_checkpoint_last_key" in failed.stderr


def test_validator_rejects_coordinated_checkpoint_batch_and_report_tamper(
    tmp_path: Path, canonical_plan: dict[str, Path | dict]
) -> None:
    tampered_db = tmp_path / "tampered-checkpoint-batches.db"
    tampered_report = tmp_path / "tampered-checkpoint-batches.json"
    shutil.copy2(Path(canonical_plan["db"]), tampered_db)
    report = json.loads(
        Path(canonical_plan["materialization_path"]).read_text(encoding="utf-8")
    )
    connection = sqlite3.connect(tampered_db)
    try:
        trigger_name = "trg_pipeline_keyset_checkpoints_completed_immutable"
        trigger_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",
            (trigger_name,),
        ).fetchone()[0]
        connection.execute(f"DROP TRIGGER {trigger_name}")
        connection.execute(
            "UPDATE pipeline_keyset_checkpoints SET batches_committed=36 "
            "WHERE stage='pairs'"
        )
        connection.execute(trigger_sql)
        connection.commit()
    finally:
        connection.close()
    for checkpoint in report["checkpoints"]:
        if checkpoint["stage"] == "pairs":
            checkpoint["batches_committed"] = 36
    report["execution"] = "replayed_noop"
    tampered_report.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    failed, _ = run_validator(
        plan_db=tampered_db,
        materialization_report=tampered_report,
        report_out=tmp_path / "tampered-checkpoint-batches-validation.json",
        expect_success=False,
    )
    assert "pairs_checkpoint_batches_exact" in failed.stderr


def test_validator_rejects_same_name_noop_trigger_tamper(
    tmp_path: Path, canonical_plan: dict[str, Path | dict]
) -> None:
    tampered_db = tmp_path / "tampered-trigger.db"
    shutil.copy2(Path(canonical_plan["db"]), tampered_db)
    connection = sqlite3.connect(tampered_db)
    try:
        trigger_name = "trg_outcome_pair_plan_pairs_no_delete"
        connection.execute(f"DROP TRIGGER {trigger_name}")
        connection.execute(
            f"CREATE TRIGGER {trigger_name} BEFORE DELETE "
            "ON outcome_pair_plan_pairs WHEN 0 BEGIN SELECT 1; END"
        )
        connection.commit()
    finally:
        connection.close()

    failed, _ = run_validator(
        plan_db=tampered_db,
        materialization_report=Path(canonical_plan["materialization_path"]),
        report_out=tmp_path / "tampered-trigger-validation.json",
        expect_success=False,
    )
    assert "canonical_schema_object_definitions" in failed.stderr
