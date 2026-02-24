#!/usr/bin/env python3
"""Import liberty_proportionality_seed_v1 into proportionality review tables."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import apply_schema, open_db
from etl.politicos_es.util import normalize_ws
from scripts.validate_liberty_proportionality_seed import WEIGHT_KEYS, validate_seed


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


def _to_int01(v: Any) -> int:
    token = _norm(v)
    return 1 if token == "1" else 0


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


def _review_key(row: dict[str, Any], method_version: str) -> str:
    given = _norm(row.get("review_key"))
    if given:
        return given
    return "|".join([method_version, _norm(row.get("fragment_id"))])


def _compute_score(row: dict[str, Any], weights: dict[str, float]) -> float:
    score = 0.0
    score += float(row.get("necessity_score") or 0.0) * float(weights.get("necessity_score") or 0.0)
    score += float(row.get("observed_effectiveness_score") or 0.0) * float(weights.get("observed_effectiveness_score") or 0.0)
    score += float(_to_int01(row.get("alternatives_less_restrictive_considered"))) * float(weights.get("alternatives_less_restrictive_considered") or 0.0)
    score += float(_to_int01(row.get("objective_defined"))) * float(weights.get("objective_defined") or 0.0)
    score += float(_to_int01(row.get("indicator_defined"))) * float(weights.get("indicator_defined") or 0.0)
    score += float(_to_int01(row.get("sunset_review_present"))) * float(weights.get("sunset_review_present") or 0.0)
    return round(score * 100.0, 6)


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
    method_version = _norm(methodology.get("method_version")) or "proportionality_v1"
    method_label = _norm(methodology.get("method_label")) or "Test de necesidad y proporcionalidad v1"
    weights_doc = methodology.get("weights") if isinstance(methodology.get("weights"), dict) else {}
    weights: dict[str, float] = {}
    for key in WEIGHT_KEYS:
        weights[key] = float(weights_doc.get(key) or 0.0)

    counts: dict[str, int] = {
        "methodology_inserted": 0,
        "methodology_updated": 0,
        "reviews_inserted": 0,
        "reviews_updated": 0,
        "unresolved_fragment_refs": 0,
    }

    method_exists = conn.execute(
        "SELECT 1 FROM liberty_proportionality_methodologies WHERE method_version = ?",
        (method_version,),
    ).fetchone()
    conn.execute(
        """
        INSERT INTO liberty_proportionality_methodologies (
          method_version, method_label, weights_json, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(method_version) DO UPDATE SET
          method_label=excluded.method_label,
          weights_json=excluded.weights_json,
          notes=excluded.notes,
          updated_at=excluded.updated_at
        """,
        (
            method_version,
            method_label,
            json.dumps(weights, ensure_ascii=False, sort_keys=True),
            _norm(methodology.get("notes")) or None,
            ts,
            ts,
        ),
    )
    counts["methodology_updated" if method_exists else "methodology_inserted"] += 1

    reviews = seed_doc.get("reviews") if isinstance(seed_doc.get("reviews"), list) else []
    for row in reviews:
        if not isinstance(row, dict):
            continue
        fragment_id = _norm(row.get("fragment_id"))
        if not _exists(conn, "legal_norm_fragments", "fragment_id", fragment_id):
            counts["unresolved_fragment_refs"] += 1
            continue

        review_key = _review_key(row, method_version)
        if not review_key:
            continue
        exists = conn.execute(
            "SELECT 1 FROM liberty_proportionality_reviews WHERE review_key = ?",
            (review_key,),
        ).fetchone()
        proportionality_score = _compute_score(row, weights)
        payload = json.dumps(
            {
                **row,
                "computed_proportionality_score": proportionality_score,
                "weights": weights,
                "method_version": method_version,
                "seed_schema_version": _norm(seed_doc.get("schema_version")),
                "snapshot_date": snapshot_date,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        conn.execute(
            """
            INSERT INTO liberty_proportionality_reviews (
              review_key, fragment_id, method_version,
              objective_defined, objective_text,
              indicator_defined, indicator_text,
              alternatives_less_restrictive_considered, alternatives_notes,
              sunset_review_present, sunset_review_notes,
              observed_effectiveness_score, necessity_score, proportionality_score,
              assessment_label, confidence,
              source_id, source_url, raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(review_key) DO UPDATE SET
              fragment_id=excluded.fragment_id,
              method_version=excluded.method_version,
              objective_defined=excluded.objective_defined,
              objective_text=excluded.objective_text,
              indicator_defined=excluded.indicator_defined,
              indicator_text=excluded.indicator_text,
              alternatives_less_restrictive_considered=excluded.alternatives_less_restrictive_considered,
              alternatives_notes=excluded.alternatives_notes,
              sunset_review_present=excluded.sunset_review_present,
              sunset_review_notes=excluded.sunset_review_notes,
              observed_effectiveness_score=excluded.observed_effectiveness_score,
              necessity_score=excluded.necessity_score,
              proportionality_score=excluded.proportionality_score,
              assessment_label=excluded.assessment_label,
              confidence=excluded.confidence,
              source_id=COALESCE(excluded.source_id, liberty_proportionality_reviews.source_id),
              source_url=excluded.source_url,
              raw_payload=excluded.raw_payload,
              updated_at=excluded.updated_at
            """,
            (
                review_key,
                fragment_id,
                method_version,
                _to_int01(row.get("objective_defined")),
                _norm(row.get("objective_text")) or None,
                _to_int01(row.get("indicator_defined")),
                _norm(row.get("indicator_text")) or None,
                _to_int01(row.get("alternatives_less_restrictive_considered")),
                _norm(row.get("alternatives_notes")) or None,
                _to_int01(row.get("sunset_review_present")),
                _norm(row.get("sunset_review_notes")) or None,
                float(row.get("observed_effectiveness_score") or 0.0),
                float(row.get("necessity_score") or 0.0),
                proportionality_score,
                _norm(row.get("assessment_label")),
                _to_float_or_none(row.get("confidence")),
                sid or None,
                _norm(row.get("source_url")) or None,
                payload,
                ts,
                ts,
            ),
        )
        counts["reviews_updated" if exists else "reviews_inserted"] += 1

    conn.commit()

    totals = conn.execute(
        """
        SELECT
          (SELECT COUNT(*) FROM liberty_proportionality_methodologies) AS methodologies_total,
          (SELECT COUNT(*) FROM liberty_proportionality_reviews) AS reviews_total,
          (SELECT COUNT(DISTINCT fragment_id) FROM liberty_proportionality_reviews) AS fragments_with_reviews_total
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
            "reviews_total": int(totals["reviews_total"]),
            "fragments_with_reviews_total": int(totals["fragments_with_reviews_total"]),
        },
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Import liberty_proportionality_seed_v1 into SQLite")
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed", default="etl/data/seeds/liberty_proportionality_seed_v1.json")
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
            "reviews_total": int(validation.get("reviews_total") or 0),
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
