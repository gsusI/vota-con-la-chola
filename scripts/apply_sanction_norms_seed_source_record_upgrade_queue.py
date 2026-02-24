#!/usr/bin/env python3
"""Apply seed->non-seed source_record upgrades for sanction responsibility evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from etl.parlamentario_es.db import open_db
from etl.politicos_es.util import normalize_ws


def _norm(v: Any) -> str:
    return normalize_ws(str(v or ""))


def _canonical_alias_source_record_id(boe_id: str) -> str:
    token = _norm(boe_id).upper()
    return f"boe_ref:{token}" if token else ""


def _is_seed_payload(raw_payload: Any, *, seed_schema_version: str) -> bool:
    return f'"seed_schema_version": "{seed_schema_version}"' in str(raw_payload or "")


def apply_upgrades(
    conn: Any,
    *,
    seed_schema_version: str = "sanction_norms_seed_v1",
    limit: int = 0,
    dry_run: bool = False,
) -> dict[str, Any]:
    sql = """
        SELECT
          e.responsibility_evidence_id,
          e.source_id AS evidence_source_id,
          e.source_record_pk AS current_source_record_pk,
          n.boe_id,
          sr.source_id AS current_source_record_source_id,
          sr.source_record_id AS current_source_record_id,
          sr.raw_payload AS current_source_record_raw_payload
        FROM legal_fragment_responsibility_evidence e
        JOIN legal_fragment_responsibilities r ON r.responsibility_id = e.responsibility_id
        JOIN legal_norm_fragments f ON f.fragment_id = r.fragment_id
        JOIN legal_norms n ON n.norm_id = f.norm_id
        JOIN source_records sr ON sr.source_record_pk = e.source_record_pk
        WHERE COALESCE(sr.raw_payload, '') LIKE ?
        ORDER BY e.responsibility_evidence_id
    """
    params: list[Any] = [f'%"seed_schema_version": "{_norm(seed_schema_version)}"%']
    if int(limit) > 0:
        sql += " LIMIT ?"
        params.append(int(limit))

    rows = conn.execute(sql, tuple(params)).fetchall()

    counts: dict[str, int] = {
        "queue_rows_seen": len(rows),
        "upgraded_rows": 0,
        "already_non_seed_rows": 0,
        "missing_boe_id_rows": 0,
        "missing_candidate_rows": 0,
        "candidate_seed_rows": 0,
    }
    upgraded_samples: list[dict[str, Any]] = []
    missing_samples: list[dict[str, Any]] = []

    for row in rows:
        evidence_id = int(row["responsibility_evidence_id"])
        boe_id = _norm(row["boe_id"]).upper()
        evidence_source_id = _norm(row["evidence_source_id"]) or _norm(row["current_source_record_source_id"])
        current_source_record_pk = int(row["current_source_record_pk"])

        if not boe_id:
            counts["missing_boe_id_rows"] += 1
            if len(missing_samples) < 20:
                missing_samples.append(
                    {
                        "responsibility_evidence_id": evidence_id,
                        "reason": "missing_boe_id",
                        "current_source_record_pk": current_source_record_pk,
                    }
                )
            continue

        candidate_source_record_id = _canonical_alias_source_record_id(boe_id)
        if not candidate_source_record_id:
            counts["missing_boe_id_rows"] += 1
            continue

        candidate = conn.execute(
            """
            SELECT source_record_pk, source_id, source_record_id, raw_payload
            FROM source_records
            WHERE source_id = ? AND source_record_id = ?
            """,
            (evidence_source_id, candidate_source_record_id),
        ).fetchone()
        if candidate is None:
            counts["missing_candidate_rows"] += 1
            if len(missing_samples) < 20:
                missing_samples.append(
                    {
                        "responsibility_evidence_id": evidence_id,
                        "reason": "missing_candidate",
                        "boe_id": boe_id,
                        "candidate_source_record_id": candidate_source_record_id,
                        "current_source_record_pk": current_source_record_pk,
                    }
                )
            continue

        candidate_pk = int(candidate["source_record_pk"])
        candidate_is_seed = _is_seed_payload(candidate["raw_payload"], seed_schema_version=seed_schema_version)
        if candidate_is_seed:
            counts["candidate_seed_rows"] += 1
            if len(missing_samples) < 20:
                missing_samples.append(
                    {
                        "responsibility_evidence_id": evidence_id,
                        "reason": "candidate_is_seed",
                        "boe_id": boe_id,
                        "candidate_source_record_pk": candidate_pk,
                        "candidate_source_record_id": _norm(candidate["source_record_id"]),
                    }
                )
            continue

        if candidate_pk == current_source_record_pk:
            counts["already_non_seed_rows"] += 1
            continue

        if not dry_run:
            conn.execute(
                """
                UPDATE legal_fragment_responsibility_evidence
                SET source_record_pk = ?, updated_at = ?
                WHERE responsibility_evidence_id = ?
                """,
                (candidate_pk, _norm(conn.execute("SELECT datetime('now')").fetchone()[0]), evidence_id),
            )

        counts["upgraded_rows"] += 1
        if len(upgraded_samples) < 20:
            upgraded_samples.append(
                {
                    "responsibility_evidence_id": evidence_id,
                    "boe_id": boe_id,
                    "from_source_record_pk": current_source_record_pk,
                    "to_source_record_pk": candidate_pk,
                    "to_source_record_id": _norm(candidate["source_record_id"]),
                }
            )

    if not dry_run:
        conn.commit()
    return {
        "seed_schema_version": _norm(seed_schema_version) or "sanction_norms_seed_v1",
        "dry_run": bool(dry_run),
        "counts": counts,
        "upgraded_samples": upgraded_samples,
        "missing_samples": missing_samples,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Apply sanction source_record upgrades from seed to non-seed aliases")
    ap.add_argument("--db", required=True)
    ap.add_argument("--seed-schema-version", default="sanction_norms_seed_v1")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    conn = open_db(Path(args.db))
    try:
        report = apply_upgrades(
            conn,
            seed_schema_version=_norm(args.seed_schema_version) or "sanction_norms_seed_v1",
            limit=int(args.limit),
            dry_run=bool(args.dry_run),
        )
    finally:
        conn.close()

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if _norm(args.out):
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
