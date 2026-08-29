#!/usr/bin/env python3
"""Package the complete real C2B discovery universe into bounded Parquet."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.outcome_pair_identity_safety import bound_regular_file
from publicdata_publish.outcome_pair_partition_validation import (
    validate_outcome_pair_partitions,
)
from publicdata_publish.outcome_pair_partitions import (
    MAXIMUM_JSON_BYTES,
    export_outcome_pair_partitions,
    outcome_pair_build_lease,
    outcome_pair_lease_path,
    secure_atomic_write_bytes,
    secure_atomic_write_json,
    secure_unlink_control,
)

REPORT_SCHEMA = "outcome_pair_discovery_package_report_v1"


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    secure_atomic_write_json(path, payload)


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    secure_atomic_write_bytes(path, payload)


def repo_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def validate_path_separation(
    *,
    input_files: list[Path],
    previous_root: Path | None,
    output_root: Path,
    manifest_out: Path,
    report_out: Path,
    validation_out: Path,
) -> None:
    inputs = [path.resolve() for path in input_files]
    output_root = output_root.resolve()
    manifest_out = manifest_out.resolve()
    report_out = report_out.resolve()
    validation_out = validation_out.resolve()
    work_root = output_root.parent / f".{output_root.name}.work"
    build_lock = outcome_pair_lease_path(output_root, namespace="build")
    command_lock = outcome_pair_lease_path(output_root, namespace="command")
    manifest_lock = outcome_pair_lease_path(manifest_out, namespace="command")
    report_lock = outcome_pair_lease_path(report_out, namespace="command")
    validation_lock = outcome_pair_lease_path(validation_out, namespace="command")
    outputs = [
        output_root,
        work_root,
        build_lock,
        command_lock,
        manifest_lock,
        report_lock,
        validation_lock,
        manifest_out,
        report_out,
        validation_out,
    ]
    for evidence_output in (manifest_out, report_out, validation_out):
        if evidence_output.exists() or evidence_output.is_symlink():
            output_stat = evidence_output.lstat()
            if (
                evidence_output.is_symlink()
                or not stat.S_ISREG(output_stat.st_mode)
                or output_stat.st_nlink != 1
            ):
                raise ValueError(
                    "manifest, report, and validation outputs must be regular "
                    "single-link files"
                )
    for index, output in enumerate(outputs):
        for other in outputs[index + 1 :]:
            if _is_within(output, other) or _is_within(other, output):
                raise ValueError(
                    "all package, work, lock, manifest, and report targets must be disjoint"
                )
        for immutable in inputs:
            if _is_within(output, immutable) or _is_within(immutable, output):
                raise ValueError("an output path overlaps immutable input evidence")
    if previous_root is not None:
        previous_root = previous_root.resolve()
        for output in outputs:
            if _is_within(output, previous_root) or _is_within(previous_root, output):
                raise ValueError(
                    "output paths must be disjoint from previous package root"
                )


def _validate_validation_invalidation_target(
    *,
    validation_out: Path,
    immutable_inputs: list[Path],
    output_root: Path,
    previous_root: Path | None,
) -> None:
    """Authorize only the first, validation-control invalidation mutation."""

    raw_target = Path(validation_out)
    if raw_target.exists() or raw_target.is_symlink():
        target_stat = raw_target.lstat()
        if (
            raw_target.is_symlink()
            or not stat.S_ISREG(target_stat.st_mode)
            or target_stat.st_nlink != 1
        ):
            raise ValueError("validation control must be a regular single-link file")
    target = raw_target.resolve()
    protected = [path.resolve() for path in immutable_inputs]
    protected.extend(
        [
            output_root.resolve(),
            output_root.resolve().parent / f".{output_root.resolve().name}.work",
        ]
    )
    if previous_root is not None:
        protected.append(previous_root.resolve())
    if any(_is_within(target, path) or _is_within(path, target) for path in protected):
        raise ValueError("validation control overlaps immutable package evidence")


def package_report(
    *,
    manifest: dict[str, Any],
    output_root: Path,
    manifest_out: Path,
    report_out: Path,
    validation_out: Path,
    package_manifest_sha256: str,
    recovered_existing_valid_package: bool,
    independent_validation_passed: bool,
) -> dict[str, Any]:
    status = (
        "recovered_existing_valid_package"
        if recovered_existing_valid_package
        else "materialized_pending_independent_validation"
    )
    return {
        "schema_version": REPORT_SCHEMA,
        "status": status,
        "recovered_existing_valid_package": recovered_existing_valid_package,
        "materialization_gate_passed": manifest["local_package_gate_passed"],
        "independent_validation_passed": independent_validation_passed,
        "promotion_gate_passed": False,
        "policy": manifest["policy"],
        "counts": {
            "pairs": int(manifest["totals"]["rows"]),
            "partitions": int(manifest["totals"]["partitions"]),
            "files": int(manifest["totals"]["files"]),
            "parquet_bytes": int(manifest["totals"]["parquet_bytes"]),
            "identity_companion_member_vote_rows": int(
                manifest["totals"]["identity_companion_member_vote_rows"]
            ),
            "identity_companion_distinct_official_names": int(
                manifest["totals"]["identity_companion_distinct_official_names"]
            ),
            "publication_eligible_rows": 0,
        },
        "roots": {
            "package_manifest_root_sha256": manifest["manifest_root_sha256"],
            "physical_inventory_root_sha256": manifest[
                "physical_inventory_root_sha256"
            ],
            "source_database_sha256": manifest["source"]["database_sha256"],
            "source_manifest_root_sha256": manifest["source"][
                "source_manifest_root_sha256"
            ],
            "source_semantic_root_sha256": manifest["source"][
                "source_semantic_root_sha256"
            ],
            "package_semantic_root_sha256": manifest["semantic_root_sha256"],
            "portable_package_root_sha256": manifest["portable_package_root_sha256"],
            "identity_companion_semantic_root_sha256": manifest["source"][
                "identity_companion_semantic_root_sha256"
            ],
            "package_manifest_sha256": package_manifest_sha256,
        },
        "incremental_contract": manifest["incremental_contract"],
        "checks": manifest["checks"],
        "artifacts": {
            "root": repo_path(output_root),
            "manifest": repo_path(manifest_out),
            "report": repo_path(report_out),
            "validation": repo_path(validation_out),
        },
        "unresolved_gates": {
            "full_l1_candidate_materialization": False,
            "real_human_review": False,
            "durable_remote_origin": False,
            "isolated_remote_restore": False,
            "publication_authorized": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export internal real C2B discovery pairs as bounded Parquet"
    )
    parser.add_argument("--db", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--source-validation", required=True)
    parser.add_argument("--identity-resolver-audit", required=True)
    parser.add_argument("--identity-source-db", required=True)
    parser.add_argument("--identity-config", required=True)
    parser.add_argument("--identity-companion-root", required=True)
    parser.add_argument("--identity-companion-manifest", required=True)
    parser.add_argument("--identity-companion-validation", required=True)
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--validation-out", required=True)
    parser.add_argument("--previous-manifest", default="")
    parser.add_argument("--previous-root", default="")
    parser.add_argument("--compression", default="zstd")
    parser.add_argument("--row-group-rows", type=int, default=25_000)
    parser.add_argument("--max-file-rows", type=int, default=100_000)
    parser.add_argument("--min-rows", type=int, default=1_000_000)
    parser.add_argument("--max-peak-rss-mb", type=float, default=1024.0)
    parser.add_argument(
        "--interrupt-after-new-partitions",
        type=int,
        default=None,
        help=(
            "Adversarial restart probe: fail immediately after this many newly "
            "checkpointed real partitions"
        ),
    )
    return parser.parse_args()


def _main_unlocked(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    source_manifest_path = Path(args.source_manifest)
    source_validation_path = Path(args.source_validation)
    identity_resolver_audit_path = Path(args.identity_resolver_audit)
    identity_source_db_path = Path(args.identity_source_db)
    identity_config_path = Path(args.identity_config)
    identity_companion_root = Path(args.identity_companion_root)
    identity_companion_manifest_path = Path(args.identity_companion_manifest)
    identity_companion_validation_path = Path(args.identity_companion_validation)
    output_root = Path(args.out_root)
    manifest_out = Path(args.manifest_out)
    report_out = Path(args.report_out)
    validation_out = Path(args.validation_out)
    previous_manifest = Path(args.previous_manifest) if args.previous_manifest else None
    previous_root = Path(args.previous_root) if args.previous_root else None
    immutable_inputs = [
        db_path,
        source_manifest_path,
        source_validation_path,
        identity_resolver_audit_path,
        identity_source_db_path,
        identity_config_path,
        identity_companion_root,
        identity_companion_manifest_path,
        identity_companion_validation_path,
        *([previous_manifest] if previous_manifest is not None else []),
    ]
    try:
        # Validation is the authoritative success control.  Invalidate it first,
        # before any fallible full-path check or report/manifest mutation.
        _validate_validation_invalidation_target(
            validation_out=validation_out,
            immutable_inputs=immutable_inputs,
            output_root=output_root,
            previous_root=previous_root,
        )
        secure_unlink_control(validation_out)
        atomic_write_json(
            validation_out,
            {
                "schema_version": ("outcome_pair_discovery_partition_validation_v1"),
                "status": "invalidated_by_materialization_attempt",
                "success_report_invalidated": True,
                "promotion_gate_passed": False,
            },
        )
        validate_path_separation(
            input_files=immutable_inputs,
            previous_root=previous_root,
            output_root=output_root,
            manifest_out=manifest_out,
            report_out=report_out,
            validation_out=validation_out,
        )
        secure_unlink_control(manifest_out)
        secure_unlink_control(report_out)
        atomic_write_json(
            report_out,
            {
                "schema_version": REPORT_SCHEMA,
                "status": "running",
                "success_manifest_invalidated": True,
                "independent_validation_passed": False,
                "promotion_gate_passed": False,
            },
        )
        root_manifest = output_root / "manifest.json"
        recovered = output_root.exists() or output_root.is_symlink()
        if recovered:
            if output_root.is_symlink() or not output_root.is_dir():
                raise ValueError("existing package root is not a real directory")
            atomic_write_json(
                validation_out,
                {
                    "schema_version": (
                        "outcome_pair_discovery_partition_validation_v1"
                    ),
                    "status": "running_existing_package_recovery_validation",
                    "success_report_invalidated": True,
                    "promotion_gate_passed": False,
                },
            )
            validation = validate_outcome_pair_partitions(
                root=output_root,
                manifest_path=root_manifest,
                source_db_path=db_path,
                source_manifest_path=source_manifest_path,
                source_validation_path=source_validation_path,
                identity_source_db_path=identity_source_db_path,
                identity_config_path=identity_config_path,
                batch_rows=5_000,
                min_rows=int(args.min_rows),
                max_peak_rss_mb=float(args.max_peak_rss_mb),
                require_source_parity=True,
            )
            atomic_write_json(validation_out, validation)
            if validation["status"] != "ok" or not all(validation["checks"].values()):
                raise RuntimeError("existing package failed full recovery validation")
            with bound_regular_file(root_manifest) as bound_manifest:
                root_manifest_bytes = bound_manifest.read_bytes(
                    max_bytes=MAXIMUM_JSON_BYTES
                )
                root_manifest_sha256 = hashlib.sha256(root_manifest_bytes).hexdigest()
            if root_manifest_sha256 != validation["manifest_sha256"]:
                raise RuntimeError("root manifest changed after recovery validation")
            manifest = json.loads(root_manifest_bytes.decode("utf-8"))
            if not isinstance(manifest, dict):
                raise TypeError("root manifest must be a JSON object")
            atomic_write_bytes(manifest_out, root_manifest_bytes)
            independent_validation_passed = True
        else:
            manifest = export_outcome_pair_partitions(
                db_path=db_path,
                source_manifest_path=source_manifest_path,
                source_validation_path=source_validation_path,
                identity_resolver_audit_path=identity_resolver_audit_path,
                identity_source_db_path=identity_source_db_path,
                identity_config_path=identity_config_path,
                identity_companion_root=identity_companion_root,
                identity_companion_manifest_path=identity_companion_manifest_path,
                identity_companion_validation_path=(identity_companion_validation_path),
                output_root=output_root,
                compression=str(args.compression),
                row_group_rows=int(args.row_group_rows),
                max_file_rows=int(args.max_file_rows),
                previous_manifest_path=previous_manifest,
                previous_root=previous_root,
                min_rows=int(args.min_rows),
                max_peak_rss_mb=float(args.max_peak_rss_mb),
                interrupt_after_new_partitions=args.interrupt_after_new_partitions,
            )
            with bound_regular_file(root_manifest) as bound_manifest:
                root_manifest_bytes = bound_manifest.read_bytes(
                    max_bytes=MAXIMUM_JSON_BYTES
                )
                root_manifest_sha256 = hashlib.sha256(root_manifest_bytes).hexdigest()
            normalized_manifest = json.loads(
                json.dumps(
                    manifest,
                    allow_nan=False,
                    ensure_ascii=True,
                    sort_keys=True,
                )
            )
            if json.loads(root_manifest_bytes.decode("utf-8")) != normalized_manifest:
                raise RuntimeError("materialized root manifest differs from producer")
            atomic_write_bytes(manifest_out, root_manifest_bytes)
            independent_validation_passed = False
        if manifest_out.read_bytes() != root_manifest_bytes:
            raise RuntimeError("external manifest is not byte-exact with package root")
        report = package_report(
            manifest=manifest,
            output_root=output_root,
            manifest_out=manifest_out,
            report_out=report_out,
            validation_out=validation_out,
            package_manifest_sha256=root_manifest_sha256,
            recovered_existing_valid_package=recovered,
            independent_validation_passed=independent_validation_passed,
        )
        atomic_write_json(report_out, report)
        with bound_regular_file(root_manifest) as final_manifest:
            final_manifest_sha256 = final_manifest.sha256()
        if final_manifest_sha256 != report["roots"]["package_manifest_sha256"]:
            raise RuntimeError("package manifest changed while controls were finalized")
    except Exception as exc:  # noqa: BLE001 - CLI boundary must persist fail-closed status
        try:
            secure_unlink_control(manifest_out)
        except Exception:
            pass
        try:
            secure_unlink_control(validation_out)
            atomic_write_json(
                validation_out,
                {
                    "schema_version": (
                        "outcome_pair_discovery_partition_validation_v1"
                    ),
                    "status": "failed",
                    "error_code": (
                        "outcome_pair_discovery_validation_invalidated_fail_closed"
                    ),
                    "error_type": type(exc).__name__,
                    "success_report_invalidated": True,
                    "promotion_gate_passed": False,
                },
            )
        except Exception:
            pass
        try:
            secure_unlink_control(report_out)
            atomic_write_json(
                report_out,
                {
                    "schema_version": REPORT_SCHEMA,
                    "status": "failed",
                    "error_code": ("outcome_pair_discovery_package_failed_fail_closed"),
                    "error_type": type(exc).__name__,
                    "success_manifest_invalidated": True,
                    "publication_eligible_rows": 0,
                },
            )
        except Exception:
            pass
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            report,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    args = parse_args()
    mutation_targets = {
        Path(args.out_root).resolve(),
        Path(args.manifest_out).resolve(),
        Path(args.report_out).resolve(),
        Path(args.validation_out).resolve(),
    }
    with ExitStack() as leases:
        for target in sorted(mutation_targets, key=lambda path: path.as_posix()):
            leases.enter_context(outcome_pair_build_lease(target, namespace="command"))
        return _main_unlocked(args)


if __name__ == "__main__":
    raise SystemExit(main())
