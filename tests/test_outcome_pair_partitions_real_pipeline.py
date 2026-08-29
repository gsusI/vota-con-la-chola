from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from publicdata_publish.outcome_pair_partition_validation import (
    _complete_file_inventory,
    _next_or_none,
    _validate_pair_parquet_decode_metadata,
    validate_outcome_pair_partitions,
)
from publicdata_publish.outcome_pair_partitions import (
    EXPECTED_IDENTITY_RESOLVER_AUDIT_SHA256,
    EXPECTED_SOURCE_CONTRACT_DATE,
    EXPECTED_SOURCE_DATABASE_SHA256,
    EXPECTED_SOURCE_SEMANTIC_ROOT_SHA256,
    MAXIMUM_JSON_BYTES,
    MAXIMUM_PACKAGE_DEPTH,
    MAXIMUM_PACKAGE_DIRECTORIES,
    MAXIMUM_PACKAGE_FILES,
    MAXIMUM_PACKAGE_PATH_BYTES,
    MINIMUM_REAL_PAIR_ROWS,
    _canonical_sha256,
    _enforce_pair_batch_bounds,
    _enforce_pair_parquet_metadata_bounds,
    _load_build_checkpoints,
    export_outcome_pair_partitions,
    iter_public_pair_rows,
    load_identity_resolver_audit,
    outcome_pair_build_lease,
    outcome_pair_lease_path,
    partition_dir,
    partition_id,
    partition_key,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_DB = REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1.db"
PLAN_MANIFEST = (
    REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1-manifest.json"
)
PLAN_VALIDATION = (
    REPO_ROOT / "etl/data/staging/outcome-context-pair-plan-c2b-v1-validation.json"
)
IDENTITY_AUDIT = (
    REPO_ROOT / "docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence/"
    "outcome-pair-identity-resolver-audit-v1.json"
)
IDENTITY_SOURCE_DB = REPO_ROOT / "etl/data/staging/politicos-es.db"
IDENTITY_CONFIG = REPO_ROOT / "etl/data/manual/outcome_links/planner_scope_c2b_v1.json"
IDENTITY_ROOT = REPO_ROOT / "etl/data/derived/outcome-pair-identity-companion-c2b-v1"
IDENTITY_MANIFEST = (
    REPO_ROOT / "etl/data/staging/outcome-pair-identity-companion-c2b-v1-manifest.json"
)
IDENTITY_VALIDATION = (
    REPO_ROOT
    / "etl/data/staging/outcome-pair-identity-companion-c2b-v1-validation.json"
)
PAIR_ROOT = REPO_ROOT / "etl/data/derived/outcome-pair-discovery-c2b-v1"
EVIDENCE_ROOT = REPO_ROOT / "docs/etl/sprints/OUTCOME-CONTEXT-20260820/evidence"
PAIR_MANIFEST = EVIDENCE_ROOT / "outcome-pair-discovery-c2b-v1-manifest.json"
PAIR_REPORT = EVIDENCE_ROOT / "outcome-pair-discovery-c2b-v1-report.json"
PAIR_VALIDATION = EVIDENCE_ROOT / "outcome-pair-discovery-c2b-v1-validation.json"
PAIR_REPLAY_ROOT = REPO_ROOT / "etl/data/derived/outcome-pair-discovery-c2b-v1-replay"
PAIR_REPLAY_MANIFEST = (
    REPO_ROOT / "etl/data/staging/outcome-pair-discovery-c2b-v1-replay-manifest.json"
)
PAIR_REPLAY_VALIDATION = (
    EVIDENCE_ROOT / "outcome-pair-discovery-c2b-v1-replay-validation.json"
)
EXPORTER = REPO_ROOT / "scripts/export_outcome_pair_partitions.py"
VALIDATOR = REPO_ROOT / "scripts/validate_outcome_pair_partitions.py"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def physical_parquet_inventory(root: Path) -> dict[str, tuple[int, str]]:
    inventory: dict[str, tuple[int, str]] = {}
    for path in sorted(root.rglob("*.parquet")):
        relative = path.relative_to(root).as_posix()
        path_stat = path.lstat()
        assert not path.is_symlink()
        assert path_stat.st_nlink == 1
        inventory[relative] = (int(path_stat.st_size), sha256_file(path))
    return inventory


def export_arguments(output_root: Path) -> dict[str, object]:
    return {
        "db_path": PLAN_DB,
        "source_manifest_path": PLAN_MANIFEST,
        "source_validation_path": PLAN_VALIDATION,
        "identity_resolver_audit_path": IDENTITY_AUDIT,
        "identity_source_db_path": IDENTITY_SOURCE_DB,
        "identity_config_path": IDENTITY_CONFIG,
        "identity_companion_root": IDENTITY_ROOT,
        "identity_companion_manifest_path": IDENTITY_MANIFEST,
        "identity_companion_validation_path": IDENTITY_VALIDATION,
        "output_root": output_root,
    }


def test_canonical_portable_real_pair_package_contract(tmp_path: Path) -> None:
    manifest = json.loads(PAIR_MANIFEST.read_text(encoding="utf-8"))
    report = json.loads(PAIR_REPORT.read_text(encoding="utf-8"))
    validation = json.loads(PAIR_VALIDATION.read_text(encoding="utf-8"))
    replay_validation = json.loads(PAIR_REPLAY_VALIDATION.read_text(encoding="utf-8"))
    replay_manifest = json.loads(PAIR_REPLAY_MANIFEST.read_text(encoding="utf-8"))

    assert (PAIR_ROOT / "manifest.json").read_bytes() == PAIR_MANIFEST.read_bytes()
    assert (
        PAIR_REPLAY_ROOT / "manifest.json"
    ).read_bytes() == PAIR_REPLAY_MANIFEST.read_bytes()
    assert manifest["manifest_root_sha256"] == _canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_root_sha256"}
    )
    assert replay_manifest["manifest_root_sha256"] == _canonical_sha256(
        {
            key: value
            for key, value in replay_manifest.items()
            if key != "manifest_root_sha256"
        }
    )
    assert manifest["source"]["database_sha256"] == EXPECTED_SOURCE_DATABASE_SHA256
    assert (
        manifest["source"]["source_semantic_root_sha256"]
        == EXPECTED_SOURCE_SEMANTIC_ROOT_SHA256
    )
    assert manifest["totals"]["rows"] == 2_865_602
    assert manifest["totals"]["partitions"] == 1_205
    assert manifest["totals"]["pair_files"] == 1_205
    assert manifest["totals"]["identity_companion_files"] == 8
    assert manifest["totals"]["files"] == 1_213
    assert manifest["totals"]["identity_companion_member_vote_rows"] == 119_116
    assert manifest["totals"]["identity_companion_distinct_official_names"] == 490
    assert manifest["totals"]["identity_companion_actions"] == 458
    assert manifest["identity_lineage"]["portable_exact_source_identity_dimension"]
    assert manifest["identity_lineage"]["exact_source_participant_projection_bundled"]
    assert manifest["identity_lineage"]["durable_remote_identity_origin"] is False
    assert manifest["policy"]["official_public_domain_personal_information_retained"]
    assert manifest["policy"]["synthetic_or_mock_records_forbidden"]
    assert manifest["local_package_gate_passed"]
    assert manifest["independent_validation_passed"] is False
    assert manifest["promotion_gate_passed"] is False
    assert manifest["promotion_checks"]["real_human_review"] is False
    assert manifest["promotion_checks"]["publication_authorized"] is False
    assert manifest["restart_contract"]["resumed_build"]
    assert manifest["restart_contract"]["partitions_recovered_from_checkpoints"] >= 1
    assert report["status"] in {
        "materialized_pending_independent_validation",
        "recovered_existing_valid_package",
    }
    assert report["recovered_existing_valid_package"] is (
        report["status"] == "recovered_existing_valid_package"
    )
    assert report["independent_validation_passed"] is (
        report["status"] == "recovered_existing_valid_package"
    )
    assert validation["status"] == "ok"
    assert validation["local_package_gate_passed"]
    assert all(validation["checks"].values())
    assert replay_validation["status"] == "ok"
    assert all(replay_validation["checks"].values())
    assert (
        validation["roots"]["portable_package_root_sha256"]
        == manifest["portable_package_root_sha256"]
        == replay_validation["roots"]["portable_package_root_sha256"]
    )
    canonical_physical = physical_parquet_inventory(PAIR_ROOT)
    replay_physical = physical_parquet_inventory(PAIR_REPLAY_ROOT)
    assert len(canonical_physical) == 1_213
    assert replay_physical == canonical_physical
    physical_entries = [
        {"path": path, "bytes": fact[0], "sha256": fact[1]}
        for path, fact in sorted(canonical_physical.items())
    ]
    assert (
        _canonical_sha256(physical_entries)
        == manifest["physical_inventory_root_sha256"]
        == replay_manifest["physical_inventory_root_sha256"]
        == validation["roots"]["physical_inventory_root_sha256"]
        == replay_validation["roots"]["physical_inventory_root_sha256"]
    )

    package_before = PAIR_ROOT.stat()
    package_manifest_before = sha256_file(PAIR_ROOT / "manifest.json")
    recovered_manifest = tmp_path / "recovered-manifest.json"
    recovered_report = tmp_path / "recovered-report.json"
    recovered_validation = tmp_path / "recovered-validation.json"
    recovered = subprocess.run(
        [
            sys.executable,
            str(EXPORTER),
            "--db",
            str(PLAN_DB),
            "--source-manifest",
            str(PLAN_MANIFEST),
            "--source-validation",
            str(PLAN_VALIDATION),
            "--identity-resolver-audit",
            str(IDENTITY_AUDIT),
            "--identity-source-db",
            str(IDENTITY_SOURCE_DB),
            "--identity-config",
            str(IDENTITY_CONFIG),
            "--identity-companion-root",
            str(IDENTITY_ROOT),
            "--identity-companion-manifest",
            str(IDENTITY_MANIFEST),
            "--identity-companion-validation",
            str(IDENTITY_VALIDATION),
            "--out-root",
            str(PAIR_ROOT),
            "--manifest-out",
            str(recovered_manifest),
            "--report-out",
            str(recovered_report),
            "--validation-out",
            str(recovered_validation),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert recovered.returncode == 0, recovered.stderr
    assert json.loads(recovered_report.read_text(encoding="utf-8"))[
        "recovered_existing_valid_package"
    ]
    assert (
        json.loads(recovered_validation.read_text(encoding="utf-8"))["status"] == "ok"
    )
    assert recovered_manifest.read_bytes() == (PAIR_ROOT / "manifest.json").read_bytes()
    package_after = PAIR_ROOT.stat()
    assert (
        package_after.st_dev,
        package_after.st_ino,
        package_after.st_size,
        package_after.st_mtime_ns,
    ) == (
        package_before.st_dev,
        package_before.st_ino,
        package_before.st_size,
        package_before.st_mtime_ns,
    )
    assert sha256_file(PAIR_ROOT / "manifest.json") == package_manifest_before

    import pyarrow.dataset as ds

    pair_dataset = ds.dataset(
        PAIR_ROOT / manifest["datasets"]["pairs"]["path"],
        format="parquet",
        partitioning="hive",
    )
    member_dataset = ds.dataset(
        PAIR_ROOT / manifest["datasets"]["identity_member_votes"]["path"],
        format="parquet",
    )
    action_dataset = ds.dataset(
        PAIR_ROOT
        / manifest["datasets"]["identity_action_participant_projections"]["path"],
        format="parquet",
    )
    assert pair_dataset.count_rows() == 2_865_602
    assert member_dataset.count_rows() == 119_116
    assert action_dataset.count_rows() == 458
    action = action_dataset.head(1).to_pylist()[0]
    action_id = action["action_id"]
    assert pair_dataset.count_rows(filter=ds.field("action_id") == action_id) > 0
    assert member_dataset.count_rows(filter=ds.field("action_id") == action_id) == int(
        action["member_vote_count"]
    )


def test_exact_source_iterator_advances_real_rows() -> None:
    rows = iter_public_pair_rows(
        PLAN_DB,
        pipeline_key=("vclc:outcome-pair-plan-c2b-pipeline:294c93befa7e73b46c84355d"),
    )
    first = _next_or_none(rows)
    second = _next_or_none(rows)
    assert first is not None
    assert second is not None
    assert first["pair_plan_id"] != second["pair_plan_id"]
    assert first["source_id"] == second["source_id"] == "senado_votaciones"


def test_identity_audit_exact_checksum_rejects_mutated_real_copy(
    tmp_path: Path,
) -> None:
    assert sha256_file(IDENTITY_AUDIT) == EXPECTED_IDENTITY_RESOLVER_AUDIT_SHA256
    changed = tmp_path / IDENTITY_AUDIT.name
    payload = json.loads(IDENTITY_AUDIT.read_text(encoding="utf-8"))
    payload["status"] = "failed"
    changed.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="checksum differs"):
        load_identity_resolver_audit(changed)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"min_rows": MINIMUM_REAL_PAIR_ROWS - 1}, "minimum real-row gate"),
        ({"max_peak_rss_mb": float("inf")}, "hard scale resource contract"),
        ({"max_peak_rss_mb": float("nan")}, "hard scale resource contract"),
        ({"row_group_rows": 1}, "canonical scale contract"),
        ({"max_file_rows": 1}, "canonical scale contract"),
    ],
)
def test_hard_resource_contract_rejects_invalid_limits_before_scan(
    tmp_path: Path, overrides: dict[str, object], message: str
) -> None:
    arguments = export_arguments(tmp_path / "invalid-resource-output")
    arguments.update(overrides)
    with pytest.raises(ValueError, match=message):
        export_outcome_pair_partitions(**arguments)


