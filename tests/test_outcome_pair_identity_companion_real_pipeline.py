"""Real-artifact-only tests for the C2B participant identity companion."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import publicdata_publish.outcome_pair_identity_companion as companion
from publicdata_publish.outcome_pair_identity_companion import (
    CANONICAL_COMPRESSION_LEVEL,
    CANONICAL_DATA_PAGE_VERSION,
    CANONICAL_DICTIONARY_PAGE_SIZE_LIMIT,
    CANONICAL_PARQUET_CREATED_BY,
    CANONICAL_PARQUET_FORMAT_VERSION,
    CANONICAL_PYARROW_VERSION,
    CANONICAL_ROW_GROUP_ROWS,
    CANONICAL_SOURCE_PAGE_SIZE,
    CANONICAL_WRITE_BATCH_SIZE,
    EXECUTED_ACTION_SCAN_SQL_SHA256,
    EXECUTED_MEMBER_SCAN_SQL_SHA256,
    EXPECTED_ACTIONS,
    EXPECTED_CONFIG_CANONICAL_SHA256,
    EXPECTED_CONFIG_FILE_SHA256,
    EXPECTED_MEMBER_COMPONENT_ROOT_SHA256,
    EXPECTED_MEMBER_ROWS,
    EXPECTED_OFFICIAL_NAMES,
    EXPECTED_PACKAGE_SEMANTIC_ROOT_SHA256,
    EXPECTED_SOURCE_DATABASE_BYTES,
    SOURCE_ACTION_SCAN_SQL,
    SOURCE_MEMBER_SCAN_SQL,
    canonical_sha256,
    load_json,
    open_readonly_database,
)
from publicdata_publish.outcome_pair_identity_companion_validation import (
    IDENTITY_INVENTORY_MAX_DEPTH,
    IDENTITY_INVENTORY_MAX_DIRECTORIES,
    IDENTITY_INVENTORY_MAX_FILES,
    IDENTITY_INVENTORY_MAX_PATH_BYTES,
    _assert_exact_inventory,
    validate_outcome_pair_identity_companion,
)
from publicdata_publish.outcome_pair_identity_safety import (
    bound_regular_file,
    exact_regular_inventory,
    identity_companion_leases,
    require_bounded_finite_float,
    require_bounded_int,
    require_exact_int,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / "etl/data/manual/outcome_links/planner_scope_c2b_v1.json"
SOURCE_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
PAIR_PLAN_DB = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1.db"
EXPORTER = REPO_ROOT / "scripts/export_outcome_pair_identity_companion.py"
VALIDATOR = REPO_ROOT / "scripts/validate_outcome_pair_identity_companion.py"
CANONICAL_ROOT = REPO_ROOT / "etl/data/derived/outcome-pair-identity-companion-c2b-v1"
CANONICAL_MANIFEST = (
    REPO_ROOT / "etl/data/staging/outcome-pair-identity-companion-c2b-v1-manifest.json"
)
CANONICAL_EXPORT_REPORT = (
    REPO_ROOT / "etl/data/staging/outcome-pair-identity-companion-c2b-v1-report.json"
)
CANONICAL_VALIDATION_REPORT = (
    REPO_ROOT
    / "etl/data/staging/outcome-pair-identity-companion-c2b-v1-validation.json"
)


def _readonly(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"file:{path.resolve().as_posix()}?mode=ro&immutable=1", uri=True
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _require_real_controls() -> None:
    missing = [
        path
        for path in (
            CANONICAL_ROOT,
            CANONICAL_MANIFEST,
            CANONICAL_EXPORT_REPORT,
            CANONICAL_VALIDATION_REPORT,
        )
        if not path.exists()
    ]
    if missing:
        raise unittest.SkipTest("canonical real identity controls are not materialized")


def _require_pyarrow() -> None:
    try:
        import pyarrow  # noqa: F401
    except ModuleNotFoundError:
        raise unittest.SkipTest("pyarrow optional dependency is not installed")


def test_pinned_real_source_has_every_public_identity() -> None:
    config = load_json(CONFIG)
    assert _sha256_file(CONFIG) == EXPECTED_CONFIG_FILE_SHA256
    assert canonical_sha256(config) == EXPECTED_CONFIG_CANONICAL_SHA256
    assert SOURCE_DB.stat().st_size == EXPECTED_SOURCE_DATABASE_BYTES
    connection = _readonly(SOURCE_DB)
    try:
        row = connection.execute(
            """
            SELECT COUNT(*) AS member_rows,
                   COUNT(DISTINCT m.member_name) AS official_names,
                   COUNT(DISTINCT m.vote_event_id) AS actions,
                   SUM(m.member_name IS NULL OR trim(m.member_name)='') AS blank_names,
                   SUM(m.member_vote_id IS NULL) AS missing_member_vote_ids,
                   SUM(m.person_id IS NULL) AS missing_person_ids,
                   SUM(m.source_url NOT LIKE 'https://www.senado.es/%') AS bad_urls
            FROM parl_vote_member_votes m
            JOIN parl_vote_events v ON v.vote_event_id=m.vote_event_id
            JOIN source_records sr ON sr.source_record_pk=v.source_record_pk
            WHERE v.source_id=? AND sr.source_snapshot_date=?
              AND v.vote_date IS NOT NULL AND trim(v.vote_date)<>''
            """,
            ("senado_votaciones", "2026-02-12"),
        ).fetchone()
    finally:
        connection.close()
    assert dict(row) == {
        "member_rows": EXPECTED_MEMBER_ROWS,
        "official_names": EXPECTED_OFFICIAL_NAMES,
        "actions": EXPECTED_ACTIONS,
        "blank_names": 0,
        "missing_member_vote_ids": 0,
        "missing_person_ids": 0,
        "bad_urls": 0,
    }


def test_manifest_binds_exact_executed_scans_and_explicit_source_projection() -> None:
    _require_real_controls()
    config = load_json(CONFIG)
    manifest = load_json(CANONICAL_MANIFEST)
    assert hashlib.sha256(SOURCE_ACTION_SCAN_SQL.encode()).hexdigest() == (
        EXECUTED_ACTION_SCAN_SQL_SHA256
    )
    assert hashlib.sha256(SOURCE_MEMBER_SCAN_SQL.encode()).hexdigest() == (
        EXECUTED_MEMBER_SCAN_SQL_SHA256
    )
    assert manifest["source"]["executed_actions_scan_sql_sha256"] == (
        EXECUTED_ACTION_SCAN_SQL_SHA256
    )
    assert manifest["source"]["executed_members_scan_sql_sha256"] == (
        EXECUTED_MEMBER_SCAN_SQL_SHA256
    )
    assert (
        manifest["source"]["configured_actions_keyset_sql_sha256"]
        == (config["query_contract"]["actions_keyset_sql_sha256"])
    )
    assert (
        manifest["source"]["configured_members_keyset_sql_sha256"]
        == (config["query_contract"]["members_keyset_sql_sha256"])
    )
    assert (
        manifest["tables"]["member_vote_identities"][
            "participant_projection_field_map"
        ]["source_url"]
        == "member_source_url"
    )


def test_bound_sqlite_descriptor_is_the_database_actually_queried() -> None:
    with bound_regular_file(SOURCE_DB, database=True) as source_bound:
        connection = open_readonly_database(source_bound)
        try:
            database_path = str(
                connection.execute("PRAGMA database_list").fetchone()[2]
            )
            member_rows = int(
                connection.execute(
                    """
                SELECT COUNT(*)
                FROM parl_vote_member_votes m
                JOIN parl_vote_events v ON v.vote_event_id=m.vote_event_id
                JOIN source_records sr ON sr.source_record_pk=v.source_record_pk
                WHERE v.source_id=? AND sr.source_snapshot_date=?
                  AND v.vote_date IS NOT NULL AND trim(v.vote_date)<>''
                """,
                    ("senado_votaciones", "2026-02-12"),
                ).fetchone()[0]
            )
        finally:
            connection.rollback()
            connection.close()
        descriptor_stat = os.fstat(source_bound.handle.fileno())
        opened_stat = Path(database_path).stat()
        assert (opened_stat.st_dev, opened_stat.st_ino, opened_stat.st_size) == (
            descriptor_stat.st_dev,
            descriptor_stat.st_ino,
            descriptor_stat.st_size,
        )
        assert member_rows == EXPECTED_MEMBER_ROWS


def test_disk_staged_real_stream_is_indexed_and_matches_plan() -> None:
    config = load_json(CONFIG)
    with tempfile.TemporaryDirectory() as temporary:
        source = open_readonly_database(SOURCE_DB)
        plan = open_readonly_database(PAIR_PLAN_DB)
        scratch = companion._scratch_connection(Path(temporary) / "real-stage.sqlite3")
        try:
            companion._stage_real_inputs(
                source_connection=source,
                plan_connection=plan,
                scratch=scratch,
                config=config,
                batch_rows=CANONICAL_SOURCE_PAGE_SIZE,
            )
            counts = tuple(
                scratch.execute(
                    "SELECT (SELECT COUNT(*) FROM source_members),"
                    "(SELECT COUNT(*) FROM official_names),"
                    "(SELECT COUNT(*) FROM source_actions),"
                    "(SELECT COUNT(*) FROM plan_actions)"
                ).fetchone()
            )
            root = companion._materialize_action_aggregates(scratch)
        finally:
            scratch.close()
            source.close()
            plan.close()
    assert counts == (
        EXPECTED_MEMBER_ROWS,
        EXPECTED_OFFICIAL_NAMES,
        EXPECTED_ACTIONS,
        EXPECTED_ACTIONS,
    )
    assert root == EXPECTED_MEMBER_COMPONENT_ROOT_SHA256


def test_resource_numbers_reject_nan_inf_bool_and_enormous_values() -> None:
    for value in (float("nan"), float("inf"), float("-inf"), True, 513.0):
        try:
            require_bounded_finite_float(
                "rss", value, minimum_exclusive=0.0, maximum=512.0
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe RSS value accepted: {value!r}")
    for value in (True, 0, 5_001, 10**12):
        try:
            require_bounded_int("batch", value, minimum=1, maximum=5_000)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe batch value accepted: {value!r}")
    for value in (True, 4_999, 5_001):
        try:
            require_exact_int("row_group", value, 5_000)
        except ValueError:
            pass
        else:
            raise AssertionError(f"non-canonical row-group value accepted: {value!r}")


def test_validation_failure_replaces_real_stale_success_control() -> None:
    _require_real_controls()
    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary)
        report = temporary_root / "validation.json"
        shutil.copy2(CANONICAL_VALIDATION_REPORT, report)
        completed = _run(
            [
                str(VALIDATOR),
                "--root",
                str(temporary_root / "missing-real-package"),
                "--source-db",
                str(SOURCE_DB),
                "--config",
                str(CONFIG),
                "--pair-plan-db",
                str(PAIR_PLAN_DB),
                "--report-out",
                str(report),
            ]
        )
        assert completed.returncode != 0
        failure = json.loads(report.read_text())
        assert failure["status"] == "failed"
        assert failure["success_report_invalidated"] is True
        assert failure["publication_gate_passed"] is False


def test_export_rejects_alias_to_real_config_without_touching_input() -> None:
    _require_real_controls()
    before = _sha256_file(CONFIG)
    with tempfile.TemporaryDirectory() as temporary:
        report = Path(temporary) / "report.json"
        shutil.copy2(CANONICAL_EXPORT_REPORT, report)
        stale_inode = report.stat().st_ino
        completed = _run(
            [
                str(EXPORTER),
                "--source-db",
                str(SOURCE_DB),
                "--config",
                str(CONFIG),
                "--pair-plan-db",
                str(PAIR_PLAN_DB),
                "--out-root",
                str(Path(temporary) / "must-not-exist"),
                "--manifest-out",
                str(CONFIG),
                "--report-out",
                str(report),
            ]
        )
        assert completed.returncode != 0
        assert report.stat().st_ino != stale_inode
        failure = json.loads(report.read_text())
        assert failure["status"] == "failed"
        assert failure["success_report_invalidated"] is True
        assert failure["success_manifest_invalidated"] is False
        serialized = json.dumps(failure, sort_keys=True)
        assert "/Users/" not in serialized
        assert "/home/" not in serialized
        assert "member_name" not in serialized
        assert "official_action_url" not in serialized
    assert _sha256_file(CONFIG) == before


def test_export_failure_invalidates_copied_real_success_controls() -> None:
    _require_real_controls()
    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary)
        occupied_root = temporary_root / "occupied-real-output"
        occupied_root.mkdir()
        manifest = temporary_root / "manifest.json"
        report = temporary_root / "report.json"
        shutil.copy2(CANONICAL_MANIFEST, manifest)
        shutil.copy2(CANONICAL_EXPORT_REPORT, report)
        completed = _run(
            [
                str(EXPORTER),
                "--source-db",
                str(SOURCE_DB),
                "--config",
                str(CONFIG),
                "--pair-plan-db",
                str(PAIR_PLAN_DB),
                "--out-root",
                str(occupied_root),
                "--manifest-out",
                str(manifest),
                "--report-out",
                str(report),
                "--max-peak-rss-mb",
                "nan",
            ]
        )
        assert completed.returncode != 0
        assert not manifest.exists()
        failure = json.loads(report.read_text())
        assert failure["status"] == "failed"
        assert failure["success_manifest_invalidated"] is True


def test_ancestor_path_failure_invalidates_real_stale_controls_fail_closed() -> None:
    _require_real_controls()
    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary)
        ancestor_manifest = temporary_root / "ancestor-manifest"
        report = temporary_root / "report.json"
        shutil.copy2(CANONICAL_MANIFEST, ancestor_manifest)
        shutil.copy2(CANONICAL_EXPORT_REPORT, report)
        completed = _run(
            [
                str(EXPORTER),
                "--source-db",
                str(SOURCE_DB),
                "--config",
                str(CONFIG),
                "--pair-plan-db",
                str(PAIR_PLAN_DB),
                "--out-root",
                str(ancestor_manifest / "package"),
                "--manifest-out",
                str(ancestor_manifest),
                "--report-out",
                str(report),
            ]
        )
        assert completed.returncode != 0
        assert not ancestor_manifest.exists()
        failure = json.loads(report.read_text())
        assert failure["status"] == "failed"
        assert failure["success_manifest_invalidated"] is True


def test_exact_inventory_rejects_real_package_special_links_and_empty_dirs() -> None:
    _require_real_controls()
    baseline_files, baseline_directories = exact_regular_inventory(CANONICAL_ROOT)

    def assert_rejected(mutator: Any) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "package"
            shutil.copytree(CANONICAL_ROOT, package)
            cleanup = mutator(package)
            try:
                try:
                    _assert_exact_inventory(
                        package, baseline_files, baseline_directories
                    )
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("adversarial inode inventory was accepted")
            finally:
                if cleanup is not None:
                    cleanup()

    assert_rejected(lambda package: (package / "undeclared-empty").mkdir())
    assert_rejected(
        lambda package: (package / "undeclared-link").symlink_to(
            package / "manifest.json"
        )
    )

    def hardlink(package: Path) -> None:
        first = next(package.rglob("*.parquet"))
        os.link(first, package / "undeclared-hardlink.parquet")

    assert_rejected(hardlink)
    assert_rejected(lambda package: os.mkfifo(package / "undeclared-fifo"))

    def unix_socket(package: Path) -> Any:
        handle = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        handle.bind(str(package / "undeclared-socket"))
        return handle.close

    assert_rejected(unix_socket)


def test_identity_inventory_stops_at_file_and_directory_hard_bounds() -> None:
    _require_real_controls()
    baseline_files, baseline_directories = exact_regular_inventory(
        CANONICAL_ROOT,
        max_files=IDENTITY_INVENTORY_MAX_FILES,
        max_directories=IDENTITY_INVENTORY_MAX_DIRECTORIES,
        max_depth=IDENTITY_INVENTORY_MAX_DEPTH,
        max_path_bytes=IDENTITY_INVENTORY_MAX_PATH_BYTES,
    )
    with tempfile.TemporaryDirectory() as temporary:
        package = Path(temporary) / "file-bound-package"
        shutil.copytree(CANONICAL_ROOT, package)
        additions = IDENTITY_INVENTORY_MAX_FILES - len(baseline_files) + 1
        for index in range(additions):
            shutil.copy2(
                CANONICAL_ROOT / "manifest.json",
                package / f"real-manifest-copy-{index:02d}.json",
            )
        try:
            exact_regular_inventory(
                package,
                max_files=IDENTITY_INVENTORY_MAX_FILES,
                max_directories=IDENTITY_INVENTORY_MAX_DIRECTORIES,
                max_depth=IDENTITY_INVENTORY_MAX_DEPTH,
                max_path_bytes=IDENTITY_INVENTORY_MAX_PATH_BYTES,
            )
        except RuntimeError as exc:
            assert "file inventory exceeds the hard bound" in str(exc)
        else:
            raise AssertionError("identity file inventory hard bound was not enforced")

    with tempfile.TemporaryDirectory() as temporary:
        package = Path(temporary) / "directory-bound-package"
        shutil.copytree(CANONICAL_ROOT, package)
        additions = IDENTITY_INVENTORY_MAX_DIRECTORIES - len(baseline_directories) + 1
        for index in range(additions):
            (package / f"bounded-directory-{index:02d}").mkdir()
        try:
            exact_regular_inventory(
                package,
                max_files=IDENTITY_INVENTORY_MAX_FILES,
                max_directories=IDENTITY_INVENTORY_MAX_DIRECTORIES,
                max_depth=IDENTITY_INVENTORY_MAX_DEPTH,
                max_path_bytes=IDENTITY_INVENTORY_MAX_PATH_BYTES,
            )
        except RuntimeError as exc:
            assert "directory inventory exceeds the hard bound" in str(exc)
        else:
            raise AssertionError(
                "identity directory inventory hard bound was not enforced"
            )

    with tempfile.TemporaryDirectory() as temporary:
        package = Path(temporary) / "depth-bound-package"
        shutil.copytree(CANONICAL_ROOT, package)
        cursor = package
        for index in range(IDENTITY_INVENTORY_MAX_DEPTH + 1):
            cursor = cursor / f"d{index}"
            cursor.mkdir()
        try:
            exact_regular_inventory(
                package,
                max_files=IDENTITY_INVENTORY_MAX_FILES,
                max_directories=64,
                max_depth=IDENTITY_INVENTORY_MAX_DEPTH,
                max_path_bytes=IDENTITY_INVENTORY_MAX_PATH_BYTES,
            )
        except RuntimeError as exc:
            assert "depth or path bytes exceed the hard bound" in str(exc)
        else:
            raise AssertionError("identity inventory depth hard bound was not enforced")

    with tempfile.TemporaryDirectory() as temporary:
        package = Path(temporary) / "path-bound-package"
        shutil.copytree(CANONICAL_ROOT, package)
        cursor = package
        for character in ("a", "b", "c"):
            cursor = cursor / (character * 180)
            cursor.mkdir()
        try:
            exact_regular_inventory(
                package,
                max_files=IDENTITY_INVENTORY_MAX_FILES,
                max_directories=64,
                max_depth=IDENTITY_INVENTORY_MAX_DEPTH,
                max_path_bytes=IDENTITY_INVENTORY_MAX_PATH_BYTES,
            )
        except RuntimeError as exc:
            assert "depth or path bytes exceed the hard bound" in str(exc)
        else:
            raise AssertionError(
                "identity inventory path-byte hard bound was not enforced"
            )


def test_dangling_control_and_package_symlink_aliases_fail_closed() -> None:
    _require_real_controls()
    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary)
        dangling_manifest = temporary_root / "dangling-manifest.json"
        dangling_manifest.symlink_to(temporary_root / "missing-target.json")
        report = temporary_root / "real-report.json"
        shutil.copy2(CANONICAL_EXPORT_REPORT, report)
        completed = _run(
            [
                str(EXPORTER),
                "--source-db",
                str(SOURCE_DB),
                "--config",
                str(CONFIG),
                "--pair-plan-db",
                str(PAIR_PLAN_DB),
                "--out-root",
                str(temporary_root / "package"),
                "--manifest-out",
                str(dangling_manifest),
                "--report-out",
                str(report),
            ]
        )
        assert completed.returncode != 0
        assert json.loads(report.read_text())["status"] == "failed"
        assert not (temporary_root / "package").exists()

        package_alias = temporary_root / "package-alias"
        package_alias.symlink_to(CANONICAL_ROOT, target_is_directory=True)
        validation_report = temporary_root / "real-validation.json"
        shutil.copy2(CANONICAL_VALIDATION_REPORT, validation_report)
        completed = _run(
            [
                str(VALIDATOR),
                "--root",
                str(package_alias),
                "--manifest",
                str(CANONICAL_MANIFEST),
                "--source-db",
                str(SOURCE_DB),
                "--config",
                str(CONFIG),
                "--pair-plan-db",
                str(PAIR_PLAN_DB),
                "--report-out",
                str(validation_report),
            ]
        )
        assert completed.returncode != 0
        assert json.loads(validation_report.read_text())["status"] == "failed"


def test_kernel_lease_blocks_second_process_without_target_path_leak() -> None:
    _require_real_controls()
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary) / "real-manifest.json"
        shutil.copy2(CANONICAL_MANIFEST, target)
        child = (
            "from pathlib import Path; import sys; "
            "from publicdata_publish.outcome_pair_identity_safety import identity_companion_leases; "
            "c=identity_companion_leases([Path(sys.argv[1])],namespace='evidence'); "
            "c.__enter__(); c.__exit__(None,None,None)"
        )
        with identity_companion_leases([target], namespace="build") as lock_paths:
            completed = _run(["-c", child, str(target)])
            assert completed.returncode != 0
            for lock_path in lock_paths:
                payload = lock_path.read_text()
                assert str(target) not in payload
                assert "target_identity_sha256" in payload

        locked_output = Path(temporary) / "locked-output"
        manifest = Path(temporary) / "stale-real-manifest.json"
        report = Path(temporary) / "stale-real-report.json"
        shutil.copy2(CANONICAL_MANIFEST, manifest)
        shutil.copy2(CANONICAL_EXPORT_REPORT, report)
        with identity_companion_leases([locked_output], namespace="evidence"):
            completed = _run(
                [
                    str(EXPORTER),
                    "--source-db",
                    str(SOURCE_DB),
                    "--config",
                    str(CONFIG),
                    "--pair-plan-db",
                    str(PAIR_PLAN_DB),
                    "--out-root",
                    str(locked_output),
                    "--manifest-out",
                    str(manifest),
                    "--report-out",
                    str(report),
                ]
            )
        assert completed.returncode != 0
        assert not manifest.exists()
        assert json.loads(report.read_text())["status"] == "failed"


def test_cli_nan_and_hard_caps_fail_before_real_package_scan() -> None:
    _require_pyarrow()
    _require_real_controls()
    with tempfile.TemporaryDirectory() as temporary:
        temporary_root = Path(temporary)
        for unsafe in ("nan", "inf", "513", "1000000000000"):
            report = temporary_root / f"validation-{unsafe}.json"
            shutil.copy2(CANONICAL_VALIDATION_REPORT, report)
            completed = _run(
                [
                    str(VALIDATOR),
                    "--root",
                    str(CANONICAL_ROOT),
                    "--manifest",
                    str(CANONICAL_MANIFEST),
                    "--source-db",
                    str(SOURCE_DB),
                    "--config",
                    str(CONFIG),
                    "--pair-plan-db",
                    str(PAIR_PLAN_DB),
                    "--report-out",
                    str(report),
                    "--max-peak-rss-mb",
                    unsafe,
                ]
            )
            assert completed.returncode != 0
            assert json.loads(report.read_text())["status"] == "failed"
        report = temporary_root / "validation-batch.json"
        completed = _run(
            [
                str(VALIDATOR),
                "--root",
                str(CANONICAL_ROOT),
                "--manifest",
                str(CANONICAL_MANIFEST),
                "--source-db",
                str(SOURCE_DB),
                "--config",
                str(CONFIG),
                "--pair-plan-db",
                str(PAIR_PLAN_DB),
                "--report-out",
                str(report),
                "--batch-rows",
                "1000000000000",
            ]
        )
        assert completed.returncode != 0
        assert json.loads(report.read_text())["status"] == "failed"


@unittest.skipUnless(
    os.environ.get("RUN_REAL_C2B_IDENTITY_E2E") == "1",
    "set RUN_REAL_C2B_IDENTITY_E2E=1 for full real export",
)
def test_full_real_export_and_independent_validation() -> None:
    _require_pyarrow()
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "etl/data/staging") as temporary:
        temporary_root = Path(temporary)
        package = temporary_root / "identity-package"
        manifest = temporary_root / "identity-manifest.json"
        export_report = temporary_root / "identity-export-report.json"
        validation_report = temporary_root / "identity-validation-report.json"
        stale_work = temporary_root / f".{package.name}.work"
        stale_work.mkdir()
        shutil.copy2(CANONICAL_MANIFEST, stale_work / "interrupted-real-manifest.json")
        exported = _run(
            [
                str(EXPORTER),
                "--source-db",
                str(SOURCE_DB),
                "--config",
                str(CONFIG),
                "--pair-plan-db",
                str(PAIR_PLAN_DB),
                "--out-root",
                str(package),
                "--manifest-out",
                str(manifest),
                "--report-out",
                str(export_report),
            ]
        )
        assert exported.returncode == 0, exported.stdout + exported.stderr
        assert not stale_work.exists()
        export_control = json.loads(export_report.read_text())
        assert export_control["status"] == "materialized_pending_independent_validation"
        assert export_control["existing_root_replay_verified"] is False
        assert export_control["controls_restored"] is False
        assert export_control["recovered_after_interruption"] is False
        validated = _run(
            [
                str(VALIDATOR),
                "--root",
                str(package),
                "--manifest",
                str(manifest),
                "--source-db",
                str(SOURCE_DB),
                "--config",
                str(CONFIG),
                "--pair-plan-db",
                str(PAIR_PLAN_DB),
                "--report-out",
                str(validation_report),
            ]
        )
        assert validated.returncode == 0, validated.stdout + validated.stderr
        report = json.loads(validation_report.read_text())
        assert report["status"] == "ok"
        assert report["counts"]["member_vote_rows"] == EXPECTED_MEMBER_ROWS
        assert report["counts"]["distinct_official_names"] == EXPECTED_OFFICIAL_NAMES
        assert (
            report["package_semantic_root_sha256"]
            == EXPECTED_PACKAGE_SEMANTIC_ROOT_SHA256
        )
        assert report["checks"]["dataset_api_compatible"] is True
        assert report["publication_gate_passed"] is False
        assert report["ranking_gate_passed"] is False
        assert report["promotion_gate_passed"] is False
        canonical_files, canonical_directories = exact_regular_inventory(
            CANONICAL_ROOT,
            max_files=IDENTITY_INVENTORY_MAX_FILES,
            max_directories=IDENTITY_INVENTORY_MAX_DIRECTORIES,
            max_depth=IDENTITY_INVENTORY_MAX_DEPTH,
            max_path_bytes=IDENTITY_INVENTORY_MAX_PATH_BYTES,
        )
        replay_files, replay_directories = exact_regular_inventory(
            package,
            max_files=IDENTITY_INVENTORY_MAX_FILES,
            max_directories=IDENTITY_INVENTORY_MAX_DIRECTORIES,
            max_depth=IDENTITY_INVENTORY_MAX_DEPTH,
            max_path_bytes=IDENTITY_INVENTORY_MAX_PATH_BYTES,
        )
        assert replay_directories == canonical_directories
        assert replay_files == canonical_files
        for relative in sorted(canonical_files):
            assert _sha256_file(package / relative) == _sha256_file(
                CANONICAL_ROOT / relative
            )
        assert manifest.read_bytes() == CANONICAL_MANIFEST.read_bytes()


def test_canonical_real_package_runs_full_independent_validation_and_dataset_apis() -> (
    None
):
    _require_pyarrow()
    _require_real_controls()
    with tempfile.TemporaryDirectory() as temporary:
        report_path = Path(temporary) / "identity-validation.json"
        completed = _run(
            [
                str(VALIDATOR),
                "--root",
                str(CANONICAL_ROOT),
                "--manifest",
                str(CANONICAL_MANIFEST),
                "--source-db",
                str(SOURCE_DB),
                "--config",
                str(CONFIG),
                "--pair-plan-db",
                str(PAIR_PLAN_DB),
                "--report-out",
                str(report_path),
            ]
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "ok"
    assert report["counts"]["member_vote_rows"] == EXPECTED_MEMBER_ROWS
    assert report["counts"]["distinct_official_names"] == EXPECTED_OFFICIAL_NAMES
    assert report["counts"]["actions"] == EXPECTED_ACTIONS
    assert (
        report["package_semantic_root_sha256"] == EXPECTED_PACKAGE_SEMANTIC_ROOT_SHA256
    )
    import pyarrow.dataset as ds
    import pyarrow.parquet as pq

    manifest = load_json(CANONICAL_MANIFEST)
    assert manifest["layout"] == {
        "compression": "zstd",
        "compression_level": CANONICAL_COMPRESSION_LEVEL,
        "row_group_rows": CANONICAL_ROW_GROUP_ROWS,
        "max_file_rows": 25_000,
        "partition_key": "action_year",
        "partition_directory_contract": (
            "member_vote_identities/by_action_year/{year}"
        ),
        "file_name_contract": "part-{semantic_sha256}.parquet",
        "content_address": "SHA-256 of ordered canonical persisted rows",
        "pyarrow_version": CANONICAL_PYARROW_VERSION,
        "parquet_created_by": CANONICAL_PARQUET_CREATED_BY,
        "parquet_format_version": CANONICAL_PARQUET_FORMAT_VERSION,
        "data_page_version": CANONICAL_DATA_PAGE_VERSION,
        "write_batch_size": CANONICAL_WRITE_BATCH_SIZE,
        "dictionary_page_size_limit_bytes": CANONICAL_DICTIONARY_PAGE_SIZE_LIMIT,
        "dictionary_encoding": True,
        "statistics": True,
        "byte_stream_split": False,
        "compliant_nested_types": True,
        "store_arrow_schema": True,
        "page_index": False,
        "page_checksum": False,
        "decimal_as_integer": False,
    }
    first = next((CANONICAL_ROOT / "member_vote_identities").rglob("*.parquet"))
    metadata = pq.ParquetFile(first).metadata
    assert metadata.created_by == CANONICAL_PARQUET_CREATED_BY
    assert str(metadata.format_version) == CANONICAL_PARQUET_FORMAT_VERSION
    assert pq.read_table(first).num_rows > 0
    dataset = ds.dataset(CANONICAL_ROOT / "member_vote_identities", format="parquet")
    assert dataset.count_rows() == EXPECTED_MEMBER_ROWS
    assert dataset.count_rows(filter=ds.field("action_year") == 2020) == 71_450


@unittest.skipUnless(
    os.environ.get("RUN_REAL_C2B_IDENTITY_E2E") == "1",
    "set RUN_REAL_C2B_IDENTITY_E2E=1 for interruption recovery",
)
def test_real_promoted_package_recovers_missing_external_controls() -> None:
    _require_pyarrow()
    _require_real_controls()
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "etl/data/staging") as temporary:
        temporary_root = Path(temporary)
        package = temporary_root / "promoted-real-package"
        shutil.copytree(CANONICAL_ROOT, package)
        manifest = temporary_root / "recovered-manifest.json"
        report = temporary_root / "recovered-report.json"
        completed = _run(
            [
                str(EXPORTER),
                "--source-db",
                str(SOURCE_DB),
                "--config",
                str(CONFIG),
                "--pair-plan-db",
                str(PAIR_PLAN_DB),
                "--out-root",
                str(package),
                "--manifest-out",
                str(manifest),
                "--report-out",
                str(report),
            ]
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        restored = json.loads(report.read_text())
        assert restored["status"] == "verified_existing_root_controls_restored"
        assert restored["controls_restored"] is True
        assert restored["existing_root_replay_verified"] is False
        assert restored["recovered_after_interruption"] is False
        assert restored["independent_validation_passed"] is True
        assert manifest.read_bytes() == (package / "manifest.json").read_bytes()


@unittest.skipUnless(
    os.environ.get("RUN_REAL_C2B_IDENTITY_E2E") == "1",
    "set RUN_REAL_C2B_IDENTITY_E2E=1 for verified existing-root replay",
)
def test_real_existing_root_replay_is_verified_without_recovery_claim() -> None:
    _require_pyarrow()
    _require_real_controls()
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "etl/data/staging") as temporary:
        temporary_root = Path(temporary)
        package = temporary_root / "verified-real-package"
        manifest = temporary_root / "verified-manifest.json"
        report = temporary_root / "verified-report.json"
        shutil.copytree(CANONICAL_ROOT, package)
        shutil.copy2(CANONICAL_MANIFEST, manifest)
        shutil.copy2(CANONICAL_EXPORT_REPORT, report)
        completed = _run(
            [
                str(EXPORTER),
                "--source-db",
                str(SOURCE_DB),
                "--config",
                str(CONFIG),
                "--pair-plan-db",
                str(PAIR_PLAN_DB),
                "--out-root",
                str(package),
                "--manifest-out",
                str(manifest),
                "--report-out",
                str(report),
            ]
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        replay = json.loads(report.read_text())
        assert replay["status"] == "verified_existing_root_replay"
        assert replay["existing_root_replay_verified"] is True
        assert replay["controls_restored"] is False
        assert replay["recovered_after_interruption"] is False
        assert replay["independent_validation_passed"] is True


@unittest.skipUnless(
    os.environ.get("RUN_REAL_C2B_IDENTITY_E2E") == "1",
    "set RUN_REAL_C2B_IDENTITY_E2E=1 for explicit interruption recovery",
)
def test_real_interruption_marker_is_required_for_recovery_claim() -> None:
    _require_pyarrow()
    _require_real_controls()
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "etl/data/staging") as temporary:
        temporary_root = Path(temporary)
        package = temporary_root / "interrupted-real-package"
        manifest = temporary_root / "interrupted-manifest.json"
        report = temporary_root / "interrupted-report.json"
        shutil.copytree(CANONICAL_ROOT, package)
        shutil.copy2(CANONICAL_MANIFEST, manifest)
        interrupted = load_json(CANONICAL_EXPORT_REPORT)
        interrupted["status"] = "running"
        interrupted["success_manifest_invalidated"] = True
        interrupted["success_report_invalidated"] = True
        report.write_text(
            json.dumps(
                interrupted,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        )
        completed = _run(
            [
                str(EXPORTER),
                "--source-db",
                str(SOURCE_DB),
                "--config",
                str(CONFIG),
                "--pair-plan-db",
                str(PAIR_PLAN_DB),
                "--out-root",
                str(package),
                "--manifest-out",
                str(manifest),
                "--report-out",
                str(report),
            ]
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        recovered = json.loads(report.read_text())
        assert recovered["status"] == "recovered_after_interruption"
        assert recovered["recovered_after_interruption"] is True
        assert recovered["controls_restored"] is True
        assert recovered["existing_root_replay_verified"] is False


@unittest.skipUnless(
    os.environ.get("RUN_REAL_C2B_IDENTITY_E2E") == "1",
    "set RUN_REAL_C2B_IDENTITY_E2E=1 for empty-partition adversary",
)
def test_real_package_manifest_cannot_declare_empty_partition() -> None:
    _require_pyarrow()
    _require_real_controls()
    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "etl/data/staging") as temporary:
        package = Path(temporary) / "real-package-empty-partition-adversary"
        shutil.copytree(CANONICAL_ROOT, package)
        manifest = load_json(package / "manifest.json")
        partition = manifest["tables"]["member_vote_identities"]["partitions"][0]
        partition["rows"] = 0
        partition["files"] = []
        partition["input_sha256"] = hashlib.sha256(b"").hexdigest()
        manifest["manifest_root_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in manifest.items()
                if key != "manifest_root_sha256"
            }
        )
        encoded = (
            json.dumps(
                manifest, ensure_ascii=True, indent=2, sort_keys=True, allow_nan=False
            )
            + "\n"
        )
        (package / "manifest.json").write_text(encoded)
        external = Path(temporary) / "real-adversarial-manifest.json"
        external.write_text(encoded)
        try:
            validate_outcome_pair_identity_companion(
                root=package,
                manifest_path=external,
                source_db_path=SOURCE_DB,
                config_path=CONFIG,
                pair_plan_db_path=PAIR_PLAN_DB,
            )
        except RuntimeError as exc:
            assert "empty member partition" in str(exc)
        else:
            raise AssertionError("empty member partition was accepted")


@unittest.skipUnless(
    os.environ.get("RUN_REAL_C2B_IDENTITY_E2E") == "1",
    "set RUN_REAL_C2B_IDENTITY_E2E=1 for physical replay adversary",
)
def test_real_rows_repacked_with_noncanonical_row_groups_are_rejected() -> None:
    _require_pyarrow()
    _require_real_controls()
    import pyarrow.parquet as pq

    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "etl/data/staging") as temporary:
        package = Path(temporary) / "real-package-physical-replay-adversary"
        shutil.copytree(CANONICAL_ROOT, package)
        manifest = load_json(package / "manifest.json")
        file_meta = manifest["tables"]["member_vote_identities"]["partitions"][0][
            "files"
        ][0]
        parquet_path = package / file_meta["path"]
        original_bytes = file_meta["bytes"]
        real_rows = pq.read_table(parquet_path)
        pq.write_table(
            real_rows,
            parquet_path,
            compression="zstd",
            row_group_size=2_500,
            use_dictionary=True,
            write_statistics=True,
            version="2.6",
        )
        file_meta["bytes"] = parquet_path.stat().st_size
        file_meta["sha256"] = _sha256_file(parquet_path)
        manifest["parquet_bytes"] += file_meta["bytes"] - original_bytes
        manifest["manifest_root_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in manifest.items()
                if key != "manifest_root_sha256"
            }
        )
        encoded = (
            json.dumps(
                manifest, ensure_ascii=True, indent=2, sort_keys=True, allow_nan=False
            )
            + "\n"
        )
        (package / "manifest.json").write_text(encoded)
        external = Path(temporary) / "real-physical-replay-manifest.json"
        external.write_text(encoded)
        try:
            validate_outcome_pair_identity_companion(
                root=package,
                manifest_path=external,
                source_db_path=SOURCE_DB,
                config_path=CONFIG,
                pair_plan_db_path=PAIR_PLAN_DB,
            )
        except RuntimeError as exc:
            assert "row-group count" in str(exc)
        else:
            raise AssertionError("non-canonical physical replay was accepted")


@unittest.skipUnless(
    os.environ.get("RUN_REAL_C2B_IDENTITY_E2E") == "1",
    "set RUN_REAL_C2B_IDENTITY_E2E=1 for writer-options adversary",
)
def test_real_rows_reencoded_with_alternate_writer_options_are_rejected() -> None:
    _require_pyarrow()
    _require_real_controls()
    import pyarrow.parquet as pq

    with tempfile.TemporaryDirectory(dir=REPO_ROOT / "etl/data/staging") as temporary:
        package = Path(temporary) / "real-package-writer-options-adversary"
        shutil.copytree(CANONICAL_ROOT, package)
        manifest = load_json(package / "manifest.json")
        file_meta = manifest["tables"]["member_vote_identities"]["partitions"][0][
            "files"
        ][0]
        parquet_path = package / file_meta["path"]
        alternate_path = parquet_path.with_name(f".{parquet_path.name}.alternate")
        real_rows = pq.read_table(parquet_path, use_threads=False)
        pq.write_table(
            real_rows,
            alternate_path,
            compression="zstd",
            compression_level=9,
            row_group_size=CANONICAL_ROW_GROUP_ROWS,
            use_dictionary=True,
            write_statistics=True,
            version=CANONICAL_PARQUET_FORMAT_VERSION,
            use_byte_stream_split=False,
            data_page_version="2.0",
            use_compliant_nested_type=True,
            write_batch_size=CANONICAL_WRITE_BATCH_SIZE,
            dictionary_pagesize_limit=CANONICAL_DICTIONARY_PAGE_SIZE_LIMIT,
            store_schema=True,
            write_page_index=False,
            write_page_checksum=False,
            store_decimal_as_integer=False,
        )
        original_bytes = int(file_meta["bytes"])
        os.replace(alternate_path, parquet_path)
        file_meta["bytes"] = parquet_path.stat().st_size
        file_meta["sha256"] = _sha256_file(parquet_path)
        manifest["parquet_bytes"] += int(file_meta["bytes"]) - original_bytes
        manifest["manifest_root_sha256"] = canonical_sha256(
            {
                key: value
                for key, value in manifest.items()
                if key != "manifest_root_sha256"
            }
        )
        encoded = (
            json.dumps(
                manifest,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        )
        (package / "manifest.json").write_text(encoded)
        external = Path(temporary) / "real-writer-options-manifest.json"
        external.write_text(encoded)
        try:
            validate_outcome_pair_identity_companion(
                root=package,
                manifest_path=external,
                source_db_path=SOURCE_DB,
                config_path=CONFIG,
                pair_plan_db_path=PAIR_PLAN_DB,
            )
        except RuntimeError as exc:
            assert "exact canonical writer replay" in str(exc)
        else:
            raise AssertionError("alternate Parquet writer options were accepted")


def load_tests(loader, standard_tests, pattern):  # noqa: ANN001
    del loader, standard_tests, pattern
    functions = [
        test_pinned_real_source_has_every_public_identity,
        test_manifest_binds_exact_executed_scans_and_explicit_source_projection,
        test_bound_sqlite_descriptor_is_the_database_actually_queried,
        test_disk_staged_real_stream_is_indexed_and_matches_plan,
        test_resource_numbers_reject_nan_inf_bool_and_enormous_values,
        test_validation_failure_replaces_real_stale_success_control,
        test_export_rejects_alias_to_real_config_without_touching_input,
        test_export_failure_invalidates_copied_real_success_controls,
        test_ancestor_path_failure_invalidates_real_stale_controls_fail_closed,
        test_exact_inventory_rejects_real_package_special_links_and_empty_dirs,
        test_identity_inventory_stops_at_file_and_directory_hard_bounds,
        test_dangling_control_and_package_symlink_aliases_fail_closed,
        test_kernel_lease_blocks_second_process_without_target_path_leak,
        test_cli_nan_and_hard_caps_fail_before_real_package_scan,
        test_canonical_real_package_runs_full_independent_validation_and_dataset_apis,
    ]
    if os.environ.get("RUN_REAL_C2B_IDENTITY_E2E") == "1":
        functions.extend(
            [
                test_full_real_export_and_independent_validation,
                test_real_promoted_package_recovers_missing_external_controls,
                test_real_existing_root_replay_is_verified_without_recovery_claim,
                test_real_interruption_marker_is_required_for_recovery_claim,
                test_real_package_manifest_cannot_declare_empty_partition,
                test_real_rows_repacked_with_noncanonical_row_groups_are_rejected,
                test_real_rows_reencoded_with_alternate_writer_options_are_rejected,
            ]
        )
    suite = unittest.TestSuite()
    for function in functions:
        suite.addTest(unittest.FunctionTestCase(function))
    return suite
