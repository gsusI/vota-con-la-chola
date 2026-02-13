from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from .config import DEFAULT_DB, DEFAULT_RAW_DIR, DEFAULT_SCHEMA, DEFAULT_TIMEOUT, SOURCE_CONFIG
from .db import apply_schema, open_db, seed_sources
from .linking import link_congreso_votes_to_initiatives, link_senado_votes_to_initiatives
from .pipeline import (
    VOTE_SOURCE_TO_MANDATE_SOURCE,
    backfill_senado_vote_details,
    backfill_vote_member_person_ids,
    ingest_one_source,
)
from .quality import (
    compute_initiative_quality_kpis,
    compute_vote_quality_kpis,
    evaluate_initiative_quality_gate,
    evaluate_vote_quality_gate,
)
from .publish import write_json_if_changed
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
    p_ing.add_argument("--congreso-legs", default=None, help="Legislaturas Congreso separadas por coma (ej: 15,14)")
    p_ing.add_argument("--senado-legs", default=None, help="Legislaturas Senado separadas por coma (ej: 15,14)")
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

    p_quality = sub.add_parser("quality-report", help="KPI + gate de calidad de votaciones")
    p_quality.add_argument("--db", default=str(DEFAULT_DB))
    p_quality.add_argument(
        "--source-ids",
        default="congreso_votaciones,senado_votaciones",
        help="Lista CSV de source_id para incluir",
    )
    p_quality.add_argument(
        "--enforce-gate",
        action="store_true",
        help="Salir con codigo != 0 si el gate falla",
    )
    p_quality.add_argument(
        "--json-out",
        default="",
        help="Ruta exacta del JSON de salida (si no se da, solo imprime por stdout)",
    )
    p_quality.add_argument(
        "--include-unmatched",
        action="store_true",
        help=(
            "Incluye un reporte en seco de votos nominales sin person_id resuelto "
            "para ayudar a detectar gaps de linking."
        ),
    )
    p_quality.add_argument(
        "--unmatched-sample-limit",
        type=int,
        default=0,
        help="Máximo de ejemplos de votos sin person_id mostrados en quality-report. 0 desactiva muestra.",
    )
    p_quality.add_argument(
        "--include-initiatives",
        action="store_true",
        help="Incluye KPIs de iniciativas (congress/senado) en el reporte.",
    )
    p_quality.add_argument(
        "--initiative-source-ids",
        default="congreso_iniciativas,senado_iniciativas",
        help="Lista CSV de source_id de iniciativas para incluir",
    )

    p_backfill = sub.add_parser(
        "backfill-member-ids",
        help="Rellenar person_id en votes nominales con clave estable por nombre",
    )
    p_backfill.add_argument("--db", default=str(DEFAULT_DB))
    p_backfill.add_argument(
        "--source-ids",
        default="congreso_votaciones,senado_votaciones",
        help="Lista CSV de source_id para procesar",
    )
    p_backfill.add_argument("--dry-run", action="store_true", help="Simula cambios sin escribir person_id")
    p_backfill.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Tamaño de lote de actualizaciones SQL",
    )
    p_backfill.add_argument(
        "--unmatched-sample-limit",
        type=int,
        default=0,
        help="Limita ejemplos de votos no resueltos mostrados en salida JSON (0 para desactivar)",
    )
    p_backfill_senado = sub.add_parser(
        "backfill-senado-details",
        help="Rellenar votos nominales de votaciones del Senado (sin member_votes)",
    )
    p_backfill_senado.add_argument("--db", default=str(DEFAULT_DB))
    p_backfill_senado.add_argument("--timeout", type=int, default=int(DEFAULT_TIMEOUT))
    p_backfill_senado.add_argument("--snapshot-date", default=None, help="YYYY-MM-DD")
    p_backfill_senado.add_argument("--max-events", type=int, default=None, help="Límite de eventos a reintentar")
    p_backfill_senado.add_argument(
        "--auto",
        action="store_true",
        help="Reintentar automáticamente en múltiples rondas hasta agotar eventos o llegar al tope de ciclos",
    )
    p_backfill_senado.add_argument(
        "--max-loops",
        type=int,
        default=None,
        help="Máximo de rondas cuando --auto está activo (mínimo 1 si se usa)",
    )
    p_backfill_senado.add_argument("--legislature", default=None, help="Filtro por legislatura (ej: 15,14)")
    p_backfill_senado.add_argument("--vote-event-ids", default=None, help="CSV de vote_event_id para limitar")
    p_backfill_senado.add_argument("--dry-run", action="store_true", help="Simula cambios sin reescribir DB")
    p_backfill_senado.add_argument("--senado-detail-dir", default=None, help="Dir local con ses_<n>.xml para enriquecer votos")
    p_backfill_senado.add_argument("--senado-detail-cookie", default=None, help="Cookie para descarga detalle Senado (opcional)")
    p_backfill_senado.add_argument(
        "--senado-detail-host",
        default=None,
        help="Host base para ses_<n>.xml (default https://www.senado.es)",
    )
    p_backfill_senado.add_argument(
        "--senado-skip-details",
        action="store_true",
        help="No intentar enriquecimiento de detalle (no agregará member_votes)",
    )
    p_backfill_senado.add_argument(
        "--detail-workers",
        type=int,
        default=8,
        help="Workers paralelos para descargar/parsear detalles Senado (>=1)",
    )

    return p.parse_args(argv)