def test_resume_preflight_rejects_symlink_before_source_scan(tmp_path: Path) -> None:
    output_root = tmp_path / "pair-package"
    work_root = tmp_path / ".pair-package.work"
    outside = tmp_path / "outside"
    outside.mkdir()
    work_root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="work root must not be a symlink"):
        export_outcome_pair_partitions(**export_arguments(output_root))
    assert list(outside.iterdir()) == []


def test_resume_before_first_checkpoint_removes_real_orphan_parquet(
    tmp_path: Path,
) -> None:
    real_parquet = next(iter(sorted(IDENTITY_ROOT.rglob("*.parquet"))), None)
    assert real_parquet is not None
    real_rows = iter_public_pair_rows(PLAN_DB)
    try:
        real_partition_key = partition_key(next(real_rows))
    finally:
        real_rows.close()
    real_partition_id = partition_id(real_partition_key)
    real_relative_dir = partition_dir(
        EXPECTED_SOURCE_CONTRACT_DATE, real_partition_key
    ).as_posix()
    staging_root = tmp_path / ".pair-package.work"
    orphan = staging_root / real_relative_dir / "part-00000.parquet"
    orphan.parent.mkdir(parents=True)
    shutil.copy2(real_parquet, orphan)
    assert sha256_file(orphan) == sha256_file(real_parquet)
    assert not (staging_root / ".checkpoints").exists()

    completed = _load_build_checkpoints(
        staging_root=staging_root,
        descriptor_sha256=None,
        partition_by_id={
            real_partition_id: {
                "partition_id": real_partition_id,
                "relative_dir": real_relative_dir,
            }
        },
        non_partition_paths=set(),
    )

    assert completed == {}
    assert not orphan.exists()


