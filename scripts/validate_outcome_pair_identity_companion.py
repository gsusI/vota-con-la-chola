#!/usr/bin/env python3
"""Validate every real row in the C2B participant identity companion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.outcome_pair_identity_companion import (
    CANONICAL_SOURCE_PAGE_SIZE,
    DEFAULT_CONFIG,
    DEFAULT_PAIR_PLAN_DB,
    DEFAULT_SOURCE_DB,
    MAXIMUM_PEAK_RSS_MB,
)
from publicdata_publish.outcome_pair_identity_companion_validation import (
    VALIDATION_SCHEMA_VERSION,
    validate_outcome_pair_identity_companion,
)
from publicdata_publish.outcome_pair_identity_safety import (
    identity_companion_leases,
    paths_overlap,
    preflight_control_target,
    secure_atomic_write_json,
)


def _resolved(path: Path) -> Path:
    return Path(path).resolve(strict=False)


def validate_path_separation(paths: list[Path]) -> None:
    resolved = [_resolved(path) for path in paths]
    for index, left in enumerate(resolved):
        for right in resolved[index + 1 :]:
            if paths_overlap(left, right):
                raise ValueError(
                    "all identity validation paths must be pairwise ancestor-disjoint"
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--source-db", default=str(DEFAULT_SOURCE_DB))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--pair-plan-db", default=str(DEFAULT_PAIR_PLAN_DB))
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--batch-rows", type=int, default=5_000)
    parser.add_argument(
        "--source-page-size", type=int, default=CANONICAL_SOURCE_PAGE_SIZE
    )
    parser.add_argument("--max-peak-rss-mb", type=float, default=MAXIMUM_PEAK_RSS_MB)
    return parser.parse_args()


def _failure(error: BaseException) -> dict[str, object]:
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "status": "failed",
        "error_code": "outcome_pair_identity_companion_validation_failed_fail_closed",
        "error_type": type(error).__name__,
        "success_report_invalidated": True,
        "publication_gate_passed": False,
        "ranking_gate_passed": False,
        "promotion_gate_passed": False,
    }


def main() -> int:
    args = parse_args()
    root = Path(args.root)
    manifest = Path(args.manifest) if args.manifest else None
    source_db = Path(args.source_db)
    config = Path(args.config)
    pair_plan_db = Path(args.pair_plan_db)
    report_raw = Path(args.report_out)
    immutable = [root, source_db, config, pair_plan_db]
    if manifest is not None:
        immutable.append(manifest)
    if report_raw.is_symlink() or any(
        paths_overlap(_resolved(report_raw), _resolved(path)) for path in immutable
    ):
        print("ERROR: validation report overlaps immutable evidence", file=sys.stderr)
        return 2
    try:
        report_out = preflight_control_target(report_raw)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    all_targets = [*immutable, report_out]
    command_leases = identity_companion_leases(all_targets, namespace="command")
    try:
        command_leases.__enter__()
    except Exception as exc:
        try:
            with identity_companion_leases([report_out], namespace="command"):
                secure_atomic_write_json(report_out, _failure(exc))
        except Exception:
            pass
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    try:
        try:
            secure_atomic_write_json(
                report_out,
                {
                    "schema_version": VALIDATION_SCHEMA_VERSION,
                    "status": "running",
                    "success_report_invalidated": True,
                    "publication_gate_passed": False,
                    "ranking_gate_passed": False,
                    "promotion_gate_passed": False,
                },
            )
            validate_path_separation(all_targets)
            report = validate_outcome_pair_identity_companion(
                root=root,
                manifest_path=manifest,
                source_db_path=source_db,
                config_path=config,
                pair_plan_db_path=pair_plan_db,
                batch_rows=int(args.batch_rows),
                source_page_size=int(args.source_page_size),
                max_peak_rss_mb=float(args.max_peak_rss_mb),
                _leases_held=True,
            )
            secure_atomic_write_json(report_out, report)
        except Exception as exc:
            secure_atomic_write_json(report_out, _failure(exc))
            print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    finally:
        command_leases.__exit__(None, None, None)
    print(
        json.dumps(
            {
                "status": report["status"],
                "member_vote_rows": report["counts"]["member_vote_rows"],
                "distinct_official_names": report["counts"]["distinct_official_names"],
                "actions": report["counts"]["actions"],
                "publication_gate_passed": report["publication_gate_passed"],
                "ranking_gate_passed": report["ranking_gate_passed"],
                "promotion_gate_passed": report["promotion_gate_passed"],
                "report_out": report_out.name,
            },
            ensure_ascii=True,
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
