#!/usr/bin/env python3
"""Import liberty_restrictions_seed_v1 into rights restriction tables."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws
from scripts.validate_liberty_restrictions_seed import WEIGHT_KEYS, validate_seed


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


def _assessment_key(row: dict[str, Any], method_version: str) -> str:
    given = _norm(row.get("assessment_key"))
    if given:
        return given
    return "|".join([method_version, _norm(row.get("fragment_id")), _norm(row.get("right_category_id"))])


def _compute_irlc_score(row: dict[str, Any], weights: dict[str, float], scale_max: float) -> float:
    acc = 0.0
    for key in WEIGHT_KEYS:
        acc += float(row.get(key) or 0.0) * float(weights.get(key) or 0.0)
    return round(acc * float(scale_max), 6)


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
    method_version = _norm(methodology.get("method_version")) or "irlc_v1"
    method_label = _norm(methodology.get("method_label")) or "Indice de Restriccion de Libertad Ciudadana v1"
    scale_max = _to_float_or_none(methodology.get("scale_max"))
    if scale_max is None or scale_max <= 0:
        scale_max = 100.0
    weights_doc = methodology.get("weights") if isinstance(methodology.get("weights"), dict) else {}
    weights: dict[str, float] = {}
    for key in WEIGHT_KEYS:
        weights[key] = float(weights_doc.get(key) or 0.0)

    counts: dict[str, int] = {
        "methodology_inserted": 0,
        "methodology_updated": 0,
        "right_categories_inserted": 0,
        "right_categories_updated": 0,
        "assessments_inserted": 0,
        "assessments_updated": 0,
        "unresolved_fragment_refs": 0,
        "unresolved_right_refs": 0,
    }

    method_exists = conn.execute(
        "SELECT 1 FROM liberty_irlc_methodologies WHERE method_version = ?",
        (method_version,),
    ).fetchone()
    method_payload = json.dumps(
        {**methodology, "seed_schema_version": _norm(seed_doc.get("schema_version")), "snapshot_date": snapshot_date},
        ensure_ascii=False,
        sort_keys=True,
    )
    conn.execute(
        """
        INSERT INTO liberty_irlc_methodologies (
          method_version, method_label, scale_max, weights_json, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(method_version) DO UPDATE SET
          method_label=excluded.method_label,
          scale_max=excluded.scale_max,
          weights_json=excluded.weights_json,
          notes=excluded.notes,
          updated_at=excluded.updated_at
        """,
        (
            method_version,
            method_label,
            float(scale_max),
            json.dumps(weights, ensure_ascii=False, sort_keys=True),
            _norm(methodology.get("notes")) or None,
            ts,
            ts,
        ),
    )
    counts["methodology_updated" if method_exists else "methodology_inserted"] += 1

    right_categories = seed_doc.get("right_categories") if isinstance(seed_doc.get("right_categories"), list) else []
    for row in right_categories:
        if not isinstance(row, dict):
            continue
        right_category_id = _norm(row.get("right_category_id"))
        if not right_category_id:
            continue
        exists = conn.execute(
            "SELECT 1 FROM liberty_right_categories WHERE right_category_id = ?",
            (right_category_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO liberty_right_categories (
              right_category_id, label, description, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(right_category_id) DO UPDATE SET
              label=excluded.label,
              description=excluded.description,
              updated_at=excluded.updated_at
            """,
            (
                right_category_id,
                _norm(row.get("label")),
                _norm(row.get("description")) or None,
                ts,
                ts,
            ),
        )
        counts["right_categories_updated" if exists else "right_categories_inserted"] += 1

    assessments = seed_doc.get("fragment_assessments") if isinstance(seed_doc.get("fragment_assessments"), list) else []
    for row in assessments:
        if not isinstance(row, dict):
            continue
        fragment_id = _norm(row.get("fragment_id"))
        right_category_id = _norm(row.get("right_category_id"))
        if not _exists(conn, "legal_norm_fragments", "fragment_id", fragment_id):
            counts["unresolved_fragment_refs"] += 1
            continue
        if not _exists(conn, "liberty_right_categories", "right_category_id", right_category_id):
            counts["unresolved_right_refs"] += 1
            continue
        key = _assessment_key(row, method_version)
        if not key:
            continue
        exists = conn.execute(
            "SELECT 1 FROM liberty_restriction_assessments WHERE assessment_key = ?",
            (key,),
        ).fetchone()

        irlc_score = _compute_irlc_score(row, weights, float(scale_max))
        payload = json.dumps(
            {
                **row,
                "computed_irlc_score": irlc_score,
                "weights": weights,
                "method_version": method_version,
                "seed_schema_version": _norm(seed_doc.get("schema_version")),
                "snapshot_date": snapshot_date,
                "methodology_payload": method_payload,
            },
            ensure_ascii=False,
            sort_keys=True,
        )

        conn.execute(
            """
            INSERT INTO liberty_restriction_assessments (
              assessment_key, fragment_id, right_category_id, method_version,
              reach_score, intensity_score, due_process_risk_score, reversibility_risk_score,
              discretionality_score, compliance_cost_score, irlc_score, confidence,
              source_id, source_url, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(assessment_key) DO UPDATE SET
              fragment_id=excluded.fragment_id,
              right_category_id=excluded.right_category_id,
              method_version=excluded.method_version,
              reach_score=excluded.reach_score,
              intensity_score=excluded.intensity_score,
              due_process_risk_score=excluded.due_process_risk_score,
              reversibility_risk_score=excluded.reversibility_risk_score,
              discretionality_score=excluded.discretionality_score,
              compliance_cost_score=excluded.compliance_cost_score,
              irlc_score=excluded.irlc_score,
              confidence=excluded.confidence,
              source_id=COALESCE(excluded.source_id, liberty_restriction_assessments.source_id),
              source_url=excluded.source_url,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                key,
                fragment_id,
                right_category_id,
                method_version,
                float(row.get("reach_score") or 0.0),
                float(row.get("intensity_score") or 0.0),
                float(row.get("due_process_risk_score") or 0.0),
                float(row.get("reversibility_risk_score") or 0.0),
                float(row.get("discretionality_score") or 0.0),
                float(row.get("compliance_cost_score") or 0.0),
                irlc_score,
                _to_float_or_none(row.get("confidence")),
                sid or None,
                _norm(row.get("source_url")) or None,
                payload,
                ts,
                ts,
            ),
        )
        counts["assessments_updated" if exists else "assessments_inserted"] += 1

    conn.commit()

    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM liberty_irlc_methodologies) AS methodologies_total,
          (SELECT COUNT(*) FROM liberty_right_categories) AS right_categories_total,
          (SELECT COUNT(*) FROM liberty_restriction_assessments) AS assessments_total,
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_restriction_assessments) AS fragments_with_irlc_total
        """
    ).fetchone()

    return {
        "status": "ok",
        "snapshot_date": snapshot_date,
        "source_id_used": sid,
        "method_version": method_version,
        "scale_max": float(scale_max),
        "counts": counts,
        "totals": {
            "methodologies_total": int(totals["methodologies_total"]),
            "right_categories_total": int(totals["right_categories_total"]),
            "assessments_total": int(totals["assessments_total"]),
            "fragments_with_irlc_total": int(totals["fragments_with_irlc_total"]),
        },
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Import liberty_restrictions_seed_v1 into SQLite")
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed", default="etl/data/seeds/liberty_restrictions_seed_v1.json")
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
            "right_categories_total": int(validation.get("right_categories_total") or 0),
            "fragment_assessments_total": int(validation.get("fragment_assessments_total") or 0),
            "method_version": _norm(validation.get("method_version")),
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