def test_source_manifest_noncanonical_basename_rejected_before_pair_scan(
    tmp_path: Path,
) -> None:
    renamed = tmp_path / "renamed-real-source-manifest.json"
    shutil.copy2(PLAN_MANIFEST, renamed)
    with pytest.raises(ValueError, match="canonical basenames"):
        export_outcome_pair_partitions(
            **{
                **export_arguments(tmp_path / "must-not-materialize"),
                "source_manifest_path": renamed,
            }
        )
    assert not (tmp_path / "must-not-materialize").exists()


def test_oversized_real_manifest_copy_rejected_before_validation_scan(
    tmp_path: Path,
) -> None:
    oversized = tmp_path / PAIR_MANIFEST.name
    real_bytes = PAIR_MANIFEST.read_bytes()
    oversized.write_bytes(
        real_bytes + (b" " * (MAXIMUM_JSON_BYTES - len(real_bytes) + 1))
    )
    with pytest.raises(ValueError, match="byte contract"):
        validate_outcome_pair_partitions(
            root=PAIR_ROOT,
            manifest_path=oversized,
            source_db_path=PLAN_DB,
            source_manifest_path=PLAN_MANIFEST,
            source_validation_path=PLAN_VALIDATION,
            identity_source_db_path=IDENTITY_SOURCE_DB,
            identity_config_path=IDENTITY_CONFIG,
            require_source_parity=True,
        )


