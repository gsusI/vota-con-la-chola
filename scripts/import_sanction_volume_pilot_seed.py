#!/usr/bin/env python3
"""Import sanction_volume_pilot_seed_v1 into sanctions observation tables."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws
from scripts.validate_sanction_volume_pilot_seed import validate_seed


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


def _to_float_or_none(v: Any) -> float | None:
    token = _norm(v)
    if not token:
        return None
    try:
        return float(token)
    except Exception:
        return None


def _to_int_or_none(v: Any) -> int | None:
    token = _norm(v)
    if not token:
        return None
    try:
        return int(float(token))
    except Exception:
        return None


def _observation_key(row: dict[str, Any]) -> str:
    given = _norm(row.get("observation_key"))
    if given:
        return given
    return "|".join(
        [
            _norm(row.get("sanction_source_id")),
            _norm(row.get("period_date")),
            _norm(row.get("period_granularity")),
            _norm(row.get("infraction_type_id")),
            _norm(row.get("norm_id")),
            _norm(row.get("fragment_id")),
        ]
    )


def _metric_key(row: dict[str, Any]) -> str:
    given = _norm(row.get("metric_key"))
    if given:
        return given
    return "|".join(
        [
            _norm(row.get("kpi_id")),
            _norm(row.get("sanction_source_id")),
            _norm(row.get("period_date")),
            _norm(row.get("period_granularity")),
        ]
    )


def _source_exists(conn: sqlite3.Connection, source_id: str) -> bool:
    sid = _norm(source_id)
    if not sid:
        return False
    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (sid,)).fetchone()
    return row is not None


def _exists(conn: sqlite3.Connection, table: str, col: str, value: str) -> bool:
    token = _norm(value)
    if not token:
        return False
    row = conn.execute(f"SELECT 1 FROM {table} WHERE {col} = ?", (token,)).fetchone()
    return row is not None


def import_seed(
    conn: sqlite3.Connection,
    *,
    seed_doc: dict[str, Any],
    source_id: str,
    snapshot_date: str,
) -> dict[str, Any]:
    ts = now_utc_iso()
    sid = _norm(source_id)
    if sid and not _source_exists(conn, sid):
        sid = ""

    counts: dict[str, int] = {
        "volume_observations_inserted": 0,
        "volume_observations_updated": 0,
        "procedural_metrics_inserted": 0,
        "procedural_metrics_updated": 0,
        "municipal_ordinances_inserted": 0,
        "municipal_ordinances_updated": 0,
        "municipal_fragments_inserted": 0,
        "municipal_fragments_updated": 0,
        "unresolved_sanction_source_refs": 0,
        "unresolved_infraction_type_refs": 0,
        "unresolved_kpi_refs": 0,
        "unresolved_norm_refs": 0,
        "unresolved_fragment_refs": 0,
        "unresolved_ordinance_refs": 0,
    }

    seed_version = _norm(seed_doc.get("schema_version")) or "sanction_volume_pilot_seed_v1"

    observations = seed_doc.get("volume_observations") if isinstance(seed_doc.get("volume_observations"), list) else []
    for row in observations:
        if not isinstance(row, dict):
            continue
        sanction_source_id = _norm(row.get("sanction_source_id"))
        if not _exists(conn, "sanction_volume_sources", "sanction_source_id", sanction_source_id):
            counts["unresolved_sanction_source_refs"] += 1
            continue
        infraction_type_id = _norm(row.get("infraction_type_id"))
        if not _exists(conn, "sanction_infraction_types", "infraction_type_id", infraction_type_id):
            counts["unresolved_infraction_type_refs"] += 1
            continue

        norm_id = _norm(row.get("norm_id"))
        if norm_id and not _exists(conn, "legal_norms", "norm_id", norm_id):
            counts["unresolved_norm_refs"] += 1
            norm_id = ""
        fragment_id = _norm(row.get("fragment_id"))
        if fragment_id and not _exists(conn, "legal_norm_fragments", "fragment_id", fragment_id):
            counts["unresolved_fragment_refs"] += 1
            fragment_id = ""

        key = _observation_key(row)
        if not key:
            continue
        exists = conn.execute(
            "SELECT 1 FROM sanction_volume_observations WHERE observation_key = ?",
            (key,),
        ).fetchone()
        payload = json.dumps(
            {
                **row,
                "seed_version": seed_version,
                "snapshot_date": snapshot_date,
                "resolved_norm_id": norm_id or None,
                "resolved_fragment_id": fragment_id or None,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        conn.execute(
            """
            INSERT INTO sanction_volume_observations (
              observation_key, sanction_source_id, period_date, period_granularity,
              norm_id, fragment_id, infraction_type_id,
              expediente_count, importe_total_eur, importe_medio_eur,
              recurso_presentado_count, recurso_estimado_count, recurso_desestimado_count,
              source_id, source_url, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(observation_key) DO UPDATE SET
              sanction_source_id=excluded.sanction_source_id,
              period_date=excluded.period_date,
              period_granularity=excluded.period_granularity,
              norm_id=excluded.norm_id,
              fragment_id=excluded.fragment_id,
              infraction_type_id=excluded.infraction_type_id,
              expediente_count=excluded.expediente_count,
              importe_total_eur=excluded.importe_total_eur,
              importe_medio_eur=excluded.importe_medio_eur,
              recurso_presentado_count=excluded.recurso_presentado_count,
              recurso_estimado_count=excluded.recurso_estimado_count,
              recurso_desestimado_count=excluded.recurso_desestimado_count,
              source_id=COALESCE(excluded.source_id, sanction_volume_observations.source_id),
              source_url=excluded.source_url,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                key,
                sanction_source_id,
                _norm(row.get("period_date")),
                _norm(row.get("period_granularity")),
                norm_id or None,
                fragment_id or None,
                infraction_type_id,
                _to_int_or_none(row.get("expediente_count")),
                _to_float_or_none(row.get("importe_total_eur")),
                _to_float_or_none(row.get("importe_medio_eur")),
                _to_int_or_none(row.get("recurso_presentado_count")),
                _to_int_or_none(row.get("recurso_estimado_count")),
                _to_int_or_none(row.get("recurso_desestimado_count")),
                sid or None,
                _norm(row.get("source_url")) or None,
                payload,
                ts,
                ts,
            ),
        )
        counts["volume_observations_updated" if exists else "volume_observations_inserted"] += 1

    procedural_metrics = seed_doc.get("procedural_metrics") if isinstance(seed_doc.get("procedural_metrics"), list) else []
    for row in procedural_metrics:
        if not isinstance(row, dict):
            continue
        kpi_id = _norm(row.get("kpi_id"))
        if not _exists(conn, "sanction_procedural_kpi_definitions", "kpi_id", kpi_id):
            counts["unresolved_kpi_refs"] += 1
            continue
        sanction_source_id = _norm(row.get("sanction_source_id"))
        if sanction_source_id and not _exists(conn, "sanction_volume_sources", "sanction_source_id", sanction_source_id):
            counts["unresolved_sanction_source_refs"] += 1
            continue
        key = _metric_key(row)
        if not key:
            continue
        exists = conn.execute(
            "SELECT 1 FROM sanction_procedural_metrics WHERE metric_key = ?",
            (key,),
        ).fetchone()
        payload = json.dumps(
            {
                **row,
                "seed_version": seed_version,
                "snapshot_date": snapshot_date,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        conn.execute(
            """
            INSERT INTO sanction_procedural_metrics (
              metric_key, kpi_id, sanction_source_id,
              period_date, period_granularity, value, numerator, denominator,
              source_id, source_url, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(metric_key) DO UPDATE SET
              kpi_id=excluded.kpi_id,
              sanction_source_id=excluded.sanction_source_id,
              period_date=excluded.period_date,
              period_granularity=excluded.period_granularity,
              value=excluded.value,
              numerator=excluded.numerator,
              denominator=excluded.denominator,
              source_id=COALESCE(excluded.source_id, sanction_procedural_metrics.source_id),
              source_url=excluded.source_url,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                key,
                kpi_id,
                sanction_source_id or None,
                _norm(row.get("period_date")),
                _norm(row.get("period_granularity")),
                _to_float_or_none(row.get("value")),
                _to_float_or_none(row.get("numerator")),
                _to_float_or_none(row.get("denominator")),
                sid or None,
                _norm(row.get("source_url")) or None,
                payload,
                ts,
                ts,
            ),
        )
        counts["procedural_metrics_updated" if exists else "procedural_metrics_inserted"] += 1

    municipal_ordinances = seed_doc.get("municipal_ordinances") if isinstance(seed_doc.get("municipal_ordinances"), list) else []
    for row in municipal_ordinances:
        if not isinstance(row, dict):
            continue
        ordinance_id = _norm(row.get("ordinance_id"))
        if not ordinance_id:
            continue
        exists = conn.execute(
            "SELECT 1 FROM sanction_municipal_ordinances WHERE ordinance_id = ?",
            (ordinance_id,),
        ).fetchone()
        payload = json.dumps({**row, "seed_version": seed_version, "snapshot_date": snapshot_date}, ensure_ascii=False, sort_keys=True)
        conn.execute(
            """
            INSERT INTO sanction_municipal_ordinances (
              ordinance_id, city_name, province_name, ordinance_label, ordinance_status,
              ordinance_url, publication_date, source_id, source_url,
              raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ordinance_id) DO UPDATE SET
              city_name=excluded.city_name,
              province_name=excluded.province_name,
              ordinance_label=excluded.ordinance_label,
              ordinance_status=excluded.ordinance_status,
              ordinance_url=excluded.ordinance_url,
              publication_date=excluded.publication_date,
              source_id=COALESCE(excluded.source_id, sanction_municipal_ordinances.source_id),
              source_url=excluded.source_url,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                ordinance_id,
                _norm(row.get("city_name")),
                _norm(row.get("province_name")) or None,
                _norm(row.get("ordinance_label")),
                _norm(row.get("ordinance_status")),
                _norm(row.get("ordinance_url")) or None,
                _norm(row.get("publication_date")) or None,
                sid or None,
                _norm(row.get("source_url")) or None,
                payload,
                ts,
                ts,
            ),
        )
        counts["municipal_ordinances_updated" if exists else "municipal_ordinances_inserted"] += 1

    municipal_fragments = seed_doc.get("municipal_fragments") if isinstance(seed_doc.get("municipal_fragments"), list) else []
    for row in municipal_fragments:
        if not isinstance(row, dict):
            continue
        ordinance_fragment_id = _norm(row.get("ordinance_fragment_id"))
        if not ordinance_fragment_id:
            continue
        ordinance_id = _norm(row.get("ordinance_id"))
        if not _exists(conn, "sanction_municipal_ordinances", "ordinance_id", ordinance_id):
            counts["unresolved_ordinance_refs"] += 1
            continue
        mapped_norm_id = _norm(row.get("mapped_norm_id"))
        if mapped_norm_id and not _exists(conn, "legal_norms", "norm_id", mapped_norm_id):
            counts["unresolved_norm_refs"] += 1
            mapped_norm_id = ""
        mapped_fragment_id = _norm(row.get("mapped_fragment_id"))
        if mapped_fragment_id and not _exists(conn, "legal_norm_fragments", "fragment_id", mapped_fragment_id):
            counts["unresolved_fragment_refs"] += 1
            mapped_fragment_id = ""
        exists = conn.execute(
            "SELECT 1 FROM sanction_municipal_ordinance_fragments WHERE ordinance_fragment_id = ?",
            (ordinance_fragment_id,),
        ).fetchone()
        payload = json.dumps(
            {
                **row,
                "seed_version": seed_version,
                "snapshot_date": snapshot_date,
                "resolved_mapped_norm_id": mapped_norm_id or None,
                "resolved_mapped_fragment_id": mapped_fragment_id or None,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        conn.execute(
            """
            INSERT INTO sanction_municipal_ordinance_fragments (
              ordinance_fragment_id, ordinance_id, fragment_label, conduct,
              amount_min_eur, amount_max_eur, competent_body, appeal_path,
              mapped_norm_id, mapped_fragment_id, source_url,
              raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ordinance_fragment_id) DO UPDATE SET
              ordinance_id=excluded.ordinance_id,
              fragment_label=excluded.fragment_label,
              conduct=excluded.conduct,
              amount_min_eur=excluded.amount_min_eur,
              amount_max_eur=excluded.amount_max_eur,
              competent_body=excluded.competent_body,
              appeal_path=excluded.appeal_path,
              mapped_norm_id=excluded.mapped_norm_id,
              mapped_fragment_id=excluded.mapped_fragment_id,
              source_url=excluded.source_url,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                ordinance_fragment_id,
                ordinance_id,
                _norm(row.get("fragment_label")),
                _norm(row.get("conduct")) or None,
                _to_float_or_none(row.get("amount_min_eur")),
                _to_float_or_none(row.get("amount_max_eur")),
                _norm(row.get("competent_body")) or None,
                _norm(row.get("appeal_path")) or None,
                mapped_norm_id or None,
                mapped_fragment_id or None,
                _norm(row.get("source_url")) or None,
                payload,
                ts,
                ts,
            ),
        )
        counts["municipal_fragments_updated" if exists else "municipal_fragments_inserted"] += 1

    conn.commit()

    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM sanction_volume_observations) AS sanction_volume_observations_total,
          (SELECT COUNT(*) FROM sanction_procedural_metrics) AS sanction_procedural_metrics_total,
          (SELECT COUNT(*) FROM sanction_municipal_ordinances) AS sanction_municipal_ordinances_total,
          (SELECT COUNT(*) FROM sanction_municipal_ordinance_fragments) AS sanction_municipal_ordinance_fragments_total
        """
    ).fetchone()

    return {
        "status": "ok",
        "snapshot_date": snapshot_date,
        "source_id_used": sid,
        "seed_schema_version": seed_version,
        "counts": counts,
        "totals": {
            "sanction_volume_observations_total": int(totals["sanction_volume_observations_total"]),
            "sanction_procedural_metrics_total": int(totals["sanction_procedural_metrics_total"]),
            "sanction_municipal_ordinances_total": int(totals["sanction_municipal_ordinances_total"]),
            "sanction_municipal_ordinance_fragments_total": int(totals["sanction_municipal_ordinance_fragments_total"]),
        },
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Import sanction_volume_pilot_seed_v1 into SQLite")
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed", default="etl/data/seeds/sanction_volume_pilot_seed_v1.json")
    ap.add_argument("--snapshot-date", default=today_utc_date())
    ap.add_argument("--source-id", default="boe_api_legal")
    ap.add_argument("--schema", default=str(Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"))
    ap.add_argument("--skip-schema", action="store_true", help="Assume schema is already applied to this DB")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    seed_path = Path(args.seed)
    validation = validate_seed(seed_path)
    if not bool(validation.get("valid")):
        payload = {"status": "invalid_seed", "validation": validation}
        rendered = json.dumps(payload, ensure_ascii=False, indent=2)
        if _norm(args.out):
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 1

    seed_doc = json.loads(seed_path.read_text(encoding="utf-8"))
    db_path = Path(args.db)
    schema_path = Path(args.schema)
    conn = open_db(db_path)
    try:
        if not args.skip_schema:
            apply_schema(conn, schema_path)
        report = import_seed(
            conn,
            seed_doc=seed_doc,
            source_id=str(args.source_id or ""),
            snapshot_date=str(args.snapshot_date or ""),
        )
    finally:
        conn.close()

    payload = {
        "generated_at": now_utc_iso(),
        "db_path": str(db_path),
        "seed_path": str(seed_path),
        "validation": {
            "valid": bool(validation.get("valid")),
            "volume_observations_total": int(validation.get("volume_observations_total") or 0),
            "procedural_metrics_total": int(validation.get("procedural_metrics_total") or 0),
            "municipal_ordinances_total": int(validation.get("municipal_ordinances_total") or 0),
            "municipal_fragments_total": int(validation.get("municipal_fragments_total") or 0),
        },
        "import": report,
    }

    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
