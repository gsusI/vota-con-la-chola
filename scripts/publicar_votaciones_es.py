#!/usr/bin/env python3
"""Publica una instantanea canonica de votaciones en etl/data/published/.

Incluye:
- Evento de voto.
- Iniciativas/temas enlazados (si existen en `parl_vote_event_initiatives`).
- Voto nominal por miembro/persona.
- Trazabilidad por nivel (evento, iniciativa, voto nominal).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Ensure repo root is importable when executing this file directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl.parlamentario_es.config import DEFAULT_SCHEMA
from etl.parlamentario_es.db import apply_schema, open_db
from etl.parlamentario_es.publish import build_votaciones_snapshot, write_json_if_changed


DEFAULT_DB = Path("etl/data/staging/politicos-es.db")
DEFAULT_OUT_DIR = Path("etl/data/published")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Publicar snapshot canonico de votaciones (JSON)")
    p.add_argument("--db", default=str(DEFAULT_DB), help="Ruta del SQLite de entrada")
    p.add_argument(
        "--snapshot-date",
        required=True,
        help="Fecha ISO YYYY-MM-DD (se usa como fecha de referencia/metadata del snapshot)",
    )
    p.add_argument(
        "--json-out",
        default="",
        help="Ruta exacta del JSON de salida (si no se da, usa etl/data/published/votaciones-es-<snapshot>.json)",
    )
    p.add_argument(
        "--source-ids",
        default="congreso_votaciones,senado_votaciones",
        help="Lista CSV de source_id para incluir",
    )
    p.add_argument(
        "--only-linked-events",
        action="store_true",
        help="Solo publicar eventos con tema/iniciativa enlazada",
    )
    p.add_argument(
        "--max-events",
        type=int,
        default=None,
        help="Limite de eventos (debug)",
    )
    p.add_argument(
        "--max-member-votes-per-event",
        type=int,
        default=None,
        help="Limite de votos nominales por evento (debug)",
    )
    p.add_argument(
        "--enforce-quality-gate",
        action="store_true",
        help="Falla con exit!=0 si quality.gate.passed es false",
    )
    p.add_argument(
        "--include-unmatched",
        action="store_true",
        help="Incluye diagnóstico en seco de votos nominales sin person_id en la sección quality.",
    )
    p.add_argument(
        "--unmatched-sample-limit",
        type=int,
        default=0,
        help="Límite de ejemplos de mismatches incluido al usar --include-unmatched. 0 sin muestra.",
    )
    return p.parse_args()


def _parse_source_ids(csv_value: str) -> tuple[str, ...]:
    vals = [x.strip() for x in str(csv_value).split(",")]
    vals = [x for x in vals if x]
    out: list[str] = []
    seen: set[str] = set()
    for v in vals:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return tuple(out)


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: DB no existe: {db_path}", file=sys.stderr)
        return 2

    snapshot_date = str(args.snapshot_date).strip()
    if not snapshot_date:
        print("ERROR: snapshot-date vacio", file=sys.stderr)
        return 2

    source_ids = _parse_source_ids(args.source_ids)
    if not source_ids:
        print("ERROR: source-ids vacio", file=sys.stderr)
        return 2
    if int(args.unmatched_sample_limit) < 0:
        print("ERROR: unmatched-sample-limit debe ser >= 0", file=sys.stderr)
        return 2

    if args.json_out:
        out_path = Path(args.json_out)
    else:
        out_path = DEFAULT_OUT_DIR / f"votaciones-es-{snapshot_date}.json"

    conn: sqlite3.Connection = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        snap = build_votaciones_snapshot(
            conn,
            snapshot_date=snapshot_date,
            source_ids=source_ids,
            only_linked_events=bool(args.only_linked_events),
            max_events=args.max_events,
            max_member_votes_per_event=args.max_member_votes_per_event,
            include_unmatched_people=bool(args.include_unmatched),
            unmatched_sample_limit=int(args.unmatched_sample_limit),
        )
    finally:
        conn.close()

    if bool(args.enforce_quality_gate):
        gate = (snap.get("quality") or {}).get("gate") or {}
        passed = bool(gate.get("passed"))
        if not passed:
            failed_metrics: list[str] = []
            failures = gate.get("failures")
            if isinstance(failures, list):
                for f in failures:
                    if not isinstance(f, dict):
                        continue
                    metric = str(f.get("metric") or "").strip()
                    if metric:
                        failed_metrics.append(metric)
            failed_metrics = sorted(dict.fromkeys(failed_metrics))
            failed_csv = ",".join(failed_metrics) if failed_metrics else "unknown"
            print(
                f"ERROR: quality gate failed for source_ids={','.join(source_ids)} "
                f"(failed_metrics={failed_csv})",
                file=sys.stderr,
            )
            return 3

    changed = write_json_if_changed(out_path, snap)
    if changed:
        print(f"OK wrote: {out_path}")
    else:
        print(f"OK unchanged: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