def test_exact_inventory_observes_undeclared_empty_directory_from_real_copy(
    tmp_path: Path,
) -> None:
    package = tmp_path / "real-control-inventory"
    control = package / "control" / IDENTITY_AUDIT.name
    control.parent.mkdir(parents=True)
    shutil.copy2(IDENTITY_AUDIT, control)
    files_before, directories_before, unsafe_before = _complete_file_inventory(package)
    assert not unsafe_before
    assert files_before == {f"control/{IDENTITY_AUDIT.name}"}
    assert directories_before == {"control"}
    (package / "undeclared-empty-directory").mkdir()
    files_after, directories_after, unsafe_after = _complete_file_inventory(package)
    assert not unsafe_after
    assert files_after == files_before
    assert directories_after == {"control", "undeclared-empty-directory"}


def test_streaming_inventory_rejects_attacker_scale_before_collection_growth(
    tmp_path: Path,
) -> None:
    package = tmp_path / "bounded-inventory"
    package.mkdir()
    for index in range(MAXIMUM_PACKAGE_DIRECTORIES + 1):
        (package / f"directory-{index:04d}").mkdir()
    with pytest.raises(ValueError, match="directory inventory exceeds"):
        _complete_file_inventory(
            package,
            max_files=MAXIMUM_PACKAGE_FILES,
            max_directories=MAXIMUM_PACKAGE_DIRECTORIES,
            max_depth=MAXIMUM_PACKAGE_DEPTH,
            max_path_bytes=MAXIMUM_PACKAGE_PATH_BYTES,
        )


