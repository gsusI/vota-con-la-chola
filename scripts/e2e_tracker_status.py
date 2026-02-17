#!/usr/bin/env python3
"""Status/gate checker for docs/etl/e2e-scrape-load-tracker.md against SQLite runs."""

from __future__ import annotations

import argparse
from datetime import date
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

# Ensure repo root is importable when executing this file directly.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.politicos_es.run_snapshot_schema import normalize_run_snapshot_file

DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_TRACKER = Path("docs/etl/e2e-scrape-load-tracker.md")
DEFAULT_WAIVERS = Path("docs/etl/mismatch-waivers.json")

# Explicit tracker row -> source_id contract.
# Row-label mapping has precedence over fuentes hint matching to avoid drift when
# free-text "Fuentes objetivo" wording changes.
TRACKER_TIPO_SOURCE_HINTS = {
    "Marco legal electoral": ["boe_api_legal"],
    # AI-OPS-09: explicit row-level contracts (avoid ambiguity between national and pilot rows).
    "Contratación autonómica (piloto 3 CCAA)": ["placsp_autonomico"],
    "Subvenciones autonómicas (piloto 3 CCAA)": ["bdns_autonomico"],
    "Contratacion publica (Espana)": ["placsp_sindicacion"],
    "Subvenciones y ayudas (Espana)": ["bdns_api_subvenciones"],
    "Indicadores (outcomes): Eurostat": ["eurostat_sdmx"],
    "Indicadores (confusores): Banco de España": ["bde_series_api"],
    "Indicadores (confusores): Banco de Espana": ["bde_series_api"],
    "Indicadores (confusores): AEMET": ["aemet_opendata_series"],
}

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
    "La Moncloa: referencias + RSS": ["moncloa_referencias", "moncloa_rss_referencias"],
    "Infoelectoral": ["infoelectoral_descargas", "infoelectoral_procesos"],
    "BOE API": ["boe_api_legal"],
    # AI-OPS-09 source families (fallback hint matching when Tipo de dato text changes).
    "PLACSP: sindicación/ATOM (CODICE)": ["placsp_sindicacion"],
    "PLACSP (filtrado por órganos autonómicos)": ["placsp_autonomico"],
    "BDNS/SNPSAP: API": ["bdns_api_subvenciones"],
    "BDNS/SNPSAP (filtrado por órgano convocante/territorio)": ["bdns_autonomico"],
    "Eurostat (API/SDMX)": ["eurostat_sdmx"],
    "Banco de España (API series)": ["bde_series_api"],
    "Banco de Espana (API series)": ["bde_series_api"],
    "AEMET OpenData": ["aemet_opendata_series"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tracker status checker (SQL vs checklist).")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite path")
    parser.add_argument("--tracker", default=str(DEFAULT_TRACKER), help="Tracker markdown path")
    parser.add_argument(
        "--waivers",
        default=str(DEFAULT_WAIVERS),
        help="Waivers JSON path (optional; missing file means no active waivers)",
    )
    parser.add_argument(
        "--as-of-date",
        default="",
        help="Date used to evaluate waiver expiry (YYYY-MM-DD). Defaults to today's date.",
    )
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
    parser.add_argument(
        "--normalize-run-snapshot-in",
        default="",
        help=(
            "Normaliza un *_run_snapshot.csv (legacy metric,value o tabular) al esquema "
            "canonico y termina"
        ),
    )
    parser.add_argument(
        "--normalize-run-snapshot-out",
        default="",
        help="Ruta de salida del snapshot canonico (por defecto, sobrescribe --normalize-run-snapshot-in)",
    )
    parser.add_argument(
        "--normalize-run-snapshot-legacy-out",
        default="",
        help="Opcional: ruta de salida adicional en formato legacy metric,value",
    )
    parser.add_argument(
        "--normalize-run-snapshot-source-id",
        default="",
        help="Override opcional para source_id durante normalizacion",
    )
    parser.add_argument(
        "--normalize-run-snapshot-mode",
        default="",
        help="Override opcional para mode durante normalizacion",
    )
    parser.add_argument(
        "--normalize-run-snapshot-snapshot-date",
        default="",
        help="Override opcional para snapshot_date (YYYY-MM-DD)",
    )
    return parser.parse_args()


def parse_tracker_statuses(tracker_path: Path) -> dict[str, str]:
    rows = parse_tracker_rows(tracker_path)
    return {source_id: str(meta.get("status") or "N/A") for source_id, meta in rows.items()}


def _is_explicitly_blocked(block_text: str) -> bool:
    # Keep this deterministic and conservative: only explicit "bloquead*" wording
    # in the tracker row activates blocked-aware status semantics.
    return "bloquead" in (block_text or "").strip().lower()


