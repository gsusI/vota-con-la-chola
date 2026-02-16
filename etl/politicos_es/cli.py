from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from .config import DEFAULT_DB, DEFAULT_RAW_DIR, DEFAULT_SCHEMA, DEFAULT_TIMEOUT
from .db import (
    apply_schema,
    backfill_normalized_dimensions,
    open_db,
    seed_dimensions,
    seed_sources,
)
from .pipeline import ingest_one_source, print_stats
from .registry import get_connectors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingesta de politicos en SQLite")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db", help="Crea/actualiza el esquema SQLite")
    init_db.add_argument("--db", default=str(DEFAULT_DB), help="Ruta al archivo SQLite")
    init_db.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Ruta SQL de esquema")

    ingest = subparsers.add_parser("ingest", help="Ingiere desde una fuente")
    ingest.add_argument("--db", default=str(DEFAULT_DB), help="Ruta al archivo SQLite")
    ingest.add_argument("--source", required=True, help="Fuente a procesar o 'all'")
    ingest.add_argument("--url", help="URL de origen (override)")
    ingest.add_argument("--from-file", help="Ruta local en lugar de descargar por URL")
    ingest.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR), help="Directorio raw")
    ingest.add_argument("--snapshot-date", help="Fecha de snapshot (YYYY-MM-DD)")
    ingest.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Timeout HTTP")
    ingest.add_argument(
        "--strict-network",
        action="store_true",
        help="Si falla la red, no usar fallback local de muestras",
    )

    stats = subparsers.add_parser("stats", help="Muestra estadisticas de la base")
    stats.add_argument("--db", default=str(DEFAULT_DB), help="Ruta al archivo SQLite")

    backfill = subparsers.add_parser(
        "backfill-normalized",
        help="Rellena columnas/tablas normalizadas para datos historicos",
    )
    backfill.add_argument("--db", default=str(DEFAULT_DB), help="Ruta al archivo SQLite")

    backfill_territories = subparsers.add_parser(
        "backfill-territories",
        help="Carga referencias territoriales (ES) y enriquece territories (level/parent)",
    )
    backfill_territories.add_argument("--db", default=str(DEFAULT_DB), help="Ruta al archivo SQLite")
    backfill_territories.add_argument(
        "--ref",
        default="etl/data/published/poblacion_municipios_es.json",
        help="JSON de referencia (población municipal) usado como catálogo territorial",
    )

    return parser.parse_args()


def cmd_init_db(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    schema_path = Path(args.schema)
    if not schema_path.exists():
        print(f"Schema no encontrado: {schema_path}", file=sys.stderr)
        return 2
    conn = open_db(db_path)
    try:
        apply_schema(conn, schema_path)
        seed_sources(conn)
        seed_dimensions(conn)
    finally:
        conn.close()
    print(f"SQLite inicializado en: {db_path}")
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    connectors = get_connectors()
    db_path = Path(args.db)
    raw_dir = Path(args.raw_dir)
    snapshot_date = args.snapshot_date
    if snapshot_date:
        _ = dt.date.fromisoformat(snapshot_date)

    if args.source != "all" and args.source not in connectors:
        choices = ", ".join(["all", *sorted(connectors.keys())])
        print(f"--source invalido: {args.source}. Opciones: {choices}", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        source_ids = list(sorted(connectors.keys())) if args.source == "all" else [args.source]

        grand_seen = 0
        grand_loaded = 0
        for source_id in source_ids:
            connector = connectors[source_id]
            from_file = Path(args.from_file) if args.from_file and args.source != "all" else None
            seen, loaded, note = ingest_one_source(
                conn=conn,
                connector=connector,
                raw_dir=raw_dir,
                timeout=args.timeout,
                from_file=from_file,
                url_override=args.url if args.source != "all" else None,
                snapshot_date=snapshot_date,
                strict_network=bool(getattr(args, "strict_network")),
            )
            grand_seen += seen
            grand_loaded += loaded
            suffix = f" [{note}]" if note and note != "network" else ""
            print(f"{source_id}: {loaded}/{seen} registros validos{suffix}")
    finally:
        conn.close()

    print(f"Total: {grand_loaded}/{grand_seen} registros validos")
    return 0


def cmd_backfill_normalized(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Base no encontrada: {db_path}", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        backfill_normalized_dimensions(conn)
    finally:
        conn.close()

    print(f"Backfill normalizado completado en: {db_path}")
    return 0


def cmd_backfill_territories(args: argparse.Namespace) -> int:
    from .territories_ref import backfill_territories_reference  # noqa: PLC0415

    db_path = Path(args.db)
    ref_path = Path(args.ref)
    if not db_path.exists():
        print(f"Base no encontrada: {db_path}", file=sys.stderr)
        return 2
    if not ref_path.exists():
        print(f"Ref no encontrada: {ref_path}", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        result = backfill_territories_reference(conn, ref_path=ref_path)
    finally:
        conn.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Base no encontrada: {db_path}", file=sys.stderr)
        return 2
    conn = open_db(db_path)
    try:
        print_stats(conn)
    finally:
        conn.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    _ = argv
    args = parse_args()
    if args.command == "init-db":
        return cmd_init_db(args)
    if args.command == "ingest":
        return cmd_ingest(args)
    if args.command == "stats":
        return cmd_stats(args)
    if args.command == "backfill-normalized":
        return cmd_backfill_normalized(args)
    if args.command == "backfill-territories":
        return cmd_backfill_territories(args)
    print(f"Comando no soportado: {args.command}", file=sys.stderr)
    return 2
