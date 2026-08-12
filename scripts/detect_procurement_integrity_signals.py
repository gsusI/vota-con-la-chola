#!/usr/bin/env python3
"""Create bounded human-review signals for procurement threshold patterns."""

from __future__ import annotations

import argparse
import calendar
import hashlib
import itertools
import json
import sqlite3
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from publicdata_evidence import (  # noqa: E402
    create_review_signal,
    supersede_internal_review_signals,
)
from publicdata_sqlite import open_db, table_exists  # noqa: E402

DETECTOR_ID = "procurement-threshold-pattern-review"
DETECTOR_VERSION = "v4"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect procurement review signals")
    parser.add_argument("--db", default="etl/data/staging/politicos-es.db")
    parser.add_argument("--threshold-eur", type=float, default=15_000.0)
    parser.add_argument("--min-records", type=int, default=3)
    parser.add_argument("--source-ids", default="")
    parser.add_argument("--max-signals", type=int, default=0)
    parser.add_argument("--evidence-sample-size", type=int, default=20)
    parser.add_argument("--supersede-missing", action="store_true")
    parser.add_argument("--supersede-prior-versions", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-out", default="")
    return parser.parse_args(argv)


def _source_ids(value: str) -> list[str]:
    return sorted({token.strip() for token in str(value).split(",") if token.strip()})


def _signal_id(
    authority: str,
    cpv_code: str,
    period_month: str,
    detection_fingerprint: str,
) -> str:
    raw = (
        f"{DETECTOR_ID}|{DETECTOR_VERSION}|{authority}|{cpv_code}|"
        f"{period_month}|{detection_fingerprint}"
    )
    return f"integrity-{hashlib.sha256(raw.encode()).hexdigest()[:32]}"


def iter_threshold_pattern_rows(
    conn: sqlite3.Connection,
    *,
    threshold_eur: float,
    min_records: int,
    source_ids: Iterable[str] = (),
) -> Iterable[sqlite3.Row]:
    sources = list(source_ids)
    source_filter = ""
    params: list[object] = [float(threshold_eur)]
    if sources:
        source_filter = f" AND candidate.source_id IN ({','.join('?' for _ in sources)})"
        params.extend(sources)
    params.extend((int(min_records), float(threshold_eur)))
    has_awards = table_exists(conn, "money_contract_award_results")
    award_candidates = ""
    if has_awards:
        award_candidates = """
          SELECT
            'award_result' AS evidence_basis,
            r.contract_award_result_id AS evidence_row_id,
            c.contract_record_id,
            r.source_id,
            r.source_record_pk,
            r.source_record_id,
            c.source_url,
            c.contracting_authority,
            c.cpv_code,
            SUBSTR(COALESCE(r.award_date, c.awarded_date, c.published_date), 1, 7)
              AS period_month,
            CAST(r.amount_eur_decimal AS REAL) AS amount_eur,
            r.amount_eur_decimal AS amount_eur_decimal,
            c.stable_contract_id,
            r.lot_id,
            r.supplier_identifier,
            sr.content_sha256
          FROM money_contract_award_results AS r
          JOIN latest_contracts AS c
            ON c.source_record_pk = r.source_record_pk AND c.version_rank = 1
          LEFT JOIN source_records AS sr
            ON sr.source_record_pk = r.source_record_pk
          WHERE r.amount_eur_decimal IS NOT NULL
            AND TRIM(r.amount_eur_decimal) != ''

          UNION ALL
        """
        no_award_filter = """
            AND NOT EXISTS (
              SELECT 1
              FROM money_contract_award_results AS award
              WHERE award.source_record_pk = c.source_record_pk
                AND award.amount_eur_decimal IS NOT NULL
                AND TRIM(award.amount_eur_decimal) != ''
            )
        """
    else:
        no_award_filter = ""
    sql = f"""
        WITH ranked_contracts AS (
          SELECT
            c.*,
            ROW_NUMBER() OVER (
              PARTITION BY c.source_id,
                COALESCE(NULLIF(c.stable_contract_id, ''),
                         'source:' || c.source_record_id)
              ORDER BY
                COALESCE(NULLIF(c.entry_updated_at, ''),
                         NULLIF(c.awarded_date, ''),
                         NULLIF(c.published_date, ''),
                         c.source_snapshot_date, '') DESC,
                c.contract_record_id DESC
            ) AS version_rank
          FROM money_contract_records AS c
        ), latest_contracts AS (
          SELECT * FROM ranked_contracts WHERE version_rank = 1
        ), candidates AS (
          {award_candidates}
          SELECT
            'contract_record' AS evidence_basis,
            c.contract_record_id AS evidence_row_id,
            c.contract_record_id,
            c.source_id,
            c.source_record_pk,
            c.source_record_id,
            c.source_url,
            c.contracting_authority,
            c.cpv_code,
            SUBSTR(COALESCE(c.awarded_date, c.published_date), 1, 7)
              AS period_month,
            CAST(COALESCE(c.amount_eur_decimal, c.amount_eur) AS REAL)
              AS amount_eur,
            COALESCE(c.amount_eur_decimal, CAST(c.amount_eur AS TEXT))
              AS amount_eur_decimal,
            c.stable_contract_id,
            c.lot_id,
            NULL AS supplier_identifier,
            sr.content_sha256
          FROM latest_contracts AS c
          LEFT JOIN source_records AS sr
            ON sr.source_record_pk = c.source_record_pk
          WHERE c.version_rank = 1
            {no_award_filter}
        ), eligible AS (
          SELECT candidate.*
          FROM candidates AS candidate
          WHERE candidate.amount_eur > 0 AND candidate.amount_eur < ?
            AND candidate.contracting_authority IS NOT NULL
            AND TRIM(candidate.contracting_authority) != ''
            AND candidate.cpv_code IS NOT NULL
            AND TRIM(candidate.cpv_code) != ''
            AND candidate.period_month GLOB '[12][0-9][0-9][0-9]-[01][0-9]'
            {source_filter}
        ), scored AS (
          SELECT *,
            COUNT(*) OVER (
              PARTITION BY contracting_authority, cpv_code, period_month
            ) AS group_records,
            SUM(amount_eur) OVER (
              PARTITION BY contracting_authority, cpv_code, period_month
            ) AS group_amount_eur
          FROM eligible
        )
        SELECT *
        FROM scored
        WHERE group_records >= ? AND group_amount_eur >= ?
        ORDER BY contracting_authority, cpv_code, period_month, evidence_row_id
    """
    yield from conn.execute(sql, params)


def detect_threshold_patterns(
    conn: sqlite3.Connection,
    *,
    threshold_eur: float,
    min_records: int,
    source_ids: Iterable[str] = (),
    max_signals: int = 0,
    evidence_sample_size: int = 20,
    persist: bool = True,
    supersede_missing: bool = False,
    supersede_prior_versions: bool = False,
) -> dict[str, Any]:
    if not table_exists(conn, "money_contract_records") or not table_exists(
        conn, "source_records"
    ):
        raise RuntimeError("money_contract_records and source_records are required")
    if threshold_eur <= 0 or min_records < 2 or evidence_sample_size < 1:
        raise ValueError("threshold must be positive; min-records >= 2; sample >= 1")

    rows = iter_threshold_pattern_rows(
        conn,
        threshold_eur=threshold_eur,
        min_records=min_records,
        source_ids=source_ids,
    )
    key_fn = lambda row: (
        str(row["contracting_authority"]),
        str(row["cpv_code"]),
        str(row["period_month"]),
    )
    totals = {
        "signals_detected": 0,
        "signals_persisted": 0,
        "signals_superseded_missing": 0,
        "signals_superseded_prior_versions": 0,
        "signals_materialized": 0,
        "evidence_rows_sampled": 0,
        "evidence_rows_materialized": 0,
        "matched_candidate_rows": 0,
        "matched_contract_rows": 0,
    }
    if persist and (supersede_missing or supersede_prior_versions):
        conn.execute(
            "CREATE TEMP TABLE IF NOT EXISTS active_detector_signal_ids "
            "(signal_id TEXT PRIMARY KEY) WITHOUT ROWID"
        )
        conn.execute("DELETE FROM active_detector_signal_ids")
    samples: list[dict[str, object]] = []
    for (authority, cpv_code, period_month), group in itertools.groupby(rows, key_fn):
        if max_signals > 0 and totals["signals_detected"] >= int(max_signals):
            break
        first: sqlite3.Row | None = None
        evidence: list[dict[str, object]] = []
        detection_digest = hashlib.sha256()
        for row in group:
            first = first or row
            detection_digest.update(
                json.dumps(
                    [
                        str(row["evidence_basis"]),
                        int(row["evidence_row_id"]),
                        int(row["source_record_pk"]),
                        str(row["amount_eur_decimal"]),
                    ],
                    ensure_ascii=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
            totals["matched_candidate_rows"] += 1
            totals["matched_contract_rows"] += 1
            if len(evidence) >= int(evidence_sample_size):
                continue
            evidence.append(
                {
                    "evidence_role": "observed",
                    "independent_source_key": str(row["source_id"]),
                    "source_id": str(row["source_id"]),
                    "source_record_pk": int(row["source_record_pk"]),
                    "source_url": str(row["source_url"] or ""),
                    "content_sha256": str(row["content_sha256"] or ""),
                    "observed_at": f"{period_month}-01",
                    "excerpt": (
                        f"Official {row['evidence_basis']} for contract record "
                        f"{row['source_record_id']} has amount_eur="
                        f"{row['amount_eur_decimal']}; pattern review only."
                    ),
                }
            )
        if first is None:
            continue
        group_records = int(first["group_records"])
        group_amount = float(first["group_amount_eur"])
        detection_fingerprint = detection_digest.hexdigest()
        signal_id = _signal_id(
            authority,
            cpv_code,
            period_month,
            detection_fingerprint,
        )
        review_subject_id = (
            f"{authority}|cpv:{cpv_code}|pattern:{detection_fingerprint[:16]}"
        )
        totals["signals_detected"] += 1
        totals["evidence_rows_sampled"] += len(evidence)
        if len(samples) < 20:
            samples.append(
                {
                    "signal_id": signal_id,
                    "subject_id": authority,
                    "review_subject_id": review_subject_id,
                    "detection_fingerprint": detection_fingerprint,
                    "cpv_code": cpv_code,
                    "period_month": period_month,
                    "records": group_records,
                    "amount_eur": round(group_amount, 2),
                }
            )
        if persist:
            year, month = (int(value) for value in period_month.split("-", 1))
            period_end = f"{period_month}-{calendar.monthrange(year, month)[1]:02d}"
            create_review_signal(
                conn,
                signal_id=signal_id,
                detector_id=DETECTOR_ID,
                detector_version=DETECTOR_VERSION,
                signal_type="contract_threshold_pattern_candidate",
                subject_type="contracting_authority_cpv",
                subject_id=review_subject_id,
                summary=(
                    f"Review signal: {group_records} records for CPV {cpv_code} in "
                    f"{period_month} are individually below the configured analytical "
                    f"threshold and total {group_amount:.2f} EUR. This is not a finding "
                    "of unlawful fragmentation, favoritism, or corruption."
                ),
                evidence=evidence,
                period_start=f"{period_month}-01",
                period_end=period_end,
                review_priority=min(100, group_records * 5),
                metrics={
                    "configured_threshold_eur": float(threshold_eur),
                    "records": group_records,
                    "amount_eur": round(group_amount, 2),
                    "cpv_code": cpv_code,
                    "contracting_authority": authority,
                    "detection_fingerprint": detection_fingerprint,
                },
                limitations=[
                    "The configured analytical threshold is not a legal threshold determination.",
                    "Related CPV and calendar month do not establish artificial contract splitting.",
                    "The signal requires procurement-file review, corroboration, and counterevidence.",
                ],
            )
            totals["signals_persisted"] += 1
            if supersede_missing or supersede_prior_versions:
                conn.execute(
                    "INSERT OR IGNORE INTO active_detector_signal_ids(signal_id) "
                    "VALUES (?)",
                    (signal_id,),
                )
    source_scope = list(source_ids)
    if persist and (supersede_missing or supersede_prior_versions):
        source_clause = ""
        source_params: list[object] = []
        if source_scope:
            source_clause = f"""
              AND EXISTS (
                SELECT 1
                FROM integrity_signal_evidence AS evidence
                WHERE evidence.signal_id = signal.signal_id
                  AND evidence.source_id IN ({','.join('?' for _ in source_scope)})
              )
            """
            source_params.extend(source_scope)
        if supersede_missing:
            stale_ids = [
                str(row[0])
                for row in conn.execute(
                    f"""
                    SELECT signal.signal_id
                    FROM integrity_signals AS signal
                    WHERE signal.detector_id = ?
                      AND signal.detector_version = ?
                      AND signal.state = 'review_signal'
                      AND signal.publication_status = 'internal'
                      AND NOT EXISTS (
                        SELECT 1 FROM active_detector_signal_ids AS active
                        WHERE active.signal_id = signal.signal_id
                      )
                      {source_clause}
                    ORDER BY signal.signal_id
                    """,
                    (DETECTOR_ID, DETECTOR_VERSION, *source_params),
                )
            ]
            totals["signals_superseded_missing"] = (
                supersede_internal_review_signals(
                    conn,
                    signal_ids=stale_ids,
                    actor_kind="detector",
                    actor_id=f"{DETECTOR_ID}:{DETECTOR_VERSION}",
                    rationale=(
                        "The latest detector run no longer reproduces this internal "
                        "evidence-set fingerprint."
                    ),
                )
            )
        if supersede_prior_versions:
            prior_ids = [
                str(row[0])
                for row in conn.execute(
                    f"""
                    SELECT signal.signal_id
                    FROM integrity_signals AS signal
                    WHERE signal.detector_id = ?
                      AND signal.detector_version != ?
                      AND signal.state = 'review_signal'
                      AND signal.publication_status = 'internal'
                      {source_clause}
                    ORDER BY signal.signal_id
                    """,
                    (DETECTOR_ID, DETECTOR_VERSION, *source_params),
                )
            ]
            totals["signals_superseded_prior_versions"] = (
                supersede_internal_review_signals(
                    conn,
                    signal_ids=prior_ids,
                    actor_kind="detector",
                    actor_id=f"{DETECTOR_ID}:{DETECTOR_VERSION}",
                    rationale=(
                        "Superseded by evidence-fingerprinted detector version v4."
                    ),
                )
            )
    if persist:
        totals["signals_materialized"] = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM integrity_signals
                WHERE detector_id = ? AND detector_version = ?
                  AND state = 'review_signal' AND publication_status = 'internal'
                """,
                (DETECTOR_ID, DETECTOR_VERSION),
            ).fetchone()[0]
        )
        totals["evidence_rows_materialized"] = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM integrity_signal_evidence AS evidence
                JOIN integrity_signals AS signal
                  ON signal.signal_id = evidence.signal_id
                WHERE signal.detector_id = ? AND signal.detector_version = ?
                """,
                (DETECTOR_ID, DETECTOR_VERSION),
            ).fetchone()[0]
        )
    return {
        "schema_version": "procurement_integrity_signal_detection_v4",
        "status": "dry_run" if not persist else "ok",
        "detector_id": DETECTOR_ID,
        "detector_version": DETECTOR_VERSION,
        "evidence_basis": (
            "latest_contract_versions_with_award_results_preferred"
            if table_exists(conn, "money_contract_award_results")
            else "latest_contract_versions"
        ),
        "signal_identity": (
            "detector_version_authority_cpv_month_evidence_set_sha256"
        ),
        "threshold_eur": float(threshold_eur),
        "min_records": int(min_records),
        "source_ids": list(source_ids),
        "totals": totals,
        "samples": samples,
        "safety": {
            "initial_state": "review_signal",
            "public_by_default": False,
            "corruption_finding": False,
            "human_review_required": True,
            "source_revision_supersession": bool(supersede_missing),
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    if not db_path.is_file() or int(args.max_signals) < 0:
        print("ERROR: DB must exist and max-signals must be >= 0", file=sys.stderr)
        return 2
    conn = open_db(db_path)
    try:
        report = detect_threshold_patterns(
            conn,
            threshold_eur=float(args.threshold_eur),
            min_records=int(args.min_records),
            source_ids=_source_ids(args.source_ids),
            max_signals=int(args.max_signals),
            evidence_sample_size=int(args.evidence_sample_size),
            persist=not bool(args.dry_run),
            supersede_missing=bool(args.supersede_missing),
            supersede_prior_versions=bool(args.supersede_prior_versions),
        )
    except (RuntimeError, ValueError, sqlite3.Error) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()
    if str(args.report_out or "").strip():
        out_path = Path(args.report_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
