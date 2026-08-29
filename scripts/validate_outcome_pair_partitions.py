#!/usr/bin/env python3
"""Validate all rows and files in a real C2B discovery-pair package."""

from __future__ import annotations

import argparse
import json
import stat
import sys
from contextlib import ExitStack
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.outcome_pair_partition_validation import (
    validate_outcome_pair_partitions,
)
from publicdata_publish.outcome_pair_partitions import (
    outcome_pair_build_lease,
    outcome_pair_lease_path,
    secure_atomic_write_json,
    secure_unlink_control,
)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    secure_atomic_write_json(path, payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--source-db", required=True)
    parser.add_argument("--source-manifest", required=True)
    parser.add_argument("--source-validation", required=True)
    parser.add_argument("--identity-source-db", required=True)
    parser.add_argument("--identity-config", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--batch-rows", type=int, default=5_000)
    parser.add_argument("--min-rows", type=int, default=1_000_000)
    parser.add_argument("--max-peak-rss-mb", type=float, default=1024.0)
    return parser.parse_args()


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _validated_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    report_out = Path(args.report_out)
    root = Path(args.root).resolve()
    manifest = (
        Path(args.manifest).resolve() if args.manifest else root / "manifest.json"
    )
    immutable_inputs = {
        manifest,
        Path(args.source_db).resolve(),
        Path(args.source_manifest).resolve(),
        Path(args.source_validation).resolve(),
        Path(args.identity_source_db).resolve(),
        Path(args.identity_config).resolve(),
    }
    resolved_report = report_out.resolve()
    if (
        resolved_report in immutable_inputs
        or _within(resolved_report, root)
        or _within(root, resolved_report)
    ):
        raise ValueError("report output aliases immutable validation input")
    if report_out.exists() or report_out.is_symlink():
        report_stat = report_out.lstat()
        if (
            report_out.is_symlink()
            or not stat.S_ISREG(report_stat.st_mode)
            or report_stat.st_nlink != 1
        ):
            raise ValueError(
                "validation report output must be a regular single-link file"
            )
    lock_path = outcome_pair_lease_path(report_out, namespace="command")
    if _within(lock_path, root) or lock_path in immutable_inputs:
        raise ValueError("validation report lock overlaps immutable input")
    return report_out, root, manifest


def _validate_report_invalidation_target(args: argparse.Namespace) -> None:
    target = Path(args.report_out).resolve()
    root = Path(args.root).resolve()
    manifest = (
        Path(args.manifest).resolve() if args.manifest else root / "manifest.json"
    )
    protected = {
        root,
        manifest,
        Path(args.source_db).resolve(),
        Path(args.source_manifest).resolve(),
        Path(args.source_validation).resolve(),
        Path(args.identity_source_db).resolve(),
        Path(args.identity_config).resolve(),
    }
    if any(_within(target, path) or _within(path, target) for path in protected):
        raise ValueError("validation report overlaps immutable package evidence")


def _main_unlocked(args: argparse.Namespace) -> int:
    report_out = Path(args.report_out)
    try:
        _validate_report_invalidation_target(args)
        secure_unlink_control(report_out)
        _atomic_write_json(
            report_out,
            {
                "schema_version": ("outcome_pair_discovery_partition_validation_v1"),
                "status": "running",
                "success_report_invalidated": True,
                "promotion_gate_passed": False,
            },
        )
        report_out, root, manifest = _validated_paths(args)
        report = validate_outcome_pair_partitions(
            root=root,
            manifest_path=manifest,
            source_db_path=Path(args.source_db),
            source_manifest_path=Path(args.source_manifest),
            source_validation_path=Path(args.source_validation),
            identity_source_db_path=Path(args.identity_source_db),
            identity_config_path=Path(args.identity_config),
            batch_rows=int(args.batch_rows),
            min_rows=int(args.min_rows),
            max_peak_rss_mb=float(args.max_peak_rss_mb),
            require_source_parity=True,
        )
        _atomic_write_json(report_out, report)
    except Exception as exc:  # noqa: BLE001 - CLI boundary must persist fail-closed status
        try:
            secure_unlink_control(report_out)
        except Exception:
            pass
        failed = {
            "schema_version": "outcome_pair_discovery_partition_validation_v1",
            "status": "failed",
            "error_code": "outcome_pair_partition_validation_failed_fail_closed",
            "error_type": type(exc).__name__,
            "success_report_invalidated": True,
            "promotion_gate_passed": False,
        }
        try:
            secure_unlink_control(report_out)
            _atomic_write_json(report_out, failed)
        except Exception:
            pass
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": report["status"],
                "pairs": report["counts"]["pairs"],
                "partitions": report["counts"]["partitions"],
                "files": report["counts"]["files"],
                "promotion_gate_passed": report["promotion_gate_passed"],
                "report_out": report_out.name,
            },
            allow_nan=False,
            sort_keys=True,
        )
    )
    if report["status"] != "ok":
        return 1
    return 0


def main() -> int:
    args = parse_args()
    mutation_targets = {
        Path(args.root).resolve(),
        Path(args.report_out).resolve(),
    }
    with ExitStack() as leases:
        for target in sorted(mutation_targets, key=lambda path: path.as_posix()):
            leases.enter_context(outcome_pair_build_lease(target, namespace="command"))
        return _main_unlocked(args)


if __name__ == "__main__":
    raise SystemExit(main())
