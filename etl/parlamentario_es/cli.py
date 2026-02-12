from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Any

from .config import DEFAULT_DB, DEFAULT_RAW_DIR, DEFAULT_SCHEMA, DEFAULT_TIMEOUT, SOURCE_CONFIG
from .db import apply_schema, open_db, seed_sources
from .linking import link_congreso_votes_to_initiatives
from .pipeline import ingest_one_source
from .registry import get_connectors


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ETL parlamentario (votaciones, iniciativas, sesiones)")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init-db", help="Crear/actualizar schema + seed sources")
    p_init.add_argument("--db", default=str(DEFAULT_DB))

    p_ing = sub.add_parser("ingest", help="Ingesta de una fuente")
    p_ing.add_argument("--db", default=str(DEFAULT_DB))
    p_ing.add_argument("--source", default="all", help="source_id o 'all'")
    p_ing.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))
    p_ing.add_argument("--timeout", type=int, default=int(DEFAULT_TIMEOUT))
    p_ing.add_argument("--snapshot-date", default=None, help="YYYY-MM-DD")
    p_ing.add_argument("--strict-network", action="store_true")
    p_ing.add_argument("--from-file", default=None, help="Archivo o directorio local (reproducible)")
    p_ing.add_argument("--url-override", default=None, help="Override URL (debug)")
    p_ing.add_argument("--max-votes", type=int, default=None, help="Limita numero de votaciones (debug)")
    p_ing.add_argument("--max-files", type=int, default=None, help="Limita numero de ficheros (debug)")
    p_ing.add_argument("--max-records", type=int, default=None, help="Limita numero de registros (debug)")
    p_ing.add_argument("--senado-detail-dir", default=None, help="Dir local con ses_<n>.xml para enriquecer votaciones Senado")
    p_ing.add_argument("--senado-detail-cookie", default=None, help="Cookie para descarga de detalle Senado (opcional)")
    p_ing.add_argument("--senado-detail-host", default=None, help="Host base para ses_<n>.xml (default videoservlet)")
    p_ing.add_argument("--senado-skip-details", action="store_true", help="No intentar enriquecer detalle por sesion en Senado")
    p_ing.add_argument("--since-date", default=None, help="Filtra por fecha >= YYYY-MM-DD (usa path yyyymmdd)")
    p_ing.add_argument("--until-date", default=None, help="Filtra por fecha <= YYYY-MM-DD (usa path yyyymmdd)")

    p_stats = sub.add_parser("stats", help="Metricas rapidas")
    p_stats.add_argument("--db", default=str(DEFAULT_DB))

    p_link = sub.add_parser("link-votes", help="Link votes -> initiatives/topics (best-effort)")
    p_link.add_argument("--db", default=str(DEFAULT_DB))
    p_link.add_argument("--max-events", type=int, default=None)
    p_link.add_argument("--dry-run", action="store_true")

    return p.parse_args(argv)


def _stats(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT COUNT(*) AS c FROM parl_vote_events").fetchone()
    events = int(rows["c"]) if rows else 0
    rows = conn.execute("SELECT COUNT(*) AS c FROM parl_vote_member_votes").fetchone()
    mv = int(rows["c"]) if rows else 0
    rows = conn.execute(
        "SELECT COUNT(*) AS c FROM parl_vote_member_votes WHERE person_id IS NULL"
    ).fetchone()
    mv_unmatched = int(rows["c"]) if rows else 0
    rows = conn.execute("SELECT COUNT(*) AS c FROM parl_initiatives").fetchone()
    initiatives = int(rows["c"]) if rows else 0
    rows = conn.execute("SELECT COUNT(*) AS c FROM parl_vote_event_initiatives").fetchone()
    links = int(rows["c"]) if rows else 0

    print(f"parl_vote_events: {events}")
    print(f"parl_vote_member_votes: {mv}")
    print(f"parl_vote_member_votes_unmatched_person: {mv_unmatched}")
    print(f"parl_initiatives: {initiatives}")
    print(f"parl_vote_event_initiatives: {links}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv or sys.argv[1:]))

    if args.cmd == "init-db":
        conn = open_db(Path(args.db))
        try:
            apply_schema(conn, DEFAULT_SCHEMA)
            seed_sources(conn)
        finally:
            conn.close()
        print("OK init-db")
        return 0

    if args.cmd == "stats":
        conn = open_db(Path(args.db))
        try:
            _stats(conn)
        finally:
            conn.close()
        return 0

    if args.cmd == "link-votes":
        conn = open_db(Path(args.db))
        try:
            apply_schema(conn, DEFAULT_SCHEMA)
            seed_sources(conn)
            result = link_congreso_votes_to_initiatives(
                conn, max_events=args.max_events, dry_run=bool(args.dry_run)
            )
        finally:
            conn.close()
        print(result)
        return 0

    if args.cmd == "ingest":
        source = str(args.source)
        connectors = get_connectors()
        if source != "all" and source not in connectors:
            raise SystemExit(f"Fuente desconocida: {source} (disponibles: {sorted(connectors)})")

        from_file = Path(args.from_file) if args.from_file else None
        raw_dir = Path(args.raw_dir)
        conn = open_db(Path(args.db))
        try:
            apply_schema(conn, DEFAULT_SCHEMA)
            seed_sources(conn)

            options: dict[str, Any] = {
                "max_votes": args.max_votes,
                "max_files": args.max_files,
                "max_records": args.max_records,
                "senado_detail_dir": args.senado_detail_dir,
                "senado_detail_cookie": args.senado_detail_cookie,
                "senado_detail_host": args.senado_detail_host,
                "senado_skip_details": args.senado_skip_details,
                "since_date": args.since_date,
                "until_date": args.until_date,
            }

            if source == "all":
                for sid, connector in connectors.items():
                    ingest_one_source(
                        conn=conn,
                        connector=connector,
                        raw_dir=raw_dir,
                        timeout=int(args.timeout),
                        from_file=from_file,
                        url_override=args.url_override,
                        snapshot_date=args.snapshot_date,
                        strict_network=bool(args.strict_network),
                        options=options,
                    )
            else:
                ingest_one_source(
                    conn=conn,
                    connector=connectors[source],
                    raw_dir=raw_dir,
                    timeout=int(args.timeout),
                    from_file=from_file,
                    url_override=args.url_override,
                    snapshot_date=args.snapshot_date,
                    strict_network=bool(args.strict_network),
                    options=options,
                )
        finally:
            conn.close()
        print("OK ingest")
        return 0

    raise SystemExit(f"Comando inesperado: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
