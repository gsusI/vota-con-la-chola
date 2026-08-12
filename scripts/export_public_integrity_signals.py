#!/usr/bin/env python3
"""Export only human-approved, safety-gated integrity signals."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.util import now_utc_iso  # noqa: E402
from publicdata_evidence import ensure_integrity_signal_schema, public_integrity_signals  # noqa: E402
from publicdata_sqlite import open_db  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export approved integrity signals")
    parser.add_argument("--db", default="etl/data/staging/politicos-es.db")
    parser.add_argument("--snapshot-date", required=True)
    parser.add_argument("--evidence-limit", type=int, default=20)
    parser.add_argument(
        "--out", default="etl/data/published/integrity-signals-latest.json"
    )
    return parser.parse_args(argv)


def build_public_integrity_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot_date: str,
    evidence_limit: int = 20,
) -> dict[str, Any]:
    if int(evidence_limit) < 1 or int(evidence_limit) > 1_000:
        raise ValueError("evidence_limit must be between 1 and 1000")
    ensure_integrity_signal_schema(conn)
    signals = public_integrity_signals(conn)
    output: list[dict[str, Any]] = []
    for signal in signals:
        evidence_rows = conn.execute(
            """
            SELECT evidence_role, independent_source_key, source_id,
                   source_url, content_sha256, observed_at
            FROM integrity_signal_evidence
            WHERE signal_id = ?
            ORDER BY evidence_role, independent_source_key, signal_evidence_id
            LIMIT ?
            """,
            (signal["signal_id"], int(evidence_limit) + 1),
        ).fetchall()
        evidence_truncated = len(evidence_rows) > int(evidence_limit)
        evidence_rows = evidence_rows[: int(evidence_limit)]
        evidence = [dict(row) for row in evidence_rows]
        independent_sources = sorted(
            {str(row["independent_source_key"]) for row in evidence_rows}
        )
        output.append(
            {
                **signal,
                "independent_source_count": len(independent_sources),
                "evidence": evidence,
                "evidence_truncated": evidence_truncated,
            }
        )
    return {
        "schema_version": "public_integrity_signals_v1",
        "snapshot_date": snapshot_date,
        "generated_at": now_utc_iso(),
        "signals_total": len(output),
        "signals": output,
        "safety_contract": {
            "review_signals_are_not_public": True,
            "models_cannot_approve_publication": True,
            "right_of_reply_resolved": True,
            "corrections_withdraw_superseded_signals": True,
            "anomaly_is_not_corruption_finding": True,
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    if not db_path.is_file():
        print(f"ERROR: DB not found: {db_path.name}", file=sys.stderr)
        return 2
    try:
        conn = open_db(db_path)
        try:
            snapshot = build_public_integrity_snapshot(
                conn,
                snapshot_date=str(args.snapshot_date),
                evidence_limit=int(args.evidence_limit),
            )
        finally:
            conn.close()
    except (ValueError, sqlite3.Error) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(snapshot, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"status": "ok", "signals_total": snapshot["signals_total"], "out": out_path.name},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
