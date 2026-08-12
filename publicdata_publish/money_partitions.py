"""Typed, incremental Parquet publication for public-money facts."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .semantic_contracts import (
    MANIFEST_SCHEMA_VERSION,
    SemanticLaneContract,
    peak_rss_mb,
    private_token_findings,
    public_http_url,
    safe_component,
    sha256_file,
)
from .semantic_parquet_io import (
    PartitionWriter,
    reusable_partition,
    reuse_partition_files,
)

MONEY_FACT_CONTRACT = SemanticLaneContract(
    lane="public_money_facts",
    transformer_version="public_money_facts_v5",
    id_column="money_fact_id",
    year_column="fact_year",
    schema=(
        {"name": "money_fact_id", "type": "string", "nullable": False},
        {"name": "fact_kind", "type": "string", "nullable": False},
        {"name": "source_id", "type": "string", "nullable": False},
        {"name": "source_record_pk", "type": "int64", "nullable": False},
        {"name": "source_record_id", "type": "string", "nullable": False},
        {"name": "source_snapshot_date", "type": "string", "nullable": True},
        {"name": "source_url", "type": "string", "nullable": False},
        {"name": "source_url_scope", "type": "string", "nullable": False},
        {"name": "lineage_state", "type": "string", "nullable": False},
        {"name": "jurisdiction", "type": "string", "nullable": False},
        {"name": "territory_code", "type": "string", "nullable": True},
        {"name": "fact_year", "type": "string", "nullable": False},
        {"name": "published_date", "type": "string", "nullable": True},
        {"name": "effective_date", "type": "string", "nullable": True},
        {"name": "primary_reference_id", "type": "string", "nullable": True},
        {"name": "secondary_reference_id", "type": "string", "nullable": True},
        {"name": "classification_code", "type": "string", "nullable": True},
        {"name": "classification_label", "type": "string", "nullable": True},
        {"name": "public_authority", "type": "string", "nullable": True},
        {"name": "counterparty_name", "type": "string", "nullable": True},
        {
            "name": "counterparty_identifier",
            "type": "string",
            "nullable": True,
        },
        {
            "name": "counterparty_entity_type",
            "type": "string",
            "nullable": False,
        },
        {
            "name": "counterparty_publication_state",
            "type": "string",
            "nullable": False,
        },
        {
            "name": "counterparty_resolution_state",
            "type": "string",
            "nullable": False,
        },
        {"name": "notice_type", "type": "string", "nullable": True},
        {"name": "procedure_type", "type": "string", "nullable": True},
        {"name": "contract_status_code", "type": "string", "nullable": True},
        {
            "name": "amount_eur",
            "type": "decimal128_38_6",
            "nullable": True,
        },
        {"name": "currency", "type": "string", "nullable": True},
        {"name": "amount_state", "type": "string", "nullable": False},
        {"name": "amount_semantics", "type": "string", "nullable": False},
        {"name": "spend_semantics", "type": "string", "nullable": False},
    ),
)

MONEY_FACT_SQL = """
WITH ranked_contracts AS (
  SELECT
    c.*,
    ROW_NUMBER() OVER (
      PARTITION BY c.source_id,
        COALESCE(NULLIF(c.stable_contract_id, ''), 'source:' || c.source_record_id)
      ORDER BY
        COALESCE(NULLIF(c.entry_updated_at, ''), NULLIF(c.awarded_date, ''),
                 NULLIF(c.published_date, ''), c.source_snapshot_date, '') DESC,
        c.contract_record_id DESC
    ) AS version_rank
  FROM money_contract_records AS c
),
latest_contracts AS (
  SELECT * FROM ranked_contracts WHERE version_rank = 1
),
facts AS (
  SELECT
    'contract_notice' AS fact_kind,
    c.contract_record_id AS numeric_id,
    c.source_id,
    c.source_record_pk,
    c.source_record_id,
    c.source_snapshot_date,
    c.source_url AS record_source_url,
    source.default_url AS source_default_url,
    c.territory_code,
    CASE
      WHEN substr(COALESCE(c.awarded_date, ''), 1, 4)
           GLOB '[12][0-9][0-9][0-9]' THEN substr(c.awarded_date, 1, 4)
      WHEN substr(COALESCE(c.published_date, ''), 1, 4)
           GLOB '[12][0-9][0-9][0-9]' THEN substr(c.published_date, 1, 4)
      WHEN substr(COALESCE(c.source_snapshot_date, ''), 1, 4)
           GLOB '[12][0-9][0-9][0-9]' THEN substr(c.source_snapshot_date, 1, 4)
      ELSE 'unknown'
    END AS fact_year,
    c.published_date,
    c.awarded_date AS effective_date,
    c.contract_id AS primary_reference_id,
    c.lot_id AS secondary_reference_id,
    c.cpv_code AS classification_code,
    c.cpv_label AS classification_label,
    c.contracting_authority AS public_authority,
    NULL AS counterparty_name,
    NULL AS counterparty_identifier,
    c.notice_type,
    c.procedure_type,
    c.contract_status_code,
    COALESCE(c.amount_eur_decimal, CAST(c.amount_eur AS TEXT)) AS amount_eur,
    c.currency,
    COALESCE(NULLIF(c.amount_semantics, ''), 'published_contract_amount_unspecified')
      AS raw_amount_semantics
  FROM latest_contracts AS c
  JOIN sources AS source ON source.source_id = c.source_id
  JOIN source_records AS sr ON sr.source_record_pk = c.source_record_pk

  UNION ALL

  SELECT
    'contract_award' AS fact_kind,
    r.contract_award_result_id AS numeric_id,
    r.source_id,
    r.source_record_pk,
    r.source_record_id,
    c.source_snapshot_date,
    c.source_url AS record_source_url,
    source.default_url AS source_default_url,
    c.territory_code,
    CASE
      WHEN substr(COALESCE(r.award_date, ''), 1, 4)
           GLOB '[12][0-9][0-9][0-9]' THEN substr(r.award_date, 1, 4)
      WHEN substr(COALESCE(c.published_date, ''), 1, 4)
           GLOB '[12][0-9][0-9][0-9]' THEN substr(c.published_date, 1, 4)
      WHEN substr(COALESCE(c.source_snapshot_date, ''), 1, 4)
           GLOB '[12][0-9][0-9][0-9]' THEN substr(c.source_snapshot_date, 1, 4)
      ELSE 'unknown'
    END AS fact_year,
    c.published_date,
    r.award_date AS effective_date,
    COALESCE(NULLIF(c.contract_id, ''), c.stable_contract_id) AS primary_reference_id,
    r.lot_id AS secondary_reference_id,
    c.cpv_code AS classification_code,
    c.cpv_label AS classification_label,
    c.contracting_authority AS public_authority,
    r.supplier_name AS counterparty_name,
    r.supplier_identifier AS counterparty_identifier,
    c.notice_type,
    c.procedure_type,
    c.contract_status_code,
    r.amount_eur_decimal AS amount_eur,
    r.currency,
    'awarded_tax_exclusive_amount' AS raw_amount_semantics
  FROM money_contract_award_results AS r
  JOIN latest_contracts AS c
    ON c.source_record_pk = r.source_record_pk
  JOIN sources AS source ON source.source_id = r.source_id
  JOIN source_records AS sr ON sr.source_record_pk = r.source_record_pk

  UNION ALL

  SELECT
    'subsidy_record' AS fact_kind,
    s.subsidy_record_id AS numeric_id,
    s.source_id,
    s.source_record_pk,
    s.source_record_id,
    s.source_snapshot_date,
    s.source_url AS record_source_url,
    source.default_url AS source_default_url,
    s.territory_code,
    CASE
      WHEN substr(COALESCE(s.concession_date, ''), 1, 4)
           GLOB '[12][0-9][0-9][0-9]' THEN substr(s.concession_date, 1, 4)
      WHEN substr(COALESCE(s.published_date, ''), 1, 4)
           GLOB '[12][0-9][0-9][0-9]' THEN substr(s.published_date, 1, 4)
      WHEN substr(COALESCE(s.source_snapshot_date, ''), 1, 4)
           GLOB '[12][0-9][0-9][0-9]' THEN substr(s.source_snapshot_date, 1, 4)
      ELSE 'unknown'
    END AS fact_year,
    s.published_date,
    s.concession_date AS effective_date,
    s.call_id AS primary_reference_id,
    s.grant_id AS secondary_reference_id,
    s.program_code AS classification_code,
    NULL AS classification_label,
    s.granting_body AS public_authority,
    s.beneficiary_name AS counterparty_name,
    s.beneficiary_identifier AS counterparty_identifier,
    NULL AS notice_type,
    NULL AS procedure_type,
    NULL AS contract_status_code,
    s.amount_eur,
    s.currency,
    'published_subsidy_amount' AS raw_amount_semantics
  FROM money_subsidy_records AS s
  JOIN sources AS source ON source.source_id = s.source_id
  JOIN source_records AS sr ON sr.source_record_pk = s.source_record_pk
)
SELECT
  *,
  public_money_jurisdiction(source_id, territory_code) AS jurisdiction
