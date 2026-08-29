#!/usr/bin/env python3
"""Export exact real C2B Senate participant identities as bounded Parquet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.outcome_pair_identity_companion import (
    CANONICAL_COMPRESSION,
    CANONICAL_MAX_FILE_ROWS,
    CANONICAL_ROW_GROUP_ROWS,
    CANONICAL_SOURCE_PAGE_SIZE,
    DEFAULT_CONFIG,
    DEFAULT_PAIR_PLAN_DB,
    DEFAULT_SOURCE_DB,
    MAXIMUM_PEAK_RSS_MB,
    export_outcome_pair_identity_companion,
    load_json_bytes,
    repo_path,
)
from publicdata_publish.outcome_pair_identity_companion_validation import (
    validate_outcome_pair_identity_companion,
)
from publicdata_publish.outcome_pair_identity_safety import (
    bound_regular_file,
    identity_companion_leases,
    paths_overlap,
    preflight_control_target,
    preflight_output_root,
    secure_atomic_write_bytes,
    secure_atomic_write_json,
    secure_unlink_regular,
)
from publicdata_publish.semantic_contracts import peak_rss_mb

REPORT_SCHEMA_VERSION = "outcome_pair_identity_companion_export_report_v1"
SUCCESS_REPORT_STATUSES = {
    "materialized_pending_independent_validation",
    "verified_existing_root_replay",
    "verified_existing_root_controls_restored",
    "recovered_after_interruption",
    # Accepted only to classify a pre-hardening canonical replay honestly.
    "recovered_after_independent_validation",
}


def _resolved(path: Path) -> Path:
    return Path(path).resolve(strict=False)


def _immutable_alias(controls: list[Path], immutable_inputs: list[Path]) -> bool:
    inputs = {_resolved(path) for path in immutable_inputs}
    return any(_resolved(control) in inputs for control in controls)


def validate_path_separation(paths: list[Path]) -> None:
    resolved = [_resolved(path) for path in paths]
    for index, left in enumerate(resolved):
        for right in resolved[index + 1 :]:
            if paths_overlap(left, right):
                raise ValueError(
                    "all identity command paths must be pairwise ancestor-disjoint"
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", default=str(DEFAULT_SOURCE_DB))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--pair-plan-db", default=str(DEFAULT_PAIR_PLAN_DB))
    parser.add_argument("--out-root", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--compression", default=CANONICAL_COMPRESSION)
    parser.add_argument("--row-group-rows", type=int, default=CANONICAL_ROW_GROUP_ROWS)
    parser.add_argument("--max-file-rows", type=int, default=CANONICAL_MAX_FILE_ROWS)
    parser.add_argument(
        "--source-page-size", type=int, default=CANONICAL_SOURCE_PAGE_SIZE
    )
    parser.add_argument("--max-peak-rss-mb", type=float, default=MAXIMUM_PEAK_RSS_MB)
    return parser.parse_args()


def _report_from_manifest(
    *,
    manifest: dict[str, Any],
    output_root: Path,
    manifest_out: Path,
    report_out: Path,
    replay_state: str,
) -> dict[str, Any]:
    statuses = {
        "fresh": "materialized_pending_independent_validation",
        "verified_replay": "verified_existing_root_replay",
        "controls_restored": "verified_existing_root_controls_restored",
        "interruption_recovery": "recovered_after_interruption",
    }
    if replay_state not in statuses:
        raise RuntimeError("unsupported identity replay state")
    existing = replay_state != "fresh"
    with bound_regular_file(output_root / "manifest.json") as root_manifest:
        manifest_file_sha256 = root_manifest.sha256()
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": statuses[replay_state],
        "materialization_gate_passed": True,
        "existing_root_replay_verified": replay_state == "verified_replay",
        "controls_restored": replay_state
        in {"controls_restored", "interruption_recovery"},
        "recovered_after_interruption": replay_state == "interruption_recovery",
        "independent_validation_passed": existing,
        "publication_gate_passed": False,
        "ranking_gate_passed": False,
        "promotion_gate_passed": False,
        "policy": manifest["policy"],
        "counts": manifest["counts"],
        "roots": {
            **manifest["roots"],
            "package_semantic_root_sha256": manifest["package_semantic_root_sha256"],
            "manifest_root_sha256": manifest["manifest_root_sha256"],
            "manifest_file_sha256": manifest_file_sha256,
        },
        "parquet_bytes": manifest["parquet_bytes"],
        "performance": {"peak_rss_mb": peak_rss_mb()},
        "artifacts": {
            "root": repo_path(output_root),
            "manifest": repo_path(manifest_out),
            "report": repo_path(report_out),
        },
    }


def _failure(
    error: BaseException,
    *,
    success_manifest_invalidated: bool = True,
) -> dict[str, Any]:
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": "failed",
        "error_code": "outcome_pair_identity_companion_export_failed_fail_closed",
        "error_type": type(error).__name__,
        "success_manifest_invalidated": success_manifest_invalidated,
        "success_report_invalidated": True,
        "independent_validation_passed": False,
        "publication_gate_passed": False,
        "ranking_gate_passed": False,
        "promotion_gate_passed": False,
    }


def _optional_control_bytes(path: Path) -> bytes | None:
    try:
        if not path.exists():
            return None
        with bound_regular_file(path) as bound:
            return bound.read_bytes(max_bytes=2 * 1024 * 1024)
    except Exception:
        return None


def _optional_control_object(path: Path) -> dict[str, Any] | None:
    payload = _optional_control_bytes(path)
    if payload is None:
        return None
    try:
        return load_json_bytes(payload)
    except Exception:
        return None


def _classify_existing_root(
    *,
    prior_manifest_bytes: bytes | None,
    prior_report: dict[str, Any] | None,
    package_manifest_bytes: bytes,
    package_manifest_sha256: str,
) -> str:
    if (
        prior_report is not None
        and prior_report.get("schema_version") == REPORT_SCHEMA_VERSION
        and prior_report.get("status") == "running"
        and prior_report.get("success_manifest_invalidated") is True
        and prior_report.get("success_report_invalidated") is True
    ):
        return "interruption_recovery"
    roots = prior_report.get("roots") if isinstance(prior_report, dict) else None
    if (
        prior_manifest_bytes == package_manifest_bytes
        and prior_report is not None
        and prior_report.get("schema_version") == REPORT_SCHEMA_VERSION
        and prior_report.get("status") in SUCCESS_REPORT_STATUSES
        and isinstance(roots, dict)
        and roots.get("manifest_file_sha256") == package_manifest_sha256
    ):
        return "verified_replay"
    return "controls_restored"


def main() -> int:
    args = parse_args()
    source_db = Path(args.source_db)
    config = Path(args.config)
    pair_plan_db = Path(args.pair_plan_db)
    output_raw = Path(args.out_root)
    manifest_raw = Path(args.manifest_out)
    report_raw = Path(args.report_out)
    immutable = [source_db, config, pair_plan_db]
    if report_raw.is_symlink() or any(
        paths_overlap(_resolved(report_raw), _resolved(path))
        for path in [*immutable, output_raw, manifest_raw]
    ):
        print(
            "ERROR: report path overlaps immutable or package targets", file=sys.stderr
        )
        return 2
    try:
        report_out = preflight_control_target(report_raw)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if _immutable_alias([manifest_raw, output_raw], immutable):
        error = ValueError("output aliases an immutable real input")
        try:
            with identity_companion_leases([report_out], namespace="command"):
                secure_atomic_write_json(
                    report_out,
                    _failure(
                        error,
                        success_manifest_invalidated=False,
                    ),
                )
        except Exception as invalidation_error:
            print(
                f"ERROR: {type(invalidation_error).__name__}: {invalidation_error}",
                file=sys.stderr,
            )
            return 1
        print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    all_targets = [
        source_db,
        config,
        pair_plan_db,
        output_raw,
        manifest_raw,
        report_out,
    ]
    command_leases = identity_companion_leases(all_targets, namespace="command")
    try:
        command_leases.__enter__()
    except Exception as exc:
        manifest_invalidated = False
        try:
            with identity_companion_leases([manifest_raw], namespace="command"):
                manifest_out = preflight_control_target(manifest_raw)
                secure_unlink_regular(manifest_out)
                manifest_invalidated = True
        except Exception:
            pass
        try:
            with identity_companion_leases([report_out], namespace="command"):
                secure_atomic_write_json(
                    report_out,
                    _failure(
                        exc,
                        success_manifest_invalidated=manifest_invalidated,
                    ),
                )
        except Exception:
            pass
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    try:
        try:
            manifest_out = preflight_control_target(manifest_raw)
            prior_manifest_bytes = _optional_control_bytes(manifest_out)
            prior_report = _optional_control_object(report_out)
            secure_unlink_regular(manifest_out)
            secure_atomic_write_json(
                report_out,
                {
                    "schema_version": REPORT_SCHEMA_VERSION,
                    "status": "running",
                    "success_manifest_invalidated": True,
                    "success_report_invalidated": True,
                    "independent_validation_passed": False,
                    "publication_gate_passed": False,
                    "ranking_gate_passed": False,
                    "promotion_gate_passed": False,
                },
            )
            validate_path_separation(all_targets)
            output_root = preflight_output_root(output_raw)
            if output_root.exists():
                validation = validate_outcome_pair_identity_companion(
                    root=output_root,
                    manifest_path=None,
                    source_db_path=source_db,
                    config_path=config,
                    pair_plan_db_path=pair_plan_db,
                    batch_rows=CANONICAL_ROW_GROUP_ROWS,
                    source_page_size=int(args.source_page_size),
                    max_peak_rss_mb=float(args.max_peak_rss_mb),
                    _leases_held=True,
                )
                if validation["status"] != "ok":
                    raise RuntimeError("existing identity package failed validation")
                with bound_regular_file(output_root / "manifest.json") as root_manifest:
                    manifest_bytes = root_manifest.read_bytes(max_bytes=2 * 1024 * 1024)
                    package_manifest_sha256 = root_manifest.sha256()
                manifest = load_json_bytes(manifest_bytes)
                secure_atomic_write_bytes(manifest_out, manifest_bytes)
                replay_state = _classify_existing_root(
                    prior_manifest_bytes=prior_manifest_bytes,
                    prior_report=prior_report,
                    package_manifest_bytes=manifest_bytes,
                    package_manifest_sha256=package_manifest_sha256,
                )
                report = _report_from_manifest(
                    manifest=manifest,
                    output_root=output_root,
                    manifest_out=manifest_out,
                    report_out=report_out,
                    replay_state=replay_state,
                )
            else:
                manifest = export_outcome_pair_identity_companion(
                    source_db_path=source_db,
                    config_path=config,
                    pair_plan_db_path=pair_plan_db,
                    output_root=output_root,
                    compression=str(args.compression),
                    row_group_rows=int(args.row_group_rows),
                    max_file_rows=int(args.max_file_rows),
                    source_page_size=int(args.source_page_size),
                    max_peak_rss_mb=float(args.max_peak_rss_mb),
                    _leases_held=True,
                )
                with bound_regular_file(output_root / "manifest.json") as root_manifest:
                    manifest_bytes = root_manifest.read_bytes(max_bytes=2 * 1024 * 1024)
                secure_atomic_write_bytes(manifest_out, manifest_bytes)
                if load_json_bytes(manifest_bytes) != manifest:
                    raise RuntimeError(
                        "external manifest differs from package manifest"
                    )
                report = _report_from_manifest(
                    manifest=manifest,
                    output_root=output_root,
                    manifest_out=manifest_out,
                    report_out=report_out,
                    replay_state="fresh",
                )
            secure_atomic_write_json(report_out, report)
        except Exception as exc:
            try:
                secure_unlink_regular(manifest_out)
            except Exception:
                pass
            secure_atomic_write_json(report_out, _failure(exc))
            print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    finally:
        command_leases.__exit__(None, None, None)
    print(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True, allow_nan=False)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
