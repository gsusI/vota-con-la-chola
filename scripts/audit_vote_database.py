#!/usr/bin/env python3
"""Audit vote/member scale, lineage-adjacent integrity, and tally reconciliation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_core.util import now_utc_iso


YES = ("Sí", "SÍ", "SI", "Si", "sí", "si", "yes", "YES")
NO = ("No", "NO", "no")
ABSTAIN = (
    "Abstención",
    "ABSTENCIÓN",
    "Abstencion",
    "ABSTENCION",
    "abstención",
    "abstencion",
    "abstain",
)
NO_VOTE = (
    "No vota",
    "NO VOTA",
    "No votan",
    "NO VOTAN",
    "no vota",
    "no votan",
    "no_vote",
)
ABSENT = ("Ausente", "AUSENTE", "ausente", "absent")
RECOGNIZED = YES + NO + ABSTAIN + NO_VOTE + ABSENT
MISMATCH_DIMENSIONS = ("yes", "no", "abstain", "no_vote", "absent")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database to audit")
    parser.add_argument("--baseline-db", default=None, help="Optional before-state SQLite database")
    parser.add_argument("--out", default=None, help="Optional JSON report path")
    return parser.parse_args(argv)


def _placeholders(values: tuple[str, ...]) -> str:
    return ",".join("?" for _ in values)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(str(row[1]) == column for row in conn.execute(f"PRAGMA table_info({table})"))


def _empty_mismatch_profile() -> dict[str, Any]:
    return {
        "events": 0,
        "classes": {
            "observed_rows_below_official_categories": 0,
            "observed_rows_above_official_categories": 0,
            "same_category_total_wrong_distribution": 0,
        },
        "dimensions": {
            dimension: {
                "events_mismatched": 0,
                "observed_minus_expected_sum": 0,
                "absolute_delta_sum": 0,
                "max_absolute_delta": 0,
            }
            for dimension in MISMATCH_DIMENSIONS
        },
    }


def _update_mismatch_profile(
    profile: dict[str, Any],
    *,
    deltas: dict[str, int | None],
) -> None:
    profile["events"] += 1
    comparable_deltas = [delta for delta in deltas.values() if delta is not None]
    population_delta = sum(comparable_deltas)
    if population_delta < 0:
        mismatch_class = "observed_rows_below_official_categories"
    elif population_delta > 0:
        mismatch_class = "observed_rows_above_official_categories"
    else:
        mismatch_class = "same_category_total_wrong_distribution"
    profile["classes"][mismatch_class] += 1
    for dimension, delta in deltas.items():
        if delta in (None, 0):
            continue
        stats = profile["dimensions"][dimension]
        absolute_delta = abs(delta)
        stats["events_mismatched"] += 1
        stats["observed_minus_expected_sum"] += delta
        stats["absolute_delta_sum"] += absolute_delta
        stats["max_absolute_delta"] = max(
            int(stats["max_absolute_delta"]), absolute_delta
        )


def _mismatch_profile(
    conn: sqlite3.Connection, *, has_absent_total: bool
) -> dict[str, Any]:
    absent_total_sql = "e.totals_absent" if has_absent_total else "NULL"
    values = YES + NO + ABSTAIN + NO_VOTE + ABSENT
    sql = f"""
    WITH observed AS (
      SELECT
        vote_event_id,
        SUM(CASE WHEN vote_choice IN ({_placeholders(YES)}) THEN 1 ELSE 0 END) AS yes_n,
        SUM(CASE WHEN vote_choice IN ({_placeholders(NO)}) THEN 1 ELSE 0 END) AS no_n,
        SUM(CASE WHEN vote_choice IN ({_placeholders(ABSTAIN)}) THEN 1 ELSE 0 END) AS abstain_n,
        SUM(CASE WHEN vote_choice IN ({_placeholders(NO_VOTE)}) THEN 1 ELSE 0 END) AS no_vote_n,
        SUM(CASE WHEN vote_choice IN ({_placeholders(ABSENT)}) THEN 1 ELSE 0 END) AS absent_n
      FROM parl_vote_member_votes
      GROUP BY vote_event_id
    ), scored AS (
      SELECT
        e.source_id,
        e.vote_event_id,
        o.yes_n,
        o.no_n,
        o.abstain_n,
        o.no_vote_n,
        o.absent_n,
        COALESCE(e.totals_yes, 0) AS expected_yes,
        COALESCE(e.totals_no, 0) AS expected_no,
        COALESCE(e.totals_abstain, 0) AS expected_abstain,
        COALESCE(e.totals_no_vote, 0) AS expected_no_vote,
        {absent_total_sql} AS expected_absent,
        CASE WHEN
          COALESCE(e.totals_yes, 0) + COALESCE(e.totals_no, 0) +
          COALESCE(e.totals_abstain, 0) + COALESCE(e.totals_no_vote, 0) +
          COALESCE({absent_total_sql}, 0) > 0 OR COALESCE(e.totals_present, 0) > 0
        THEN 1 ELSE 0 END AS totals_available
      FROM parl_vote_events AS e
      JOIN observed AS o USING (vote_event_id)
    )
    SELECT *
    FROM scored
    WHERE totals_available = 1 AND NOT (
      yes_n = expected_yes AND
      no_n = expected_no AND
      abstain_n = expected_abstain AND
      no_vote_n = expected_no_vote AND
      (expected_absent IS NULL OR absent_n = expected_absent)
    )
    ORDER BY source_id, vote_event_id
    """
    total = _empty_mismatch_profile()
    sources: dict[str, dict[str, Any]] = {}
    for row in conn.execute(sql, values):
        expected_absent = row["expected_absent"]
        deltas: dict[str, int | None] = {
            "yes": int(row["yes_n"]) - int(row["expected_yes"]),
            "no": int(row["no_n"]) - int(row["expected_no"]),
            "abstain": int(row["abstain_n"]) - int(row["expected_abstain"]),
            "no_vote": int(row["no_vote_n"]) - int(row["expected_no_vote"]),
            "absent": (
                int(row["absent_n"]) - int(expected_absent)
                if expected_absent is not None
                else None
            ),
        }
        source_id = str(row["source_id"])
        source = sources.setdefault(source_id, _empty_mismatch_profile())
        _update_mismatch_profile(total, deltas=deltas)
        _update_mismatch_profile(source, deltas=deltas)
    return {"total": total, "sources": sources}


def audit_database(path: Path, *, include_sha256: bool = True) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        has_absent_total = _has_column(conn, "parl_vote_events", "totals_absent")
        absent_total_sql = "e.totals_absent" if has_absent_total else "NULL"
        values = YES + NO + ABSTAIN + NO_VOTE + ABSENT + RECOGNIZED
        sql = f"""
        WITH observed AS (
          SELECT
            vote_event_id,
            SUM(CASE WHEN vote_choice IN ({_placeholders(YES)}) THEN 1 ELSE 0 END) AS yes_n,
            SUM(CASE WHEN vote_choice IN ({_placeholders(NO)}) THEN 1 ELSE 0 END) AS no_n,
            SUM(CASE WHEN vote_choice IN ({_placeholders(ABSTAIN)}) THEN 1 ELSE 0 END) AS abstain_n,
            SUM(CASE WHEN vote_choice IN ({_placeholders(NO_VOTE)}) THEN 1 ELSE 0 END) AS no_vote_n,
            SUM(CASE WHEN vote_choice IN ({_placeholders(ABSENT)}) THEN 1 ELSE 0 END) AS absent_n,
            SUM(CASE WHEN vote_choice NOT IN ({_placeholders(RECOGNIZED)}) THEN 1 ELSE 0 END) AS other_n,
            COUNT(*) AS member_votes,
            SUM(CASE WHEN person_id IS NOT NULL THEN 1 ELSE 0 END) AS person_ids
          FROM parl_vote_member_votes
          GROUP BY vote_event_id
        ), scored AS (
          SELECT
            e.source_id,
            e.vote_event_id,
            o.*,
            COALESCE(e.totals_yes, 0) AS expected_yes,
            COALESCE(e.totals_no, 0) AS expected_no,
            COALESCE(e.totals_abstain, 0) AS expected_abstain,
            COALESCE(e.totals_no_vote, 0) AS expected_no_vote,
            {absent_total_sql} AS expected_absent,
            CASE WHEN
              COALESCE(e.totals_yes, 0) + COALESCE(e.totals_no, 0) +
              COALESCE(e.totals_abstain, 0) + COALESCE(e.totals_no_vote, 0) +
              COALESCE({absent_total_sql}, 0) > 0 OR COALESCE(e.totals_present, 0) > 0
            THEN 1 ELSE 0 END AS totals_available
          FROM parl_vote_events AS e
          JOIN observed AS o USING (vote_event_id)
        ), event_counts AS (
          SELECT source_id, COUNT(*) AS events_total
          FROM parl_vote_events
          GROUP BY source_id
        )
        SELECT
          event_counts.source_id,
          event_counts.events_total,
          COUNT(scored.vote_event_id) AS events_with_member_votes,
          COALESCE(SUM(scored.totals_available), 0) AS events_totals_available,
          COALESCE(SUM(CASE WHEN scored.expected_absent IS NOT NULL THEN 1 ELSE 0 END), 0)
            AS events_absent_totals_available,
          COALESCE(SUM(CASE WHEN scored.totals_available = 1 AND
            scored.yes_n = scored.expected_yes AND
            scored.no_n = scored.expected_no AND
            scored.abstain_n = scored.expected_abstain AND
            scored.no_vote_n = scored.expected_no_vote AND
            (scored.expected_absent IS NULL OR scored.absent_n = scored.expected_absent)
          THEN 1 ELSE 0 END), 0) AS events_reconciled,
          COALESCE(SUM(CASE WHEN scored.totals_available = 1 AND NOT (
            scored.yes_n = scored.expected_yes AND
            scored.no_n = scored.expected_no AND
            scored.abstain_n = scored.expected_abstain AND
            scored.no_vote_n = scored.expected_no_vote AND
            (scored.expected_absent IS NULL OR scored.absent_n = scored.expected_absent)
          ) THEN 1 ELSE 0 END), 0) AS events_not_reconciled,
          COALESCE(SUM(CASE WHEN scored.totals_available = 0 THEN 1 ELSE 0 END), 0)
            AS events_totals_unavailable,
          COALESCE(SUM(scored.member_votes), 0) AS member_votes,
          COALESCE(SUM(scored.person_ids), 0) AS member_votes_with_person_id,
          COALESCE(SUM(scored.absent_n), 0) AS member_votes_absent,
          COALESCE(SUM(scored.other_n), 0) AS member_votes_other_choice
        FROM event_counts
        LEFT JOIN scored ON scored.source_id = event_counts.source_id
        GROUP BY event_counts.source_id, event_counts.events_total
        ORDER BY event_counts.source_id
        """
        sources: list[dict[str, Any]] = []
        for row in conn.execute(sql, values):
            item = {key: int(row[key]) if key != "source_id" else str(row[key]) for key in row.keys()}
            denominator = int(item["events_totals_available"])
            member_denominator = int(item["member_votes"])
            item["events_reconciled_pct"] = (
                round(int(item["events_reconciled"]) / denominator, 6)
                if denominator
                else 0.0
            )
            item["member_votes_with_person_id_pct"] = (
                round(int(item["member_votes_with_person_id"]) / member_denominator, 6)
                if member_denominator
                else 0.0
            )
            sources.append(item)

        totals: dict[str, int | float] = {}
        additive_keys = (
            "events_total",
            "events_with_member_votes",
            "events_totals_available",
            "events_absent_totals_available",
            "events_reconciled",
            "events_not_reconciled",
            "events_totals_unavailable",
            "member_votes",
            "member_votes_with_person_id",
            "member_votes_absent",
            "member_votes_other_choice",
        )
        for key in additive_keys:
            totals[key] = sum(int(item[key]) for item in sources)
        totals_available = int(totals["events_totals_available"])
        member_votes = int(totals["member_votes"])
        totals["events_reconciled_pct"] = (
            round(int(totals["events_reconciled"]) / totals_available, 6)
            if totals_available
            else 0.0
        )
        totals["member_votes_with_person_id_pct"] = (
            round(int(totals["member_votes_with_person_id"]) / member_votes, 6)
            if member_votes
            else 0.0
        )

        integrity_rows = [str(row[0]) for row in conn.execute("PRAGMA integrity_check")]
        foreign_key_errors = sum(1 for _ in conn.execute("PRAGMA foreign_key_check"))
        entity_counts = {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("persons", "mandates")
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            is not None
        }
        return {
            "database_file": path.name,
            "database_bytes": int(path.stat().st_size),
            "database_sha256": _sha256_file(path) if include_sha256 else None,
            "integrity_check": integrity_rows,
            "foreign_key_errors": int(foreign_key_errors),
            "has_totals_absent_column": bool(has_absent_total),
            "entity_counts": entity_counts,
            "mismatch_profile": _mismatch_profile(
                conn, has_absent_total=has_absent_total
            ),
            "sources": sources,
            "totals": totals,
            "checks": {
                "sqlite_integrity": integrity_rows == ["ok"],
                "foreign_keys": foreign_key_errors == 0,
                "recognized_vote_choices": int(totals["member_votes_other_choice"]) == 0,
                "million_member_votes": member_votes >= 1_000_000,
            },
        }
    finally:
        conn.close()


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "events_with_member_votes",
        "events_reconciled",
        "events_not_reconciled",
        "member_votes",
        "member_votes_with_person_id",
    )
    entity_keys = set(after.get("entity_counts") or {}) | set(
        before.get("entity_counts") or {}
    )
    return {
        **{
            key: int(after["totals"][key]) - int(before["totals"][key])
            for key in keys
        },
        "foreign_key_errors": int(after["foreign_key_errors"])
        - int(before["foreign_key_errors"]),
        "events_reconciled_pct_points": round(
            100
            * (
                float(after["totals"]["events_reconciled_pct"])
                - float(before["totals"]["events_reconciled_pct"])
            ),
            4,
        ),
        "entity_counts": {
            key: int((after.get("entity_counts") or {}).get(key, 0))
            - int((before.get("entity_counts") or {}).get(key, 0))
            for key in sorted(entity_keys)
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    current = audit_database(Path(args.db))
    baseline = audit_database(Path(args.baseline_db)) if args.baseline_db else None
    report: dict[str, Any] = {
        "schema_version": "vote_database_audit_v2",
        "generated_at": now_utc_iso(),
        "current": current,
        "baseline": baseline,
        "delta": _delta(current, baseline) if baseline else None,
        "limitations": [
            "Tally reconciliation proves agreement with published aggregates; it does not prove the upstream roll call is complete or substantively correct.",
            "Absent is distinct from no-vote and is compared only where the event stores an explicit absence total.",
            "Mismatch classes compare observed member-row category counts with the official categories available for that event; they identify repair shape, not cause or responsibility.",
            "A person_id coverage gap remains a separate identity-resolution problem.",
        ],
    }
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "database": current["database_file"],
                "member_votes": current["totals"]["member_votes"],
                "events_reconciled_pct": current["totals"]["events_reconciled_pct"],
                "foreign_key_errors": current["foreign_key_errors"],
                "out": Path(args.out).name if args.out else None,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
