#!/usr/bin/env python3
"""Status/gate checker for docs/etl/e2e-scrape-load-tracker.md against SQLite runs."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_TRACKER = Path("docs/etl/e2e-scrape-load-tracker.md")

# Mapping between tracker table rows and source_id values.
TRACKER_SOURCE_HINTS = {
    "Congreso OpenData Diputados": ["congreso_diputados"],
    "Congreso votaciones": ["congreso_votaciones"],
    "Congreso iniciativas": ["congreso_iniciativas"],
    "Senado votaciones/mociones": ["senado_votaciones"],
    "Senado CSV Senadores": ["senado_senadores"],
    "Senado OpenData XML": ["senado_senadores"],
    "Europarl MEP XML": ["europarl_meps"],
    "RED SARA Concejales": ["municipal_concejales"],
    "Asamblea de Madrid": ["asamblea_madrid_ocupaciones"],
    "Asamblea de Ceuta": ["asamblea_ceuta_diputados"],
    "Asamblea de Melilla": ["asamblea_melilla_diputados"],
    "Cortes de Aragon": ["cortes_aragon_diputados"],
    "Asamblea de Extremadura": ["asamblea_extremadura_diputados"],
    "Asamblea Regional de Murcia": ["asamblea_murcia_diputados"],
    "Junta General del Principado de Asturias": ["jgpa_diputados"],
    "Parlament de Catalunya": ["parlament_catalunya_diputats"],
    "Parlamento de Canarias": ["parlamento_canarias_diputados"],
    "Parlamento de Cantabria": ["parlamento_cantabria_diputados"],
    "Parlament de les Illes Balears": ["parlament_balears_diputats"],
    "Parlamento de La Rioja": ["parlamento_larioja_diputados"],
    "Corts Valencianes": ["corts_valencianes_diputats"],
    "Cortes de Castilla-La Mancha": ["cortes_clm_diputados"],
    "Cortes de Castilla y Leon": ["cortes_cyl_procuradores"],
    "Parlamento de Andalucia": ["parlamento_andalucia_diputados"],
    "Parlamento de Galicia": ["parlamento_galicia_deputados"],
    "Parlamento de Navarra": ["parlamento_navarra_parlamentarios_forales"],
    "Parlamento Vasco": ["parlamento_vasco_parlamentarios"],
    "Infoelectoral": ["infoelectoral_descargas", "infoelectoral_procesos"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tracker status checker (SQL vs checklist).")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite path")
    parser.add_argument("--tracker", default=str(DEFAULT_TRACKER), help="Tracker markdown path")
    parser.add_argument(
        "--print-done-sources",
        action="store_true",
        help="Print source_ids marked DONE in tracker, one per line, then exit",
    )
    parser.add_argument(
        "--fail-on-mismatch",
        action="store_true",
        help="Exit non-zero if checklist status and SQL-derived status differ",
    )
    parser.add_argument(
        "--fail-on-done-zero-real",
        action="store_true",
        help="Exit non-zero if a DONE source has zero records loaded from real network runs",
    )
    return parser.parse_args()


def parse_tracker_statuses(tracker_path: Path) -> dict[str, str]:
    if not tracker_path.exists():
        raise FileNotFoundError(f"Tracker not found: {tracker_path}")

    lines = tracker_path.read_text(encoding="utf-8").splitlines()
    header = "| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |"

    in_table = False
    statuses: dict[str, str] = {}
    for line in lines:
        if line.strip() == header:
            in_table = True
            continue
        if not in_table:
            continue
        if not line.strip().startswith("|"):
            break
        if line.strip().startswith("|---"):
            continue

        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        fuente = cells[2]
        estado = cells[3].upper()
        for hint, source_ids in TRACKER_SOURCE_HINTS.items():
            if hint in fuente:
                for source_id in source_ids:
                    statuses[source_id] = estado
                break
    return statuses


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def fetch_source_metrics(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
          s.source_id AS source_id,
          COUNT(ir.run_id) AS runs_total,
          SUM(CASE WHEN ir.status = 'ok' THEN 1 ELSE 0 END) AS runs_ok,
          COALESCE(MAX(ir.records_loaded), 0) AS max_loaded_any,
          COALESCE(
            MAX(
              CASE
                WHEN rf.source_url LIKE 'http%' THEN ir.records_loaded
                ELSE NULL
              END
            ),
            0
          ) AS max_loaded_network,
          SUM(CASE WHEN rf.source_url LIKE 'http%' THEN 1 ELSE 0 END) AS network_fetches,
          SUM(CASE WHEN rf.source_url LIKE 'file://%' THEN 1 ELSE 0 END) AS fallback_fetches,
          COALESCE((
            SELECT ir2.records_loaded
            FROM ingestion_runs ir2
            WHERE ir2.source_id = s.source_id
            ORDER BY ir2.run_id DESC
            LIMIT 1
          ), 0) AS last_loaded,
          COALESCE((
            SELECT ir2.status
            FROM ingestion_runs ir2
            WHERE ir2.source_id = s.source_id
            ORDER BY ir2.run_id DESC
            LIMIT 1
          ), '') AS last_status
        FROM sources s
        LEFT JOIN ingestion_runs ir ON ir.source_id = s.source_id
        LEFT JOIN raw_fetches rf ON rf.run_id = ir.run_id
        GROUP BY s.source_id
        ORDER BY s.source_id
        """
    ).fetchall()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        result[row["source_id"]] = dict(row)
    return result


