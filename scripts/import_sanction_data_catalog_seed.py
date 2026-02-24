#!/usr/bin/env python3
"""Import sanction_data_catalog_seed_v1 into sanctions catalog tables."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws
from scripts.validate_sanction_data_catalog_seed import validate_seed


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


def _source_exists(conn: sqlite3.Connection, source_id: str) -> bool:
    sid = _norm(source_id)
    if not sid:
        return False
    row = conn.execute("SELECT 1 FROM sources WHERE source_id = ?", (sid,)).fetchone()
    return row is not None


def _mapping_key(row: dict[str, Any]) -> str:
    given = _norm(row.get("mapping_key"))
    if given:
        return given
    return "|".join(
        [
            _norm(row.get("infraction_type_id")),
            _norm(row.get("source_system")),
            _norm(row.get("source_code")),
            _norm(row.get("norm_id")),
            _norm(row.get("fragment_id")),
        ]
    )


def _norm_exists(conn: sqlite3.Connection, norm_id: str) -> bool:
    nid = _norm(norm_id)
    if not nid:
        return False
    return conn.execute("SELECT 1 FROM legal_norms WHERE norm_id = ?", (nid,)).fetchone() is not None


def _fragment_exists(conn: sqlite3.Connection, fragment_id: str) -> bool:
    fid = _norm(fragment_id)
    if not fid:
        return False
    return conn.execute("SELECT 1 FROM legal_norm_fragments WHERE fragment_id = ?", (fid,)).fetchone() is not None


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
        "volume_sources_inserted": 0,
        "volume_sources_updated": 0,
        "infraction_types_inserted": 0,
        "infraction_types_updated": 0,
        "infraction_mappings_inserted": 0,
        "infraction_mappings_updated": 0,
        "procedural_kpis_inserted": 0,
        "procedural_kpis_updated": 0,
        "unresolved_norm_refs": 0,
        "unresolved_fragment_refs": 0,
    }

    seed_version = _norm(seed_doc.get("schema_version")) or "sanction_data_catalog_seed_v1"

    volume_sources = seed_doc.get("volume_sources") if isinstance(seed_doc.get("volume_sources"), list) else []
    for row in volume_sources:
        if not isinstance(row, dict):
            continue
        sanction_source_id = _norm(row.get("sanction_source_id"))
        if not sanction_source_id:
            continue

        exists = conn.execute(
            "SELECT 1 FROM sanction_volume_sources WHERE sanction_source_id = ?",
            (sanction_source_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO sanction_volume_sources (
              sanction_source_id, label, organismo, admin_scope, territory_scope,
              publication_frequency, source_url, source_id, data_contract_json,
              raw_payload, seed_version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sanction_source_id) DO UPDATE SET
              label=excluded.label,
              organismo=excluded.organismo,
              admin_scope=excluded.admin_scope,
              territory_scope=excluded.territory_scope,
              publication_frequency=excluded.publication_frequency,
              source_url=excluded.source_url,
              source_id=COALESCE(excluded.source_id, sanction_volume_sources.source_id),
              data_contract_json=excluded.data_contract_json,
              raw_payload=excluded.raw_payload,
              seed_version=excluded.seed_version,
              updated_at=excluded.updated_at
            """,
            (
                sanction_source_id,
                _norm(row.get("label")),
                _norm(row.get("organismo")) or None,
                _norm(row.get("admin_scope")) or None,
                _norm(row.get("territory_scope")) or None,
                _norm(row.get("publication_frequency")) or None,
                _norm(row.get("source_url")) or None,
                sid or None,
                json.dumps(
                    {
                        "expected_metrics": row.get("expected_metrics", []),
                        "notes": _norm(row.get("notes")),
                        "snapshot_date": snapshot_date,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                json.dumps(row, ensure_ascii=False, sort_keys=True),
                seed_version,
                ts,
                ts,
            ),
        )
        counts["volume_sources_updated" if exists else "volume_sources_inserted"] += 1

    infraction_types = seed_doc.get("infraction_types") if isinstance(seed_doc.get("infraction_types"), list) else []
    for row in infraction_types:
        if not isinstance(row, dict):
            continue
        infraction_type_id = _norm(row.get("infraction_type_id"))
        if not infraction_type_id:
            continue
        exists = conn.execute(
            "SELECT 1 FROM sanction_infraction_types WHERE infraction_type_id = ?",
            (infraction_type_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO sanction_infraction_types (
              infraction_type_id, label, domain, description, canonical_unit, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(infraction_type_id) DO UPDATE SET
              label=excluded.label,
              domain=excluded.domain,
              description=excluded.description,
              canonical_unit=excluded.canonical_unit,
              updated_at=excluded.updated_at
            """,
            (
                infraction_type_id,
                _norm(row.get("label")),
                _norm(row.get("domain")) or None,
                _norm(row.get("description")) or None,
                _norm(row.get("canonical_unit")) or None,
                ts,
                ts,
            ),
        )
        counts["infraction_types_updated" if exists else "infraction_types_inserted"] += 1

    infraction_mappings = seed_doc.get("infraction_mappings") if isinstance(seed_doc.get("infraction_mappings"), list) else []
    for row in infraction_mappings:
        if not isinstance(row, dict):
            continue
        infraction_type_id = _norm(row.get("infraction_type_id"))
        if not infraction_type_id:
            continue
        mk = _mapping_key(row)
        if not mk:
            continue

        norm_id = _norm(row.get("norm_id"))
        fragment_id = _norm(row.get("fragment_id"))
        if norm_id and not _norm_exists(conn, norm_id):
            counts["unresolved_norm_refs"] += 1
            norm_id = ""
        if fragment_id and not _fragment_exists(conn, fragment_id):
            counts["unresolved_fragment_refs"] += 1
            fragment_id = ""

        exists = conn.execute(
            "SELECT 1 FROM sanction_infraction_type_mappings WHERE mapping_key = ?",
            (mk,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO sanction_infraction_type_mappings (
              mapping_key, infraction_type_id, norm_id, fragment_id, source_system, source_code,
              source_label, confidence, source_url, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(mapping_key) DO UPDATE SET
              infraction_type_id=excluded.infraction_type_id,
              norm_id=excluded.norm_id,
              fragment_id=excluded.fragment_id,
              source_system=excluded.source_system,
              source_code=excluded.source_code,
              source_label=excluded.source_label,
              confidence=excluded.confidence,
              source_url=excluded.source_url,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                mk,
                infraction_type_id,
                norm_id or None,
                fragment_id or None,
                _norm(row.get("source_system")) or None,
                _norm(row.get("source_code")) or None,
                _norm(row.get("source_label")) or None,
                float(_norm(row.get("confidence")) or 0.0) if _norm(row.get("confidence")) else None,
                _norm(row.get("source_url")) or None,
                json.dumps(
                    {
                        **row,
                        "seed_version": seed_version,
                        "snapshot_date": snapshot_date,
                        "resolved_norm_id": norm_id or None,
                        "resolved_fragment_id": fragment_id or None,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                ts,
                ts,
            ),
        )
        counts["infraction_mappings_updated" if exists else "infraction_mappings_inserted"] += 1

    procedural_kpis = seed_doc.get("procedural_kpis") if isinstance(seed_doc.get("procedural_kpis"), list) else []
    for row in procedural_kpis:
        if not isinstance(row, dict):
            continue
        kpi_id = _norm(row.get("kpi_id"))
        if not kpi_id:
            continue
        exists = conn.execute(
            "SELECT 1 FROM sanction_procedural_kpi_definitions WHERE kpi_id = ?",
            (kpi_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO sanction_procedural_kpi_definitions (
              kpi_id, label, metric_formula, interpretation, target_direction,
              source_requirements_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(kpi_id) DO UPDATE SET
              label=excluded.label,
              metric_formula=excluded.metric_formula,
              interpretation=excluded.interpretation,
              target_direction=excluded.target_direction,
              source_requirements_json=excluded.source_requirements_json,
              updated_at=excluded.updated_at
            """,
            (
                kpi_id,
                _norm(row.get("label")),
                _norm(row.get("metric_formula")),
                _norm(row.get("interpretation")) or None,
                _norm(row.get("target_direction")) or None,
                json.dumps(row.get("source_requirements", []), ensure_ascii=False, sort_keys=True),
                ts,
                ts,
            ),
        )
        counts["procedural_kpis_updated" if exists else "procedural_kpis_inserted"] += 1

    conn.commit()

    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM sanction_volume_sources) AS sanction_volume_sources_total,
          (SELECT COUNT(*) FROM sanction_infraction_types) AS sanction_infraction_types_total,
          (SELECT COUNT(*) FROM sanction_infraction_type_mappings) AS sanction_infraction_type_mappings_total,
          (SELECT COUNT(*) FROM sanction_procedural_kpi_definitions) AS sanction_procedural_kpi_definitions_total
        """
    ).fetchone()

    return {
        "status": "ok",
        "snapshot_date": snapshot_date,
        "source_id_used": sid,
        "seed_schema_version": seed_version,
        "counts": counts,
        "totals": {
            "sanction_volume_sources_total": int(totals["sanction_volume_sources_total"]),
            "sanction_infraction_types_total": int(totals["sanction_infraction_types_total"]),
            "sanction_infraction_type_mappings_total": int(totals["sanction_infraction_type_mappings_total"]),
            "sanction_procedural_kpi_definitions_total": int(totals["sanction_procedural_kpi_definitions_total"]),
        },
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Import sanction_data_catalog_seed_v1 into SQLite")
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed", default="etl/data/seeds/sanction_data_catalog_seed_v1.json")
    ap.add_argument("--snapshot-date", default=today_utc_date())
    ap.add_argument("--source-id", default="boe_api_legal")
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
    schema_path = Path(__file__).resolve().parents[1] / "etl" / "load" / "sqlite_schema.sql"
    conn = open_db(db_path)
    try:
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
            "volume_sources_total": int(validation.get("volume_sources_total") or 0),
            "infraction_types_total": int(validation.get("infraction_types_total") or 0),
            "infraction_mappings_total": int(validation.get("infraction_mappings_total") or 0),
            "procedural_kpis_total": int(validation.get("procedural_kpis_total") or 0),
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
