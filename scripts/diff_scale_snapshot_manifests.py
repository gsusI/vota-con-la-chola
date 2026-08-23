#!/usr/bin/env python3
"""Write an exact, bounded diff between two real scale-origin manifests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_publish.snapshot_attestation import (
    SnapshotAttestationError,
    diff_scale_manifests,
    write_json_canonical,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--max-samples", type=int, default=25)
    parser.add_argument("--out", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = diff_scale_manifests(
            before_path=Path(args.before),
            after_path=Path(args.after),
            max_samples=args.max_samples,
        )
        write_json_canonical(Path(args.out), report)
        print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    except (OSError, SnapshotAttestationError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
