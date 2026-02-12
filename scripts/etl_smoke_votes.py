#!/usr/bin/env python3
"""Smoke gate for parliamentary vote evidence (events + nominal votes).

This is intentionally lightweight and deterministic: it validates that vote tables
contain non-empty data for the requested parliamentary sources.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        required=True,
        type=Path,
        help="Ruta del SQLite ETL (ej: etl/data/staging/politicos-es.db)",
    )
    parser.add_argument(
        "--source-ids",
        default="congreso_votaciones,senado_votaciones",
        help="Lista separada por comas de fuentes de votaciones",
    )
    parser.add_argument(
        "--min-events",
        type=int,
        default=1,
        help="Mínimo de eventos esperados por fuente",
    )
    parser.add_argument(
        "--min-total-member-votes",
        type=int,
        default=1,
        help="Mínimo total de votos nominales agregados para todas las fuentes",
    )
    args = parser.parse_args()

    source_ids = [s.strip() for s in args.source_ids.split(",") if s.strip()]
    if not source_ids:
        raise SystemExit("[smoke-votes] --source-ids no puede estar vacio")

    conn = sqlite3.connect(args.db)
    try:
        total_member_votes = 0
        for source_id in source_ids:
            events = conn.execute(
                "SELECT COUNT(*) FROM parl_vote_events WHERE source_id = ?",
                (source_id,),
            ).fetchone()[0]
            if int(events) < args.min_events:
                raise SystemExit(
                    f"[smoke-votes] {source_id}: eventos insuficientes ({events}) < {args.min_events}"
                )

            member_votes = conn.execute(
                "SELECT COUNT(*) FROM parl_vote_member_votes mv "
                "JOIN parl_vote_events ve ON ve.vote_event_id = mv.vote_event_id "
                "WHERE ve.source_id = ?",
                (source_id,),
            ).fetchone()[0]
            total_member_votes += int(member_votes)

        if total_member_votes < args.min_total_member_votes:
            raise SystemExit(
                f"[smoke-votes] votos nominales insuficientes: {total_member_votes} < {args.min_total_member_votes}"
            )

        print("[smoke-votes] OK")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