def test_streaming_inventory_rejects_path_depth_before_scan_growth(
    tmp_path: Path,
) -> None:
    package = tmp_path / "bounded-depth"
    current = package
    for index in range(MAXIMUM_PACKAGE_DEPTH + 1):
        current = current / f"level-{index:02d}"
    current.mkdir(parents=True)
    with pytest.raises(ValueError, match="depth or byte bound"):
        _complete_file_inventory(
            package,
            max_files=MAXIMUM_PACKAGE_FILES,
            max_directories=MAXIMUM_PACKAGE_DIRECTORIES,
            max_depth=MAXIMUM_PACKAGE_DEPTH,
            max_path_bytes=MAXIMUM_PACKAGE_PATH_BYTES,
        )


def test_real_pair_parquet_decode_bounds_are_preventive() -> None:
    import pyarrow.parquet as pq

    real_pair_file = next(
        iter(sorted((PAIR_ROOT / "lane=outcome_pair_discovery").rglob("*.parquet")))
    )
    parquet_file = pq.ParquetFile(real_pair_file)
    observed_row_group, observed_column = _validate_pair_parquet_decode_metadata(
        parquet_file.metadata
    )
    assert observed_row_group > 0
    assert observed_column > 0
    _enforce_pair_parquet_metadata_bounds(parquet_file.metadata)
    with pytest.raises(ValueError, match="row group exceeds"):
        _enforce_pair_parquet_metadata_bounds(
            parquet_file.metadata,
            max_row_group_uncompressed_bytes=observed_row_group - 1,
        )
    batch = next(parquet_file.iter_batches(batch_size=5_000, use_threads=False))
    _enforce_pair_batch_bounds(batch)
    assert batch.nbytes > 1
    with pytest.raises(ValueError, match="record batch exceeds"):
        _enforce_pair_batch_bounds(
            batch,
            max_batch_bytes=int(batch.nbytes) - 1,
        )