def _infer_tracker_source_ids(tipo_dato: str, fuente: str) -> list[str]:
    if tipo_dato in TRACKER_TIPO_SOURCE_HINTS:
        return list(TRACKER_TIPO_SOURCE_HINTS[tipo_dato])
    for hint, source_ids in TRACKER_SOURCE_HINTS.items():
        if hint in fuente:
            return list(source_ids)
    return []


def parse_tracker_rows(tracker_path: Path) -> dict[str, dict[str, Any]]:
    if not tracker_path.exists():
        raise FileNotFoundError(f"Tracker not found: {tracker_path}")

    lines = tracker_path.read_text(encoding="utf-8").splitlines()
    header = "| Tipo de dato | Dominio | Fuentes objetivo | Estado | Bloque principal |"

    in_table = False
    rows: dict[str, dict[str, Any]] = {}
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
        tipo_dato = cells[0]
        fuente = cells[2]
        estado = cells[3].upper()
        bloque = cells[4]
        blocked = _is_explicitly_blocked(bloque)
        source_ids = _infer_tracker_source_ids(tipo_dato, fuente)
        for source_id in source_ids:
            rows[source_id] = {
                "status": estado,
                "blocked": blocked,
                "bloque": bloque,
                "fuente": fuente,
            }
    return rows


def _parse_as_of_date(value: str) -> date:
    token = (value or "").strip()
    if not token:
        return date.today()
    try:
        return date.fromisoformat(token)
    except ValueError as exc:
        raise ValueError("Parametro '--as-of-date' debe tener formato YYYY-MM-DD") from exc