def sql_status_from_metrics(metrics: dict[str, Any]) -> str:
    runs_total = int(metrics.get("runs_total") or 0)
    max_loaded_network = int(metrics.get("max_loaded_network") or 0)
    max_loaded_any = int(metrics.get("max_loaded_any") or 0)
    if runs_total == 0:
        return "TODO"
    if max_loaded_network > 0:
        return "DONE"
    if max_loaded_any > 0:
        return "PARTIAL"
    return "PARTIAL"


def format_row(cols: list[str], widths: list[int]) -> str:
    parts = []
    for i, col in enumerate(cols):
        parts.append(col.ljust(widths[i]))
    return " | ".join(parts)


def print_report(
    tracker_status: dict[str, str], metrics_by_source: dict[str, dict[str, Any]]
) -> tuple[list[str], list[str]]:
    headers = [
        "source_id",
        "checklist",
        "sql",
        "runs_ok/total",
        "max_net",
        "max_any",
        "last_loaded",
        "net/fallback_fetches",
        "result",
    ]
    table_rows: list[list[str]] = []
    mismatches: list[str] = []
    done_zero_real: list[str] = []

    source_ids = sorted(set(metrics_by_source.keys()) | set(tracker_status.keys()))
    for source_id in source_ids:
        metrics = metrics_by_source.get(source_id, {})
        checklist = tracker_status.get(source_id, "N/A")
        sql_status = sql_status_from_metrics(metrics) if metrics else "TODO"

        runs_ok = int(metrics.get("runs_ok") or 0)
        runs_total = int(metrics.get("runs_total") or 0)
        max_net = int(metrics.get("max_loaded_network") or 0)
        max_any = int(metrics.get("max_loaded_any") or 0)
        last_loaded = int(metrics.get("last_loaded") or 0)
        net_fetches = int(metrics.get("network_fetches") or 0)
        fallback_fetches = int(metrics.get("fallback_fetches") or 0)

        result = "OK"
        if checklist != "N/A" and checklist != sql_status:
            result = "MISMATCH"
            mismatches.append(source_id)
        if checklist == "DONE" and max_net == 0:
            result = "DONE_ZERO_REAL"
            done_zero_real.append(source_id)

        table_rows.append(
            [
                source_id,
                checklist,
                sql_status,
                f"{runs_ok}/{runs_total}",
                str(max_net),
                str(max_any),
                str(last_loaded),
                f"{net_fetches}/{fallback_fetches}",
                result,
            ]
        )

    widths = [len(h) for h in headers]
    for row in table_rows:
        for i, col in enumerate(row):
            widths[i] = max(widths[i], len(col))

    print(format_row(headers, widths))
    print("-+-".join("-" * w for w in widths))
    for row in table_rows:
        print(format_row(row, widths))

    print()
    print(f"tracker_sources: {len(tracker_status)}")
    print(f"sources_in_db: {len(metrics_by_source)}")
    print(f"mismatches: {len(mismatches)}")
    print(f"done_zero_real: {len(done_zero_real)}")
    return mismatches, done_zero_real


def main() -> int:
    args = parse_args()
    tracker_path = Path(args.tracker)
    db_path = Path(args.db)

    try:
        tracker_status = parse_tracker_statuses(tracker_path)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR parsing tracker: {exc}", file=sys.stderr)
        return 2

    if args.print_done_sources:
        done_sources = sorted(s for s, st in tracker_status.items() if st == "DONE")
        for source_id in done_sources:
            print(source_id)
        return 0

    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 2

    try:
        with open_db(db_path) as conn:
            metrics_by_source = fetch_source_metrics(conn)
    except sqlite3.Error as exc:
        print(f"ERROR reading SQLite: {exc}", file=sys.stderr)
        return 2

    mismatches, done_zero_real = print_report(tracker_status, metrics_by_source)

    if args.fail_on_mismatch and mismatches:
        print("FAIL: checklist/sql mismatches detected.", file=sys.stderr)
        return 1
    if args.fail_on_done_zero_real and done_zero_real:
        print("FAIL: DONE sources with zero real-network loaded records detected.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
