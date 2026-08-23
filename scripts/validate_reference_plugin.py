#!/usr/bin/env python3
"""Validate the reference plugin by replaying its exact official capture twice."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_reference_plugin import run_reference_plugin


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="", help="Optional JSON report path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with tempfile.TemporaryDirectory(prefix="vclc-reference-plugin-") as temp_dir:
        temp_root = Path(temp_dir)
        report = run_reference_plugin(
            manifest_path=Path("plugins/congreso_representatives/plugin.json"),
            ontology_path=Path("docs/data-model/core-ontology-v1.json"),
            db_path=temp_root / "congreso-reference-plugin.db",
            raw_dir=temp_root / "raw",
            snapshot_date="2026-02-12",
            network_enabled=False,
            repeat=2,
        )
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