def load_mismatch_waivers(
    waivers_path: Path,
    *,
    as_of_date: date,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if not waivers_path.exists():
        return {}, {}

    raw = json.loads(waivers_path.read_text(encoding="utf-8"))
    entries: list[Any]
    if isinstance(raw, dict):
        entries = list(raw.get("waivers") or [])
    elif isinstance(raw, list):
        entries = list(raw)
    else:
        raise ValueError("Waivers JSON invalido: se esperaba objeto con 'waivers' o lista")

    active: dict[str, dict[str, Any]] = {}
    expired: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for idx, item in enumerate(entries):
        if not isinstance(item, dict):
            raise ValueError(f"Waiver invalido en indice {idx}: se esperaba objeto")

        source_id = str(item.get("source_id") or "").strip()
        reason = str(item.get("reason") or "").strip()
        owner = str(item.get("owner") or "").strip()
        expires_on_str = str(item.get("expires_on") or "").strip()

        if not source_id:
            raise ValueError(f"Waiver invalido en indice {idx}: falta 'source_id'")
        if not reason:
            raise ValueError(f"Waiver invalido para {source_id}: falta 'reason'")
        if not owner:
            raise ValueError(f"Waiver invalido para {source_id}: falta 'owner'")
        if not expires_on_str:
            raise ValueError(f"Waiver invalido para {source_id}: falta 'expires_on'")

        try:
            expires_on = date.fromisoformat(expires_on_str)
        except ValueError as exc:
            raise ValueError(f"Waiver invalido para {source_id}: 'expires_on' debe ser YYYY-MM-DD") from exc

        if source_id in seen:
            raise ValueError(f"Waiver duplicado para source_id={source_id}")
        seen.add(source_id)

        payload = {
            "source_id": source_id,
            "reason": reason,
            "owner": owner,
            "expires_on": expires_on.isoformat(),
        }
        if as_of_date <= expires_on:
            active[source_id] = payload
        else:
            expired[source_id] = payload

    return active, expired


def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def fetch_source_metrics(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    fetch_table = "run_fetches" if table_exists(conn, "run_fetches") else "raw_fetches"
    rows = conn.execute(
        f"""
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
        LEFT JOIN {fetch_table} rf ON rf.run_id = ir.run_id
        GROUP BY s.source_id
        ORDER BY s.source_id
        """
    ).fetchall()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        result[row["source_id"]] = dict(row)
    return result


def sql_status_from_metrics(metrics: dict[str, Any], *, tracker_blocked: bool = False) -> str:
    runs_total = int(metrics.get("runs_total") or 0)
    max_loaded_network = int(metrics.get("max_loaded_network") or 0)
    max_loaded_any = int(metrics.get("max_loaded_any") or 0)
    last_loaded = int(metrics.get("last_loaded") or 0)
    if runs_total == 0:
        return "TODO"
    # Blocked-aware guard: if tracker explicitly marks the source as blocked and the
    # latest run loaded 0, don't auto-promote to DONE just because an older network
    # run once loaded records.
    if tracker_blocked and last_loaded == 0 and max_loaded_network > 0:
        return "PARTIAL"
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
    tracker_rows: dict[str, dict[str, Any]],
    metrics_by_source: dict[str, dict[str, Any]],
    *,
    waivers_active: dict[str, dict[str, Any]],
    waivers_expired: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
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
    waived_mismatches: list[str] = []
    done_zero_real: list[str] = []

    source_ids = sorted(set(metrics_by_source.keys()) | set(tracker_rows.keys()))
    for source_id in source_ids:
        metrics = metrics_by_source.get(source_id, {})
        tracker_meta = tracker_rows.get(source_id, {})
        checklist = str(tracker_meta.get("status") or "N/A")
        tracker_blocked = bool(tracker_meta.get("blocked"))
        sql_status = sql_status_from_metrics(metrics, tracker_blocked=tracker_blocked) if metrics else "TODO"

        runs_ok = int(metrics.get("runs_ok") or 0)
        runs_total = int(metrics.get("runs_total") or 0)
        max_net = int(metrics.get("max_loaded_network") or 0)
        max_any = int(metrics.get("max_loaded_any") or 0)
        last_loaded = int(metrics.get("last_loaded") or 0)
        net_fetches = int(metrics.get("network_fetches") or 0)
        fallback_fetches = int(metrics.get("fallback_fetches") or 0)

        result = "OK"
        has_mismatch = checklist != "N/A" and checklist != sql_status
        if has_mismatch:
            if source_id in waivers_active:
                result = "WAIVED_MISMATCH"
                waived_mismatches.append(source_id)
            else:
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
    print(f"tracker_sources: {len(tracker_rows)}")
    print(f"sources_in_db: {len(metrics_by_source)}")
    print(f"mismatches: {len(mismatches)}")
    print(f"waived_mismatches: {len(waived_mismatches)}")
    print(f"waivers_active: {len(waivers_active)}")
    print(f"waivers_expired: {len(waivers_expired)}")
    print(f"done_zero_real: {len(done_zero_real)}")
    return mismatches, done_zero_real, waived_mismatches


def normalize_run_snapshot_cli(args: argparse.Namespace) -> int:
    input_raw = str(args.normalize_run_snapshot_in or "").strip()
    if not input_raw:
        print("ERROR: falta --normalize-run-snapshot-in", file=sys.stderr)
        return 2
    input_path = Path(input_raw)

    output_raw = str(args.normalize_run_snapshot_out or "").strip()
    output_path = Path(output_raw) if output_raw else input_path

    defaults: dict[str, str] = {}
    source_id_override = str(args.normalize_run_snapshot_source_id or "").strip()
    if source_id_override:
        defaults["source_id"] = source_id_override
    mode_override = str(args.normalize_run_snapshot_mode or "").strip()
    if mode_override:
        defaults["mode"] = mode_override
    snapshot_override = str(args.normalize_run_snapshot_snapshot_date or "").strip()
    if snapshot_override:
        defaults["snapshot_date"] = snapshot_override

    legacy_output_raw = str(args.normalize_run_snapshot_legacy_out or "").strip()
    legacy_output = Path(legacy_output_raw) if legacy_output_raw else None

    try:
        normalized_path, legacy_path, normalized = normalize_run_snapshot_file(
            input_path=input_path,
            output_path=output_path,
            defaults=defaults,
            legacy_output_path=legacy_output,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR normalizando run snapshot: {exc}", file=sys.stderr)
        return 2

    print(f"OK normalized run snapshot -> {normalized_path}")
    if legacy_path is not None:
        print(f"OK legacy metric,value snapshot -> {legacy_path}")
    print(f"source_id: {normalized.get('source_id', '')}")
    print(f"mode: {normalized.get('mode', '')}")
    print(f"exit_code: {normalized.get('exit_code', '')}")
    print(f"run_records_loaded: {normalized.get('run_records_loaded', '')}")
    print(f"snapshot_date: {normalized.get('snapshot_date', '')}")
    return 0


def main() -> int:
    args = parse_args()

    if str(args.normalize_run_snapshot_in or "").strip():
        return normalize_run_snapshot_cli(args)

    tracker_path = Path(args.tracker)
    db_path = Path(args.db)
    waivers_path = Path(args.waivers)

    try:
        as_of_date = _parse_as_of_date(args.as_of_date)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        tracker_rows = parse_tracker_rows(tracker_path)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR parsing tracker: {exc}", file=sys.stderr)
        return 2

    if args.print_done_sources:
        done_sources = sorted(s for s, meta in tracker_rows.items() if str(meta.get("status") or "") == "DONE")
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

    try:
        waivers_active, waivers_expired = load_mismatch_waivers(waivers_path, as_of_date=as_of_date)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR loading waivers: {exc}", file=sys.stderr)
        return 2

    mismatches, done_zero_real, _waived_mismatches = print_report(
        tracker_rows,
        metrics_by_source,
        waivers_active=waivers_active,
        waivers_expired=waivers_expired,
    )

    if args.fail_on_mismatch and mismatches:
        print("FAIL: checklist/sql mismatches detected.", file=sys.stderr)
        return 1
    if args.fail_on_done_zero_real and done_zero_real:
        print("FAIL: DONE sources with zero real-network loaded records detected.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