FROM facts
ORDER BY fact_kind, source_id, jurisdiction, fact_year, numeric_id
"""


def capacity_class_for_rows(rows: int) -> str:
    """Return the shared scale class for an exact count of real rows."""
    if rows >= 1_000_000:
        return "s2_1m"
    if rows >= 100_000:
        return "s1_100k"
    return "below_s1_100k"


AMOUNT_QUANTUM = Decimal("0.000001")
LEGAL_ENTITY_IDENTIFIER = re.compile(
    r"^[ABCDEFGHJNPQRSUVW][0-9]{7}[0-9A-J]$", re.IGNORECASE
)
NATURAL_PERSON_IDENTIFIER = re.compile(
    r"^(?:[0-9]{8}[A-Z]|[XYZ][0-9]{7}[A-Z])$", re.IGNORECASE
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _amount(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"invalid monetary amount: {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError(f"non-finite monetary amount: {value!r}")
    return parsed.quantize(AMOUNT_QUANTUM)


def _jurisdiction(source_id: str, territory_code: Any) -> str:
    source = source_id.strip().lower()
    territory = str(territory_code or "").strip()
    if "autonomico" in source:
        return "es-autonomic"
    if territory:
        return "es-territorial"
    return "es-national"


def _public_counterparty(
    row: sqlite3.Row,
) -> tuple[str | None, str | None, str, str]:
    if row["fact_kind"] == "contract_notice":
        return None, None, "not_available", "not_materialized"
    name = _text(row["counterparty_name"])
    identifier = _text(row["counterparty_identifier"])
    normalized_identifier = identifier.upper() if identifier else None
    if normalized_identifier and LEGAL_ENTITY_IDENTIFIER.fullmatch(
        normalized_identifier
    ):
        return (
            name,
            normalized_identifier,
            "legal_entity",
            "published_legal_entity",
        )
    if normalized_identifier and NATURAL_PERSON_IDENTIFIER.fullmatch(
        normalized_identifier
    ):
        return (
            name,
            normalized_identifier,
            "potential_natural_person",
            "published_natural_person",
        )
    if name or normalized_identifier:
        return name, normalized_identifier, "unclassified", "published_unclassified"
    return None, None, "unclassified", "not_available"


def _counterparty_state(
    fact_kind: str,
    name: str | None,
    identifier: str | None,
    publication_state: str,
) -> str:
    if fact_kind == "contract_notice":
        return "not_materialized_in_source_table"
    if identifier:
        return "official_identifier_present_unresolved"
    if name:
        return "name_only_unresolved"
    return "missing_counterparty"


def _spend_semantics(fact_kind: str) -> str:
    if fact_kind == "contract_notice":
        return "published_contract_notice_not_payment"
    if fact_kind == "contract_award":
        return "published_contract_award_not_payment"
    return "published_subsidy_amount_not_disbursement"


def _public_row(row: sqlite3.Row) -> dict[str, Any]:
    record_url = public_http_url(row["record_source_url"])
    default_url = public_http_url(row["source_default_url"])
    source_url = record_url or default_url
    if source_url is None:
        raise ValueError(
            f"money fact has no public source URL: {row['fact_kind']}:{row['numeric_id']}"
        )
    amount = _amount(row["amount_eur"])
    fact_kind = str(row["fact_kind"])
    currency = _text(row["currency"])
    (
        counterparty_name,
        counterparty_identifier,
        counterparty_entity_type,
        counterparty_publication_state,
    ) = _public_counterparty(row)
    return {
        "money_fact_id": f"{fact_kind}:{int(row['numeric_id']):020d}",
        "fact_kind": fact_kind,
        "source_id": str(row["source_id"]),
        "source_record_pk": int(row["source_record_pk"]),
        "source_record_id": str(row["source_record_id"]),
        "source_snapshot_date": _text(row["source_snapshot_date"]),
        "source_url": source_url,
        "source_url_scope": "record" if record_url else "source_default",
        "lineage_state": "source_record",
        "jurisdiction": str(row["jurisdiction"]),
        "territory_code": _text(row["territory_code"]),
        "fact_year": str(row["fact_year"]),
        "published_date": _text(row["published_date"]),
        "effective_date": _text(row["effective_date"]),
        "primary_reference_id": _text(row["primary_reference_id"]),
        "secondary_reference_id": _text(row["secondary_reference_id"]),
        "classification_code": _text(row["classification_code"]),
        "classification_label": _text(row["classification_label"]),
        "public_authority": _text(row["public_authority"]),
        "counterparty_name": counterparty_name,
        "counterparty_identifier": counterparty_identifier,
        "counterparty_entity_type": counterparty_entity_type,
        "counterparty_publication_state": counterparty_publication_state,
        "counterparty_resolution_state": _counterparty_state(
            fact_kind,
            counterparty_name,
            counterparty_identifier,
            counterparty_publication_state,
        ),
        "notice_type": _text(row["notice_type"]),
        "procedure_type": _text(row["procedure_type"]),
        "contract_status_code": _text(row["contract_status_code"]),
        "amount_eur": amount,
        "currency": currency.upper() if currency else None,
        "amount_state": (
            "missing"
            if amount is None
            else "present_nonnegative"
            if amount >= 0
            else "present_negative"
        ),
        "amount_semantics": str(row["raw_amount_semantics"]),
        "spend_semantics": _spend_semantics(fact_kind),
    }


def _iter_rows(db_path: Path) -> Iterator[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.create_function(
        "public_money_jurisdiction", 2, _jurisdiction, deterministic=True
    )
    try:
        for row in conn.execute(MONEY_FACT_SQL):
            yield _public_row(row)
    finally:
        conn.close()


def _partition_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row["fact_kind"]),
        str(row["source_id"]),
        str(row["jurisdiction"]),
        str(row["fact_year"]),
    )


def _partition_id(key: tuple[str, str, str, str]) -> str:
    return "|".join(key)


def _partition_dir(snapshot_date: str, key: tuple[str, str, str, str]) -> Path:
    fact_kind, source_id, jurisdiction, year = key
    return Path(
        f"lane={MONEY_FACT_CONTRACT.lane}",
        f"snapshot_date={safe_component(snapshot_date)}",
        f"fact_kind={safe_component(fact_kind)}",
        f"source_id={safe_component(source_id)}",
        f"jurisdiction={safe_component(jurisdiction)}",
        f"year={safe_component(year)}",
    )


def _new_partition(
    snapshot_date: str, key: tuple[str, str, str, str]
) -> dict[str, Any]:
    return {
        "partition_id": _partition_id(key),
        "values": {
            "snapshot_date": snapshot_date,
            "fact_kind": key[0],
            "source_id": key[1],
            "jurisdiction": key[2],
            "year": key[3],
        },
        "relative_dir": _partition_dir(snapshot_date, key).as_posix(),
        "rows": 0,
        "min_id": None,
        "max_id": None,
        "source_url_rows": 0,
        "source_record_rows": 0,
        "amount_rows": 0,
        "nonnegative_amount_rows": 0,
        "eur_rows": 0,
        "counterparty_name_rows": 0,
        "counterparty_identifier_rows": 0,
        "counterparty_published_rows": 0,
        "counterparty_published_legal_entity_rows": 0,
        "counterparty_published_natural_person_rows": 0,
        "counterparty_published_unclassified_rows": 0,
        "counterparty_not_available_rows": 0,
        "private_token_findings": 0,
        "amount_eur_total": "0.000000",
        "_amount_total": Decimal(0),
        "_digest": hashlib.sha256(),
    }


def scan_money_partitions(
    db_path: Path, *, snapshot_date: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    totals: dict[str, Any] = {
        "rows": 0,
        "contract_notice_rows": 0,
        "contract_award_rows": 0,
        "subsidy_record_rows": 0,
        "source_url_rows": 0,
        "source_record_rows": 0,
        "amount_rows": 0,
        "nonnegative_amount_rows": 0,
        "eur_rows": 0,
        "counterparty_name_rows": 0,
        "counterparty_identifier_rows": 0,
        "counterparty_published_rows": 0,
        "counterparty_published_legal_entity_rows": 0,
        "counterparty_published_natural_person_rows": 0,
        "counterparty_published_unclassified_rows": 0,
        "counterparty_not_available_rows": 0,
        "unknown_year_rows": 0,
        "private_token_findings": 0,
        "amount_eur_total": Decimal(0),
        "amount_eur_by_fact_kind": {},
    }
    partitions: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_key: tuple[str, str, str, str] | None = None
    previous_id: str | None = None
    for row in _iter_rows(db_path):
        key = _partition_key(row)
        if current_key != key:
            if current is not None:
                current["amount_eur_total"] = format(current.pop("_amount_total"), "f")
                current["input_sha256"] = current.pop("_digest").hexdigest()
                partitions.append(current)
            current_key = key
            current = _new_partition(snapshot_date, key)
            previous_id = None
        assert current is not None
        row_id = str(row["money_fact_id"])
        if previous_id is not None and row_id <= previous_id:
            raise RuntimeError("money-fact input is not ordered within partition")
        previous_id = row_id
        current["rows"] += 1
        current["min_id"] = (
            row_id if current["min_id"] is None else min(current["min_id"], row_id)
        )
        current["max_id"] = (
            row_id if current["max_id"] is None else max(current["max_id"], row_id)
        )
        totals[str(row["fact_kind"]) + "_rows"] += 1
        for metric, field in (
            ("source_url_rows", "source_url"),
            ("source_record_rows", "source_record_pk"),
            ("counterparty_name_rows", "counterparty_name"),
            ("counterparty_identifier_rows", "counterparty_identifier"),
        ):
            if row[field] not in (None, ""):
                current[metric] += 1
                totals[metric] += 1
        publication_state = str(row["counterparty_publication_state"])
        publication_metric = {
            "published_legal_entity": "counterparty_published_legal_entity_rows",
            "published_natural_person": "counterparty_published_natural_person_rows",
            "published_unclassified": "counterparty_published_unclassified_rows",
            "not_available": "counterparty_not_available_rows",
        }.get(publication_state)
        if publication_metric:
            current[publication_metric] += 1
            totals[publication_metric] += 1
        if publication_state.startswith("published_"):
            current["counterparty_published_rows"] += 1
            totals["counterparty_published_rows"] += 1
        amount = row["amount_eur"]
        if amount is not None:
            current["amount_rows"] += 1
            totals["amount_rows"] += 1
            current["_amount_total"] += amount
            totals["amount_eur_total"] += amount
            kind_totals = totals["amount_eur_by_fact_kind"]
            kind_totals[row["fact_kind"]] = (
                kind_totals.get(row["fact_kind"], Decimal(0)) + amount
            )
            if amount >= 0:
                current["nonnegative_amount_rows"] += 1
                totals["nonnegative_amount_rows"] += 1
        if row["currency"] == "EUR":
            current["eur_rows"] += 1
            totals["eur_rows"] += 1
        if row["fact_year"] == "unknown":
            totals["unknown_year_rows"] += 1
        findings = private_token_findings(row)
        current["private_token_findings"] += findings
        totals["private_token_findings"] += findings
        current["_digest"].update(MONEY_FACT_CONTRACT.canonical_row_bytes(row))
        totals["rows"] += 1
    if current is not None:
        current["amount_eur_total"] = format(current.pop("_amount_total"), "f")
        current["input_sha256"] = current.pop("_digest").hexdigest()
        partitions.append(current)
    totals["amount_eur_total"] = format(totals["amount_eur_total"], "f")
    totals["amount_eur_by_fact_kind"] = {
        key: format(value, "f")
        for key, value in sorted(totals["amount_eur_by_fact_kind"].items())
    }
    return partitions, totals


def _database_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        latest_contract_cte = """
            WITH ranked AS (
              SELECT c.source_id, c.source_record_pk, c.source_record_id,
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
            )
        """
        contracts = int(
            conn.execute(
                latest_contract_cte
                + "SELECT COUNT(*) FROM ranked WHERE version_rank = 1"
            ).fetchone()[0]
        )
        awards = int(
            conn.execute(
                latest_contract_cte
                + """
                  SELECT COUNT(*)
                  FROM money_contract_award_results AS a
                  JOIN ranked AS c ON c.source_record_pk = a.source_record_pk
                  WHERE c.version_rank = 1
                """
            ).fetchone()[0]
        )
        subsidies = int(
            conn.execute("SELECT COUNT(*) FROM money_subsidy_records").fetchone()[0]
        )
        counterparty_source_counts = conn.execute(
            latest_contract_cte
            + """
              SELECT
                SUM(has_name) AS name_rows,
                SUM(has_identifier) AS identifier_rows
              FROM (
                SELECT
                  CASE WHEN NULLIF(TRIM(a.supplier_name), '') IS NOT NULL
                       THEN 1 ELSE 0 END AS has_name,
                  CASE WHEN NULLIF(TRIM(a.supplier_identifier), '') IS NOT NULL
                       THEN 1 ELSE 0 END AS has_identifier
                FROM money_contract_award_results AS a
                JOIN ranked AS c ON c.source_record_pk = a.source_record_pk
                WHERE c.version_rank = 1
                UNION ALL
                SELECT
                  CASE WHEN NULLIF(TRIM(s.beneficiary_name), '') IS NOT NULL
                       THEN 1 ELSE 0 END,
                  CASE WHEN NULLIF(TRIM(s.beneficiary_identifier), '') IS NOT NULL
                       THEN 1 ELSE 0 END
                FROM money_subsidy_records AS s
              )
            """
        ).fetchone()
        joined = int(
            conn.execute(
                latest_contract_cte
                + """
                  SELECT
                    (SELECT COUNT(*) FROM ranked AS c
                     JOIN sources AS s ON s.source_id = c.source_id
                     JOIN source_records AS sr
                       ON sr.source_record_pk = c.source_record_pk
                     WHERE c.version_rank = 1)
                    +
                    (SELECT COUNT(*) FROM money_contract_award_results AS a
                     JOIN ranked AS c ON c.source_record_pk = a.source_record_pk
                     JOIN sources AS s ON s.source_id = a.source_id
                     JOIN source_records AS sr
                       ON sr.source_record_pk = a.source_record_pk
                     WHERE c.version_rank = 1)
                    +
                    (SELECT COUNT(*) FROM money_subsidy_records AS m
                     JOIN sources AS s ON s.source_id = m.source_id
                     JOIN source_records AS sr
                       ON sr.source_record_pk = m.source_record_pk)
                """
            ).fetchone()[0]
        )
        distinct_source_records = int(
            conn.execute(
                latest_contract_cte
                + """
                  SELECT COUNT(*) FROM (
                    SELECT source_record_pk FROM ranked WHERE version_rank = 1
                    UNION
                    SELECT source_record_pk FROM money_subsidy_records
                  )
                """
            ).fetchone()[0]
        )
        return {
            "contract_table_rows": contracts,
            "contract_award_table_rows": awards,
            "subsidy_table_rows": subsidies,
            "money_table_rows": contracts + awards + subsidies,
            "joined_rows": joined,
            "distinct_source_records": distinct_source_records,
            "source_counterparty_name_rows": int(
                counterparty_source_counts[0] or 0
            ),
            "source_counterparty_identifier_rows": int(
                counterparty_source_counts[1] or 0
            ),
        }
    finally:
        conn.close()


def _previous_partitions(
    manifest_path: Path | None,
) -> tuple[dict[str, dict[str, Any]], str | None]:
    if manifest_path is None:
        return {}, None
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    valid = (
        payload.get("schema_version") == MANIFEST_SCHEMA_VERSION
        and payload.get("lane") == MONEY_FACT_CONTRACT.lane
        and payload.get("transformer_version")
        == MONEY_FACT_CONTRACT.transformer_version
        and payload.get("schema_sha256") == MONEY_FACT_CONTRACT.schema_sha256
    )
    partitions = (
        {
            str(item["partition_id"]): item
            for item in list(payload.get("partitions") or [])
        }
        if valid
        else {}
    )
    return partitions, sha256_file(manifest_path)


def export_money_partitions(
    *,
    db_path: Path,
    output_root: Path,
    snapshot_date: str,
    compression: str = "zstd",
    row_group_rows: int = 25_000,
    max_file_rows: int = 100_000,
    previous_manifest_path: Path | None = None,
    previous_root: Path | None = None,
    min_rows: int = 1,
    max_peak_rss_mb: float = 1024.0,
    enforce: bool = False,
) -> dict[str, Any]:
    db_path = Path(db_path)
    output_root = Path(output_root)
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    if output_root.exists():
        raise FileExistsError(output_root)
    if row_group_rows <= 0 or max_file_rows <= 0:
        raise ValueError("row-group-rows and max-file-rows must be positive")
    if row_group_rows > max_file_rows:
        raise ValueError("row-group-rows cannot exceed max-file-rows")
    if (previous_manifest_path is None) != (previous_root is None):
        raise ValueError(
            "previous-manifest and previous-root must be provided together"
        )

    started = time.monotonic()
    scan_started = time.monotonic()
    partitions, scan_totals = scan_money_partitions(
        db_path, snapshot_date=snapshot_date
    )
    scan_seconds = time.monotonic() - scan_started
    database_counts = _database_counts(db_path)
    previous_by_id, previous_sha256 = _previous_partitions(previous_manifest_path)
    reusable: dict[str, dict[str, Any]] = {}
    for partition in partitions:
        eligible = reusable_partition(
            partition=partition,
            previous=previous_by_id.get(str(partition["partition_id"])),
            previous_root=previous_root,
        )
        if eligible is not None:
            reusable[str(partition["partition_id"])] = eligible

    output_root.parent.mkdir(parents=True, exist_ok=True)
    staging_root = Path(
        tempfile.mkdtemp(prefix=f".{output_root.name}.staging-", dir=output_root.parent)
    )
    partition_by_id = {str(item["partition_id"]): item for item in partitions}
    hardlinks = 0
    copies = 0
    try:
        for partition_id, previous in reusable.items():
            partition = partition_by_id[partition_id]
            files, modes = reuse_partition_files(
                previous=previous,
                previous_root=Path(previous_root),
                staging_root=staging_root,
                partition=partition,
            )
            partition["files"] = files
            partition["materialization"] = "reused"
            hardlinks += modes["hardlink"]
            copies += modes["copy"]

        export_started = time.monotonic()
        active_id: str | None = None
        active_writer: PartitionWriter | None = None
        if len(reusable) < len(partitions):
            for row in _iter_rows(db_path):
                partition_id = _partition_id(_partition_key(row))
                if partition_id != active_id:
                    if active_writer is not None:
                        partition_by_id[str(active_id)]["files"] = active_writer.close()
                        partition_by_id[str(active_id)]["materialization"] = "rebuilt"
                    active_id = partition_id
                    active_writer = (
                        None
                        if partition_id in reusable
                        else PartitionWriter(
                            root=staging_root,
                            partition=partition_by_id[partition_id],
                            contract=MONEY_FACT_CONTRACT,
                            compression=compression,
                            row_group_rows=row_group_rows,
                            max_file_rows=max_file_rows,
                        )
                    )
                if active_writer is not None:
                    active_writer.append(row)
            if active_writer is not None:
                partition_by_id[str(active_id)]["files"] = active_writer.close()
                partition_by_id[str(active_id)]["materialization"] = "rebuilt"
        export_seconds = time.monotonic() - export_started

        rows = int(scan_totals["rows"])
        files = sum(len(list(item.get("files") or [])) for item in partitions)
        parquet_bytes = sum(
            int(file_meta["bytes"])
            for partition in partitions
            for file_meta in list(partition.get("files") or [])
        )
        peak_rss = peak_rss_mb()
        checks = {
            "minimum_rows": rows >= int(min_rows),
            "database_join_balance": database_counts["money_table_rows"]
            == database_counts["joined_rows"]
            == rows,
            "fact_kind_balance": database_counts["contract_table_rows"]
            == scan_totals["contract_notice_rows"]
            and database_counts["contract_award_table_rows"]
            == scan_totals["contract_award_rows"]
            and database_counts["subsidy_table_rows"]
            == scan_totals["subsidy_record_rows"],
            "distinct_source_records_bounded": 0
            < database_counts["distinct_source_records"]
            <= rows,
            "source_url_complete": scan_totals["source_url_rows"] == rows,
            "source_record_complete": scan_totals["source_record_rows"] == rows,
            "amount_states_explicit": scan_totals["amount_rows"] <= rows,
            "amounts_nonnegative": scan_totals["nonnegative_amount_rows"]
            == scan_totals["amount_rows"],
            "currency_eur_for_amounts": scan_totals["eur_rows"]
            == scan_totals["amount_rows"],
            "no_private_tokens": scan_totals["private_token_findings"] == 0,
            "public_domain_counterparty_retention_complete": (
                scan_totals["counterparty_published_rows"]
                + scan_totals["counterparty_not_available_rows"]
                == scan_totals["subsidy_record_rows"]
                + scan_totals["contract_award_rows"]
            ),
            "counterparty_names_retained_exactly": (
                scan_totals["counterparty_name_rows"]
                == database_counts["source_counterparty_name_rows"]
            ),
            "counterparty_identifiers_retained_exactly": (
                scan_totals["counterparty_identifier_rows"]
                == database_counts["source_counterparty_identifier_rows"]
            ),
            "bounded_peak_rss": peak_rss <= float(max_peak_rss_mb),
            "bounded_file_rows": all(
                int(file_meta["rows"]) <= int(max_file_rows)
                for partition in partitions
                for file_meta in list(partition.get("files") or [])
            ),
        }
        analytical_gate_passed = all(checks.values())
        promotion_checks = {
            "analytical_partition_gate": analytical_gate_passed,
            "representative_100k_real_rows": rows >= 100_000,
            "million_real_rows": rows >= 1_000_000,
            "official_live_source_totals_reconciled": False,
            "counterparty_entity_resolution_verified": False,
            "durable_public_origin_verified": False,
        }
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "generated_at": _now_iso(),
            "snapshot_date": snapshot_date,
            "lane": MONEY_FACT_CONTRACT.lane,
            "transformer_version": MONEY_FACT_CONTRACT.transformer_version,
            "schema": MONEY_FACT_CONTRACT.schema,
            "schema_sha256": MONEY_FACT_CONTRACT.schema_sha256,
            "partition_contract": {
                "strategy": "semantic_hive_money_fact_kind",
                "keys": [
                    "snapshot_date",
                    "fact_kind",
                    "source_id",
                    "jurisdiction",
                    "year",
                ],
                "ordering": [
                    "fact_kind",
                    "source_id",
                    "jurisdiction",
                    "year",
                    "money_fact_id",
                ],
                "row_group_rows": int(row_group_rows),
                "max_file_rows": int(max_file_rows),
                "compression": compression,
                "exact_territory_retained_as_column": True,
            },
            "incremental_contract": {
                "input_fingerprint": "sha256_canonical_public_rows",
                "reuse_key": [
                    "partition_id",
                    "input_sha256",
                    "schema_sha256",
                    "transformer_version",
                ],
                "previous_manifest_sha256": previous_sha256,
                "partitions_reused": len(reusable),
                "partitions_rebuilt": len(partitions) - len(reusable),
                "files_hardlinked": hardlinks,
                "files_copied": copies,
            },
            "source": {
                "database_file": db_path.name,
                "database_bytes": int(db_path.stat().st_size),
                "tables": [
                    "money_contract_records",
                    "money_contract_award_results",
                    "money_subsidy_records",
                ],
                "raw_payload_published": False,
            },
            "totals": {
                **database_counts,
                **scan_totals,
                "partitions": len(partitions),
                "files": files,
                "parquet_bytes": parquet_bytes,
            },
            "coverage": {
                "source_url": round(scan_totals["source_url_rows"] / rows, 8)
                if rows
                else 0.0,
                "source_record": round(scan_totals["source_record_rows"] / rows, 8)
                if rows
                else 0.0,
                "amount": round(scan_totals["amount_rows"] / rows, 8) if rows else 0.0,
                "counterparty_name": round(
                    scan_totals["counterparty_name_rows"] / rows, 8
                )
                if rows
                else 0.0,
                "counterparty_identifier": round(
                    scan_totals["counterparty_identifier_rows"] / rows, 8
                )
                if rows
                else 0.0,
                "counterparty_publication_state": round(
                    (
                        scan_totals["counterparty_published_rows"]
                        + scan_totals["counterparty_not_available_rows"]
                    )
                    / (
                        scan_totals["subsidy_record_rows"]
                        + scan_totals["contract_award_rows"]
                    ),
                    8,
                )
                if (
                    scan_totals["subsidy_record_rows"]
                    + scan_totals["contract_award_rows"]
                )
                else 1.0,
            },
            "money_assurance": "published_amounts_not_execution_or_disbursement",
            "counterparty_publication_assurance": (
                "all_official_public_domain_names_and_identifiers_retained;"
                "entity_type_is_classification_not_suppression"
            ),
            "checks": checks,
            "analytical_partition_gate_passed": analytical_gate_passed,
            "promotion_checks": promotion_checks,
            "promotion_gate_passed": all(promotion_checks.values()),
            "publication_status": "local_generated_not_published",
            "capacity_class": capacity_class_for_rows(rows),
            "performance": {
                "fingerprint_seconds": round(scan_seconds, 6),
                "materialize_seconds": round(export_seconds, 6),
                "total_seconds": round(time.monotonic() - started, 6),
                "rows_per_second": round(
                    rows / max(time.monotonic() - started, 0.000001), 3
                ),
                "peak_rss_mb": peak_rss,
                "max_peak_rss_mb": float(max_peak_rss_mb),
            },
            "partitions": partitions,
            "limitations": [
                "Contract amounts are publication/noticing values, not verified payments.",
                "Subsidy amounts are published award/call values, not verified disbursements.",
                "PLACSP exact lexical decimals are retained; legacy SQLite REAL subsidy inputs are normalized to six-decimal Arrow decimals.",
                "Official-source counterparty names and identifiers are retained for legal entities, natural persons, and unclassified counterparties; classification never suppresses public-domain evidence.",
                "Published counterparties remain unresolved evidence, not merged or externally verified identities.",
                (
                    "This artifact reflects only the supplied cohort; row scale does not prove complete official coverage or representative mix."
                    if rows >= 100_000
                    else "The canonical runtime contains only a tiny fallback/sample-derived baseline, not a representative live-source corpus."
                ),
                "Local materialization does not prove durable public-origin publication or restore.",
            ],
        }
        if enforce and not analytical_gate_passed:
            failed = [key for key, value in checks.items() if not value]
            raise RuntimeError("analytical partition gate failed: " + ", ".join(failed))
        (staging_root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging_root.rename(output_root)
    except BaseException:
        shutil.rmtree(staging_root, ignore_errors=True)
        raise
    return manifest


__all__ = ["MONEY_FACT_CONTRACT", "export_money_partitions", "scan_money_partitions"]