def _validate_vote_source_ids(requested: tuple[str, ...], *, for_command: str) -> tuple[str, ...]:
    allowed = tuple(sorted(VOTE_SOURCE_TO_MANDATE_SOURCE.keys()))
    if not requested:
        raise SystemExit(f"{for_command}: source-ids vacio")

    unknown = tuple(s for s in requested if s not in allowed)
    if unknown:
        raise SystemExit(
            f"{for_command}: source-ids desconocidos para votaciones {', '.join(unknown)} (esperados: {', '.join(allowed)})"
        )
    return requested


def _validate_initiative_source_ids(
    requested: tuple[str, ...],
    *,
    for_command: str,
) -> tuple[str, ...]:
    allowed = ("congreso_iniciativas", "senado_iniciativas")
    if not requested:
        raise SystemExit(f"{for_command}: source-ids de iniciativas vacio")

    unknown = tuple(s for s in requested if s not in allowed)
    if unknown:
        raise SystemExit(
            f"{for_command}: source-ids de iniciativas desconocidos: {', '.join(unknown)} (esperados: {', '.join(allowed)})"
        )
    return requested


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


def _quality_report(conn: sqlite3.Connection, *, source_ids: tuple[str, ...]) -> dict[str, Any]:
    kpis = compute_vote_quality_kpis(conn, source_ids=source_ids)
    gate = evaluate_vote_quality_gate(kpis)
    return {
        "source_ids": list(source_ids),
        "kpis": kpis,
        "gate": gate,
    }


def _initiative_quality_report(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...],
) -> dict[str, Any]:
    kpis = compute_initiative_quality_kpis(conn, source_ids=source_ids)
    gate = evaluate_initiative_quality_gate(kpis)
    return {
        "source_ids": list(source_ids),
        "kpis": kpis,
        "gate": gate,
    }


