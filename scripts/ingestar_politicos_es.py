#!/usr/bin/env python3
"""Wrapper CLI.

Keep this path stable because it is referenced by `justfile` and docs.
The main implementation lives in `etl.politicos_es.cli`.

This wrapper also exposes a compatibility adapter command used by carryover
evidence packets:

- `normalize-run-snapshot` (alias: `adapt-run-snapshot`)

The adapter normalizes legacy/tabular run snapshots into canonical schema v2 so
parity consumers can rely on stable fields such as `source_id`, `mode`, and
`run_records_loaded` while optionally emitting a legacy `metric,value` file for
older report readers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

# Ensure repo root is importable when executing this file directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.cli import main as etl_main
from etl.politicos_es.run_snapshot_schema import normalize_run_snapshot_file


def _snapshot_adapter_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts/ingestar_politicos_es.py normalize-run-snapshot",
        description=(
            "Normaliza un *_run_snapshot.csv legacy/tabular al schema canonico "
            "y mantiene opcion de salida legacy metric,value."
        ),
    )
    parser.add_argument("--in", dest="input_path", required=True, help="Snapshot de entrada")
    parser.add_argument(
        "--out",
        dest="output_path",
        default="",
        help="Salida canonica; por defecto sobrescribe --in",
    )
    parser.add_argument(
        "--legacy-kv-out",
        dest="legacy_output_path",
        default="",
        help="Salida opcional adicional en formato legacy metric,value",
    )
    parser.add_argument("--source-id", default="", help="Override opcional para source_id")
    parser.add_argument("--mode", default="", help="Override opcional para mode")
    parser.add_argument(
        "--snapshot-date",
        default="",
        help="Override opcional para snapshot_date (YYYY-MM-DD)",
    )
    return parser


def _run_snapshot_adapter(argv: Sequence[str]) -> int:
    parser = _snapshot_adapter_parser()
    args = parser.parse_args(list(argv))

    input_path = Path(args.input_path)
    output_path = Path(args.output_path) if str(args.output_path or "").strip() else input_path
    legacy_path = str(args.legacy_output_path or "").strip()

    if not input_path.exists():
        print(f"ERROR snapshot no encontrado: {input_path}", file=sys.stderr)
        return 2
    if input_path.stat().st_size == 0:
        print(f"ERROR snapshot vacio: {input_path}", file=sys.stderr)
        return 2

    defaults: dict[str, str] = {}
    for key, raw in (
        ("source_id", args.source_id),
        ("mode", args.mode),
        ("snapshot_date", args.snapshot_date),
    ):
        value = str(raw or "").strip()
        if value:
            defaults[key] = value

    normalized_path, legacy_output, normalized = normalize_run_snapshot_file(
        input_path=input_path,
        output_path=output_path,
        defaults=defaults,
        legacy_output_path=legacy_path or None,
    )
    if not (
        str(normalized.get("source_id", "")).strip()
        or str(normalized.get("mode", "")).strip()
        or str(normalized.get("run_records_loaded", "")).strip()
    ):
        print(
            "ERROR snapshot normalizado sin campos clave (source_id/mode/run_records_loaded). "
            "Revise formato de entrada u overrides.",
            file=sys.stderr,
        )
        return 2

    print(f"OK normalized run snapshot -> {normalized_path}")
    if legacy_output is not None:
        print(f"OK legacy metric,value snapshot -> {legacy_output}")

    # Emit stable parity summary for packet scripts/report ingestion.
    print(
        json.dumps(
            {
                "source_id": normalized.get("source_id", ""),
                "mode": normalized.get("mode", ""),
                "run_records_loaded": normalized.get("run_records_loaded", ""),
                "snapshot_date": normalized.get("snapshot_date", ""),
            },
            ensure_ascii=False,
        )
    )
    return 0


def _dispatch(argv: Sequence[str]) -> int:
    args = list(argv)
    if args and args[0] in {"normalize-run-snapshot", "adapt-run-snapshot"}:
        return _run_snapshot_adapter(args[1:])
    return etl_main(args)


if __name__ == "__main__":
    raise SystemExit(_dispatch(sys.argv[1:]))
