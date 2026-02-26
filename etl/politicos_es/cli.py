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
from .run_snapshot_schema import (
    normalize_run_snapshot_row,
    write_legacy_metric_value_snapshot,
    write_normalized_run_snapshot_csv,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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

    backfill_policy_events_moncloa = subparsers.add_parser(
        "backfill-policy-events-moncloa",
        help="Mapea source_records de Moncloa a policy_events (trazable e idempotente)",
    )
    backfill_policy_events_moncloa.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="Ruta al archivo SQLite",
    )
    backfill_policy_events_moncloa.add_argument(
        "--source-ids",
        nargs="+",
        default=["moncloa_referencias", "moncloa_rss_referencias"],
        help="Source IDs Moncloa a mapear",
    )

    backfill_policy_events_boe = subparsers.add_parser(
        "backfill-policy-events-boe",
        help="Mapea source_records de BOE a policy_events (trazable e idempotente)",
    )
    backfill_policy_events_boe.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="Ruta al archivo SQLite",
    )
    backfill_policy_events_boe.add_argument(
        "--source-ids",
        nargs="+",
        default=["boe_api_legal"],
        help="Source IDs BOE a mapear",
    )

    backfill_policy_events_money = subparsers.add_parser(
        "backfill-policy-events-money",
        help="Mapea source_records de PLACSP/BDNS a policy_events canonicos de dinero (trazable e idempotente)",
    )
    backfill_policy_events_money.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="Ruta al archivo SQLite",
    )
    backfill_policy_events_money.add_argument(
        "--source-ids",
        nargs="+",
        default=["placsp_sindicacion", "placsp_autonomico", "bdns_api_subvenciones", "bdns_autonomico"],
        help="Source IDs money (PLACSP/BDNS) a mapear",
    )

    backfill_money_staging = subparsers.add_parser(
        "backfill-money-staging",
        help="Mapea source_records de PLACSP/BDNS a money_contract_records y money_subsidy_records",
    )
    backfill_money_staging.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="Ruta al archivo SQLite",
    )
    backfill_money_staging.add_argument(
        "--source-ids",
        nargs="+",
        default=["placsp_sindicacion", "placsp_autonomico", "bdns_api_subvenciones", "bdns_autonomico"],
        help="Source IDs money (PLACSP/BDNS) a mapear",
    )

    backfill_money_contract_records = subparsers.add_parser(
        "backfill-money-contract-records",
        help="Mapea source_records de PLACSP a money_contract_records",
    )
    backfill_money_contract_records.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="Ruta al archivo SQLite",
    )
    backfill_money_contract_records.add_argument(
        "--source-ids",
        nargs="+",
        default=["placsp_sindicacion", "placsp_autonomico"],
        help="Source IDs money de contratos a mapear",
    )

    backfill_placsp_contract_details = subparsers.add_parser(
        "backfill-placsp-contract-details",
        help="Descarga y extrae detalle estructurado de PLACSP desde páginas de detalle de licitación",
    )
    backfill_placsp_contract_details.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="Ruta al archivo SQLite",
    )
    backfill_placsp_contract_details.add_argument(
        "--raw-dir",
        default=str(DEFAULT_RAW_DIR),
        help="Directorio raw para guardar HTML de detalle PLACSP",
    )
    backfill_placsp_contract_details.add_argument(
        "--source-ids",
        nargs="+",
        default=["placsp_sindicacion", "placsp_autonomico"],
        help="Source IDs PLACSP a procesar",
    )
    backfill_placsp_contract_details.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximo número de source_records a procesar",
    )
    backfill_placsp_contract_details.add_argument(
        "--only-missing",
        action="store_true",
        help="Solo procesa source_records sin registro en placsp_contract_detail_records",
    )
    backfill_placsp_contract_details.add_argument(
        "--timeout",
        type=int,
        default=45,
        help="Timeout HTTP en segundos para la descarga de detalle",
    )
    backfill_placsp_contract_details.add_argument(
        "--strict-network",
        action="store_true",
        help="Si falla red o parseo, aborta en vez de saltar filas con warnings",
    )
    backfill_placsp_contract_details.add_argument(
        "--dry-run",
        action="store_true",
        help="Parsea y reporta sin escribir en DB ni guardar raw",
    )

    backfill_money_subsidy_records = subparsers.add_parser(
        "backfill-money-subsidy-records",
        help="Mapea source_records de BDNS a money_subsidy_records",
    )
    backfill_money_subsidy_records.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="Ruta al archivo SQLite",
    )
    backfill_money_subsidy_records.add_argument(
        "--source-ids",
        nargs="+",
        default=["bdns_api_subvenciones", "bdns_autonomico"],
        help="Source IDs money de subvenciones a mapear",
    )

    backfill_indicators = subparsers.add_parser(
        "backfill-indicators",
        help="Armoniza source_records de Eurostat/BDE/AEMET hacia indicator_series/indicator_points/observation_records",
    )
    backfill_indicators.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help="Ruta al archivo SQLite",
    )
    backfill_indicators.add_argument(
        "--source-ids",
        nargs="+",
        default=["eurostat_sdmx", "bde_series_api", "aemet_opendata_series"],
        help="Source IDs de indicadores a armonizar",
    )

    export_run_snapshot = subparsers.add_parser(
        "export-run-snapshot",
        help="Exporta snapshot canonico de ingestion_runs para auditoria/paridad",
    )
    export_run_snapshot.add_argument("--db", default=str(DEFAULT_DB), help="Ruta al archivo SQLite")
    export_run_snapshot.add_argument("--source-id", required=True, help="Source ID del run")
    export_run_snapshot.add_argument(
        "--run-id",
        type=int,
        default=None,
        help="run_id especifico (por defecto usa el ultimo run para --source-id)",
    )
    export_run_snapshot.add_argument("--mode", default="", help="Mode explicito (strict-network/from-file/replay)")
    export_run_snapshot.add_argument(
        "--command",
        dest="run_command",
        default="",
        help="Comando ejecutado (opcional)",
    )
    export_run_snapshot.add_argument(
        "--snapshot-date",
        default="",
        help="Snapshot date YYYY-MM-DD (opcional, se infiere de run_finished_at)",
    )
    export_run_snapshot.add_argument(
        "--out",
        required=True,
        help="Ruta de salida para CSV canonico (schema v2)",
    )
    export_run_snapshot.add_argument(
        "--legacy-kv-out",
        default="",
        help="Opcional: salida adicional en formato legacy metric,value",
    )

    return parser.parse_args(argv)


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


