#!/usr/bin/env python3
"""Build deterministic strict/from-file/replay probe matrix for carryover sources."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

# Ensure repo root imports work when script is executed directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.config import DEFAULT_DB, DEFAULT_TIMEOUT, SOURCE_CONFIG

DEFAULT_SNAPSHOT_DATE = "2026-02-17"
DEFAULT_OUT = Path("docs/etl/sprints/AI-OPS-10/exports/source_probe_matrix.tsv")
DEFAULT_REPLAY_ROOT = Path("docs/etl/sprints/AI-OPS-10/evidence/replay-inputs")
DEFAULT_LOG_DIR = Path("docs/etl/sprints/AI-OPS-10/evidence/source-probe-logs")
DEFAULT_SQL_DIR = Path("docs/etl/sprints/AI-OPS-10/evidence/source-probe-sql")

CARRYOVER_SOURCE_ORDER: tuple[str, ...] = (
    "placsp_autonomico",
    "bdns_autonomico",
    "placsp_sindicacion",
    "bdns_api_subvenciones",
    "eurostat_sdmx",
    "bde_series_api",
    "aemet_opendata_series",
)

MODE_ORDER: tuple[str, ...] = ("strict-network", "from-file", "replay")

SOURCE_FAMILY: dict[str, str] = {
    "placsp_autonomico": "placsp",
    "placsp_sindicacion": "placsp",
    "bdns_autonomico": "bdns",
    "bdns_api_subvenciones": "bdns",
    "eurostat_sdmx": "outcomes",
    "bde_series_api": "outcomes",
    "aemet_opendata_series": "outcomes",
}

# Tracker-aligned strict probes for carryover blockers.
STRICT_URL_OVERRIDES: dict[str, str] = {
    "eurostat_sdmx": "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/une_rt_a",
    "bde_series_api": "https://api.bde.es/datos/series/PARO.TASA.ES.M",
    "aemet_opendata_series": "https://opendata.aemet.es/opendata/api/valores/climatologicos",
}

# Default timeout policy: config default for non-strict rows, tracker override for strict probes.
STRICT_TIMEOUT_OVERRIDES: dict[str, int] = {
    "placsp_autonomico": 30,
    "bdns_autonomico": 30,
    "placsp_sindicacion": 60,
    "bdns_api_subvenciones": 30,
    "eurostat_sdmx": 30,
    "bde_series_api": 30,
    "aemet_opendata_series": 30,
}

STRICT_REQUIRED_ENV: dict[str, str] = {
    "aemet_opendata_series": "AEMET_API_KEY",
}

FIELDNAMES: tuple[str, ...] = (
    "row_id",
    "source_family",
    "source_id",
    "mode",
    "snapshot_date",
    "timeout_seconds",
    "timeout_policy",
    "strict_network",
    "required_env",
    "url_override",
    "from_file_input",
    "replay_input_expected",
    "replay_input_policy",
    "ingest_command",
    "expected_stdout_log",
    "expected_stderr_log",
    "expected_run_snapshot_csv",
    "expected_source_records_snapshot_csv",
    "notes",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate deterministic source probe matrix for strict/from-file/replay execution.",
    )
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite path used in generated commands")
    parser.add_argument(
        "--snapshot-date",
        default=DEFAULT_SNAPSHOT_DATE,
        help="Snapshot date used in generated commands (YYYY-MM-DD)",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output matrix path")
    parser.add_argument(
        "--format",
        choices=("tsv", "csv"),
        default="",
        help="Force output format; if omitted inferred from --out suffix",
    )
    parser.add_argument(
        "--timeout-default",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Default timeout for non-strict rows",
    )
    parser.add_argument(
        "--replay-root",
        default=str(DEFAULT_REPLAY_ROOT),
        help="Root directory for replay input expectations",
    )
    parser.add_argument(
        "--log-dir",
        default=str(DEFAULT_LOG_DIR),
        help="Directory for expected stdout/stderr logs",
    )
    parser.add_argument(
        "--sql-dir",
        default=str(DEFAULT_SQL_DIR),
        help="Directory for expected SQL artifacts",
    )
    return parser.parse_args(argv)


def _infer_format(out_path: Path, forced: str) -> str:
    token = str(forced or "").strip().lower()
    if token in {"tsv", "csv"}:
        return token
    if out_path.suffix.lower() == ".csv":
        return "csv"
    return "tsv"


def _validate_snapshot_date(value: str) -> str:
    token = str(value or "").strip()
    dt.date.fromisoformat(token)
    return token


def _replay_extension_for_source(source_id: str) -> str:
    fmt = str(SOURCE_CONFIG[source_id].get("format") or "json").strip().lower()
    if fmt in {"xml", "atom"}:
        return "xml"
    return "json"


def _build_replay_input_path(source_id: str, snapshot_date: str, replay_root: Path) -> str:
    stamp = snapshot_date.replace("-", "")
    ext = _replay_extension_for_source(source_id)
    return str(replay_root / source_id / f"{source_id}_replay_{stamp}.{ext}")


def _build_ingest_command(
    *,
    db: str,
    source_id: str,
    mode: str,
    snapshot_date: str,
    timeout_seconds: int,
    url_override: str,
    from_file_input: str,
) -> str:
    parts = [
        "python3",
        "scripts/ingestar_politicos_es.py",
        "ingest",
        "--db",
        db,
        "--source",
        source_id,
    ]
    if url_override:
        parts.extend(["--url", url_override])
    if from_file_input and from_file_input != "-":
        parts.extend(["--from-file", from_file_input])
    parts.extend(["--snapshot-date", snapshot_date])
    if mode == "strict-network":
        parts.append("--strict-network")
    parts.extend(["--timeout", str(timeout_seconds)])
    return " ".join(parts)


def build_rows(args: argparse.Namespace) -> list[dict[str, str]]:
    replay_root = Path(args.replay_root)
    log_dir = Path(args.log_dir)
    sql_dir = Path(args.sql_dir)
    db = str(args.db)
    snapshot_date = str(args.snapshot_date)
    timeout_default = int(args.timeout_default)

    rows: list[dict[str, str]] = []
    for source_id in CARRYOVER_SOURCE_ORDER:
        cfg = SOURCE_CONFIG.get(source_id)
        if cfg is None:
            raise KeyError(f"source_id '{source_id}' no existe en SOURCE_CONFIG")
        fallback_file = str(cfg.get("fallback_file") or "").strip()
        min_records_loaded = int(cfg.get("min_records_loaded_strict") or 0)
        source_family = SOURCE_FAMILY[source_id]

        for mode in MODE_ORDER:
            row_id = f"{source_id}__{mode}"
            timeout_seconds = timeout_default
            timeout_policy = f"default_timeout={timeout_default}s"
            strict_network = "1" if mode == "strict-network" else "0"
            required_env = ""
            url_override = ""
            replay_input_expected = ""
            replay_input_policy = "not-applicable"
            from_file_input = "-"
            notes_parts = [
                f"min_records_loaded_strict={min_records_loaded}",
                "replay_schema=normalized_run_snapshot_v2",
            ]

            if mode == "strict-network":
                timeout_seconds = int(STRICT_TIMEOUT_OVERRIDES.get(source_id, timeout_default))
                if source_id in STRICT_TIMEOUT_OVERRIDES:
                    timeout_policy = f"strict_override_tracker={timeout_seconds}s"
                url_override = STRICT_URL_OVERRIDES.get(source_id, "")
                required_env = STRICT_REQUIRED_ENV.get(source_id, "")
                notes_parts.append("strict_network_fallback_disabled=true")
                notes_parts.append("url_override=tracker" if url_override else "url_override=default")
                if required_env:
                    notes_parts.append(f"required_env={required_env}")
            elif mode == "from-file":
                from_file_input = fallback_file
                notes_parts.append("fixture_source=fallback_file")
            else:
                replay_input_expected = _build_replay_input_path(source_id, snapshot_date, replay_root)
                replay_input_policy = "must-exist-before-run"
                from_file_input = replay_input_expected
                notes_parts.append("fixture_source=replay_capture")

            ingest_command = _build_ingest_command(
                db=db,
                source_id=source_id,
                mode=mode,
                snapshot_date=snapshot_date,
                timeout_seconds=timeout_seconds,
                url_override=url_override,
                from_file_input=from_file_input,
            )

            stem = f"{source_id}__{mode}"
            rows.append(
                {
                    "row_id": row_id,
                    "source_family": source_family,
                    "source_id": source_id,
                    "mode": mode,
                    "snapshot_date": snapshot_date,
                    "timeout_seconds": str(timeout_seconds),
                    "timeout_policy": timeout_policy,
                    "strict_network": strict_network,
                    "required_env": required_env or "-",
                    "url_override": url_override or "-",
                    "from_file_input": from_file_input,
                    "replay_input_expected": replay_input_expected or "-",
                    "replay_input_policy": replay_input_policy,
                    "ingest_command": ingest_command,
                    "expected_stdout_log": str(log_dir / f"{stem}.stdout.log"),
                    "expected_stderr_log": str(log_dir / f"{stem}.stderr.log"),
                    "expected_run_snapshot_csv": str(sql_dir / f"{stem}_run_snapshot.csv"),
                    "expected_source_records_snapshot_csv": str(sql_dir / f"{stem}_source_records_snapshot.csv"),
                    "notes": "; ".join(notes_parts),
                }
            )
    return rows


def write_matrix(rows: list[dict[str, str]], out_path: Path, output_format: str) -> None:
    delimiter = "\t" if output_format == "tsv" else ","
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=FIELDNAMES,
            delimiter=delimiter,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        args.snapshot_date = _validate_snapshot_date(str(args.snapshot_date))
    except ValueError:
        print("Parametro invalido: --snapshot-date debe tener formato YYYY-MM-DD", file=sys.stderr)
        return 2

    rows = build_rows(args)
    out_path = Path(args.out)
    output_format = _infer_format(out_path, str(args.format))
    write_matrix(rows, out_path, output_format)

    print(f"Wrote {len(rows)} rows to {out_path} ({output_format})")
    print(f"Carryover sources: {len(CARRYOVER_SOURCE_ORDER)}")
    print(f"Modes per source: {len(MODE_ORDER)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