def test_export_failure_invalidates_copied_real_validation_success(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "must-not-materialize"
    manifest_out = tmp_path / "manifest.json"
    report_out = tmp_path / "report.json"
    validation_out = tmp_path / "validation.json"
    shutil.copy2(PAIR_VALIDATION, validation_out)
    completed = subprocess.run(
        [
            sys.executable,
            str(EXPORTER),
            "--db",
            str(PLAN_DB),
            "--source-manifest",
            str(PLAN_MANIFEST),
            "--source-validation",
            str(PLAN_VALIDATION),
            "--identity-resolver-audit",
            str(IDENTITY_AUDIT),
            "--identity-source-db",
            str(IDENTITY_SOURCE_DB),
            "--identity-config",
            str(IDENTITY_CONFIG),
            "--identity-companion-root",
            str(IDENTITY_ROOT),
            "--identity-companion-manifest",
            str(IDENTITY_MANIFEST),
            "--identity-companion-validation",
            str(IDENTITY_VALIDATION),
            "--out-root",
            str(output_root),
            "--manifest-out",
            str(manifest_out),
            "--report-out",
            str(report_out),
            "--validation-out",
            str(validation_out),
            "--row-group-rows",
            "1",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert not output_root.exists()
    assert not manifest_out.exists()
    failed_validation = json.loads(validation_out.read_text(encoding="utf-8"))
    assert failed_validation["status"] == "failed"
    assert failed_validation["success_report_invalidated"] is True


def test_export_early_report_path_failure_cannot_leave_stale_validation_success(
    tmp_path: Path,
) -> None:
    validation_out = tmp_path / "validation.json"
    manifest_out = tmp_path / "manifest.json"
    invalid_report_parent = tmp_path / "report-parent.json"
    shutil.copy2(PAIR_VALIDATION, validation_out)
    shutil.copy2(PAIR_MANIFEST, manifest_out)
    shutil.copy2(PAIR_REPORT, invalid_report_parent)
    stale_validation_sha256 = sha256_file(validation_out)
    completed = subprocess.run(
        [
            sys.executable,
            str(EXPORTER),
            "--db",
            str(PLAN_DB),
            "--source-manifest",
            str(PLAN_MANIFEST),
            "--source-validation",
            str(PLAN_VALIDATION),
            "--identity-resolver-audit",
            str(IDENTITY_AUDIT),
            "--identity-source-db",
            str(IDENTITY_SOURCE_DB),
            "--identity-config",
            str(IDENTITY_CONFIG),
            "--identity-companion-root",
            str(IDENTITY_ROOT),
            "--identity-companion-manifest",
            str(IDENTITY_MANIFEST),
            "--identity-companion-validation",
            str(IDENTITY_VALIDATION),
            "--out-root",
            str(tmp_path / "must-not-materialize"),
            "--manifest-out",
            str(manifest_out),
            "--report-out",
            str(invalid_report_parent / "report.json"),
            "--validation-out",
            str(validation_out),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert not manifest_out.exists()
    assert sha256_file(validation_out) != stale_validation_sha256
    assert json.loads(validation_out.read_text(encoding="utf-8"))["status"] == "failed"


def test_canonical_basename_source_database_symlink_is_rejected(
    tmp_path: Path,
) -> None:
    linked_database = tmp_path / PLAN_DB.name
    linked_database.symlink_to(PLAN_DB)
    with pytest.raises(RuntimeError, match="path is a symlink"):
        export_outcome_pair_partitions(
            **{
                **export_arguments(tmp_path / "must-not-materialize"),
                "db_path": linked_database,
            }
        )
    assert not (tmp_path / "must-not-materialize").exists()


def test_validation_control_hardlink_is_rejected_without_mutating_real_copy(
    tmp_path: Path,
) -> None:
    protected_copy = tmp_path / "protected-validation.json"
    shutil.copy2(PAIR_VALIDATION, protected_copy)
    before = sha256_file(protected_copy)
    validation_out = tmp_path / "linked-validation.json"
    os.link(protected_copy, validation_out)
    completed = subprocess.run(
        [
            sys.executable,
            str(EXPORTER),
            "--db",
            str(PLAN_DB),
            "--source-manifest",
            str(PLAN_MANIFEST),
            "--source-validation",
            str(PLAN_VALIDATION),
            "--identity-resolver-audit",
            str(IDENTITY_AUDIT),
            "--identity-source-db",
            str(IDENTITY_SOURCE_DB),
            "--identity-config",
            str(IDENTITY_CONFIG),
            "--identity-companion-root",
            str(IDENTITY_ROOT),
            "--identity-companion-manifest",
            str(IDENTITY_MANIFEST),
            "--identity-companion-validation",
            str(IDENTITY_VALIDATION),
            "--out-root",
            str(tmp_path / "must-not-materialize"),
            "--manifest-out",
            str(tmp_path / "manifest.json"),
            "--report-out",
            str(tmp_path / "report.json"),
            "--validation-out",
            str(validation_out),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert sha256_file(protected_copy) == before
    assert protected_copy.lstat().st_nlink == 1
    assert validation_out.lstat().st_nlink == 1
    assert sha256_file(validation_out) != before
    assert json.loads(validation_out.read_text(encoding="utf-8"))["status"] == "failed"


def test_validator_early_missing_root_cannot_leave_stale_success(
    tmp_path: Path,
) -> None:
    report_out = tmp_path / "validation.json"
    shutil.copy2(PAIR_VALIDATION, report_out)
    stale_sha256 = sha256_file(report_out)
    completed = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--root",
            str(tmp_path / "missing-package"),
            "--source-db",
            str(PLAN_DB),
            "--source-manifest",
            str(PLAN_MANIFEST),
            "--source-validation",
            str(PLAN_VALIDATION),
            "--identity-source-db",
            str(IDENTITY_SOURCE_DB),
            "--identity-config",
            str(IDENTITY_CONFIG),
            "--report-out",
            str(report_out),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode != 0
    assert sha256_file(report_out) != stale_sha256
    failed = json.loads(report_out.read_text(encoding="utf-8"))
    assert failed["status"] == "failed"
    assert failed["success_report_invalidated"] is True


def test_writer_lease_rejects_second_process_and_recovers(tmp_path: Path) -> None:
    target = tmp_path / "lease-target"
    script = (
        "from pathlib import Path; "
        "from publicdata_publish.outcome_pair_partitions import outcome_pair_build_lease; "
        f"target=Path({str(target)!r}); "
        "lease=outcome_pair_build_lease(target); lease.__enter__()"
    )
    with outcome_pair_build_lease(target):
        contender = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    assert contender.returncode != 0
    assert "holds the build lease" in contender.stderr
    with outcome_pair_build_lease(target):
        pass


def test_writer_lease_rejects_hardlink_without_truncating_real_copy(
    tmp_path: Path,
) -> None:
    target = tmp_path / "hardlink-target"
    lock_path = outcome_pair_lease_path(target, namespace="build")
    lock_path.unlink(missing_ok=True)
    real_copy = lock_path.with_name(f"{lock_path.name}.protected-real-copy")
    real_copy.unlink(missing_ok=True)
    shutil.copy2(IDENTITY_AUDIT, real_copy)
    before = sha256_file(real_copy)
    os.link(real_copy, lock_path)
    try:
        with (
            pytest.raises(RuntimeError, match="lease inode is unsafe"),
            outcome_pair_build_lease(target),
        ):
            pass
        assert sha256_file(real_copy) == before
    finally:
        lock_path.unlink(missing_ok=True)
        real_copy.unlink(missing_ok=True)