def _quality_report_with_unmatched_people(
    conn: sqlite3.Connection,
    *,
    source_ids: tuple[str, ...],
    unmatched_sample_limit: int = 0,
) -> dict[str, Any]:
    report = _quality_report(conn, source_ids=source_ids)
    unmatched = backfill_vote_member_person_ids(
        conn,
        vote_source_ids=source_ids,
        dry_run=True,
        unmatched_sample_limit=unmatched_sample_limit,
    )
    return {
        "source_ids": report.get("source_ids", list(source_ids)),
        "kpis": report["kpis"],
        "gate": report["gate"],
        "unmatched_vote_ids": unmatched,
    }


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
            congreso = link_congreso_votes_to_initiatives(
                conn, max_events=args.max_events, dry_run=bool(args.dry_run)
            )
            senado = link_senado_votes_to_initiatives(
                conn, max_events=args.max_events, dry_run=bool(args.dry_run)
            )
            result = {
                "events_seen": int(congreso.get("events_seen", 0)) + int(senado.get("events_seen", 0)),
                "links_prepared": int(congreso.get("links_prepared", 0)) + int(senado.get("links_prepared", 0)),
                "links_written": int(congreso.get("links_written", 0)) + int(senado.get("links_written", 0)),
                "dry_run": bool(args.dry_run),
                "by_source": {
                    "congreso": congreso,
                    "senado": senado,
                },
            }
        finally:
            conn.close()
        print(result)
        return 0

    if args.cmd == "quality-report":
        source_ids = _validate_vote_source_ids(
            _parse_source_ids(str(args.source_ids)),
            for_command="quality-report",
        )
        include_initiatives = bool(args.include_initiatives)
        initiative_source_ids = _validate_initiative_source_ids(
            _parse_source_ids(str(args.initiative_source_ids)),
            for_command="quality-report",
        )

        conn = open_db(Path(args.db))
        try:
            apply_schema(conn, DEFAULT_SCHEMA)
            seed_sources(conn)
            if bool(args.include_unmatched):
                unmatched_sample_limit = int(args.unmatched_sample_limit)
                if unmatched_sample_limit < 0:
                    raise SystemExit("unmatched-sample-limit debe ser >= 0")
                result = _quality_report_with_unmatched_people(
                    conn,
                    source_ids=source_ids,
                    unmatched_sample_limit=unmatched_sample_limit,
                )
            else:
                result = _quality_report(conn, source_ids=source_ids)
            if include_initiatives:
                result["initiatives"] = _initiative_quality_report(
                    conn, source_ids=initiative_source_ids
                )
        finally:
            conn.close()

        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
        if getattr(args, "json_out", ""):
            out_path = Path(str(args.json_out))
            changed = write_json_if_changed(out_path, result)
            if changed:
                print(f"OK wrote: {out_path}")
            else:
                print(f"OK unchanged: {out_path}")
        if bool(args.enforce_gate) and not bool(result.get("gate", {}).get("passed")):
            return 1
        if (
            bool(args.enforce_gate)
            and include_initiatives
            and not bool(result.get("initiatives", {}).get("gate", {}).get("passed"))
        ):
            return 1
        return 0

    if args.cmd == "backfill-member-ids":
        source_ids = _validate_vote_source_ids(
            _parse_source_ids(str(args.source_ids)),
            for_command="backfill-member-ids",
        )
        batch_size = int(args.batch_size)
        if batch_size <= 0:
            raise SystemExit("batch-size debe ser mayor a 0")
        unmatched_sample_limit = int(args.unmatched_sample_limit)
        if unmatched_sample_limit < 0:
            raise SystemExit("unmatched-sample-limit debe ser >= 0")
        conn = open_db(Path(args.db))
        try:
            apply_schema(conn, DEFAULT_SCHEMA)
            seed_sources(conn)
            result = backfill_vote_member_person_ids(
                conn,
                vote_source_ids=source_ids,
                dry_run=bool(args.dry_run),
                batch_size=batch_size,
                unmatched_sample_limit=unmatched_sample_limit,
            )
        finally:
            conn.close()
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
        return 0

    if args.cmd == "backfill-senado-details":
        if args.max_events is not None:
            max_events = int(args.max_events)
            if max_events <= 0:
                raise SystemExit("max-events debe ser > 0")
        else:
            max_events = None
        if args.auto and args.max_loops is not None:
            max_loops = int(args.max_loops)
            if max_loops <= 0:
                raise SystemExit("max-loops debe ser > 0")
        else:
            max_loops = None
        detail_workers = int(args.detail_workers)
        if detail_workers <= 0:
            raise SystemExit("detail-workers debe ser > 0")

        legislation = (
            _parse_source_ids(str(args.legislature))
            if args.legislature is not None and str(args.legislature).strip()
            else tuple()
        )
        event_ids = (
            _parse_source_ids(str(args.vote_event_ids))
            if args.vote_event_ids is not None and str(args.vote_event_ids).strip()
            else tuple()
        )
        if args.auto and event_ids:
            max_loops = max_loops or 1
        conn = open_db(Path(args.db))
        try:
            apply_schema(conn, DEFAULT_SCHEMA)
            seed_sources(conn)
            if not bool(args.auto):
                result = backfill_senado_vote_details(
                    conn,
                    timeout=int(args.timeout),
                    snapshot_date=args.snapshot_date,
                    limit=max_events,
                    legislature_filter=legislation,
                    vote_event_ids=event_ids,
                    senado_detail_dir=args.senado_detail_dir,
                    senado_detail_host=args.senado_detail_host,
                    senado_detail_cookie=args.senado_detail_cookie,
                    senado_skip_details=bool(args.senado_skip_details),
                    dry_run=bool(args.dry_run),
                    detail_workers=detail_workers,
                )
            else:
                remaining_limit = max_events
                loops_run = 0
                stop_reason = "not_started"
                aggregate: dict[str, Any] = {
                    "source_id": "senado_votaciones",
                    "dry_run": bool(args.dry_run),
                    "auto": True,
                    "loops_requested": max_loops,
                    "loops_run": 0,
                    "events_considered": 0,
                    "events_with_payload": 0,
                    "events_without_payload": 0,
                    "events_with_member_votes": 0,
                    "events_without_member_votes": 0,
                    "events_reingested": 0,
                    "member_votes_loaded": 0,
                    "would_reingest": 0,
                    "errors_summary": {},
                    "detail_failures": [],
                    "results_by_loop": [],
                }
                details_seen: set[str] = set()
                cursor_after = None
                while True:
                    if max_loops is not None and loops_run >= max_loops:
                        stop_reason = "max_loops_reached"
                        break

                    loops_run += 1
                    call_limit = remaining_limit
                    loop_result = backfill_senado_vote_details(
                        conn,
                        timeout=int(args.timeout),
                        snapshot_date=args.snapshot_date,
                        limit=call_limit,
                        vote_event_min=cursor_after,
                        legislature_filter=legislation,
                        vote_event_ids=event_ids,
                        senado_detail_dir=args.senado_detail_dir,
                            senado_detail_host=args.senado_detail_host,
                            senado_detail_cookie=args.senado_detail_cookie,
                            senado_skip_details=bool(args.senado_skip_details),
                            dry_run=bool(args.dry_run),
                            detail_workers=detail_workers,
                        )
                    events_considered = int(loop_result.get("events_considered", 0))
                    events_reingested = int(loop_result.get("events_reingested", 0))

                    aggregate["results_by_loop"].append({
                        "loop": loops_run,
                        "events_considered": events_considered,
                        "events_with_payload": int(loop_result.get("events_with_payload", 0)),
                        "events_with_member_votes": int(loop_result.get("events_with_member_votes", 0)),
                        "events_reingested": events_reingested,
                        "member_votes_loaded": int(loop_result.get("member_votes_loaded", 0)),
                        "errors_summary": loop_result.get("errors_summary", {}),
                        "detail_failures": list(loop_result.get("detail_failures", [])),
                    })

                    aggregate["loops_run"] = loops_run
                    aggregate["events_considered"] += events_considered
                    aggregate["events_with_payload"] += int(loop_result.get("events_with_payload", 0))
                    aggregate["events_without_payload"] += int(loop_result.get("events_without_payload", 0))
                    aggregate["events_with_member_votes"] += int(loop_result.get("events_with_member_votes", 0))
                    aggregate["events_without_member_votes"] += int(loop_result.get("events_without_member_votes", 0))
                    aggregate["events_reingested"] += events_reingested
                    aggregate["member_votes_loaded"] += int(loop_result.get("member_votes_loaded", 0))
                    aggregate["would_reingest"] += int(loop_result.get("would_reingest", 0))

                    for key, value in loop_result.get("errors_summary", {}).items():
                        aggregate["errors_summary"][str(key)] = int(aggregate["errors_summary"].get(str(key), 0)) + int(value)
                    for item in loop_result.get("detail_failures", []):
                        normalized = normalize_ws(str(item))
                        if normalized:
                            details_seen.add(normalized)

                    next_cursor = loop_result.get("last_vote_event_id")
                    if isinstance(next_cursor, str) and next_cursor > "":
                        cursor_after = next_cursor
                    else:
                        cursor_after = None

                    if call_limit is not None:
                        remaining_limit = max(0, call_limit - events_considered)

                    if events_considered <= 0:
                        stop_reason = "no_events_considered"
                        break
                    if call_limit is not None and remaining_limit <= 0:
                        stop_reason = "limit_exhausted"
                        break

                aggregate["detail_failures"] = sorted(details_seen)
                if stop_reason == "not_started":
                    stop_reason = "unknown"
                aggregate["stop_reason"] = stop_reason
                result = aggregate
        finally:
            conn.close()
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
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
                "congreso_legs": args.congreso_legs,
                "senado_legs": args.senado_legs,
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