def cmd_backfill_policy_events_moncloa(args: argparse.Namespace) -> int:
    from .policy_events import backfill_moncloa_policy_events  # noqa: PLC0415

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Base no encontrada: {db_path}", file=sys.stderr)
        return 2

    source_ids = tuple(str(s).strip() for s in (args.source_ids or []) if str(s).strip())
    if not source_ids:
        print("Debe indicar al menos un source_id", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        result = backfill_moncloa_policy_events(conn, source_ids=source_ids)
    finally:
        conn.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_backfill_policy_events_boe(args: argparse.Namespace) -> int:
    from .policy_events import backfill_boe_policy_events  # noqa: PLC0415

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Base no encontrada: {db_path}", file=sys.stderr)
        return 2

    source_ids = tuple(str(s).strip() for s in (args.source_ids or []) if str(s).strip())
    if not source_ids:
        print("Debe indicar al menos un source_id", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        result = backfill_boe_policy_events(conn, source_ids=source_ids)
    finally:
        conn.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_backfill_policy_events_money(args: argparse.Namespace) -> int:
    from .policy_events import backfill_money_policy_events  # noqa: PLC0415

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Base no encontrada: {db_path}", file=sys.stderr)
        return 2

    source_ids = tuple(str(s).strip() for s in (args.source_ids or []) if str(s).strip())
    if not source_ids:
        print("Debe indicar al menos un source_id", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        result = backfill_money_policy_events(conn, source_ids=source_ids)
    finally:
        conn.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_backfill_money_staging(args: argparse.Namespace) -> int:
    from .policy_events import backfill_money_staging  # noqa: PLC0415

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Base no encontrada: {db_path}", file=sys.stderr)
        return 2

    source_ids = tuple(str(s).strip() for s in (args.source_ids or []) if str(s).strip())
    if not source_ids:
        print("Debe indicar al menos un source_id", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        result = backfill_money_staging(conn, source_ids=source_ids)
    finally:
        conn.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_backfill_money_contract_records(args: argparse.Namespace) -> int:
    from .policy_events import backfill_money_contract_records  # noqa: PLC0415

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Base no encontrada: {db_path}", file=sys.stderr)
        return 2

    source_ids = tuple(str(s).strip() for s in (args.source_ids or []) if str(s).strip())
    if not source_ids:
        print("Debe indicar al menos un source_id", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        result = backfill_money_contract_records(conn, source_ids=source_ids)
    finally:
        conn.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_backfill_placsp_contract_details(args: argparse.Namespace) -> int:
    from .policy_events import backfill_placsp_contract_details  # noqa: PLC0415

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Base no encontrada: {db_path}", file=sys.stderr)
        return 2

    source_ids = tuple(str(s).strip() for s in (args.source_ids or []) if str(s).strip())
    if not source_ids:
        print("Debe indicar al menos un source_id", file=sys.stderr)
        return 2

    raw_dir = Path(args.raw_dir)
    timeout = int(args.timeout)
    if timeout <= 0:
        print("timeout debe ser > 0", file=sys.stderr)
        return 2
    limit = args.limit
    if limit is not None and limit <= 0:
        print("limit debe ser > 0", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        result = backfill_placsp_contract_details(
            conn,
            raw_dir=raw_dir,
            source_ids=source_ids,
            limit=limit,
            only_missing=bool(args.only_missing),
            strict_network=bool(args.strict_network),
            timeout=timeout,
            dry_run=bool(args.dry_run),
        )
    finally:
        conn.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_backfill_money_subsidy_records(args: argparse.Namespace) -> int:
    from .policy_events import backfill_money_subsidy_records  # noqa: PLC0415

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Base no encontrada: {db_path}", file=sys.stderr)
        return 2

    source_ids = tuple(str(s).strip() for s in (args.source_ids or []) if str(s).strip())
    if not source_ids:
        print("Debe indicar al menos un source_id", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        result = backfill_money_subsidy_records(conn, source_ids=source_ids)
    finally:
        conn.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_backfill_indicators(args: argparse.Namespace) -> int:
    from .indicator_backfill import backfill_indicator_harmonization  # noqa: PLC0415

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Base no encontrada: {db_path}", file=sys.stderr)
        return 2

    source_ids = tuple(str(s).strip() for s in (args.source_ids or []) if str(s).strip())
    if not source_ids:
        print("Debe indicar al menos un source_id", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        apply_schema(conn, DEFAULT_SCHEMA)
        seed_sources(conn)
        seed_dimensions(conn)
        result = backfill_indicator_harmonization(conn, source_ids=source_ids)
    finally:
        conn.close()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _infer_snapshot_date(run_finished_at: str, snapshot_override: str) -> str:
    override = str(snapshot_override or "").strip()
    if override:
        return override
    token = str(run_finished_at or "").strip()
    if "T" in token and len(token) >= 10:
        return token[:10]
    return token


def _fetch_run_row(
    conn,
    *,
    source_id: str,
    run_id: int | None,
):
    if run_id is None:
        return conn.execute(
            """
            SELECT run_id, source_id, started_at, finished_at, status, source_url, records_seen, records_loaded, message
            FROM ingestion_runs
            WHERE source_id = ?
            ORDER BY run_id DESC
            LIMIT 1
            """,
            (source_id,),
        ).fetchone()

    return conn.execute(
        """
        SELECT run_id, source_id, started_at, finished_at, status, source_url, records_seen, records_loaded, message
        FROM ingestion_runs
        WHERE source_id = ? AND run_id = ?
        LIMIT 1
        """,
        (source_id, run_id),
    ).fetchone()


def _count_source_records(conn, *, source_id: str, at_or_before: str | None = None, before: str | None = None) -> int:
    if at_or_before:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM source_records
            WHERE source_id = ? AND created_at <= ?
            """,
            (source_id, at_or_before),
        ).fetchone()
        return int(row["c"] if row else 0)
    if before:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM source_records
            WHERE source_id = ? AND created_at < ?
            """,
            (source_id, before),
        ).fetchone()
        return int(row["c"] if row else 0)
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM source_records WHERE source_id = ?",
        (source_id,),
    ).fetchone()
    return int(row["c"] if row else 0)


def cmd_export_run_snapshot(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Base no encontrada: {db_path}", file=sys.stderr)
        return 2

    source_id = str(args.source_id or "").strip()
    if not source_id:
        print("Debe indicar --source-id", file=sys.stderr)
        return 2

    conn = open_db(db_path)
    try:
        run_row = _fetch_run_row(conn, source_id=source_id, run_id=args.run_id)
        if run_row is None:
            run_ref = f"run_id={args.run_id}" if args.run_id is not None else "latest run"
            print(f"No se encontro {run_ref} para source_id={source_id}", file=sys.stderr)
            return 2

        finished_at = str(run_row["finished_at"] or "")
        started_at = str(run_row["started_at"] or "")
        after_records = _count_source_records(
            conn,
            source_id=source_id,
            at_or_before=finished_at if finished_at else None,
        )
        before_records = _count_source_records(
            conn,
            source_id=source_id,
            before=started_at if started_at else None,
        )

        # Keep deterministic counters even when created_at timestamps are unavailable.
        if before_records > after_records:
            loaded = int(run_row["records_loaded"] or 0)
            before_records = max(after_records - loaded, 0)
        delta_records = max(after_records - before_records, 0)

        raw_row = {
            "source_id": source_id,
            "mode": str(args.mode or "").strip(),
            "command": str(args.run_command or "").strip(),
            "exit_code": "0" if str(run_row["status"] or "") == "ok" else "1",
            "before_records": str(before_records),
            "after_records": str(after_records),
            "delta_records": str(delta_records),
            "run_id": str(run_row["run_id"] or ""),
            "run_status": str(run_row["status"] or ""),
            "run_records_seen": str(run_row["records_seen"] or 0),
            "run_records_loaded": str(run_row["records_loaded"] or 0),
            "run_started_at": started_at,
            "run_finished_at": finished_at,
            "source_url": str(run_row["source_url"] or ""),
            "snapshot_date": _infer_snapshot_date(finished_at, str(args.snapshot_date or "")),
            "message": str(run_row["message"] or ""),
        }
        normalized = normalize_run_snapshot_row(raw_row, defaults={"source_id": source_id})

        out_path = write_normalized_run_snapshot_csv(args.out, normalized)
        print(f"Run snapshot canonico escrito en: {out_path}")

        legacy_out = str(args.legacy_kv_out or "").strip()
        if legacy_out:
            legacy_path = write_legacy_metric_value_snapshot(legacy_out, normalized)
            print(f"Run snapshot legacy escrito en: {legacy_path}")

        summary = {
            "source_id": normalized.get("source_id", ""),
            "mode": normalized.get("mode", ""),
            "exit_code": normalized.get("exit_code", ""),
            "run_records_loaded": normalized.get("run_records_loaded", ""),
            "snapshot_date": normalized.get("snapshot_date", ""),
            "run_id": normalized.get("run_id", ""),
        }
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    finally:
        conn.close()


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
    args = parse_args(argv)
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
    if args.command == "backfill-policy-events-moncloa":
        return cmd_backfill_policy_events_moncloa(args)
    if args.command == "backfill-policy-events-boe":
        return cmd_backfill_policy_events_boe(args)
    if args.command == "backfill-policy-events-money":
        return cmd_backfill_policy_events_money(args)
    if args.command == "backfill-money-staging":
        return cmd_backfill_money_staging(args)
    if args.command == "backfill-money-contract-records":
        return cmd_backfill_money_contract_records(args)
    if args.command == "backfill-placsp-contract-details":
        return cmd_backfill_placsp_contract_details(args)
    if args.command == "backfill-money-subsidy-records":
        return cmd_backfill_money_subsidy_records(args)
    if args.command == "backfill-indicators":
        return cmd_backfill_indicators(args)
    if args.command == "export-run-snapshot":
        return cmd_export_run_snapshot(args)
    print(f"Comando no soportado: {args.command}", file=sys.stderr)
    return 2
