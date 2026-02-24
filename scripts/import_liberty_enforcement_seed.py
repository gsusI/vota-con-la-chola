#!/usr/bin/env python3
"""Import liberty_enforcement_seed_v1 into territorial enforcement tables."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws
from scripts.validate_liberty_enforcement_seed import THRESHOLD_KEYS, validate_seed


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_utc_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _norm(v: Any) -> str:
    if v is None:
        return ""
    return normalize_ws(str(v))


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


def _observation_key(row: dict[str, Any], method_version: str) -> str:
    given = _norm(row.get("observation_key"))
    if given:
        return given
    return "|".join(
        [
            method_version,
            _norm(row.get("fragment_id")),
            _norm(row.get("territory_key")),
            _norm(row.get("period_date")),
        ]
    )


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

    methodology = seed_doc.get("methodology") if isinstance(seed_doc.get("methodology"), dict) else {}
    method_version = _norm(methodology.get("method_version")) or "enforcement_variation_v1"
    method_label = _norm(methodology.get("method_label")) or "Variacion territorial de enforcement v1"
    thresholds_doc = methodology.get("thresholds") if isinstance(methodology.get("thresholds"), dict) else {}
    thresholds: dict[str, float] = {}
    for key in THRESHOLD_KEYS:
        thresholds[key] = float(thresholds_doc.get(key) or 0.0)

    counts: dict[str, int] = {
        "methodology_inserted": 0,
        "methodology_updated": 0,
        "observations_inserted": 0,
        "observations_updated": 0,
        "unresolved_fragment_refs": 0,
    }

    method_exists = conn.execute(
        "SELECT 1 FROM liberty_enforcement_methodologies WHERE method_version = ?",
        (method_version,),
    ).fetchone()
    conn.execute(
        """
        INSERT INTO liberty_enforcement_methodologies (
          method_version, method_label, thresholds_json, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(method_version) DO UPDATE SET
          method_label=excluded.method_label,
          thresholds_json=excluded.thresholds_json,
          notes=excluded.notes,
          updated_at=excluded.updated_at
        """,
        (
            method_version,
            method_label,
            json.dumps(thresholds, ensure_ascii=False, sort_keys=True),
            _norm(methodology.get("notes")) or None,
            ts,
            ts,
        ),
    )
    counts["methodology_updated" if method_exists else "methodology_inserted"] += 1

    observations = seed_doc.get("observations") if isinstance(seed_doc.get("observations"), list) else []
    for row in observations:
        if not isinstance(row, dict):
            continue
        fragment_id = _norm(row.get("fragment_id"))
        if not _exists(conn, "legal_norm_fragments", "fragment_id", fragment_id):
            counts["unresolved_fragment_refs"] += 1
            continue

        observation_key = _observation_key(row, method_version)
        if not observation_key:
            continue
        exists = conn.execute(
            "SELECT 1 FROM liberty_enforcement_observations WHERE observation_key = ?",
            (observation_key,),
        ).fetchone()
        payload = json.dumps(
            {
                **row,
                "method_version": method_version,
                "seed_schema_version": _norm(seed_doc.get("schema_version")),
                "snapshot_date": snapshot_date,
                "thresholds": thresholds,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        conn.execute(
            """
            INSERT INTO liberty_enforcement_observations (
              observation_key, fragment_id, method_version,
              territory_key, territory_label, period_date,
              sanction_rate_per_1000, annulment_rate, resolution_delay_p90_days, sample_size,
              source_id, source_url, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(observation_key) DO UPDATE SET
              fragment_id=excluded.fragment_id,
              method_version=excluded.method_version,
              territory_key=excluded.territory_key,
              territory_label=excluded.territory_label,
              period_date=excluded.period_date,
              sanction_rate_per_1000=excluded.sanction_rate_per_1000,
              annulment_rate=excluded.annulment_rate,
              resolution_delay_p90_days=excluded.resolution_delay_p90_days,
              sample_size=excluded.sample_size,
              source_id=COALESCE(excluded.source_id, liberty_enforcement_observations.source_id),
              source_url=excluded.source_url,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                observation_key,
                fragment_id,
                method_version,
                _norm(row.get("territory_key")),
                _norm(row.get("territory_label")) or None,
                _norm(row.get("period_date")),
                _to_float_or_none(row.get("sanction_rate_per_1000")),
                _to_float_or_none(row.get("annulment_rate")),
                _to_float_or_none(row.get("resolution_delay_p90_days")),
                _to_int_or_none(row.get("sample_size")),
                sid or None,
                _norm(row.get("source_url")) or None,
                payload,
                ts,
                ts,
            ),
        )
        counts["observations_updated" if exists else "observations_inserted"] += 1

    conn.commit()

    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM liberty_enforcement_methodologies) AS methodologies_total,
          (SELECT COUNT(*) FROM liberty_enforcement_observations) AS observations_total,
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_enforcement_observations) AS fragments_with_observations_total
        """
    ).fetchone()

    return {
        "status": "ok",
        "snapshot_date": snapshot_date,
        "source_id_used": sid,
        "method_version": method_version,
        "counts": counts,
        "totals": {
            "methodologies_total": int(totals["methodologies_total"]),
            "observations_total": int(totals["observations_total"]),
            "fragments_with_observations_total": int(totals["fragments_with_observations_total"]),
        },
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Import liberty_enforcement_seed_v1 into SQLite")
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed", default="etl/data/seeds/liberty_enforcement_seed_v1.json")
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
            "method_version": _norm(validation.get("method_version")),
            "observations_total": int(validation.get("observations_total") or 0),
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
