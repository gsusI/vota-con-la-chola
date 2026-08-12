#!/usr/bin/env python3
"""Export bounded, incremental semantic Parquet partitions from SQLite."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.accountability_partitions import (
    export_accountability_partitions,
)
from publicdata_publish.actor_mandate_partitions import (
    export_actor_mandate_partitions,
)
from publicdata_publish.candidate_occurrence_partitions import (
    export_candidate_occurrence_partitions,
)
from publicdata_publish.indicator_partitions import export_indicator_partitions
from publicdata_publish.money_partitions import export_money_partitions
from publicdata_publish.semantic_partitions import export_member_vote_partitions


def _iso_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("snapshot date must be YYYY-MM-DD") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--lane",
        choices=(
            "member_votes",
            "accountability_ledger",
            "actor_mandates",
            "candidate_occurrences",
            "public_money_facts",
            "indicator_observations",
        ),
        default="member_votes",
    )
    parser.add_argument("--db", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--snapshot-date", required=True, type=_iso_date)
    parser.add_argument("--compression", default="zstd")
    parser.add_argument("--row-group-rows", type=int, default=25_000)
    parser.add_argument("--max-file-rows", type=int, default=100_000)
    parser.add_argument("--previous-manifest")
    parser.add_argument("--previous-root")
    parser.add_argument("--vote-audit")
    parser.add_argument("--manifest-out")
    parser.add_argument("--min-rows", type=int, default=1)
    parser.add_argument("--max-peak-rss-mb", type=float, default=1024.0)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        common = {
            "db_path": Path(args.db),
            "output_root": Path(args.output_root),
            "snapshot_date": args.snapshot_date,
            "compression": args.compression,
            "row_group_rows": args.row_group_rows,
            "max_file_rows": args.max_file_rows,
            "previous_manifest_path": (
                Path(args.previous_manifest) if args.previous_manifest else None
            ),
            "previous_root": (Path(args.previous_root) if args.previous_root else None),
            "min_rows": args.min_rows,
            "max_peak_rss_mb": args.max_peak_rss_mb,
            "enforce": args.enforce,
        }
        if args.lane == "member_votes":
            manifest = export_member_vote_partitions(
                **common,
                vote_audit_path=(Path(args.vote_audit) if args.vote_audit else None),
            )
        elif args.lane == "accountability_ledger":
            if args.vote_audit:
                raise ValueError("--vote-audit applies only to member_votes")
            manifest = export_accountability_partitions(**common)
        elif args.lane == "actor_mandates":
            if args.vote_audit:
                raise ValueError("--vote-audit applies only to member_votes")
            manifest = export_actor_mandate_partitions(**common)
        elif args.lane == "candidate_occurrences":
            if args.vote_audit:
                raise ValueError("--vote-audit applies only to member_votes")
            manifest = export_candidate_occurrence_partitions(**common)
        elif args.lane == "indicator_observations":
            if args.vote_audit:
                raise ValueError("--vote-audit applies only to member_votes")
            manifest = export_indicator_partitions(**common)
        else:
            if args.vote_audit:
                raise ValueError("--vote-audit applies only to member_votes")
            manifest = export_money_partitions(**common)
    except (
        FileNotFoundError,
        FileExistsError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if args.manifest_out:
        manifest_out = Path(args.manifest_out)
        manifest_out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(args.output_root) / "manifest.json", manifest_out)
    print(
        json.dumps(
            {
                "status": "ok",
                "lane": manifest["lane"],
                "rows": manifest["totals"]["rows"],
                "partitions": manifest["totals"]["partitions"],
                "files": manifest["totals"]["files"],
                "partitions_reused": manifest["incremental_contract"][
                    "partitions_reused"
                ],
                "partitions_rebuilt": manifest["incremental_contract"][
                    "partitions_rebuilt"
                ],
                "analytical_partition_gate_passed": manifest[
                    "analytical_partition_gate_passed"
                ],
                "promotion_gate_passed": manifest["promotion_gate_passed"],
                "output_root": Path(args.output_root).name,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
