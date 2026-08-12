#!/usr/bin/env python3
"""Validate every row and file in a semantic Parquet partition set."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.accountability_partition_validation import (
    validate_accountability_partitions,
)
from publicdata_publish.actor_mandate_partition_validation import (
    validate_actor_mandate_partitions,
)
from publicdata_publish.candidate_occurrence_partition_validation import (
    validate_candidate_occurrence_partitions,
)
from publicdata_publish.indicator_partition_validation import (
    validate_indicator_partitions,
)
from publicdata_publish.money_partition_validation import validate_money_partitions
from publicdata_publish.semantic_partition_validation import (
    validate_semantic_partitions,
)


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
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest")
    parser.add_argument("--report-out")
    parser.add_argument("--batch-rows", type=int, default=10_000)
    parser.add_argument("--min-rows", type=int, default=1)
    parser.add_argument("--max-peak-rss-mb", type=float, default=1024.0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--enforce", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validators = {
            "member_votes": validate_semantic_partitions,
            "accountability_ledger": validate_accountability_partitions,
            "actor_mandates": validate_actor_mandate_partitions,
            "candidate_occurrences": validate_candidate_occurrence_partitions,
            "public_money_facts": validate_money_partitions,
            "indicator_observations": validate_indicator_partitions,
        }
        validator = validators[args.lane]
        validator_kwargs = {
            "root": Path(args.root),
            "manifest_path": Path(args.manifest) if args.manifest else None,
            "batch_rows": args.batch_rows,
            "min_rows": args.min_rows,
            "max_peak_rss_mb": args.max_peak_rss_mb,
        }
        if args.lane == "candidate_occurrences":
            validator_kwargs["workers"] = args.workers
        elif args.workers != 1:
            raise ValueError(
                "workers greater than one currently require candidate_occurrences"
            )
        report = validator(
            **validator_kwargs,
        )
    except (
        FileNotFoundError,
        RuntimeError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    if args.report_out:
        report_out = Path(args.report_out)
        report_out.parent.mkdir(parents=True, exist_ok=True)
        report_out.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "status": report["status"],
                "lane": args.lane,
                "rows": report["totals"]["rows"],
                "partitions": report["totals"]["partitions"],
                "files": report["totals"]["files"],
                "promotion_gate_passed": report["promotion_gate_passed"],
                "report_out": Path(args.report_out).name if args.report_out else None,
            },
            sort_keys=True,
        )
    )
    if args.enforce and report["status"] != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
